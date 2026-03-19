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

# ===== إعداد التسجيل =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== التوكن =====
TOKEN = os.environ.get("8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# ===== مجلد مؤقت =====
DOWNLOAD_FOLDER = tempfile.mkdtemp()
logger.info(f"📁 Temp Folder: {DOWNLOAD_FOLDER}")

# ===== إعدادات التحميل =====
YDL_OPTIONS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'merge_output_format': 'mp4',
}

# ===== بدء =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\n\n"
        "📥 أرسل رابط فيديو وسأحمله فورًا\n\n"
        "🔥 يدعم:\n"
        "YouTube / TikTok / Instagram / Facebook"
    )

# ===== تحميل الفيديو =====
async def download_video(url):
    try:
        loop = asyncio.get_event_loop()

        def run():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

                # تأكد MP4
                if not file_path.endswith(".mp4"):
                    base = os.path.splitext(file_path)[0]
                    mp4_file = base + ".mp4"
                    if os.path.exists(mp4_file):
                        file_path = mp4_file

                return file_path if os.path.exists(file_path) else None

        return await loop.run_in_executor(None, run)

    except Exception as e:
        logger.error(f"❌ Download Error: {e}")
        return None

# ===== استقبال الرسائل =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith("http"):
        return await update.message.reply_text("❌ أرسل رابط صحيح")

    msg = await update.message.reply_text("⏳ جاري التحميل...")

    video_path = await download_video(url)

    if not video_path:
        return await msg.edit_text("❌ فشل التحميل (الرابط خاص أو غير مدعوم)")

    file_size = os.path.getsize(video_path) / (1024 * 1024)

    if file_size > 50:
        os.remove(video_path)
        return await msg.edit_text(f"❌ الحجم كبير ({file_size:.1f}MB)")

    try:
        await update.message.reply_video(
            video=open(video_path, 'rb'),
            caption=f"✅ تم التحميل\n📦 {file_size:.1f} MB",
            supports_streaming=True
        )
    except:
        await update.message.reply_document(
            document=open(video_path, 'rb'),
            caption="📁 تم الإرسال كملف"
        )

    os.remove(video_path)

# ===== تنظيف =====
def cleanup():
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except:
        pass

# ===== تشغيل =====
def main():
    logger.info("🚀 Bot Starting...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

    cleanup()

if __name__ == "__main__":
    main()
