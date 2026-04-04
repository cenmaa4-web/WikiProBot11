import os
import json
import requests
import yt_dlp
import time
import re
import subprocess

BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

START_MESSAGE = """
🎬 **بوت التحميل الشامل - النسخة المصححة**

📌 **طريقة الاستخدام:**

1️⃣ **أرسل رابط فيديو** من أي منصة
   ← يرفع الفيديو مباشرة

2️⃣ **أرسل رابط يوتيوب**
   ← يظهر 3 أزرار:
   • 🎬 تحميل فيديو
   • 🎵 تحميل صوت MP3  
   • 🔊 بصمة صوتية (30 ث)

3️⃣ **أرسل أي كلمة بحث**
   ← 4 نتائج من يوتيوب مع صور

✨ **المنصات المدعومة:**
YouTube | TikTok | Facebook | Twitter | Reddit | Vimeo
"""

def api_request(method, data=None, files=None):
    url = f"{API_URL}/{method}"
    if files:
        return requests.post(url, data=data, files=files)
    return requests.post(url, json=data)

def send_message(chat_id, text, reply_markup=None, edit=False, message_id=None):
    if edit and message_id:
        data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
        api_request("editMessageText", data)
    else:
        data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        api_request("sendMessage", data)

def send_video(chat_id, video_path, caption=""):
    with open(video_path, 'rb') as video:
        files = {'video': video}
        data = {'chat_id': chat_id, 'caption': caption}
        api_request("sendVideo", data, files)

def send_audio(chat_id, audio_path, title=""):
    with open(audio_path, 'rb') as audio:
        files = {'audio': audio}
        data = {'chat_id': chat_id, 'title': title}
        api_request("sendAudio", data, files)

def send_photo(chat_id, photo_url, caption="", reply_markup=None):
    data = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    api_request("sendPhoto", data)

def delete_message(chat_id, message_id):
    api_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

def answer_callback(callback_id):
    api_request("answerCallbackQuery", {"callback_query_id": callback_id})

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    response = requests.get(f"{API_URL}/getUpdates", params=params)
    return response.json().get("result", [])

