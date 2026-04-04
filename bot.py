import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
import yt_dlp

BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

START_MESSAGE = """
🎬 **بوت التحميل الشامل**

• ارسل رابط فيديو من اي منصة ← يرفع الفيديو مباشرة
• ارسل رابط يوتيوب ← يظهر لك خيارات التحميل  
• ارسل كلمة بحث ← يعطيك 4 نتائج من يوتيوب

**المنصات المدعومة:** يوتيوب - تيك توك - انستغرام - فيسبوك - تويتر - سناب شات
"""

class VideoDownloader:
    def is_youtube(self, url):
        return 'youtube.com' in url or 'youtu.be' in url
    
    def is_social(self, url):
        sites = ['tiktok.com', 'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'snapchat.com']
        return any(s in url for s in sites)
    
    def download_video(self, url):
        os.makedirs('downloads', exist_ok=True)
        opts = {
            'format': 'best[height<=720]',
            'outtmpl': 'downloads/video_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True
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
    
    def search_youtube(self, query):
        opts = {'quiet': True, 'extract_flat': True, 'no_warnings': True}
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

def youtube_buttons(url):
    keyboard = [
        [InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"video_{url}")],
        [InlineKeyboardButton("🎵 تحميل صوت MP3", callback_data=f"audio_{url}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def start(update, context):
    update.message.reply_text(START_MESSAGE, parse_mode='Markdown')

def handle_message(update, context):
    msg = update.message.text.strip()
    if not msg:
        return
    
    status = update.message.reply_text("⏳ جاري المعالجة...")
    
    if 'http://' in msg or 'https://' in msg:
        if downloader.is_youtube(msg):
            status.edit_text("✅ رابط يوتيوب - اختر ما تريد:", reply_markup=youtube_buttons(msg))
        
        elif downloader.is_social(msg):
            status.edit_text("📥 جاري تحميل الفيديو...")
            try:
                path = downloader.download_video(msg)
                with open(path, 'rb') as video:
                    update.message.reply_video(video, caption="✅ تم التحميل بنجاح!")
                os.remove(path)
                status.delete()
            except Exception as e:
                status.edit_text(f"❌ فشل التحميل: {str(e)[:100]}")
        else:
            status.edit_text("❌ هذا الرابط غير مدعوم")
    
    else:
        status.edit_text(f"🔍 جاري البحث عن: {msg}")
        try:
            results = downloader.search_youtube(msg)
            status.delete()
            
            for result in results:
                button = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 تحميل", callback_data=f"video_{result['url']}")]])
                caption = f"🎥 **{result['title'][:50]}**"
                update.message.reply_photo(result['thumbnail'], caption=caption, reply_markup=button, parse_mode='Markdown')
        except Exception as e:
            status.edit_text(f"❌ فشل البحث: {str(e)[:100]}")

def handle_callback(update, context):
    query = update.callback_query
    query.answer()
    
    data = query.data
    action, url = data.split('_', 1)
    
    query.edit_message_text("⏳ جاري التحميل... يرجى الانتظار")
    
    try:
        if action == 'video':
            path = downloader.download_video(url)
            with open(path, 'rb') as video:
                query.message.reply_video(video, caption="✅ تم تحميل الفيديو!")
            os.remove(path)
        
        elif action == 'audio':
            path = downloader.download_audio(url)
            with open(path, 'rb') as audio:
                query.message.reply_audio(audio, title="صوت من يوتيوب", performer="Downloader Bot")
            os.remove(path)
        
        query.delete_message()
    
    except Exception as e:
        query.edit_message_text(f"❌ فشل التحميل: {str(e)[:100]}")

if __name__ == '__main__':
    print("=" * 40)
    print("🚀 تشغيل بوت التحميل الشامل...")
    print("=" * 40)
    
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    
    print("✅ البوت يعمل الآن!")
    print("📱 اذهب إلى تليجرام وابدأ باستخدام البوت")
    print("=" * 40)
    
    updater.start_polling()
    updater.idle()
