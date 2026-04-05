import os
import re
import asyncio
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import tempfile

# التوكن الخاص بك (تم وضعه مباشرة)
BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **البوت يعمل بنجاح!**\n\nأرسل لي رابط فيديو من إنستقرام وسأرسله لك مع الإحصائيات.\n\nمثال: `https://www.instagram.com/reel/xxxxx/`",
        parse_mode='Markdown'
    )

async def get_instagram_info(url: str):
    ydl_opts = {'quiet': True, 'no_warnings': True}
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
            stats = {
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'comments': info.get('comment_count', 0),
                'uploader': info.get('uploader', 'غير معروف'),
            }
            return stats
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return None

async def download_instagram_video(url: str):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()
    base_path = temp_path[:-4]
    
    ydl_opts = {
        'outtmpl': base_path,
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    }
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.download([url]))
            for path in [f"{base_path}.mp4", temp_path]:
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    return path
            return None
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return None

def format_stats(stats):
    if not stats:
        return "✅ تم التحميل بنجاح!"
    msg = f"📊 إحصائيات الفيديو\n━━━━━━━━━━━━━━\n"
    if stats.get('views'): msg += f"👁️ المشاهدات: {stats['views']:,}\n"
    if stats.get('likes'): msg += f"❤️ الإعجابات: {stats['likes']:,}\n"
    if stats.get('uploader'): msg += f"👤 الناشر: {stats['uploader']}\n"
    return msg

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ جاري المعالجة...")
    
    try:
        video_path = await download_instagram_video(url)
        if not video_path:
            await msg.edit_text("❌ فشل التحميل. تأكد من الرابط.")
            return
        
        stats = await get_instagram_info(url)
        stats_text = format_stats(stats)
        
        with open(video_path, 'rb') as f:
            await update.message.reply_video(video=InputFile(f), caption=stats_text)
        
        await msg.delete()
        os.unlink(video_path)
    except Exception as e:
        await msg.edit_text(f"⚠️ خطأ: {str(e)[:100]}")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'instagram\.com'), handle_link))
    app.add_handler(MessageHandler(filters.TEXT, lambda u,c: u.message.reply_text("أرسل رابط إنستقرام فقط")))
    
    print("✅ البوت يعمل...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
