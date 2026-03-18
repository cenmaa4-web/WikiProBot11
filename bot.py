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
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# استخدام مجلد مؤقت في Railway
DOWNLOAD_FOLDER = '/tmp/downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
    logger.info(f"✅ تم إنشاء مجلد التحميلات: {DOWNLOAD_FOLDER}")

# التحقق من وجود ffmpeg
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        logger.info("✅ FFmpeg مثبت")
        return True
    except Exception as e:
        logger.error(f"❌ FFmpeg غير مثبت: {e}")
        return False

# إعدادات yt-dlp المبسطة
YDL_OPTIONS = {
    'format': 'best[filesize<50M][height<=720]',  # فيديو أقل من 50 ميجا
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'extract_flat': False,
    'force_generic_extractor': False,
    'socket_timeout': 30,
    'retries': 5,
    'fragment_retries': 5,
    'file_access_retries': 3,
    'extractor_retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "👋 مرحباً! أنا بوت تحميل الفيديوهات\n\n"
        "📥 أرسل لي رابط فيديو وسأقوم بتحميله لك فوراً\n\n"
        "✅ المنصات المدعومة:\n"
        "• YouTube - تيك توك - انستغرام\n"
        "• فيسبوك - تويتر - Pinterest\n\n"
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
        logger.info(f"محاولة تحميل: {url}")
        
        # تحميل الفيديو
        video_info = await download_video(url)
        
        if video_info and video_info['path'] and os.path.exists(video_info['path']):
            file_size = os.path.getsize(video_info['path']) / (1024 * 1024)
            
            if file_size > 50:
                await progress_msg.edit_text(f"❌ الفيديو كبير جداً ({file_size:.1f} MB)")
                os.remove(video_info['path'])
                return
            
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(video_info['path'], 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"✅ تم التحميل بنجاح!\n📹 {video_info['title'][:50]}...\n📊 {file_size:.1f} MB",
                    supports_streaming=True
                )
            
            # حذف الملف
            os.remove(video_info['path'])
            logger.info(f"✅ تم حذف الملف: {video_info['path']}")
            
        else:
            await progress_msg.edit_text(
                "❌ لم أتمكن من تحميل الفيديو\n\n"
                "🔍 تأكد من:\n"
                "• الرابط صحيح\n"
                "• الفيديو عام وليس خاص\n"
                "• جرب رابط آخر"
            )
            
    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        await progress_msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def download_video(url):
    """تحميل الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    # محاولة التحميل
                    logger.info("بدء التحميل...")
                    
                    # استخراج المعلومات والتحميل
                    info = ydl.extract_info(url, download=True)
                    
                    if info is None:
                        logger.error("لا يمكن استخراج معلومات الفيديو")
                        return None
                    
                    # البحث عن الملف المحمل
                    filename = None
                    
                    # الطريقة الأولى: من requested_downloads
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                filename = download['filepath']
                                break
                    
                    # الطريقة الثانية: prepare_filename
                    if not filename or not os.path.exists(filename):
                        test_filename = ydl.prepare_filename(info)
                        if os.path.exists(test_filename):
                            filename = test_filename
                    
                    # الطريقة الثالثة: البحث في المجلد
                    if not filename or not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            # خذ أحدث ملف
                            filename = max(files, key=os.path.getctime)
                    
                    if filename and os.path.exists(filename):
                        logger.info(f"✅ تم التحميل: {filename}")
                        return {
                            'path': filename,
                            'title': info.get('title', 'فيديو'),
                            'size': os.path.getsize(filename)
                        }
                    else:
                        logger.error("لم يتم العثور على الملف")
                        return None
                        
            except Exception as e:
                logger.error(f"خطأ في التحميل: {str(e)}")
                return None
        
        # تنفيذ التحميل
        result = await loop.run_in_executor(None, download_sync)
        return result
        
    except Exception as e:
        logger.error(f"خطأ عام: {str(e)}")
        return None

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت...")
    
    # التحقق من ffmpeg
    check_ffmpeg()
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل البوت
    logger.info("✅ البوت جاهز للعمل!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
