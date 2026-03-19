#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp
import tempfile
import shutil
import re
import time
import json
from urllib.parse import urlparse
from datetime import datetime, timedelta

# ============= الكود الأصلي بالكامل =============

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

# ============= إضافات جديدة مع الحفاظ على القائمة الأصلية =============

# قائمة المنصات المدعومة الأصلية (كما هي)
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

# إضافة منصات جديدة (إضافات)
EXTRA_SITES = [
    "snapchat.com",
    "discord.com",
    "spotify.com",
    "soundcloud.com",
    "rumble.com",
    "odysee.com",
    "bitchute.com",
    "lbry.tv",
    "kick.com",
    "threads.net",
    "bsky.app",
    "mastodon.social",
    "t.co",
    "youtube.com/shorts",
    "instagram.com/reel",
    "facebook.com/watch",
    "twitter.com/i/status",
    "tiktok.com/@",
]

# دمج القوائم (كل المنصات)
ALL_SUPPORTED_SITES = SUPPORTED_SITES + EXTRA_SITES

# إعدادات yt-dlp الأصلية (مع تحسينات طفيفة)
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

# خيارات بديلة إذا فشل التحميل الأول (جودة أقل)
FALLBACK_OPTIONS = [
    {'format': 'best[height<=480]'},  # جودة أقل
    {'format': 'best[height<=360]'},  # جودة منخفضة
    {'format': 'worst'},  # أسوأ جودة
]

