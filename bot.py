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
🎬 **بوت التحميل الشامل - النسخة النهائية**

📌 **طريقة الاستخدام:**

1️⃣ **أرسل رابط فيديو** من أي منصة
   ← يرفع الفيديو مباشرة

2️⃣ **أرسل رابط يوتيوب**
   ← يظهر 4 أزرار تفاعلية:
   • 🎬 تحميل فيديو
   • 🎵 تحميل صوت MP3  
   • 🔊 بصمة صوتية (30 ث)
   • 🔍 بحث جديد

3️⃣ **أرسل أي كلمة بحث**
   ← 4 نتائج من يوتيوب
   ← كل نتيجة: صورة + معلومات + زر تحميل

✨ **المنصات المدعومة:**
YouTube | TikTok | Instagram | Facebook | Twitter | SnapChat | Reddit | Vimeo | Dailymotion | Twitch
"""

def api_request(method, data=None, files=None):
    """وظيفة موحدة لإرسال طلبات API"""
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
        data = {'chat_id': chat_id, 'caption': caption, 'supports_streaming': True}
        api_request("sendVideo", data, files)

def send_audio(chat_id, audio_path, title="", performer=""):
    with open(audio_path, 'rb') as audio:
        files = {'audio': audio}
        data = {'chat_id': chat_id, 'title': title, 'performer': performer}
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
    params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
    if offset:
        params["offset"] = offset
    response = requests.get(f"{API_URL}/getUpdates", params=params)
    return response.json().get("result", [])

class VideoDownloader:
    def __init__(self):
        os.makedirs('downloads', exist_ok=True)
    
    def is_youtube(self, url):
        patterns = [r'youtube\.com/watch', r'youtu\.be/', r'youtube\.com/shorts', r'youtube\.com/embed']
        return any(re.search(p, url, re.I) for p in patterns)
    
    def is_social(self, url):
        sites = ['tiktok', 'instagram', 'facebook', 'twitter', 'x.com', 'snapchat', 'reddit', 'vimeo', 'dailymotion', 'twitch']
        return any(s in url.lower() for s in sites)
    
    def get_site_name(self, url):
        sites = {'tiktok': 'TikTok', 'instagram': 'Instagram', 'facebook': 'Facebook', 'twitter': 'Twitter', 'snapchat': 'SnapChat', 'reddit': 'Reddit', 'vimeo': 'Vimeo'}
        for key, name in sites.items():
            if key in url.lower():
                return name
        return "Social Media"
    
    def download_video(self, url):
        opts = {
            'format': 'best[height<=720]',
            'outtmpl': 'downloads/video_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test = filename.split('.')[0] + ext
                        if os.path.exists(test):
                            return test
                return filename
            except Exception as e:
                raise Exception(f"فشل التحميل: {str(e)[:100]}")
    
    def download_audio(self, url):
        opts = {
            'format': 'bestaudio',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': 'downloads/audio_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.opus', '.mp3')
            if not os.path.exists(filename):
                base = filename.replace('.mp3', '')
                for f in os.listdir('downloads'):
                    if f.startswith(os.path.basename(base)) and f.endswith('.mp3'):
                        return os.path.join('downloads', f)
            return filename
    
    def download_preview(self, url, duration=30):
        audio_file = self.download_audio(url)
        preview_file = audio_file.replace('.mp3', f'_preview.mp3')
        
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
                for entry in info.get('entries', []):
                    if entry:
                        duration = entry.get('duration', 0) or 0
                        minutes = duration // 60
                        seconds = duration % 60
                        results.append({
                            'title': entry.get('title', 'بدون عنوان'),
                            'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                            'thumbnail': entry.get('thumbnail', ''),
                            'duration': f"{minutes}:{seconds:02d}",
                            'channel': entry.get('uploader', 'غير معروف')
                        })
                return results
        except Exception as e:
            raise Exception(f"فشل البحث: {str(e)[:100]}")

downloader = VideoDownloader()
last_update_id = 0

def make_youtube_buttons(url):
    """أزرار تفاعلية لرابط اليوتيوب"""
    return {
        "inline_keyboard": [
            [
                {"text": "🎬 تحميل فيديو", "callback_data": f"video_{url}"},
                {"text": "🎵 تحميل صوت MP3", "callback_data": f"audio_{url}"}
            ],
            [
                {"text": "🔊 بصمة صوتية (30 ث)", "callback_data": f"preview_{url}"},
                {"text": "🔍 بحث في يوتيوب", "callback_data": "search_mode"}
            ]
        ]
    }

def make_search_button(url):
    """زر تحميل لنتائج البحث"""
    return {"inline_keyboard": [[{"text": "🎬 تحميل الفيديو", "callback_data": f"video_{url}"}]]}

def make_search_keyboard():
    """لوحة مفاتيح للبحث"""
    return {"inline_keyboard": [[{"text": "🔍 بحث جديد", "callback_data": "new_search"}]]}

def handle_start(chat_id):
    send_message(chat_id, START_MESSAGE)

def handle_message(chat_id, text):
    text = text.strip()
    if not text:
        return
    
    # إرسال رسالة المعالجة
    send_message(chat_id, "⏳ جاري معالجة طلبك...")
    
    # رابط
    if 'http://' in text or 'https://' in text:
        if downloader.is_youtube(text):
            send_message(chat_id, "📹 **✅ تم اكتشاف رابط يوتيوب!**\n\n🎯 اختر ما تريد تحميله:", make_youtube_buttons(text))
        
        elif downloader.is_social(text):
            site = downloader.get_site_name(text)
            send_message(chat_id, f"📥 جاري تحميل الفيديو من {site}...")
            try:
                path = downloader.download_video(text)
                send_video(chat_id, path, f"✅ تم التحميل بنجاح من {site}! 🎉")
                os.remove(path)
            except Exception as e:
                send_message(chat_id, f"❌ فشل التحميل: {str(e)[:150]}")
        else:
            send_message(chat_id, "❌ عذراً، هذا الرابط غير مدعوم!\n\nالمنصات المدعومة:\nYouTube | TikTok | Instagram | Facebook | Twitter | SnapChat | Reddit | Vimeo")
    
    # بحث
    else:
        send_message(chat_id, f"🔍 جاري البحث عن: **{text}**...")
        try:
            results = downloader.search_youtube(text)
            
            if not results:
                send_message(chat_id, "❌ لم يتم العثور على نتائج\nحاول بكلمات مختلفة")
                return
            
            for r in results:
                caption = f"🎥 **{r['title'][:55]}**\n\n⏱️ **المدة:** {r['duration']}\n📺 **القناة:** {r['channel']}\n🔗 [اضغط للمشاهدة]({r['url']})"
                
                if r['thumbnail']:
                    send_photo(chat_id, r['thumbnail'], caption, make_search_button(r['url']))
                else:
                    send_message(chat_id, caption, make_search_button(r['url']))
            
            # إضافة زر بحث جديد
            send_message(chat_id, "🔍 **للبحث مرة أخرى، فقط اكتب كلمة جديدة!**", make_search_keyboard())
            
        except Exception as e:
            send_message(chat_id, f"❌ فشل البحث: {str(e)[:150]}")

def handle_callback(chat_id, callback_data, message_id, callback_id):
    answer_callback(callback_id)
    
    # زر البحث الجديد
    if callback_data == "new_search":
        send_message(chat_id, "📝 **أرسل كلمة البحث التي تريدها**")
        return
    
    if callback_data == "search_mode":
        send_message(chat_id, "📝 **أرسل كلمة البحث التي تريدها**")
        return
    
    # تحميل فيديو أو صوت
    parts = callback_data.split('_', 1)
    if len(parts) < 2:
        return
    
    dl_type = parts[0]
    url = parts[1]
    
    send_message(chat_id, "⏳ جاري التحميل... يرجى الانتظار", edit=True, message_id=message_id)
    
    try:
        if dl_type == 'video':
            path = downloader.download_video(url)
            send_video(chat_id, path, "✅ تم تحميل الفيديو بنجاح! 🎬")
            os.remove(path)
        
        elif dl_type == 'audio':
            path = downloader.download_audio(url)
            send_audio(chat_id, path, "🎵 تحميل من يوتيوب", "YouTube Bot")
            os.remove(path)
        
        elif dl_type == 'preview':
            path = downloader.download_preview(url, 30)
            send_audio(chat_id, path, "🔊 بصمة صوتية (30 ثانية)", "YouTube Preview")
            os.remove(path)
        
        delete_message(chat_id, message_id)
        
    except Exception as e:
        send_message(chat_id, f"❌ فشل التحميل: {str(e)[:200]}\n\n💡 تأكد من صحة الرابط وحاول مرة أخرى", edit=True, message_id=message_id)

# ===================== تشغيل البوت =====================
print("=" * 55)
print("🚀 تشغيل بوت التحميل الشامل - النسخة النهائية")
print("=" * 55)
print("✅ البوت يعمل الآن!")
print("📱 اذهب إلى تليجرام وابدأ باستخدام البوت")
print("💡 أرسل /start لبدء الاستخدام")
print("=" * 55)

while True:
    try:
        updates = get_updates(last_update_id + 1)
        
        for update in updates:
            last_update_id = update['update_id']
            
            # معالجة الرسائل
            if 'message' in update:
                msg = update['message']
                chat_id = msg['chat']['id']
                
                if 'text' in msg:
                    text = msg['text']
                    if text == '/start':
                        handle_start(chat_id)
                    else:
                        handle_message(chat_id, text)
            
            # معالجة الأزرار
            elif 'callback_query' in update:
                query = update['callback_query']
                chat_id = query['message']['chat']['id']
                message_id = query['message']['message_id']
                callback_data = query['data']
                callback_id = query['id']
                
                handle_callback(chat_id, callback_data, message_id, callback_id)
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"⚠️ خطأ: {e}")
        time.sleep(3)
