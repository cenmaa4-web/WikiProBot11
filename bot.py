import os
import json
import requests
import yt_dlp
import time
import re

BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# رسالة الترحيب
START_MESSAGE = """
🎬 **بوت التحميل الشامل - النسخة المطورة**

📌 **طريقة الاستخدام:**

1️⃣ **أرسل رابط فيديو من أي منصة** (تيك توك، انستغرام، فيسبوك، تويتر، سناب شات)
   ← سيتم رفع الفيديو مباشرة في المحادثة

2️⃣ **أرسل رابط يوتيوب**
   ← ستظهر لك 3 أزرار:
   • 🎬 تحميل فيديو
   • 🎵 تحميل صوت MP3
   • 🔊 بصمة صوتية (30 ثانية)

3️⃣ **أرسل أي كلمة بحث**
   ← سأعطيك 4 نتائج من يوتيوب
   ← كل نتيجة: صورة + رابط + زر تحميل تحتها

✨ **المنصات المدعومة:**
YouTube | TikTok | Instagram | Facebook | Twitter/X | SnapChat | Reddit | Vimeo
"""

def send_message(chat_id, text, reply_markup=None, edit=False, message_id=None):
    if edit and message_id:
        url = f"{API_URL}/editMessageText"
        data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    else:
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
        data = {'chat_id': chat_id, 'title': title, 'performer': "YouTube Bot"}
        requests.post(url, data=data, files=files)

def send_photo(chat_id, photo_url, caption="", reply_markup=None):
    url = f"{API_URL}/sendPhoto"
    data = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=data)

def delete_message(chat_id, message_id):
    url = f"{API_URL}/deleteMessage"
    requests.post(url, json={"chat_id": chat_id, "message_id": message_id})

def get_updates(offset=None):
    url = f"{API_URL}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    response = requests.get(url, params=params)
    return response.json().get("result", [])

def answer_callback(callback_id):
    url = f"{API_URL}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_id})

