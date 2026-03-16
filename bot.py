import os
import re
import time
import json
import asyncio
import logging
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# ================== الإعدادات الأساسية ==================
TOKEN = "YOUR_BOT_TOKEN_HERE"  # ضع توكن البوت هنا
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت حد تليجرام
MAX_FILE_SIZE_WARNING = 45 * 1024 * 1024  # تحذير عند 45 ميجا
ADMIN_IDS = [123456789]  # ضع معرفات المشرفين هنا

# قائمة المنصات المدعومة مع أيقوناتها
SUPPORTED_PLATFORMS = {
    'youtube.com': '📺 YouTube',
    'youtu.be': '📺 YouTube',
    'twitter.com': '🐦 Twitter',
    'x.com': '🐦 Twitter',
    'instagram.com': '📸 Instagram',
    'facebook.com': '📘 Facebook',
    'fb.watch': '📘 Facebook',
    'tiktok.com': '🎵 TikTok',
    'reddit.com': '👽 Reddit',
    'pinterest.com': '📌 Pinterest',
    'dailymotion.com': '🎬 Dailymotion',
    'vimeo.com': '🎥 Vimeo',
    'twitch.tv': '🎮 Twitch',
    'youtube.com/shorts': '📱 YouTube Shorts'
}

# إعداد المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/temp", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/logs", exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(f"{DOWNLOAD_DIR}/logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================== إعدادات yt-dlp المتطورة ==================
YDL_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'restrictfilenames': True,
    'noplaylist': True,
    'geo_bypass': True,
    'socket_timeout': 30,
    'retries': 5,
    'fragment_retries': 5,
    'skip_unavailable_fragments': True,
    'extract_flat': False,
}

# إعدادات الصوت فقط
AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# ================== دوال المساعدة ==================
def get_platform_name(url: str) -> str:
    """استخراج اسم المنصة من الرابط"""
    parsed_url = urlparse(url.lower())
    domain = parsed_url.netloc.replace('www.', '')
    
    for key, value in SUPPORTED_PLATFORMS.items():
        if key in domain or key in url:
            return value
    
    return '🌐 منصة أخرى'

def clean_filename(filename: str) -> str:
    """تنظيف اسم الملف من الرموز غير المسموحة"""
    # إزالة الرموز غير المسموحة
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # تقصير الاسم الطويل
    if len(filename) > 100:
        filename = filename[:97] + '...'
    return filename

def format_size(size: int) -> str:
    """تحويل الحجم إلى صيغة مقروءة"""
    if size < 0:
        return "غير معروف"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def format_duration(seconds: int) -> str:
    """تحويل المدة إلى صيغة مقروءة"""
    if not seconds or seconds <= 0:
        return "غير معروفة"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def format_number(num: int) -> str:
    """تنسيق الأرقام الكبيرة"""
    if not num:
        return "0"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def check_ffmpeg() -> bool:
    """التحقق من تثبيت FFmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

async def get_video_info(url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """الحصول على معلومات الفيديو بشكل آمن"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # تنظيف البيانات
            clean_info = {
                'title': info.get('title', 'فيديو بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', info.get('channel', 'غير معروف')),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'thumbnail': info.get('thumbnail', ''),
                'platform': get_platform_name(url),
                'extractor': info.get('extractor_key', 'unknown'),
                'webpage_url': info.get('webpage_url', url),
                'filesize': info.get('filesize', 0),
                'filesize_approx': info.get('filesize_approx', 0),
            }
            
            return clean_info, None
            
    except yt_dlp.utils.DownloadError as e:
        return None, "الرابط غير صالح أو الفيديو خاص"
    except Exception as e:
        logger.error(f"Error in get_video_info: {e}")
        return None, str(e)

async def download_media(url: str, mode: str = 'video') -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """تحميل الوسائط (فيديو أو صوت)"""
    try:
        options = YDL_OPTIONS.copy() if mode == 'video' else AUDIO_OPTIONS.copy()
        
        with yt_dlp.YoutubeDL(options) as ydl:
            # استخراج المعلومات أولاً
            info = ydl.extract_info(url, download=False)
            
            # تقدير الحجم
            estimated_size = info.get('filesize') or info.get('filesize_approx') or 0
            if estimated_size > MAX_FILE_SIZE * 1.1:  # زيادة 10% للتسامح
                return None, f"الملف كبير جداً ({format_size(estimated_size)})", info
            
            # تحميل الملف
            info = ydl.extract_info(url, download=True)
            
            # الحصول على اسم الملف
            if mode == 'audio':
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            else:
                filename = ydl.prepare_filename(info)
                if not filename.endswith('.mp4'):
                    filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            # التحقق من وجود الملف
            if os.path.exists(filename):
                return filename, None, info
            else:
                # البحث عن الملف بامتدادات مختلفة
                base = filename.rsplit('.', 1)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                    test_file = base + ext
                    if os.path.exists(test_file):
                        return test_file, None, info
                
                return None, "لم يتم العثور على الملف المحمل", info
                
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Video unavailable" in error_msg:
            return None, "الفيديو غير متاح", None
        elif "Private video" in error_msg:
            return None, "الفيديو خاص", None
        elif "Copyright" in error_msg:
            return None, "الفيديو محمي بحقوق النشر", None
        else:
            return None, f"خطأ في التحميل", None
    except Exception as e:
        logger.error(f"Error in download_media: {e}")
        return None, str(e), None

