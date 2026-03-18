#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import time
import re

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # تغيير إلى DEBUG لمشاهدة التفاصيل
)
logger = logging.getLogger(__name__)

# توكن البوت - ضع التوكن الخاص بك هنا
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# إنشاء مجلد التحميلات إذا لم يكن موجوداً
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
    print(f"✅ تم إنشاء مجلد التحميلات: {DOWNLOAD_FOLDER}")

# إعدادات yt-dlp المحسنة
YDL_OPTIONS = {
    'format': 'best[height<=720]',  # أفضل جودة حتى 720p
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'extract_flat': False,
    'force_generic_extractor': False,
    'socket_timeout': 30,
    'retries': 10,
    'fragment_retries': 10,
    'file_access_retries': 5,
    'extractor_retries': 5,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "👋 مرحباً! أنا بوت تحميل الفيديوهات\n\n"
        "📥 أرسل لي رابط فيديو من أي منصة وسأقوم بتحميله لك\n\n"
        "المنصات المدعومة:\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Twitter/X\n"
        "• Pinterest\n"
        "• وغيرها الكثير...\n\n"
        "✨ فقط أرسل الرابط وسأبدأ التحميل فوراً!\n\n"
        "⚡ أمثلة على روابط:\n"
        "• https://www.youtube.com/watch?v=...\n"
        "• https://www.tiktok.com/@user/video/...\n"
        "• https://www.instagram.com/p/..."
    )
    await update.message.reply_text(welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل (الروابط)"""
    url = update.message.text.strip()
    
    # التحقق من أن النص يحتوي على رابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    # إرسال رسالة بأن التحميل بدأ
    progress_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو... الرجاء الانتظار (قد يستغرق دقيقة)")
    
    try:
        logger.info(f"محاولة تحميل: {url}")
        
        # تحميل الفيديو
        video_path = await download_video(url, update, progress_msg)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # حجم الملف بالميجابايت
            
            if file_size > 50:  # تليجرام يسمح حتى 50 ميجابايت
                await progress_msg.edit_text(f"❌ الفيديو كبير جداً ({file_size:.1f} MB). الحد الأقصى 50 MB")
                os.remove(video_path)
                return
            
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو مع شريط التقدم
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"✅ تم التحميل بنجاح!\n📊 الحجم: {file_size:.1f} MB",
                    supports_streaming=True,
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=60,
                    pool_timeout=60
                )
            
            # حذف الفيديو بعد الإرسال لتوفير المساحة
            os.remove(video_path)
            logger.info(f"✅ تم حذف الملف: {video_path}")
            
        else:
            await progress_msg.edit_text("❌ عذراً، لم أتمكن من تحميل الفيديو. تأكد من:\n• الرابط صحيح\n• الفيديو متاح\n• جرب رابط آخر")
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        await progress_msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def download_video(url, update=None, progress_msg=None):
    """تحميل الفيديو باستخدام yt-dlp"""
    try:
        # تشغيل yt-dlp في thread منفصل
        loop = asyncio.get_event_loop()
        
        def download():
            try:
                # إنشاء اسم ملف مؤقت
                temp_filename = None
                
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    logger.info(f"بدء تحميل: {url}")
                    
                    # استخراج معلومات الفيديو أولاً (بدون تحميل)
                    try:
                        info = ydl.extract_info(url, download=False)
                        
                        if info is None:
                            logger.error("لا يمكن استخراج معلومات الفيديو")
                            return None
                        
                        # التحقق من حجم الفيديو
                        if 'filesize' in info and info['filesize']:
                            size_mb = info['filesize'] / (1024 * 1024)
                            logger.info(f"حجم الفيديو المقدر: {size_mb:.1f} MB")
                            if size_mb > 50:
                                logger.warning(f"الفيديو كبير جداً: {size_mb:.1f} MB")
                                return None
                        
                        # تحميل الفيديو الآن
                        logger.info(f"جاري تحميل الفيديو...")
                        info = ydl.extract_info(url, download=True)
                        
                    except Exception as e:
                        logger.error(f"خطأ في استخراج المعلومات: {str(e)}")
                        return None
                    
                    # البحث عن الملف المحمل
                    if info is None:
                        return None
                    
                    # محاولة الحصول على اسم الملف
                    if 'requested_downloads' in info and info['requested_downloads']:
                        temp_filename = info['requested_downloads'][0].get('filepath')
                    
                    if not temp_filename:
                        # محاولة بناء اسم الملف
                        filename = ydl.prepare_filename(info)
                        if os.path.exists(filename):
                            temp_filename = filename
                    
                    # إذا لم نجد الملف، ابحث في مجلد التحميلات
                    if not temp_filename or not os.path.exists(temp_filename):
                        # ابحث عن أحدث ملف تم إنشاؤه
                        files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER)]
                        if files:
                            # ابحث عن ملف تم إنشاؤه في آخر 30 ثانية
                            current_time = time.time()
                            recent_files = [f for f in files if os.path.getctime(f) > current_time - 30]
                            if recent_files:
                                temp_filename = max(recent_files, key=os.path.getctime)
                                logger.info(f"تم العثور على ملف حديث: {temp_filename}")
                    
                    if temp_filename and os.path.exists(temp_filename):
                        logger.info(f"✅ تم التحميل بنجاح: {temp_filename}")
                        return temp_filename
                    else:
                        logger.error("لم يتم العثور على الملف المحمل")
                        return None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل: {str(e)}")
                return None
        
        # تنفيذ التحميل في thread منفصل
        result = await loop.run_in_executor(None, download)
        return result
            
    except Exception as e:
        logger.error(f"خطأ عام في التحميل: {str(e)}")
        return None

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text("❌ حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى")
    except:
        pass

def check_ffmpeg():
    """التحقق من وجود ffmpeg"""
    import subprocess
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg مثبت")
        return True
    except:
        print("⚠️ FFmpeg غير مثبت. قد لا تعمل بعض المواقع")
        return False

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    try:
        # التحقق من ffmpeg
        check_ffmpeg()
        
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", start))
        
        # إضافة معالج للرسائل النصية (الروابط)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # معلومات التشغيل
        print("="*50)
        print("🤖 البوت يعمل الآن...")
        print("📝 توكن البوت:", TOKEN[:10] + "...")
        print("📁 مجلد التحميلات:", DOWNLOAD_FOLDER)
        print("🚀 جاهز لاستقبال الروابط")
        print("="*50)
        
        # بدء البوت
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {str(e)}")
        print(f"❌ خطأ: {str(e)}")

if __name__ == '__main__':
    main()