class VideoDownloader:
    def is_youtube(self, url):
        youtube_patterns = [r'(youtube\.com/watch\?v=)', r'(youtu\.be/)', r'(youtube\.com/shorts/)']
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in youtube_patterns)
    
    def is_social(self, url):
        sites = ['tiktok.com', 'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'snapchat.com', 'reddit.com', 'vimeo.com']
        return any(site in url.lower() for site in sites)
    
    def get_site_name(self, url):
        for site in ['tiktok', 'instagram', 'facebook', 'twitter', 'snapchat', 'reddit', 'vimeo']:
            if site in url.lower():
                return site.upper()
        return "المنصة"
    
    def download_video(self, url):
        os.makedirs('downloads', exist_ok=True)
        opts = {
            'format': 'best[height<=720]',
            'outtmpl': 'downloads/video_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    
    def download_audio(self, url):
        os.makedirs('downloads', exist_ok=True)
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
            return filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
    
    def download_preview(self, url, duration=30):
        """تحميل بصمة صوتية (مقتطف قصير)"""
        os.makedirs('downloads', exist_ok=True)
        opts = {
            'format': 'bestaudio',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
            'outtmpl': 'downloads/preview_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            # محاولة قص الصوت (يتطلب ffmpeg)
            preview_file = filename.replace('.mp3', f'_preview.mp3')
            try:
                import subprocess
                subprocess.run([
                    'ffmpeg', '-i', filename, '-t', str(duration),
                    '-acodec', 'mp3', '-ab', '128k', preview_file, '-y'
                ], capture_output=True, timeout=30)
                if os.path.exists(preview_file) and os.path.getsize(preview_file) > 0:
                    os.remove(filename)
                    return preview_file
            except:
                pass
            return filename
    
    def search_youtube(self, query):
        opts = {'quiet': True, 'extract_flat': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch4:{query}", download=False)
            results = []
            for entry in info['entries']:
                if entry:
                    duration = entry.get('duration', 0) or 0
                    minutes = duration // 60
                    seconds = duration % 60
                    results.append({
                        'title': entry['title'],
                        'url': f"https://youtube.com/watch?v={entry['id']}",
                        'thumbnail': entry.get('thumbnail', ''),
                        'duration': f"{minutes}:{seconds:02d}",
                        'channel': entry.get('uploader', 'غير معروف')
                    })
            return results

downloader = VideoDownloader()
last_update_id = 0

def make_youtube_buttons(url):
    """أزرار تحميل اليوتيوب: فيديو - صوت - بصمة"""
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
    """زر تحميل لنتائج البحث"""
    return {
        "inline_keyboard": [
            [{"text": "🎬 تحميل الفيديو", "callback_data": f"video_{url}"}]
        ]
    }

def handle_start(chat_id):
    send_message(chat_id, START_MESSAGE)

def handle_message(chat_id, text, message_id=None):
    text = text.strip()
    if not text:
        return
    
    # رسالة جاري المعالجة
    processing_msg = send_message(chat_id, "⏳ جاري معالجة طلبك...")
    
    if 'http://' in text or 'https://' in text:
        # حالة 1: رابط يوتيوب
        if downloader.is_youtube(text):
            keyboard = make_youtube_buttons(text)
            send_message(chat_id, "📹 **✅ تم اكتشاف رابط يوتيوب!**\n\n🎯 اختر ما تريد تحميله:", keyboard)
        
        # حالة 2: رابط منصة تواصل اجتماعي
        elif downloader.is_social(text):
            site_name = downloader.get_site_name(text)
            send_message(chat_id, f"📥 جاري تحميل الفيديو من {site_name}...")
            try:
                path = downloader.download_video(text)
                send_video(chat_id, path, f"✅ تم التحميل بنجاح من {site_name}! 🎉")
                os.remove(path)
            except Exception as e:
                send_message(chat_id, f"❌ فشل التحميل: {str(e)[:100]}")
        
        # حالة 3: رابط غير مدعوم
        else:
            send_message(chat_id, "❌ عذراً، هذا الرابط غير مدعوم حالياً!\n\nالمنصات المدعومة:\nYouTube | TikTok | Instagram | Facebook | Twitter | SnapChat | Reddit | Vimeo")
    
    else:
        # حالة 4: بحث في يوتيوب
        send_message(chat_id, f"🔍 جاري البحث عن: **{text}**...")
        try:
            results = downloader.search_youtube(text)
            
            if not results:
                send_message(chat_id, "❌ لم يتم العثور على نتائج\nحاول بكلمات مختلفة")
                return
            
            for result in results:
                caption = f"🎥 **{result['title'][:60]}**\n\n⏱️ **المدة:** {result['duration']}\n📺 **القناة:** {result['channel']}\n🔗 [اضغط للمشاهدة]({result['url']})"
                
                keyboard = make_search_button(result['url'])
                
                if result['thumbnail']:
                    send_photo(chat_id, result['thumbnail'], caption, keyboard)
                else:
                    send_message(chat_id, caption, keyboard)
                    
        except Exception as e:
            send_message(chat_id, f"❌ فشل البحث: {str(e)[:100]}")

def handle_callback(chat_id, callback_data, message_id, callback_id):
    # الرد على callback
    answer_callback(callback_id)
    
    # استخراج نوع التحميل والرابط
    parts = callback_data.split('_', 1)
    if len(parts) < 2:
        return
    
    dl_type = parts[0]  # video, audio, preview
    url = parts[1]
    
    # تعديل الرسالة إلى "جاري التحميل"
    send_message(chat_id, "⏳ جاري التحميل... يرجى الانتظار", edit=True, message_id=message_id)
    
    try:
        if dl_type == 'video':
            path = downloader.download_video(url)
            send_video(chat_id, path, "✅ تم تحميل الفيديو بنجاح! 🎬")
            os.remove(path)
        
        elif dl_type == 'audio':
            path = downloader.download_audio(url)
            send_audio(chat_id, path, "🎵 تحميل من يوتيوب")
            os.remove(path)
        
        elif dl_type == 'preview':
            path = downloader.download_preview(url, duration=30)
            send_audio(chat_id, path, "🔊 بصمة صوتية (30 ثانية)")
            os.remove(path)
        
        # حذف رسالة "جاري التحميل"
        delete_message(chat_id, message_id)
        
    except Exception as e:
        send_message(chat_id, f"❌ فشل التحميل: {str(e)[:200]}\n\n💡 تأكد من صحة الرابط وحاول مرة أخرى", edit=True, message_id=message_id)

# ===================== تشغيل البوت =====================
print("=" * 50)
print("🚀 تشغيل بوت التحميل الشامل - النسخة المطورة")
print("=" * 50)
print("✅ البوت يعمل الآن!")
print("📱 اذهب إلى تليجرام وابدأ باستخدام البوت")
print("💡 أرسل /start لبدء الاستخدام")
print("=" * 50)

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
        
        time.sleep(1)
        
    except Exception as e:
        print(f"⚠️ خطأ: {e}")
        time.sleep(3)
