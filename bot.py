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

# قائمة المنصات المدعومة
SUPPORTED_SITES = [
    "youtube.com", "youtu.be",
    "tiktok.com",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "pinterest.com",
    "reddit.com",
    "linkedin.com",
    "dailymotion.com",
    "vimeo.com",
    "twitch.tv",
    "tumblr.com",
    "vk.com",
    "telegram.org",
    "whatsapp.com"
]

# إعدادات yt-dlp المحسّنة
YDL_OPTIONS = {
    'format': 'best[height<=720][filesize<50M]',  # أفضل جودة مع حجم أقل من 50 ميجا
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

# خيارات بديلة إذا فشل التحميل الأول
FALLBACK_OPTIONS = [
    {'format': 'best[height<=480]'},  # جودة أقل
    {'format': 'best[height<=360]'},  # جودة منخفضة
    {'format': 'worst'},  # أسوأ جودة
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات المتطور!**\n\n"
        "📥 **أرسل لي رابط فيديو وسأقوم بتحميله لك فوراً**\n\n"
        "✅ **المنصات المدعومة:**\n"
        "• YouTube - TikTok - Instagram\n"
        "• Facebook - Twitter/X - Pinterest\n"
        "• Reddit - LinkedIn - Dailymotion\n"
        "• Vimeo - Twitch - Tumblr\n"
        "• VK - Telegram - WhatsApp\n"
        "• **وغيرها الكثير...**\n\n"
        "⚡ **مميزات البوت:**\n"
        "• تحميل بجودة عالية (حتى 720p)\n"
        "• دعم جميع المنصات تقريباً\n"
        "• سرعة تحميل عالية\n"
        "• معالجة ذكية للأخطاء\n\n"
        "✨ **فقط أرسل الرابط وسأبدأ التحميل فوراً!**"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مساعدة البوت"""
    help_msg = (
        "🆘 **كيفية استخدام البوت:**\n\n"
        "1️⃣ أرسل رابط الفيديو مباشرة\n"
        "2️⃣ انتظر حتى يتم التحميل\n"
        "3️⃣ استلم الفيديو في نفس الدردشة\n\n"
        "📝 **مثال:**\n"
        "`https://www.youtube.com/watch?v=...`\n\n"
        "⚠️ **ملاحظات مهمة:**\n"
        "• الحد الأقصى لحجم الفيديو: 50 ميجابايت\n"
        "• الفيديوهات الأطول قد تستغرق وقتاً أطول\n"
        "• تأكد من أن الفيديو عام وليس خاص\n\n"
        "📊 **لمعرفة حالة البوت:** /status"
    )
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة البوت"""
    status_msg = (
        "📊 **حالة البوت:**\n\n"
        "✅ **الحالة:** يعمل\n"
        f"📁 **المجلد المؤقت:** {DOWNLOAD_FOLDER}\n"
        f"🌐 **المنصات المدعومة:** {len(SUPPORTED_SITES)} منصة\n"
        f"⚡ **الإصدار:** 2.0 (مطور)\n\n"
        "🚀 **جاهز لاستقبال الروابط!**"
    )
    await update.message.reply_text(status_msg, parse_mode='Markdown')

def is_supported_url(url):
    """التحقق من أن الرابط مدعوم"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # إزالة www.
    if domain.startswith('www.'):
        domain = domain[4:]
    
    # التحقق من النطاق
    for site in SUPPORTED_SITES:
        if site in domain:
            return True
    
    # إذا كان الرابط قصير (bit.ly, etc) نسمح به
    if any(shortener in domain for shortener in ['bit.ly', 'tinyurl', 'shorturl']):
        return True
    
    return False

async def download_video(url, progress_msg=None):
    """تحميل الفيديو مع محاولات متعددة"""
    
    async def update_progress(text):
        if progress_msg:
            try:
                await progress_msg.edit_text(text)
            except:
                pass
    
    try:
        loop = asyncio.get_event_loop()
        
        def try_download_with_options(options):
            """محاولة التحميل بخيارات محددة"""
            try:
                # دمج الخيارات مع الإعدادات الأساسية
                download_options = YDL_OPTIONS.copy()
                download_options.update(options)
                
                with yt_dlp.YoutubeDL(download_options) as ydl:
                    logger.info(f"محاولة التحميل بالخيارات: {options}")
                    
                    # استخراج المعلومات أولاً
                    info = ydl.extract_info(url, download=False)
                    
                    if info is None:
                        return None, "لا يمكن استخراج معلومات الفيديو"
                    
                    # التحقق من حجم الفيديو
                    filesize = None
                    if 'filesize' in info and info['filesize']:
                        filesize = info['filesize'] / (1024 * 1024)
                    elif 'filesize_approx' in info and info['filesize_approx']:
                        filesize = info['filesize_approx'] / (1024 * 1024)
                    
                    if filesize and filesize > 50:
                        return None, f"حجم الفيديو كبير جداً ({filesize:.1f} MB)"
                    
                    # تحميل الفيديو
                    info = ydl.extract_info(url, download=True)
                    
                    # البحث عن الملف المحمل
                    filename = None
                    
                    # الطريقة 1: من requested_downloads
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                filename = download['filepath']
                                break
                    
                    # الطريقة 2: prepare_filename
                    if not filename or not os.path.exists(filename):
                        test_filename = ydl.prepare_filename(info)
                        if os.path.exists(test_filename):
                            filename = test_filename
                    
                    # الطريقة 3: البحث في المجلد
                    if not filename or not os.path.exists(filename):
                        import glob
                        import time
                        
                        # ابحث عن أحدث ملف
                        current_time = time.time()
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        
                        # ابحث عن ملف تم إنشاؤه في آخر 30 ثانية
                        recent_files = [f for f in files if os.path.getctime(f) > current_time - 30]
                        
                        if recent_files:
                            filename = max(recent_files, key=os.path.getctime)
                    
                    if filename and os.path.exists(filename):
                        return filename, None
                    else:
                        return None, "لم يتم العثور على الملف المحمل"
                    
            except Exception as e:
                return None, str(e)
        
        # المحاولة الأولى: الإعدادات الافتراضية
        await update_progress("⏳ جاري تحميل الفيديو... (محاولة 1/4)")
        filename, error = await loop.run_in_executor(None, try_download_with_options, {})
        
        if filename:
            return filename
        
        # المحاولة الثانية: جودة أقل
        await update_progress("⏳ جاري تحميل الفيديو... (محاولة 2/4)")
        filename, error = await loop.run_in_executor(None, try_download_with_options, FALLBACK_OPTIONS[0])
        
        if filename:
            return filename
        
        # المحاولة الثالثة: جودة منخفضة
        await update_progress("⏳ جاري تحميل الفيديو... (محاولة 3/4)")
        filename, error = await loop.run_in_executor(None, try_download_with_options, FALLBACK_OPTIONS[1])
        
        if filename:
            return filename
        
        # المحاولة الرابعة: أسوأ جودة
        await update_progress("⏳ جاري تحميل الفيديو... (محاولة 4/4)")
        filename, error = await loop.run_in_executor(None, try_download_with_options, FALLBACK_OPTIONS[2])
        
        if filename:
            return filename
        
        logger.error(f"جميع المحاولات فشلت: {error}")
        return None
        
    except Exception as e:
        logger.error(f"خطأ عام في التحميل: {str(e)}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل"""
    url = update.message.text.strip()
    
    # التحقق من الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ **رابط غير صحيح**\n\n"
            "الرجاء إرسال رابط يبدأ بـ http:// أو https://",
            parse_mode='Markdown'
        )
        return
    
    # التحقق من أن الرابط مدعوم
    if not is_supported_url(url):
        sites_list = "\n".join([f"• {site}" for site in SUPPORTED_SITES[:10]])
        await update.message.reply_text(
            f"⚠️ **الرابط غير مدعوم أو غير معروف**\n\n"
            f"المنصات المدعومة:\n{sites_list}\n\n"
            f"• وغيرها الكثير...\n\n"
            f"تأكد من الرابط وحاول مرة أخرى",
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
        video_path = await download_video(url, progress_msg)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            
            # التحقق من حجم الملف
            if file_size > 50:
                await progress_msg.edit_text(
                    f"❌ **الفيديو كبير جداً**\n\n"
                    f"الحجم: {file_size:.1f} MB\n"
                    f"الحد الأقصى: 50 MB\n\n"
                    f"جرب رابط آخر بجودة أقل",
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
                    caption=(
                        f"✅ **تم التحميل بنجاح!**\n\n"
                        f"📊 **الحجم:** {file_size:.1f} MB\n"
                        f"📹 **جودة:** 720p (محسّنة)\n"
                        f"🤖 **بوت تحميل الفيديوهات**"
                    ),
                    supports_streaming=True,
                    parse_mode='Markdown'
                )
            
            # حذف الفيديو بعد الإرسال
            os.remove(video_path)
            logger.info(f"✅ تم حذف الملف: {video_path}")
            
        else:
            await progress_msg.edit_text(
                "❌ **فشل التحميل**\n\n"
                "الأسباب المحتملة:\n"
                "• الرابط غير صحيح\n"
                "• الفيديو خاص أو محمي\n"
                "• الفيديو طويل جداً\n"
                "• مشكلة في المنصة\n\n"
                "**حلول:**\n"
                "• تأكد من الرابط\n"
                "• جرب رابط آخر\n"
                "• أعد المحاولة لاحقاً",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ غير متوقع**\n\n"
            f"الخطأ: {str(e)[:100]}\n\n"
            f"الرجاء المحاولة مرة أخرى",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ **حدث خطأ في البوت**\n\n"
                "تم تسجيل الخطأ وسيتم إصلاحه قريباً\n"
                "الرجاء المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    except:
        pass

def cleanup():
    """تنظيف الملفات المؤقتة عند الإغلاق"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم تنظيف الملفات المؤقتة")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت المتطور...")
    
    try:
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # تشغيل البوت
        logger.info("✅ البوت المتطور جاهز للعمل!")
        print("\n" + "="*50)
        print("🤖 البوت المتطور يعمل الآن!")
        print("📝 توكن:", TOKEN[:15] + "...")
        print("📁 مجلد التحميلات:", DOWNLOAD_FOLDER)
        print("✅ جاهز لاستقبال الروابط")
        print("="*50 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {str(e)}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