def cleanup_old_files():
    """تنظيف الملفات المؤقتة القديمة"""
    try:
        now = time.time()
        temp_dir = f"{DOWNLOAD_DIR}/temp"
        
        for file in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, file)
            if os.path.isfile(filepath):
                # حذف الملفات الأقدم من ساعة
                if os.path.getmtime(filepath) < now - 3600:
                    os.remove(filepath)
                    logger.info(f"Cleaned up: {file}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

# ================== معالجات البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب المطورة"""
    user = update.effective_user
    ffmpeg_status = "✅ متوفر" if check_ffmpeg() else "⚠️ غير متوفر (الصوت فقط قد لا يعمل)"
    
    welcome_text = f"""
🎬 <b>مرحباً بك {user.first_name} في بوت التحميل المتطور!</b>

✨ <b>المميزات الحصرية:</b>
• تحميل من 15+ منصة مختلفة
• اختيار جودة التحميل (HD - 480p - 240p)
• تحميل الصوت فقط بصيغة MP3
• عرض معلومات الفيديو قبل التحميل
• واجهة تفاعلية عربية سهلة
• تنظيف تلقائي للملفات

📥 <b>فقط أرسل الرابط وسأقوم بالباقي!</b>

<b>المنصات المدعومة:</b>
📺 YouTube - 🐦 Twitter - 📸 Instagram
📘 Facebook - 🎵 TikTok - 👽 Reddit
📌 Pinterest - 🎬 Dailymotion - 🎥 Vimeo
🎮 Twitch - والمزيد...

⚙️ <b>حالة البوت:</b>
• FFmpeg: {ffmpeg_status}
• الحد الأقصى: {format_size(MAX_FILE_SIZE)}
    """
    
    keyboard = [
        [InlineKeyboardButton("📱 قناة البوت", url="https://t.me/your_channel")],
        [InlineKeyboardButton("👨‍💻 المطور", url="https://t.me/your_username")],
        [InlineKeyboardButton("ℹ️ معلومات", callback_data="about")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات البوت"""
    query = update.callback_query
    await query.answer()
    
    about_text = """
ℹ️ <b>معلومات البوت:</b>

<b>الإصدار:</b> 2.0.0
<b>المطور:</b> @your_username
<b>لغة البرمجة:</b> Python 3.10+
<b>المكتبات:</b> python-telegram-bot, yt-dlp

<b>آخر تحديث:</b> 2024
<b>حالة التشغيل:</b> 🟢 نشط

💡 <b>لمزيد من المعلومات:</b>
/help - عرض المساعدة
/stats - إحصائيات البوت
    """
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
    
    await query.edit_message_text(
        about_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة التفصيلية"""
    help_text = """
📚 <b>دليل استخدام البوت:</b>

<b>🔹 الخطوات:</b>
1️⃣ أرسل رابط الفيديو
2️⃣ اختر الجودة المناسبة
3️⃣ انتظر التحميل
4️⃣ استلم الملف مباشرة

<b>🔸 خيارات الجودة:</b>
🎥 عالية (HD) - أفضل جودة
📺 متوسطة (480p) - جودة متوازنة
📱 منخفضة (240p) - حجم صغير
🎵 صوت فقط - MP3 بحجم صغير

<b>🔹 المنصات المدعومة بالكامل:</b>
• يوتيوب (فيديوهات عادية + Shorts)
• تويتر (فيديوهات + GIF)
• انستغرام (منشورات + Reels)
• فيسبوك (فيديوهات عامة)
• تيك توك (فيديوهات بدون علامة مائية)
• ريديت (فيديوهات + GIF)

<b>⚠️ ملاحظات مهمة:</b>
• الحد الأقصى: 50 ميجابايت
• الفيديوهات الطويلة قد تستغرق وقتاً
• بعض الفيديوهات الخاصة لا يمكن تحميلها
    """
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط المرسل بشكل محسن"""
    url = update.message.text.strip()
    
    # التحقق من الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ <b>رابط غير صحيح</b>\n\n"
            "الرجاء إرسال رابط يبدأ بـ http:// أو https://",
            parse_mode='HTML'
        )
        return
    
    # تنظيف الملفات القديمة
    cleanup_old_files()
    
    # إرسال رسالة المعالجة
    status_message = await update.message.reply_text(
        "🔄 <b>جاري تحليل الرابط...</b>",
        parse_mode='HTML'
    )
    
    try:
        # استخراج معلومات الفيديو
        info, error = await get_video_info(url)
        
        if error:
            await status_message.edit_text(
                f"❌ <b>خطأ في تحليل الرابط</b>\n\n{error}",
                parse_mode='HTML'
            )
            return
        
        if not info:
            await status_message.edit_text(
                "❌ <b>عذراً، لم نتمكن من تحليل هذا الرابط</b>",
                parse_mode='HTML'
            )
            return
        
        # حفظ المعلومات في context
        context.user_data['video_info'] = info
        context.user_data['video_url'] = url
        
        # تحضير رسالة المعلومات
        platform_icon = info.get('platform', '🌐')
        duration = format_duration(info.get('duration', 0))
        views = format_number(info.get('view_count', 0))
        likes = format_number(info.get('like_count', 0))
        
        # تقدير حجم الفيديو
        estimated_size = max(info.get('filesize', 0), info.get('filesize_approx', 0))
        size_warning = "⚠️ <b>تنبيه:</b> حجم الفيديو قد يكون كبيراً\n" if estimated_size > MAX_FILE_SIZE_WARNING else ""
        
        info_text = f"""
{platform_icon} <b>معلومات الفيديو:</b>

📹 <b>العنوان:</b> {info['title'][:150]}
👤 <b>القناة:</b> {info['uploader']}
⏱️ <b>المدة:</b> {duration}
👁️ <b>المشاهدات:</b> {views}
❤️ <b>الإعجابات:</b> {likes}
📊 <b>الحجم التقريبي:</b> {format_size(estimated_size)}

{size_warning}
📥 <b>اختر جودة التحميل:</b>
        """
        
        # إنشاء أزرار الجودة
        keyboard = [
            [
                InlineKeyboardButton("🎥 عالية (HD)", callback_data="quality_best"),
                InlineKeyboardButton("📺 متوسطة (480p)", callback_data="quality_medium")
            ],
            [
                InlineKeyboardButton("📱 منخفضة (240p)", callback_data="quality_low"),
                InlineKeyboardButton("🎵 صوت فقط (MP3)", callback_data="quality_audio")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        
        # إرسال الصورة المصغرة مع المعلومات
        if info.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=info_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await status_message.delete()
            except:
                await status_message.edit_text(
                    info_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await status_message.edit_text(
                info_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Error in handle_url: {e}")
        await status_message.edit_text(
            f"❌ <b>حدث خطأ غير متوقع</b>\n\n{str(e)[:200]}",
            parse_mode='HTML'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار بشكل محسن"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text(
            "✅ <b>تم إلغاء العملية</b>",
            parse_mode='HTML'
        )
        return
    
    if query.data == "about":
        await about(update, context)
        return
    
    if query.data == "help":
        await help_command(update, context)
        return
    
    if query.data == "back_to_start":
        await back_to_start(update, context)
        return
    
    if query.data.startswith("quality_"):
        quality = query.data.replace("quality_", "")
        
        # الحصول على المعلومات المحفوظة
        info = context.user_data.get('video_info', {})
        url = context.user_data.get('video_url')
        
        if not url:
            await query.edit_message_text(
                "❌ <b>انتهت صلاحية الجلسة</b>\n\nالرجاء إرسال الرابط مرة أخرى",
                parse_mode='HTML'
            )
            return
        
        # تحديث رسالة الحالة
        quality_names = {
            'best': '🎥 عالية (HD)',
            'medium': '📺 متوسطة (480p)',
            'low': '📱 منخفضة (240p)',
            'audio': '🎵 صوت فقط (MP3)'
        }
        
        await query.edit_message_text(
            f"⏳ <b>جاري التحميل...</b>\n\n"
            f"الجودة المختارة: {quality_names.get(quality, quality)}\n"
            f"العنوان: {info.get('title', '')[:50]}...\n\n"
            f"قد يستغرق هذا بعض الوقت حسب حجم الفيديو",
            parse_mode='HTML'
        )
        
        try:
            # تحميل الملف
            mode = 'audio' if quality == 'audio' else 'video'
            filename, error, video_info = await download_media(url, mode)
            
            if error:
                await query.edit_message_text(
                    f"❌ <b>خطأ في التحميل</b>\n\n{error}",
                    parse_mode='HTML'
                )
                return
            
            if not filename or not os.path.exists(filename):
                await query.edit_message_text(
                    "❌ <b>فشل تحميل الملف</b>",
                    parse_mode='HTML'
                )
                return
            
            # التحقق من حجم الملف
            file_size = os.path.getsize(filename)
            if file_size > MAX_FILE_SIZE:
                os.remove(filename)
                await query.edit_message_text(
                    f"❌ <b>الملف كبير جداً</b>\n\n"
                    f"الحد الأقصى: {format_size(MAX_FILE_SIZE)}\n"
                    f"حجم الملف: {format_size(file_size)}",
                    parse_mode='HTML'
                )
                return
            
            # رفع الملف
            await query.edit_message_text(
                "📤 <b>جاري رفع الملف...</b>",
                parse_mode='HTML'
            )
            
            with open(filename, 'rb') as file:
                if quality == 'audio':
                    await query.message.reply_audio(
                        audio=file,
                        title=info.get('title', 'صوت'),
                        performer=info.get('uploader', 'غير معروف'),
                        duration=info.get('duration'),
                        caption=f"✅ <b>تم التحميل بنجاح!</b>\n\n🎵 {info.get('title', '')[:100]}"
                    )
                else:
                    await query.message.reply_video(
                        video=file,
                        caption=f"✅ <b>تم التحميل بنجاح!</b>\n\n🎬 {info.get('title', '')[:100]}",
                        supports_streaming=True,
                        duration=info.get('duration')
                    )
            
            # حذف الملف المؤقت
            os.remove(filename)
            
            # حذف رسالة الحالة
            await query.delete_message()
            
        except Exception as e:
            logger.error(f"Error in button_callback: {e}")
            await query.edit_message_text(
                f"❌ <b>حدث خطأ</b>\n\n{str(e)[:200]}",
                parse_mode='HTML'
            )
            
            # تنظيف الملفات
            cleanup_old_files()

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات البوت (للمشرفين)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "❌ <b>عذراً، هذه الخاصية متاحة فقط للمشرفين</b>",
            parse_mode='HTML'
        )
        return
    
    # حساب الإحصائيات
    temp_dir = Path(f"{DOWNLOAD_DIR}/temp")
    total_files = 0
    total_size = 0
    
    if temp_dir.exists():
        for file in temp_dir.iterdir():
            if file.is_file():
                total_files += 1
                total_size += file.stat().st_size
    
    # وقت التشغيل
    uptime = datetime.now() - context.bot.start_time if hasattr(context.bot, 'start_time') else datetime.now() - datetime.now()
    
    stats_text = f"""
📊 <b>إحصائيات البوت:</b>

<b>🖥️ النظام:</b>
• الملفات المؤقتة: {total_files}
• المساحة المستخدمة: {format_size(total_size)}
• وقت التشغيل: {str(uptime).split('.')[0]}

<b>📈 الأداء:</b>
• FFmpeg: {'✅ متوفر' if check_ffmpeg() else '❌ غير متوفر'}
• الحد الأقصى: {format_size(MAX_FILE_SIZE)}
• آخر تنظيف: {datetime.now().strftime('%H:%M:%S')}

<b>👥 المستخدمون:</b>
• عدد المستخدمين النشطين: {len(context.application.chat_data) if hasattr(context.application, 'chat_data') else 0}
    """
    
    keyboard = [[InlineKeyboardButton("🔄 تحديث", callback_data="refresh_stats")]]
    
    await update.message.reply_text(
        stats_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    logger.error(f"Exception: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ <b>عذراً، حدث خطأ غير متوقع</b>\n\n"
                "الرجاء المحاولة مرة أخرى أو الاتصال بالمطور",
                parse_mode='HTML'
            )
    except:
        pass

# ================== تشغيل البوت ==================
def main():
    """الدالة الرئيسية لتشغيل البوت"""
    
    # التحقق من FFmpeg
    if not check_ffmpeg():
        logger.warning("FFmpeg غير مثبت! تحميل الصوت قد لا يعمل بشكل صحيح")
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # حفظ وقت بدء التشغيل
    application.bot.start_time = datetime.now()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # إضافة معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # تنظيف أولي
    cleanup_old_files()
    
    # تشغيل البوت
    print("="*50)
    print("🤖 البوت يعمل بنجاح!")
    print("="*50)
    print(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
    print(f"📊 الحد الأقصى: {format_size(MAX_FILE_SIZE)}")
    print(f"🎵 FFmpeg: {'✅ متوفر' if check_ffmpeg() else '❌ غير متوفر'}")
    print("="*50)
    print("✅ اضغط Ctrl+C للإيقاف")
    print("="*50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
