#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت - ضع التوكن الخاص بك هنا
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# إعدادات yt-dlp
YDL_OPTIONS = {
    'format': 'best[height<=720]',  # أفضل جودة حتى 720p
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
}

# إنشاء مجلد التحميلات إذا لم يكن موجوداً
if not os.path.exists('downloads'):
    os.makedirs('downloads')

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
        "✨ فقط أرسل الرابط وسأبدأ التحميل فوراً!"
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
    progress_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو... الرجاء الانتظار")
    
    try:
        # تحميل الفيديو
        video_path = await download_video(url)
        
        if video_path and os.path.exists(video_path):
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ تم التحميل بنجاح!"
                )
            
            # حذف الفيديو بعد الإرسال لتوفير المساحة
            os.remove(video_path)
            logger.info(f"تم حذف الملف: {video_path}")
            
        else:
            await progress_msg.edit_text("❌ عذراً، لم أتمكن من تحميل الفيديو. تأكد من الرابط وحاول مرة أخرى")
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        await progress_msg.edit_text("❌ حدث خطأ أثناء التحميل. الرجاء التأكد من الرابط والمحاولة مرة أخرى")

async def download_video(url):
    """تحميل الفيديو باستخدام yt-dlp"""
    try:
        # تشغيل yt-dlp في thread منفصل لمنع حظر الحدث
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    # استخراج معلومات الفيديو وتحميله
                    info = ydl.extract_info(url, download=True)
                    
                    # الحصول على مسار الملف المحمل
                    if 'entries' in info:  # إذا كان قائمة تشغيل
                        video = info['entries'][0]
                    else:
                        video = info
                    
                    filename = ydl.prepare_filename(video)
                    
                    # التأكد من وجود الملف
                    if os.path.exists(filename):
                        return filename
                    
                    # البحث عن الملف بامتدادات مختلفة
                    base_filename = filename.rsplit('.', 1)[0]
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test_filename = base_filename + ext
                        if os.path.exists(test_filename):
                            return test_filename
                    
                    # بحث عام عن أي ملف حديث في مجلد التحميلات
                    downloads_dir = 'downloads'
                    files = [f for f in os.listdir(downloads_dir) if os.path.isfile(os.path.join(downloads_dir, f))]
                    if files:
                        # أخذ أحدث ملف
                        latest_file = max([os.path.join(downloads_dir, f) for f in files], key=os.path.getctime)
                        return latest_file
                    
                    return None
                    
                except Exception as e:
                    logger.error(f"خطأ في yt-dlp: {str(e)}")
                    return None
        
        # تنفيذ التحميل في thread منفصل
        result = await loop.run_in_executor(None, download)
        return result
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        return None

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    try:
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", start))
        
        # إضافة معالج للرسائل النصية (الروابط)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # تشغيل البوت
        print("🤖 البوت يعمل الآن...")
        print("📝 توكن البوت:", TOKEN[:10] + "...")
        print("🚀 انتظر حتى يبدأ البوت باستقبال الرسائل...")
        
        # بدء البوت
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {str(e)}")
        print(f"❌ خطأ: {str(e)}")

if __name__ == '__main__':
    main()
