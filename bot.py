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
import re
from urllib.parse import urlparse

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت
TOKEN = os.environ.get("TOKEN", "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# مجلد مؤقت للتحميلات
DOWNLOAD_FOLDER = tempfile.mkdtemp()
logger.info(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")

# إعدادات yt-dlp المحسنة
YDL_OPTIONS = {
    'format': 'best[height<=720]',  # أفضل جودة حتى 720p
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'extract_flat': False,
    'socket_timeout': 30,
    'retries': 5,
    'fragment_retries': 5,
    'file_access_retries': 3,
    'extractor_retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

# قائمة المنصات الرئيسية (للتأكد من الدعم)
MAIN_PLATFORMS = [
    'youtube', 'tiktok', 'instagram', 'facebook', 
    'twitter', 'pinterest', 'reddit', 'linkedin',
    'dailymotion', 'vimeo', 'twitch', 'tumblr', 'vk'
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "👋 **مرحباً! أنا بوت تحميل الفيديوهات**\n\n"
        "📥 **أرسل لي رابط فيديو وسأقوم بتحميله لك**\n\n"
        "✅ **المنصات المدعومة:**\n"
        "• YouTube - TikTok - Instagram\n"
        "• Facebook - Twitter - Pinterest\n"
        "• Reddit - LinkedIn - Dailymotion\n"
        "• Vimeo - Twitch - Tumblr - VK\n"
        "• **وغيرها الكثير...**\n\n"
        "⚡ **فقط أرسل الرابط وسأبدأ التحميل فوراً!**"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def download_video(url):
    """تحميل الفيديو مع محاولة واحدة ناجحة"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    # تحميل الفيديو
                    info = ydl.extract_info(url, download=True)
                    
                    # البحث عن الملف المحمل
                    filename = None
                    
                    # طريقة 1: من requested_downloads
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                filename = download['filepath']
                                break
                    
                    # طريقة 2: prepare_filename
                    if not filename or not os.path.exists(filename):
                        test_filename = ydl.prepare_filename(info)
                        if os.path.exists(test_filename):
                            filename = test_filename
                    
                    # طريقة 3: البحث في المجلد
                    if not filename or not os.path.exists(filename):
                        import glob
                        import time
                        
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        current_time = time.time()
                        recent_files = [f for f in files if os.path.getctime(f) > current_time - 30]
                        
                        if recent_files:
                            filename = max(recent_files, key=os.path.getctime)
                    
                    if filename and os.path.exists(filename):
                        return filename
                    return None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل المتزامن: {e}")
                return None
        
        # تنفيذ التحميل
        result = await loop.run_in_executor(None, download_sync)
        return result
        
    except Exception as e:
        logger.error(f"خطأ عام في التحميل: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل"""
    url = update.message.text.strip()
    
    # التحقق من الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ **رابط غير صحيح**\n"
            "الرجاء إرسال رابط صحيح",
            parse_mode='Markdown'
        )
        return
    
    # إرسال رسالة التحميل
    progress_msg = await update.message.reply_text(
        "⏳ **جاري تحميل الفيديو...**\n"
        "الرجاء الانتظار قليلاً",
        parse_mode='Markdown'
    )
    
    try:
        logger.info(f"محاولة تحميل: {url}")
        
        # تحميل الفيديو
        video_path = await download_video(url)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            
            # التحقق من حجم الملف
            if file_size > 50:
                await progress_msg.edit_text(
                    f"❌ **الفيديو كبير جداً**\n"
                    f"الحجم: {file_size:.1f} MB\n"
                    f"الحد الأقصى: 50 MB",
                    parse_mode='Markdown'
                )
                os.remove(video_path)
                return
            
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"✅ **تم التحميل بنجاح!**\n📊 الحجم: {file_size:.1f} MB",
                    supports_streaming=True,
                    parse_mode='Markdown'
                )
            
            # حذف الفيديو بعد الإرسال
            os.remove(video_path)
            logger.info(f"✅ تم حذف الملف: {video_path}")
            
        else:
            await progress_msg.edit_text(
                "❌ **فشل التحميل**\n\n"
                "تأكد من:\n"
                "• الرابط صحيح\n"
                "• الفيديو متاح\n"
                "• جرب رابط آخر",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

def cleanup():
    """تنظيف الملفات المؤقتة"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم التنظيف")
    except:
        pass

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت...")
    
    try:
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # تشغيل البوت
        print("\n" + "="*50)
        print("🤖 البوت يعمل الآن!")
        print(f"📝 التوكن: {TOKEN[:15]}...")
        print("="*50 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
