#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import tempfile
import shutil

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# التوكن
TOKEN = os.environ.get("8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# مجلد مؤقت
DOWNLOAD_FOLDER = tempfile.mkdtemp()
logger.info(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")

# ✅ تم تعديل الإعدادات (أهم جزء)
YDL_OPTIONS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'merge_output_format': 'mp4',
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "👋 مرحباً! أنا بوت تحميل الفيديوهات\n\n"
        "📥 أرسل رابط فيديو وسأقوم بتحميله لك فوراً\n\n"
        "✅ المنصات المدعومة:\n"
        "• YouTube - TikTok - Instagram\n"
        "• Facebook - Twitter - وغيرها\n\n"
        "✨ فقط أرسل الرابط وسأبدأ التحميل!"
    )
    await update.message.reply_text(welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح")
        return
    
    progress_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو...")

    try:
        logger.info(f"تحميل: {url}")
        
        video_path = await download_video(url)
        
        if video_path and os.path.exists(video_path):

            file_size = os.path.getsize(video_path) / (1024 * 1024)

            if file_size > 50:
                await progress_msg.edit_text(f"❌ الفيديو كبير ({file_size:.1f} MB)")
                os.remove(video_path)
                return

            await progress_msg.delete()

            # ✅ تم تحسين الإرسال
            try:
                await update.message.reply_video(
                    video=open(video_path, 'rb'),
                    caption=f"✅ تم التحميل\n📊 {file_size:.1f} MB",
                    supports_streaming=True
                )
            except:
                await update.message.reply_document(
                    document=open(video_path, 'rb'),
                    caption="📁 تم الإرسال كملف"
                )

            os.remove(video_path)
            logger.info("✅ تم الحذف")

        else:
            await progress_msg.edit_text("❌ فشل التحميل (الرابط خاص أو غير مدعوم)")

    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        await progress_msg.edit_text(f"❌ خطأ: {str(e)[:100]}")

async def download_video(url):
    try:
        loop = asyncio.get_event_loop()

        def download_sync():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(url, download=True)

                    # ✅ أفضل طريقة لجلب الملف
                    if info:
                        if 'requested_downloads' in info:
                            for d in info['requested_downloads']:
                                if 'filepath' in d:
                                    return d['filepath']

                        filename = ydl.prepare_filename(info)
                        if os.path.exists(filename):
                            return filename

                    # fallback
                    import glob
                    files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                    if files:
                        return max(files, key=os.path.getctime)

                    return None

            except Exception as e:
                logger.error(f"yt-dlp error: {e}")
                return None

        return await loop.run_in_executor(None, download_sync)

    except Exception as e:
        logger.error(f"download error: {e}")
        return None

def cleanup():
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("🧹 تم التنظيف")
    except:
        pass

def main():
    logger.info("🚀 بدء تشغيل البوت...")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

    cleanup()

if __name__ == '__main__':
    main()