class VideoDownloader:
    def __init__(self):
        os.makedirs('downloads', exist_ok=True)
    
    def is_youtube(self, url):
        return 'youtube.com' in url or 'youtu.be' in url
    
    def is_social(self, url):
        sites = ['tiktok.com', 'facebook.com', 'twitter.com', 'x.com', 'reddit.com', 'vimeo.com']
        return any(s in url.lower() for s in sites)
    
    def download_video(self, url):
        opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': 'downloads/video_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    filename = ydl.prepare_filename(info)
                    if os.path.exists(filename):
                        return filename
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test = filename.rsplit('.', 1)[0] + ext
                        if os.path.exists(test):
                            return test
                raise Exception("لم يتم العثور على الملف")
        except Exception as e:
            raise Exception(str(e))
    
    def download_audio(self, url):
        opts = {
            'format': 'bestaudio',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'outtmpl': 'downloads/audio_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
                if os.path.exists(filename):
                    return filename
                raise Exception("لم يتم العثور على الملف الصوتي")
        except Exception as e:
            raise Exception(str(e))
    
    def download_preview(self, url, duration=30):
        audio_file = self.download_audio(url)
        preview_file = audio_file.replace('.mp3', '_preview.mp3')
        try:
            subprocess.run([
                'ffmpeg', '-i', audio_file, '-t', str(duration),
                '-acodec', 'mp3', '-ab', '128k', preview_file, '-y'
            ], capture_output=True, timeout=30, check=False)
            if os.path.exists(preview_file) and os.path.getsize(preview_file) > 1000:
                os.remove(audio_file)
                return preview_file
        except:
            pass
        return audio_file
    
    def search_youtube(self, query):
        opts = {'quiet': True, 'extract_flat': True, 'no_warnings': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch4:{query}", download=False)
                results = []
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry and entry.get('id'):
                            duration = entry.get('duration', 0)
                            if duration is None:
                                duration = 0
                            minutes = int(duration) // 60
                            seconds = int(duration) % 60
                            results.append({
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={entry['id']}",
                                'thumbnail': entry.get('thumbnail', ''),
                                'duration': f"{minutes}:{seconds:02d}",
                                'channel': entry.get('uploader', 'غير معروف')
                            })
                return results
        except Exception as e:
            raise Exception(str(e))

downloader = VideoDownloader()
last_update_id = 0

def make_youtube_buttons(url):
    return {
        "inline_keyboard": [
            [
                {"text": "🎬 تحميل فيديو", "callback_data": f"video_{url}"},
                {"text": "🎵 تحميل صوت MP3", "callback_data": f"audio_{url}"}
            ],
            [
                {"text": "🔊 بصمة صوتية (30 ث)", "callback_data": f"preview_{url}"}
            ]
        ]
    }

def make_search_button(url):
    return {"inline_keyboard": [[{"text": "🎬 تحميل الفيديو", "callback_data": f"video_{url}"}]]}

def handle_start(chat_id):
    send_message(chat_id, START_MESSAGE)

def handle_message(chat_id, text):
    text = text.strip()
    if not text:
        return
    
    # رسالة المعالجة
    msg_data = api_request("sendMessage", {"chat_id": chat_id, "text": "⏳ جاري المعالجة..."})
    msg_id = msg_data.json().get('result', {}).get('message_id')
    
    if 'http://' in text or 'https://' in text:
        if downloader.is_youtube(text):
            send_message(chat_id, "📹 ✅ رابط يوتيوب!\n🎯 اختر ما تريد:", make_youtube_buttons(text))
            delete_message(chat_id, msg_id)
        
        elif downloader.is_social(text):
            send_message(chat_id, "📥 جاري التحميل...")
            try:
                path = downloader.download_video(text)
                send_video(chat_id, path, "✅ تم التحميل بنجاح!")
                os.remove(path)
                delete_message(chat_id, msg_id)
            except Exception as e:
                send_message(chat_id, f"❌ فشل التحميل: {str(e)[:100]}")
                delete_message(chat_id, msg_id)
        else:
            send_message(chat_id, "❌ رابط غير مدعوم")
            delete_message(chat_id, msg_id)
    
    else:
        send_message(chat_id, f"🔍 جاري البحث عن: {text}")
        try:
            results = downloader.search_youtube(text)
            delete_message(chat_id, msg_id)
            
            if not results:
                send_message(chat_id, "❌ لم يتم العثور على نتائج")
                return
            
            for r in results:
                caption = f"🎥 **{r['title'][:50]}**\n⏱️ {r['duration']}\n📺 {r['channel']}"
                if r['thumbnail']:
                    send_photo(chat_id, r['thumbnail'], caption, make_search_button(r['url']))
                else:
                    send_message(chat_id, caption, make_search_button(r['url']))
        except Exception as e:
            send_message(chat_id, f"❌ فشل البحث: {str(e)[:100]}")
            delete_message(chat_id, msg_id)

def handle_callback(chat_id, callback_data, message_id, callback_id):
    answer_callback(callback_id)
    
    parts = callback_data.split('_', 1)
    if len(parts) < 2:
        return
    
    dl_type = parts[0]
    url = parts[1]
    
    send_message(chat_id, "⏳ جاري التحميل...", edit=True, message_id=message_id)
    
    try:
        if dl_type == 'video':
            path = downloader.download_video(url)
            send_video(chat_id, path, "✅ تم التحميل!")
            os.remove(path)
        
        elif dl_type == 'audio':
            path = downloader.download_audio(url)
            send_audio(chat_id, path, "🎵 صوت من يوتيوب")
            os.remove(path)
        
        elif dl_type == 'preview':
            path = downloader.download_preview(url, 30)
            send_audio(chat_id, path, "🔊 بصمة صوتية")
            os.remove(path)
        
        delete_message(chat_id, message_id)
        
    except Exception as e:
        send_message(chat_id, f"❌ فشل: {str(e)[:150]}", edit=True, message_id=message_id)

print("=" * 50)
print("🚀 تشغيل البوت - النسخة المصححة")
print("✅ البوت يعمل الآن!")
print("=" * 50)

while True:
    try:
        updates = get_updates(last_update_id + 1)
        for update in updates:
            last_update_id = update['update_id']
            
            if 'message' in update:
                msg = update['message']
                chat_id = msg['chat']['id']
                if 'text' in msg:
                    text = msg['text']
                    if text == '/start':
                        handle_start(chat_id)
                    else:
                        handle_message(chat_id, text)
            
            elif 'callback_query' in update:
                query = update['callback_query']
                chat_id = query['message']['chat']['id']
                message_id = query['message']['message_id']
                callback_data = query['data']
                callback_id = query['id']
                handle_callback(chat_id, callback_data, message_id, callback_id)
        
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ {e}")
        time.sleep(3)
