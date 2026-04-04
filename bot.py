# bot.py - نسخة متوافقة مع Python 3.13
import os
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# ===================== إعدادات البوت =====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# رسالة الترحيب
START_MESSAGE = """
🎬 **مرحباً بك في بوت التحميل الشامل!**

📌 **طريقة الاستخدام:**
• أرسل رابط فيديو من أي منصة ← سيتم رفع الفيديو مباشرة
• أرسل رابط يوتيوب ← ستظهر لك خيارات التحميل
• أرسل أي كلمة بحث ← سأعطيك 4 نتائج من اليوتيوب مع الصور

✨ **المنصات المدعومة:**
✅ YouTube | ✅ TikTok | ✅ Instagram | ✅ Facebook
✅ Twitter/X | ✅ SnapChat | ✅ Reddit | ✅ Vimeo
"""

# ===================== كلاس تحميل الفيديوهات =====================
class VideoDownloader:
    def __init__(self):
        self.downloads_folder = "downloads"
        os.makedirs(self.downloads_folder, exist_ok=True)
        
    def is_youtube_link(self, url: str) -> bool:
        youtube_patterns = [
            r'(youtube\.com/watch\?v=)',
            r'(youtu\.be/)',
            r'(youtube\.com/shorts/)',
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
    def is_social_link(self, url: str) -> bool:
        social_sites = [
            'tiktok.com', 'instagram.com', 'facebook.com', 
            'twitter.com', 'x.com', 'snapchat.com',
            'reddit.com', 'vimeo.com'
        ]
        return any(site in url.lower() for site in social_sites)
    
    async def download_video(self, url: str) -> str:
        ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': f'{self.downloads_folder}/%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            return ydl.prepare_filename(info)
    
    async def download_audio(self, url: str) -> str:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{self.downloads_folder}/audio_%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            filename = ydl.prepare_filename(info)
            return filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
    
    async def download_audio_preview(self, url: str, duration: int = 30) -> str:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': f'{self.downloads_folder}/preview_%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            filename = ydl.prepare_filename(info)
            return filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
    
    async def search_youtube(self, query: str, max_results: int = 4) -> list:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        loop = asyncio.get_event_loop()
        search_query = f"ytsearch{max_results}:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(search_query, download=False))
            results = []
            if info and 'entries' in info:
                for entry in info['entries']:
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

def get_youtube_buttons(video_url: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"dl_video_{video_url}"),
            InlineKeyboardButton("🎵 تحميل صوت MP3", callback_data=f"dl_audio_{video_url}"),
        ],
        [
            InlineKeyboardButton("🔊 بصمة صوتية", callback_data=f"dl_preview_{video_url}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

downloader = VideoDownloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()
    
    if not user_message:
        return
    
    processing_msg = await update.message.reply_text("⏳ **جاري معالجة طلبك...**", parse_mode='Markdown')
    
    if 'http://' in user_message or 'https://' in user_message:
        if downloader.is_youtube_link(user_message):
            buttons = get_youtube_buttons(user_message)
            await processing_msg.edit_text(
                "📹 **تم اكتشاف رابط يوتيوب!**\n\nاختر ما تريد:",
                reply_markup=buttons,
                parse_mode='Markdown'
            )
        elif downloader.is_social_link(user_message):
            await processing_msg.edit_text("📥 جاري تحميل الفيديو...", parse_mode='Markdown')
            try:
                video_path = await downloader.download_video(user_message)
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(video=video_file, caption="✅ تم التحميل بنجاح!")
                os.remove(video_path)
                await processing_msg.delete()
            except Exception as e:
                await processing_msg.edit_text(f"❌ فشل التحميل: {str(e)[:100]}")
        else:
            await processing_msg.edit_text("❌ هذا الرابط غير مدعوم حالياً")
    else:
        await processing_msg.edit_text(f"🔍 جاري البحث عن: {user_message}", parse_mode='Markdown')
        try:
            results = await downloader.search_youtube(user_message, max_results=4)
            if not results:
                await processing_msg.edit_text("❌ لم يتم العثور على نتائج")
                return
            
            await processing_msg.delete()
            for result in results:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎬 تحميل", callback_data=f"dl_video_{result['url']}")
                ]])
                caption = f"🎥 **{result['title'][:50]}**\n⏱️ {result['duration']}"
                await update.message.reply_photo(photo=result['thumbnail'], caption=caption, reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            await processing_msg.edit_text(f"❌ فشل البحث: {str(e)[:100]}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split('_', 2)
    if len(parts) < 3:
        return
    
    dl_type = parts[1]
    url = parts[2]
    
    await query.edit_message_text("⏳ جاري التحميل...")
    
    try:
        if dl_type == 'video':
            video_path = await downloader.download_video(url)
            with open(video_path, 'rb') as video_file:
                await query.message.reply_video(video=video_file, caption="✅ تم التحميل!")
            os.remove(video_path)
        elif dl_type == 'audio':
            audio_path = await downloader.download_audio(url)
            with open(audio_path, 'rb') as audio_file:
                await query.message.reply_audio(audio=audio_file, title="صوت من يوتيوب")
            os.remove(audio_path)
        elif dl_type == 'preview':
            preview_path = await downloader.download_audio_preview(url)
            with open(preview_path, 'rb') as preview_file:
                await query.message.reply_audio(audio=preview_file, title="بصمة صوتية")
            os.remove(preview_path)
        await query.delete_message()
    except Exception as e:
        await query.edit_message_text(f"❌ فشل التحميل: {str(e)[:100]}")

async def main():
    print("🚀 تشغيل البوت...")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("✅ البوت يعمل الآن!")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
