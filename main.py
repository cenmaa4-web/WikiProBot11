import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import tempfile

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0")

async def get_instagram_info(url: str):
    """جلب معلومات الفيديو (الرابط + الإحصائيات) بدون حساب"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            stats = {
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'comments': info.get('comment_count', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'title': info.get('title', '')[:100],
            }
            return video_url, stats
    except Exception as e:
        logger.error(f"خطأ في جلب المعلومات: {e}")
        return None, None

async def download_instagram_video(url: str):
    """تحميل الفيديو"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()
    
    ydl_opts = {
        'outtmpl': temp_path.replace('.mp4', ''),
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            actual_path = temp_path.replace('.mp4', '') + '.mp4'
            if os.path.exists(actual_path):
                return actual_path
            return None
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        return None

def format_stats(stats: dict):
    if not stats:
        return "❌ لم نتمكن من جلب الإحصائيات"
    return (
        f"📊 **إحصائيات الفيديو**\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👁️ **المشاهدات:** {stats.get('views', 0):,}\n"
        f"❤️ **الإعجابات:** {stats.get('likes', 0):,}\n"
        f"💬 **التعليقات:** {stats.get('comments', 0):,}\n"
        f"👤 **الناشر:** {stats.get('uploader')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n✨ شكراً لاستخدام البوت!"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **مرحباً!**\nأرسل لي رابط فيديو من إنستقرام وسأرسله لك مع الإحصائيات.\n\n"
        "✅ مثال: `https://www.instagram.com/reel/xxxxx/`",
        parse_mode='Markdown'
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ جاري المعالجة...")
    
    try:
        video_path = await download_instagram_video(url)
        if not video_path:
            await msg.edit_text("❌ فشل التحميل. تأكد من صحة الرابط.")
            return
        
        _, stats = await get_instagram_info(url)
        stats_text = format_stats(stats)
        
        with open(video_path, 'rb') as f:
            await update.message.reply_video(
                video=InputFile(f, filename="instagram.mp4"),
                caption=stats_text,
                parse_mode='Markdown'
            )
        
        await msg.delete()
        os.unlink(video_path)
        
    except Exception as e:
        await msg.edit_text(f"⚠️ حدث خطأ: {e}")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'instagram\.com'), handle_link))
    await app.run_polling()

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("❌ لم يتم العثور على BOT_TOKEN في ملف .env")
    else:
        asyncio.run(main())