# إضافة خيارات جديدة للتحميل
QUALITY_OPTIONS = {
    'high': {'format': 'best[height<=720]', 'name': '🎥 عالية (720p)'},
    'medium': {'format': 'best[height<=480]', 'name': '📺 متوسطة (480p)'},
    'low': {'format': 'worst', 'name': '📱 منخفضة'},
    'audio': {'format': 'bestaudio/best', 'name': '🎵 صوت فقط', 'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]}
}

# إضافة تخزين مؤقت للبيانات
user_sessions = {}
download_stats = {
    'total_downloads': 0,
    'total_users': 0,
    'start_time': datetime.now()
}

# ============= الدوال الأصلية (بدون تغيير) =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب الأصلية + إضافات"""
    welcome_msg = (
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات المتطور!**\n\n"
        "📥 **أرسل لي رابط فيديو وسأقوم بتحميله لك فوراً**\n\n"
        "✅ **المنصات المدعومة:**\n"
        "• YouTube - TikTok - Instagram\n"
        "• Facebook - Twitter/X - Pinterest\n"
        "• Reddit - LinkedIn - Dailymotion\n"
        "• Vimeo - Twitch - Tumblr\n"
        "• VK - Telegram - WhatsApp\n"
        "• Snapchat - Discord - Spotify\n"
        "• SoundCloud - Rumble - Odysee\n"
        "• Kick - Threads - Bluesky\n"
        "• **وغيرها الكثير...**\n\n"
        "⚡ **مميزات البوت:**\n"
        "• تحميل بجودة عالية (حتى 720p)\n"
        "• دعم جميع المنصات تقريباً\n"
        "• سرعة تحميل عالية\n"
        "• معالجة ذكية للأخطاء\n"
        "• اختيار جودة التحميل\n"
        "• تحميل صوت فقط MP3\n\n"
        "✨ **فقط أرسل الرابط وسأبدأ التحميل فوراً!**"
    )
    
    # إضافة أزرار تفاعلية (إضافة جديدة)
    keyboard = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
            InlineKeyboardButton("❓ المساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton("🌐 جميع المنصات", callback_data="all_platforms"),
            InlineKeyboardButton("⚡ السرعة", callback_data="speed")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    # تحديث إحصائيات المستخدمين
    download_stats['total_users'] += 1

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مساعدة البوت (مطورة)"""
    help_msg = (
        "🆘 **كيفية استخدام البوت:**\n\n"
        "1️⃣ أرسل رابط الفيديو مباشرة\n"
        "2️⃣ اختر الجودة المناسبة\n"
        "3️⃣ انتظر حتى يتم التحميل\n"
        "4️⃣ استلم الفيديو في نفس الدردشة\n\n"
        "📝 **مثال:**\n"
        "`https://www.youtube.com/watch?v=...`\n"
        "`https://www.tiktok.com/@user/video/...`\n"
        "`https://www.instagram.com/p/...`\n\n"
        "⚠️ **ملاحظات مهمة:**\n"
        "• الحد الأقصى لحجم الفيديو: 50 ميجابايت\n"
        "• الفيديوهات الأطول قد تستغرق وقتاً أطول\n"
        "• تأكد من أن الفيديو عام وليس خاص\n"
        "• يمكنك تحميل صوت فقط بصيغة MP3\n\n"
        "📊 **لمعرفة حالة البوت:** /status\n"
        "📈 **لمعرفة الإحصائيات:** /stats"
    )
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة البوت (مطورة)"""
    uptime = datetime.now() - download_stats['start_time']
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    status_msg = (
        "📊 **حالة البوت:**\n\n"
        f"✅ **الحالة:** يعمل\n"
        f"📁 **المجلد المؤقت:** {DOWNLOAD_FOLDER}\n"
        f"🌐 **المنصات المدعومة:** {len(ALL_SUPPORTED_SITES)} منصة\n"
        f"📥 **إجمالي التحميلات:** {download_stats['total_downloads']}\n"
        f"👥 **إجمالي المستخدمين:** {download_stats['total_users']}\n"
        f"⏱️ **وقت التشغيل:** {int(hours)} ساعة {int(minutes)} دقيقة\n"
        f"⚡ **الإصدار:** 3.0 (مطور جداً)\n\n"
        "🚀 **جاهز لاستقبال الروابط!**"
    )
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات إضافية"""
    await status_command(update, context)

def is_supported_url(url):
    """التحقق من أن الرابط مدعوم (مطور)"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # إزالة www.
    if domain.startswith('www.'):
        domain = domain[4:]
    
    # التحقق من النطاق (مع القائمة الموسعة)
    for site in ALL_SUPPORTED_SITES:
        if site in domain:
            return True
    
    # إذا كان الرابط قصير (bit.ly, etc) نسمح به
    shorteners = ['bit.ly', 'tinyurl', 'shorturl', 'ow.ly', 'is.gd', 'buff.ly']
    if any(shortener in domain for shortener in shorteners):
        return True
    
    return False

async def download_video(url, progress_msg=None, quality='high'):
    """تحميل الفيديو مع محاولات متعددة (مطور مع خيارات جودة)"""
    
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
        
        # اختيار مسار التحميل بناءً على الجودة
        if quality in QUALITY_OPTIONS:
            await update_progress(f"⏳ جاري تحميل {QUALITY_OPTIONS[quality]['name']}... (محاولة 1/4)")
            filename, error = await loop.run_in_executor(None, try_download_with_options, QUALITY_OPTIONS[quality])
            if filename:
                return filename
        
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

# ============= دوال جديدة مضافة =============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار التفاعلية"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "stats":
        uptime = datetime.now() - download_stats['start_time']
        hours = uptime.total_seconds() // 3600
        minutes = (uptime.total_seconds() % 3600) // 60
        
        stats_text = (
            "📈 **إحصائيات البوت:**\n\n"
            f"📥 **التحميلات:** {download_stats['total_downloads']}\n"
            f"👥 **المستخدمين:** {download_stats['total_users']}\n"
            f"⏱️ **وقت التشغيل:** {int(hours)} ساعة {int(minutes)} دقيقة\n"
            f"🌐 **المنصات:** {len(ALL_SUPPORTED_SITES)}\n"
        )
        await query.edit_message_text(stats_text, parse_mode='Markdown')
        
    elif query.data == "help":
        await help_command(update, context)
        
    elif query.data == "all_platforms":
        platforms_text = "**🌐 جميع المنصات المدعومة:**\n\n"
        
        # تقسيم المنصات إلى مجموعات
        platforms_text += "**📱 منصات فيديو:**\n"
        platforms_text += "YouTube, TikTok, Instagram, Facebook, Twitter, Pinterest, Reddit\n"
        platforms_text += "LinkedIn, Dailymotion, Vimeo, Twitch, Tumblr, VK, Rumble\n\n"
        
        platforms_text += "**🎵 منصات صوت:**\n"
        platforms_text += "Spotify, SoundCloud, Telegram Voice\n\n"
        
        platforms_text += "**💬 منصات تواصل:**\n"
        platforms_text += "Snapchat, Discord, Threads, Bluesky, Mastodon, Kick\n\n"
        
        platforms_text += "**➕ منصات أخرى:**\n"
        platforms_text += "Odysee, Bitchute, LBRY, WhatsApp, Telegram\n\n"
        
        platforms_text += f"✅ **الإجمالي:** {len(ALL_SUPPORTED_SITES)} منصة"
        
        await query.edit_message_text(platforms_text, parse_mode='Markdown')
        
    elif query.data == "speed":
        speed_text = (
            "⚡ **معلومات السرعة:**\n\n"
            "• سرعة التحميل تعتمد على:\n"
            "  - سرعة الإنترنت لديك\n"
            "  - حجم الفيديو\n"
            "  - خوادم المنصة\n\n"
            "🚀 **نصائح للسرعة القصوى:**\n"
            "• استخدم فيديوهات قصيرة\n"
            "• اختر جودة متوسطة (480p)\n"
            "• جرب في أوقات مختلفة"
        )
        await query.edit_message_text(speed_text, parse_mode='Markdown')

async def quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض خيارات الجودة بعد إرسال الرابط"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ **رابط غير صحيح**\n\n"
            "الرجاء إرسال رابط صحيح",
            parse_mode='Markdown'
        )
        return
    
    if not is_supported_url(url):
        await update.message.reply_text(
            "⚠️ **الرابط غير مدعوم**\n"
            "تأكد من الرابط وحاول مرة أخرى",
            parse_mode='Markdown'
        )
        return
    
    # حفظ الرابط في الجلسة
    user_id = update.effective_user.id
    user_sessions[user_id] = {'url': url}
    
    # عرض أزرار اختيار الجودة
    keyboard = []
    row = []
    
    for i, (key, quality) in enumerate(QUALITY_OPTIONS.items()):
        if i % 2 == 0 and row:
            keyboard.append(row)
            row = []
        row.append(InlineKeyboardButton(quality['name'], callback_data=f"quality_{key}"))
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎯 **اختر جودة التحميل:**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الجودة"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data.startswith("quality_"):
        quality = query.data.replace("quality_", "")
        
        if user_id in user_sessions:
            url = user_sessions[user_id]['url']
            
            await query.edit_message_text(
                f"⏳ **جاري تحميل {QUALITY_OPTIONS[quality]['name']}...**\n"
                "الرجاء الانتظار",
                parse_mode='Markdown'
            )
            
            try:
                # تحميل الفيديو بالجودة المختارة
                video_path = await download_video(url, query.message, quality)
                
                if video_path and os.path.exists(video_path):
                    file_size = os.path.getsize(video_path) / (1024 * 1024)
                    
                    if file_size > 50:
                        await query.edit_message_text(
                            f"❌ **الفيديو كبير جداً**\nالحجم: {file_size:.1f} MB",
                            parse_mode='Markdown'
                        )
                        os.remove(video_path)
                        return
                    
                    # حذف رسالة التقدم
                    await query.message.delete()
                    
                    # إرسال الفيديو
                    with open(video_path, 'rb') as video_file:
                        await update.effective_user.send_video(
                            video=video_file,
                            caption=(
                                f"✅ **تم التحميل بنجاح!**\n"
                                f"📊 الحجم: {file_size:.1f} MB\n"
                                f"🎯 الجودة: {QUALITY_OPTIONS[quality]['name']}"
                            ),
                            supports_streaming=True,
                            parse_mode='Markdown'
                        )
                    
                    # تحديث الإحصائيات
                    download_stats['total_downloads'] += 1
                    
                    # حذف الملف
                    os.remove(video_path)
                    
                else:
                    await query.edit_message_text(
                        "❌ **فشل التحميل**\nحاول بجودة أخرى",
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                logger.error(f"خطأ: {e}")
                await query.edit_message_text(
                    f"❌ **حدث خطأ**\n{str(e)[:100]}",
                    parse_mode='Markdown'
                )
    
    elif query.data == "cancel":
        await query.edit_message_text(
            "✅ **تم الإلغاء**\nأرسل رابط جديد للتحميل",
            parse_mode='Markdown'
        )
        if user_id in user_sessions:
            del user_sessions[user_id]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل (مطورة مع خيارات الجودة)"""
    await quality_selection(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء (كما هي)"""
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
    """تنظيف الملفات المؤقتة عند الإغلاق (كما هي)"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم تنظيف الملفات المؤقتة")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

def main():
    """تشغيل البوت (مطور)"""
    logger.info("🚀 بدء تشغيل البوت المتطور جداً...")
    
    try:
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة المعالجات الأصلية
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # إضافة معالج جديد للرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # إضافة معالج الأزرار الجديد
        application.add_handler(CallbackQueryHandler(button_handler, pattern="^(stats|help|all_platforms|speed)$"))
        application.add_handler(CallbackQueryHandler(quality_callback, pattern="^(quality_|cancel)"))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # تشغيل البوت
        logger.info("✅ البوت المتطور جداً جاهز للعمل!")
        print("\n" + "="*60)
        print("🤖 البوت المتطور جداً يعمل الآن!".center(60))
        print("="*60)
        print(f"📝 توكن:", TOKEN[:15] + "...")
        print(f"📁 مجلد التحميلات:", DOWNLOAD_FOLDER)
        print(f"🌐 المنصات المدعومة:", len(ALL_SUPPORTED_SITES))
        print("="*60 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {str(e)}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
