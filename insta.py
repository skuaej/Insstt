import re
import os
import sys
import time
from itertools import cycle
from io import StringIO
from quart import Quart, request, jsonify, send_file
from yt_dlp import YoutubeDL

# Auto-update layer dependencies
os.system(f"{sys.executable} -m pip install --upgrade yt-dlp")

app = Quart(__name__)

INSTAGRAM_REGEX = r".*(instagram\.com|instagr\.am)/(p|reel|tv|share)/[^\s]+"

# ==========================================================
# 🌐 PROXY POOL ROTATION
# ==========================================================
RAW_PROXIES = [
    "38.154.203.95:5863:zbgnspng:l75251a9tnum",
    "198.105.121.200:6462:zbgnspng:l75251a9tnum",
    "64.137.96.74:6641:zbgnspng:l75251a9tnum",
    "209.127.138.10:5784:zbgnspng:l75251a9tnum",
    "38.154.185.97:6370:zbgnspng:l75251a9tnum",
    "84.247.60.125:6095:zbgnspng:l75251a9tnum",
    "142.111.67.146:5611:zbgnspng:l75251a9tnum",
    "191.96.254.138:6185:zbgnspng:l75251a9tnum",
    "31.58.9.4:6077:zbgnspng:l75251a9tnum",
    "104.239.107.47:5699:zbgnspng:l75251a9tnum"
]

def format_proxy(p_str):
    parts = p_str.strip().split(":")
    if len(parts) == 4:
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"
    return f"http://{parts[0]}:{parts[1]}"

PROXY_POOL = cycle([format_proxy(p) for p in RAW_PROXIES])

# ==========================================================
# 🍪 LIVE COOKIES
# ==========================================================
COOKIES_FILE_PATH = "instagram_cookies.txt"
COOKIES_DATA = r"""
# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

.instagram.com	TRUE	/	TRUE	1815543658	csrftoken	UHOEPGsEWWZCyWaTiQREctWt6VCVpEi2
.instagram.com	TRUE	/	TRUE	1815543467	datr	q6YnagrdppRbnk_z74CLmql7
.instagram.com	TRUE	/	TRUE	1812519467	ig_did	83632560-C690-4FB6-8BF3-BD321873D9AF
.instagram.com	TRUE	/	TRUE	1781588459	wd	360x634
.instagram.com	TRUE	/	TRUE	1781588346	dpr	3
.instagram.com	TRUE	/	TRUE	1815543468	mid	aiemqwABAAF5b3O6W9brtE9zHHO0
.instagram.com	TRUE	/	TRUE	1788759658	ds_user_id	25349046417
.instagram.com	TRUE	/	TRUE	1812519546	sessionid	25349046417%3AelmMsdUhcSc1He%3A4%3AAYjZFTNLvevhBdQs48r-Bh5FxmIXO0yRu4uibe5kaw
.instagram.com	TRUE	/	TRUE	1815543547	ps_l	1
.instagram.com	TRUE	/	TRUE	1815543547	ps_n	1
.instagram.com	TRUE	/	TRUE	0	rur	"SNB\05425349046417\0541812519658:01fffc9637faa298604a83c726eeea0db1be399feb6739f78b44fa57fa6ae6e555759255"
"""

with open(COOKIES_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(COOKIES_DATA.strip())

# ==========================================================
# CORE PROCESSING LOGIC
# ==========================================================

def get_instagram_all_data(url, proxy):
    clean_url = url.split("?")[0].strip().rstrip("/")
    ydl_opts = {
        'format': 'best', 
        'quiet': True,
        'no_warnings': True,
        'get_comments': True,                     
        'extractor_args': {'instagram': ['get_comments']}, 
        'cookiefile': COOKIES_FILE_PATH,
        'proxy': proxy,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Referer': 'https://www.instagram.com/',
        }
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(clean_url, download=False)
            video_url = info.get('url') or (info['formats'][-1]['url'] if 'formats' in info else None)
            real_caption = info.get('description') or info.get('title') or info.get('alt_title') or 'No Caption'
            
            metadata = {
                "status": "success",
                "id": info.get('id') or str(int(time.time())),
                "video_url": video_url,
                "title": real_caption.strip(),
                "uploader": info.get('uploader', 'Unknown_User'),
                "duration": info.get('duration'),
                "view_count": info.get('view_count', 'N/A'),
                "like_count": info.get('like_count', 'N/A'),
                "comments": []
            }
            
            raw_comments = info.get('comments', [])
            if raw_comments:
                sorted_comments = sorted(raw_comments, key=lambda x: (x.get('like_count', 0) or 0, len(x.get('text', '') or '')), reverse=True)
                for c in sorted_comments:
                    author = c.get('author') or c.get('username') or 'user'
                    text = c.get('text', '').strip().replace('\n', ' ')
                    if text: 
                        metadata["comments"].append({"author": f"@{author}", "comment": text})
                    if len(metadata["comments"]) >= 10: 
                        break
            return metadata
        except Exception as e:
            return {"status": "error", "message": str(e)}

def download_video_locally(url, video_id, proxy):
    out_filename = f'video_{video_id}.mp4'
    ydl_opts = {
        'format': 'best',
        'outtmpl': out_filename,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': COOKIES_FILE_PATH,
        'proxy': proxy,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Referer': 'https://www.instagram.com/',
        }
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return out_filename

# ==========================================================
# API ENDPOINTS
# ==========================================================

@app.route('/api/metadata', methods=['GET'])
async def fetch_metadata():
    """Returns pure video details and top 10 comments in JSON format"""
    url = request.args.get('url')
    if not url or not re.match(INSTAGRAM_REGEX, url):
        return jsonify({"status": "error", "message": "Missing or invalid Instagram URL"}), 400
    
    selected_proxy = next(PROXY_POOL)
    loop = asyncio.get_event_loop()
    
    # Run synchronous yt-dlp in executor to keep endpoint responsive
    data = await loop.run_in_executor(None, get_instagram_all_data, url, selected_proxy)
    return jsonify(data)


@app.route('/api/download', methods=['GET'])
async def download_video():
    """Downloads the file via proxy rotation and streams the clean .mp4 back to client"""
    url = request.args.get('url')
    if not url or not re.match(INSTAGRAM_REGEX, url):
        return jsonify({"status": "error", "message": "Missing or invalid Instagram URL"}), 400
        
    selected_proxy = next(PROXY_POOL)
    loop = asyncio.get_event_loop()
    
    # Fetch data first to acquire video structural ID
    meta_data = await loop.run_in_executor(None, get_instagram_all_data, url, selected_proxy)
    if meta_data.get("status") == "error":
        return jsonify(meta_data), 400
        
    video_id = meta_data["id"]
    
    try:
        # Download file to local storage pipeline
        file_path = await loop.run_in_executor(None, download_video_locally, url, video_id, selected_proxy)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            # Send file down the stream connection safely
            response = await send_file(file_path, mimetype="video/mp4", as_attachment=True, attachment_filename=f"{video_id}.mp4")
            
            # Delete local file after transmission finishes to keep your VPS space empty
            @response.call_on_close
            def cleanup():
                if os.path.exists(file_path):
                    os.remove(file_path)
            return response
        else:
            return jsonify({"status": "error", "message": "File downloaded but contains zero bytes container error"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": f"Pipeline broke down: {str(e)}"}), 500


if __name__ == "__main__":
    # Runs the server locally on port 5000
    app.run(host="0.0.0.0", port=5000, debug=False)
    
