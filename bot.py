#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import tempfile
import subprocess
import sys

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت - ضع التوكن الخاص بك هنا
TOKEN = os.environ.get("TOKEN", "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# استخدام مجلد مؤقت في Railway
DOWNLOAD_FOLDER = '/tmp/downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# إعدادات yt-dlp المبسطة
YDL_OPTIONS = {
    'format': 'best[height<=480]',  # جودة أقل لضمان الحجم
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "👋 مرحباً! أنا بوت تحميل الفيديوهات\n\n"
        "📥 أرسل لي رابط فيديو وسأقوم بتحميله لك فوراً\n\n"
        "✨ فقط أرسل الرابط وسأبدأ التحميل!"
    )
    await update.message.reply_text(welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح")
        return
    
    # رسالة التحميل
    progress_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو...")
    
    try:
        # تحميل الفيديو
        video_path = await download_video(url)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            
            if file_size > 50:
                await progress_msg.edit_text(f"❌ الفيديو كبير جداً ({file_size:.1f} MB)")
                os.remove(video_path)
                return
            
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"✅ تم التحميل بنجاح!\n📊 {file_size:.1f} MB",
                    supports_streaming=True
                )
            
            # حذف الملف
            os.remove(video_path)
            
        else:
            await progress_msg.edit_text("❌ لم أتمكن من تحميل الفيديو")
            
    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        await progress_msg.edit_text("❌ حدث خطأ أثناء التحميل")

async def download_video(url):
    """تحميل الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    # تحميل الفيديو
                    info = ydl.extract_info(url, download=True)
                    
                    # البحث عن الملف
                    if 'requested_downloads' in info:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                return download['filepath']
                    
                    # طريقة بديلة
                    filename = ydl.prepare_filename(info)
                    if os.path.exists(filename):
                        return filename
                    
                    # بحث في المجلد
                    import glob
                    files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                    if files:
                        return max(files, key=os.path.getctime)
                    
                except Exception as e:
                    logger.error(f"خطأ في التحميل: {str(e)}")
                    return None
        
        result = await loop.run_in_executor(None, download_sync)
        return result
        
    except Exception as e:
        logger.error(f"خطأ عام: {str(e)}")
        return None

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت...")
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل البوت
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"✅ البوت جاهز للعمل على المنفذ {port}!")
    
    # استخدام webhook بدلاً من polling في Railway
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=f"https://{os.environ.get('RAILWAY_STATIC_URL', '')}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
