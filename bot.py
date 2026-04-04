import os
import json
import requests
import yt_dlp
import time

BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=data)

def send_video(chat_id, video_path, caption=""):
    url = f"{API_URL}/sendVideo"
    with open(video_path, 'rb') as video:
        files = {'video': video}
        data = {'chat_id': chat_id, 'caption': caption}
        requests.post(url, data=data, files=files)

def send_audio(chat_id, audio_path, title=""):
    url = f"{API_URL}/sendAudio"
    with open(audio_path, 'rb') as audio:
        files = {'audio': audio}
        data = {'chat_id': chat_id, 'title': title}
        requests.post(url, data=data, files=files)

def send_photo(chat_id, photo_url, caption="", reply_markup=None):
    url = f"{API_URL}/sendPhoto"
    data = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=data)

def get_updates(offset=None):
    url = f"{API_URL}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    response = requests.get(url, params=params)
    return response.json().get("result", [])

class VideoDownloader:
    def is_youtube(self, url):
        return 'youtube.com' in url or 'youtu.be' in url
    
    def is_social(self, url):
        sites = ['tiktok.com', 'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'snapchat.com']
        return any(s in url for s in sites)
    
    def download_video(self, url):
        os.makedirs('downloads', exist_ok=True)
        opts = {'format': 'best[height<=720]', 'outtmpl': 'downloads/video_%(id)s.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    
    def download_audio(self, url):
        os.makedirs('downloads', exist_ok=True)
        opts = {'format': 'bestaudio', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}], 'outtmpl': 'downloads/audio_%(id)s.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
    
    def search_youtube(self, query):
        opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch4:{query}", download=False)
            results = []
            for entry in info['entries']:
                if entry:
                    results.append({
                        'title': entry['title'],
                        'url': f"https://youtube.com/watch?v={entry['id']}",
                        'thumbnail': entry.get('thumbnail', '')
                    })
            return results

downloader = VideoDownloader()
last_update_id = 0

def make_keyboard(buttons):
    return {"inline_keyboard": [[{"text": text, "callback_data": data}] for text, data in buttons]}

def handle_message(chat_id, text):
    if 'http://' in text or 'https://' in text:
        if downloader.is_youtube(text):
            keyboard = make_keyboard([
                ("🎬 تحميل فيديو", f"video_{text}"),
                ("🎵 تحميل صوت", f"audio_{text}")
            ])
            send_message(chat_id, "✅ رابط يوتيوب - اختر:", keyboard)
        elif downloader.is_social(text):
            send_message(chat_id, "📥 جاري تحميل الفيديو...")
            try:
                path = downloader.download_video(text)
                send_video(chat_id, path, "✅ تم التحميل!")
                os.remove(path)
            except Exception as e:
                send_message(chat_id, f"❌ فشل: {str(e)[:100]}")
        else:
            send_message(chat_id, "❌ رابط غير مدعوم")
    else:
        send_message(chat_id, f"🔍 جاري البحث عن: {text}")
        try:
            results = downloader.search_youtube(text)
            for r in results:
                keyboard = make_keyboard([("🎬 تحميل", f"video_{r['url']}")])
                send_photo(chat_id, r['thumbnail'], f"🎥 {r['title'][:50]}", keyboard)
        except Exception as e:
            send_message(chat_id, f"❌ فشل البحث: {str(e)[:100]}")

def handle_callback(chat_id, callback_data, message_id):
    action, url = callback_data.split('_', 1)
    send_message(chat_id, "⏳ جاري التحميل...")
    
    try:
        if action == 'video':
            path = downloader.download_video(url)
            send_video(chat_id, path, "✅ تم تحميل الفيديو!")
        else:
            path = downloader.download_audio(url)
            send_audio(chat_id, path, "صوت من يوتيوب")
        os.remove(path)
    except Exception as e:
        send_message(chat_id, f"❌ فشل: {str(e)[:100]}")

print("🚀 تشغيل البوت...")
print("✅ البوت يعمل الآن!")

while True:
    try:
        updates = get_updates(last_update_id + 1)
        for update in updates:
            last_update_id = update['update_id']
            
            if 'message' in update:
                msg = update['message']
                chat_id = msg['chat']['id']
                if 'text' in msg:
                    handle_message(chat_id, msg['text'])
            
            elif 'callback_query' in update:
                query = update['callback_query']
                chat_id = query['message']['chat']['id']
                message_id = query['message']['message_id']
                callback_data = query['data']
                
                # الرد على callback
                url = f"{API_URL}/answerCallbackQuery"
                requests.post(url, json={"callback_query_id": query['id']})
                
                handle_callback(chat_id, callback_data, message_id)
        
        time.sleep(1)
    except Exception as e:
        print(f"خطأ: {e}")
        time.sleep(3)
