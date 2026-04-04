import os
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

START_MESSAGE = """
🎬 بوت التحميل الشامل

• ارسل رابط فيديو من اي منصة ← يرفع الفيديو مباشرة
• ارسل رابط يوتيوب ← يظهر لك خيارات التحميل
• ارسل كلمة بحث ← يعطيك 4 نتائج من يوتيوب مع صور

المنصات المدعومة: يوتيوب - تيك توك - انستغرام - فيسبوك - تويتر - سناب شات
"""

class Downloader:
    def is_youtube(self, url):
        return 'youtube.com' in url or 'youtu.be' in url
    
    def is_social(self, url):
        sites = ['tiktok.com', 'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'snapchat.com']
        return any(s in url for s in sites)
    
    async def download_video(self, url):
        os.makedirs('downloads', exist_ok=True)
        opts = {'format': 'best[height<=720]', 'outtmpl': 'downloads/video_%(id)s.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    
    async def download_audio(self, url):
        os.makedirs('downloads', exist_ok=True)
        opts = {'format': 'bestaudio', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}], 'outtmpl': 'downloads/audio_%(id)s.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
    
    async def search(self, query):
        opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch4:{query}", download=False)
            results = []
            for e in info['entries']:
                if e:
                    results.append({'title': e['title'], 'url': f"https://youtube.com/watch?v={e['id']}", 'thumbnail': e.get('thumbnail', '')})
            return results

dl = Downloader()

def yt_buttons(url):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎬 فيديو", callback_data=f"v_{url}"), InlineKeyboardButton("🎵 صوت", callback_data=f"a_{url}")]])

async def start(update, context):
    await update.message.reply_text(START_MESSAGE)

async def handle(update, context):
    msg = update.message.text.strip()
    if not msg: return
    status = await update.message.reply_text("⏳ جاري...")
    
    if 'http' in msg:
        if dl.is_youtube(msg):
            await status.edit_text("اختر:", reply_markup=yt_buttons(msg))
        elif dl.is_social(msg):
            await status.edit_text("📥 جاري التحميل...")
            try:
                path = await dl.download_video(msg)
                with open(path, 'rb') as f:
                    await update.message.reply_video(f, caption="✅ تم")
                os.remove(path)
                await status.delete()
            except Exception as e:
                await status.edit_text(f"❌ {str(e)[:80]}")
        else:
            await status.edit_text("❌ رابط غير مدعوم")
    else:
        await status.edit_text(f"🔍 جاري البحث عن: {msg}")
        try:
            results = await dl.search(msg)
            await status.delete()
            for r in results:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 تحميل", callback_data=f"v_{r['url']}")]])
                await update.message.reply_photo(r['thumbnail'], caption=f"🎥 {r['title'][:50]}", reply_markup=btn)
        except Exception as e:
            await status.edit_text(f"❌ {str(e)[:80]}")

async def callback(update, context):
    q = update.callback_query
    await q.answer()
    t = q.data[0]
    url = q.data[2:]
    await q.edit_message_text("⏳ جاري التحميل...")
    try:
        if t == 'v':
            path = await dl.download_video(url)
            with open(path, 'rb') as f:
                await q.message.reply_video(f, caption="✅ تم")
        else:
            path = await dl.download_audio(url)
            with open(path, 'rb') as f:
                await q.message.reply_audio(f, title="صوت")
        os.remove(path)
        await q.delete_message()
    except Exception as e:
        await q.edit_message_text(f"❌ {str(e)[:80]}")

if __name__ == '__main__':
    print("🚀 تشغيل البوت...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(callback))
    print("✅ يعمل")
    app.run_polling()
