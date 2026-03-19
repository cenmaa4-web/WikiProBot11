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

# توكن البوت - ضع التوكن الخاص بك هنا
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# مجلد مؤقت للتحميلات
DOWNLOAD_FOLDER = tempfile.mkdtemp()
logger.info(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")

# إعدادات yt-dlp المبسطة
YDL_OPTIONS = {
    'format': 'best[height<=480]',  # جودة متوسطة لضمان الحجم
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "👋 مرحباً! أنا بوت تحميل الفيديوهات\n\n"
        "📥 أرسل لي رابط فيديو وسأقوم بتحميله لك فوراً\n\n"
        "✅ المنصات المدعومة:\n"
        "• YouTube - TikTok - Instagram\n"
        "• Facebook - Twitter - وغيرها\n\n"
        "✨ فقط أرسل الرابط وسأبدأ التحميل!"
    )
    await update.message.reply_text(welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل"""
    url = update.message.text.strip()
    
    # التحقق من الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    # إرسال رسالة التحميل
    progress_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو... الرجاء الانتظار")
    
    try:
        logger.info(f"محاولة تحميل: {url}")
        
        # تحميل الفيديو
        video_path = await download_video(url)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # حجم الملف بالميجابايت
            
            # التحقق من حجم الملف (تليجرام يسمح حتى 50 ميجابايت)
            if file_size > 50:
                await progress_msg.edit_text(f"❌ الفيديو كبير جداً ({file_size:.1f} MB). الحد الأقصى 50 MB")
                os.remove(video_path)
                return
            
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"✅ تم التحميل بنجاح!\n📊 الحجم: {file_size:.1f} MB",
                    supports_streaming=True
                )
            
            # حذف الفيديو بعد الإرسال
            os.remove(video_path)
            logger.info(f"✅ تم حذف الملف: {video_path}")
            
        else:
            await progress_msg.edit_text(
                "❌ عذراً، لم أتمكن من تحميل الفيديو\n\n"
                "تأكد من:\n"
                "• الرابط صحيح\n"
                "• الفيديو متاح للعامة\n"
                "• جرب رابط آخر"
            )
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        await progress_msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def download_video(url):
    """تحميل الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    # تحميل الفيديو
                    logger.info("بدء التحميل...")
                    info = ydl.extract_info(url, download=True)
                    
                    # الحصول على مسار الملف
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                return download['filepath']
                    
                    # طريقة بديلة
                    filename = ydl.prepare_filename(info)
                    if os.path.exists(filename):
                        return filename
                    
                    # بحث في مجلد التحميلات
                    import glob
                    files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                    if files:
                        # خذ أحدث ملف
                        latest_file = max(files, key=os.path.getctime)
                        return latest_file
                    
                    return None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل المتزامن: {str(e)}")
                return None
        
        # تنفيذ التحميل في thread منفصل
        result = await loop.run_in_executor(None, download_sync)
        return result
        
    except Exception as e:
        logger.error(f"خطأ عام في التحميل: {str(e)}")
        return None

def cleanup():
    """تنظيف الملفات المؤقتة عند الإغلاق"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم تنظيف الملفات المؤقتة")
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
        
        # تشغيل البوت باستخدام polling
        logger.info("✅ البوت جاهز للعمل! باستخدام Polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {str(e)}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
