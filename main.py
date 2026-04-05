import os
import re
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import tempfile

BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **البوت يعمل!**\n\nأرسل رابط فيديو من إنستقرام",
        parse_mode='Markdown'
    )

def download_video_sync(url: str):
    """تحميل الفيديو (نسخة متزامنة)"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()
    
    ydl_opts = {
        'outtmpl': temp_path[:-4],
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            final_path = f"{temp_path[:-4]}.mp4"
            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                return final_path
        return None
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return None

def get_info_sync(url: str):
    """جلب المعلومات (نسخة متزامنة)"""
    ydl_opts = {'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'uploader': info.get('uploader', 'غير معروف'),
            }
    except:
        return None

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ جاري التحميل...")
    
    try:
        # تشغيل التحميل في thread منفصل
        video_path = await asyncio.get_event_loop().run_in_executor(None, download_video_sync, url)
        
        if not video_path:
            await msg.edit_text("❌ فشل التحميل")
            return
        
        stats = await asyncio.get_event_loop().run_in_executor(None, get_info_sync, url)
        
        caption = "✅ تم التحميل بنجاح!"
        if stats:
            caption = f"📊 إحصائيات\n👁️ مشاهدات: {stats['views']:,}\n❤️ إعجابات: {stats['likes']:,}\n👤 ناشر: {stats['uploader']}"
        
        with open(video_path, 'rb') as f:
            await update.message.reply_video(video=InputFile(f), caption=caption)
        
        await msg.delete()
        os.unlink(video_path)
    except Exception as e:
        await msg.edit_text(f"⚠️ خطأ: {str(e)[:100]}")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'instagram\.com'), handle_link))
    
    print("✅ البوت يعمل...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
