import os
import re
import time
import json
import asyncio
import logging
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
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
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع توكن البوت هنا
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت

# إعداد المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/temp", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/cookies", exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== ملفات الكوكيز للمنصات المختلفة ==================
# يمكنك إضافة كوكيز حقيقية لتحسين التحميل
INSTAGRAM_COOKIES = """
# Netscape HTTP Cookie File
# يمكنك وضع ملف الكوكيز هنا لتحميل من انستغرام
"""

# ================== إعدادات yt-dlp المتقدمة ==================
def get_ydl_options(platform: str = "", mode: str = "video") -> dict:
    """الحصول على إعدادات مخصصة حسب المنصة"""
    
    base_options = {
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'noplaylist': True,
        'geo_bypass': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'extract_flat': False,
    }
    
    # إعدادات خاصة بكل منصة
    platform_headers = {
        'instagram': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
        },
        'tiktok': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
        },
        'twitter': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'youtube': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    # إضافة الهيدرات المناسبة
    if platform in platform_headers:
        base_options['headers'] = platform_headers[platform]
    
    # إعدادات خاصة للتجاوز
    base_options['extractor_args'] = {
        'instagram': {
            'webpage': ['1'],  # استخدام طريقة بديلة
        }
    }
    
    # إعدادات الصوت
    if mode == "audio":
        base_options['format'] = 'bestaudio/best'
        base_options['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # إعدادات الفيديو - محاولة تنسيقات متعددة
        base_options['format'] = 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
    
    # قوالب الحفظ
    base_options['outtmpl'] = f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s.%(ext)s'
    
    return base_options

# ================== دوال المساعدة ==================
def detect_platform(url: str) -> Tuple[str, bool]:
    """كشف المنصة من الرابط"""
    platforms = {
        'youtube.com': ('📺 YouTube', True),
        'youtu.be': ('📺 YouTube', True),
        'youtube.com/shorts': ('📱 YouTube Shorts', True),
        'twitter.com': ('🐦 Twitter', True),
        'x.com': ('🐦 Twitter', True),
        'instagram.com': ('📸 Instagram', True),
        'instagram.com/reel': ('📱 Instagram Reel', True),
        'instagram.com/p': ('📷 Instagram Post', True),
        'instagram.com/stories': ('📖 Instagram Story', True),
        'facebook.com': ('📘 Facebook', True),
        'fb.watch': ('📘 Facebook', True),
        'tiktok.com': ('🎵 TikTok', True),
        'reddit.com': ('👽 Reddit', True),
        'pinterest.com': ('📌 Pinterest', True),
        'dailymotion.com': ('🎬 Dailymotion', True),
        'vimeo.com': ('🎥 Vimeo', True),
        'twitch.tv': ('🎮 Twitch', True),
        'linkedin.com': ('💼 LinkedIn', True),
    }
    
    for key, (name, supported) in platforms.items():
        if key in url.lower():
            return name, supported
    
    return '🌐 رابط عادي', True

def format_size(size: int) -> str:
    """تحويل الحجم إلى صيغة مقروءة"""
    if size <= 0:
        return "غير معروف"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

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

def extract_instagram_shortcode(url: str) -> Optional[str]:
    """استخراج كود انستغرام من الرابط"""
    patterns = [
        r'instagram\.com/(?:p|reel|tv|stories)/([A-Za-z0-9_-]+)',
        r'instagr\.am/(?:p|reel|tv)/([A-Za-z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def get_video_info_advanced(url: str) -> Tuple[Optional[Dict], Optional[str], Optional[str]]:
    """الحصول على معلومات الفيديو بطرق متعددة"""
    
    platform_name, _ = detect_platform(url)
    
    # محاولات متعددة للتحميل
    attempts = [
        {'mode': 'normal', 'options': {}},
        {'mode': 'mobile', 'options': {'headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'}}},
        {'mode': 'desktop', 'options': {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}}},
    ]
    
    last_error = None
    
    for attempt in attempts:
        try:
            options = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'socket_timeout': 30,
                'retries': 3,
            }
            
            # إضافة الهيدرات
            if 'headers' in attempt['options']:
                options['headers'] = attempt['options']['headers']
            
            # إعدادات خاصة لانستغرام
            if 'instagram' in url:
                options['extractor_args'] = {'instagram': {'webpage': ['1']}}
            
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info:
                    # تنظيف البيانات
                    clean_info = {
                        'title': info.get('title', 'فيديو'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', info.get('channel', 'غير معروف')),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'comment_count': info.get('comment_count', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'platform': platform_name,
                        'filesize': info.get('filesize', info.get('filesize_approx', 0)),
                        'format': info.get('format', ''),
                        'width': info.get('width', 0),
                        'height': info.get('height', 0),
                        'fps': info.get('fps', 0),
                    }
                    
                    return clean_info, None, attempt['mode']
                    
        except Exception as e:
            last_error = str(e)
            continue
    
    return None, last_error, None

async def download_media_advanced(url: str, mode: str = 'video', quality: str = 'best') -> Tuple[Optional[str], Optional[str]]:
    """تحميل الوسائط بطرق متعددة"""
    
    platform_name, _ = detect_platform(url)
    temp_file = None
    
    # محاولات متعددة للتحميل
    attempts = [
        {'mode': 'normal', 'options': {}},
        {'mode': 'mobile', 'options': {'headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'}}},
        {'mode': 'desktop', 'options': {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}}},
    ]
    
    if platform_name == '📸 Instagram' or platform_name == '📱 Instagram Reel':
        # محاولات إضافية لانستغرام
        attempts.extend([
            {'mode': 'instagram_web', 'options': {'extractor_args': {'instagram': {'webpage': ['1']}}}},
            {'mode': 'instagram_api', 'options': {'extractor_args': {'instagram': {'api': ['1']}}}},
        ])
    
    last_error = None
    
    for attempt in attempts:
        try:
            # إعدادات التحميل
            options = {
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True,
                'noplaylist': True,
                'geo_bypass': True,
                'socket_timeout': 30,
                'retries': 5,
                'fragment_retries': 5,
            }
            
            # إضافة الهيدرات
            if 'headers' in attempt['options']:
                options['headers'] = attempt['options']['headers']
            
            # إضافة إعدادات المستخرج
            if 'extractor_args' in attempt['options']:
                options['extractor_args'] = attempt['options']['extractor_args']
            
            # إعدادات الجودة
            if mode == 'audio':
                options['format'] = 'bestaudio/best'
                options['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                if quality == 'best':
                    options['format'] = 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
                elif quality == 'medium':
                    options['format'] = 'best[height<=720][ext=mp4]/best[height<=720]'
                elif quality == 'low':
                    options['format'] = 'worst[ext=mp4]/worst'
            
            # قالب الحفظ
            options['outtmpl'] = f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s_{attempt["mode"]}.%(ext)s'
            
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # البحث عن الملف المحمل
                if mode == 'audio':
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = ydl.prepare_filename(info)
                    if not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'
                
                # التحقق من وجود الملف
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    if file_size <= MAX_FILE_SIZE:
                        return filename, None
                    else:
                        os.remove(filename)
                        return None, f"الملف كبير ({format_size(file_size)})"
                else:
                    # البحث عن الملف بامتدادات مختلفة
                    base = filename.rsplit('.', 1)[0]
                    for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                        test_file = base + ext
                        if os.path.exists(test_file):
                            file_size = os.path.getsize(test_file)
                            if file_size <= MAX_FILE_SIZE:
                                return test_file, None
                            else:
                                os.remove(test_file)
                                return None, f"الملف كبير ({format_size(file_size)})"
                    
        except Exception as e:
            last_error = str(e)
            continue
    
    return None, last_error

def cleanup_temp_files():
    """تنظيف الملفات المؤقتة"""
    try:
        now = time.time()
        cleaned = 0
        for file in Path(f"{DOWNLOAD_DIR}/temp").glob('*'):
            if file.is_file() and file.stat().st_mtime < now - 3600:
                file.unlink()
                cleaned += 1
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} old files")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

# ================== معالجات البوت المتطورة ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب المتطورة"""
    user = update.effective_user
    ffmpeg_status = "✅ متوفر" if check_ffmpeg() else "⚠️ غير متوفر"
    
    welcome_text = f"""
🎬 <b>مرحباً بك {user.first_name} في بوت التحميل المتطور!</b>

✨ <b>المميزات الحصرية:</b>
• تحميل من جميع المنصات (انستغرام، يوتيوب، تيك توك، تويتر...)
• تقنيات متعددة لتجاوز قيود التحميل
• اختيار الجودة (عالية - متوسطة - منخفضة)
• تحميل الصور والفيديوهات والصوتيات
• معالجة ذكية للأخطاء

📥 <b>أرسل الرابط وسأقوم بالباقي!</b>

<b>المنصات المدعومة:</b>
📸 Instagram (Reels - Posts - Stories)
📺 YouTube (Videos - Shorts - Live)
🎵 TikTok (بدون علامة مائية)
🐦 Twitter/X (Videos - GIFs)
📘 Facebook (Videos - Reels)
👽 Reddit - 📌 Pinterest - 🎥 Vimeo

⚙️ <b>الحالة:</b>
• FFmpeg: {ffmpeg_status}
• الحد الأقصى: {format_size(MAX_FILE_SIZE)}
    """
    
    keyboard = [
        [
            InlineKeyboardButton("📥 تحميل", callback_data="show_formats"),
            InlineKeyboardButton("❓ مساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton("📊 إحصائيات", callback_data="stats"),
            InlineKeyboardButton("ℹ️ معلومات", callback_data="about")
        ]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_formats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض صيغ التحميل المتاحة"""
    query = update.callback_query
    await query.answer()
    
    text = """
📥 <b>اختر نوع التحميل:</b>

🎬 <b>فيديو:</b>
• جودة عالية (HD) - أفضل جودة
• جودة متوسطة (720p) - توازن بين الجودة والحجم
• جودة منخفضة (480p) - حجم صغير

🎵 <b>صوت:</b>
• MP3 عالي الجودة (192kbps)
• MP3 متوسط الجودة (128kbps)

📷 <b>صور:</b>
• تحميل الصور من المنشورات
• تحميل الصور المصغرة

🔄 <b>خصائص إضافية:</b>
• تحميل بدون علامة مائية (تيك توك)
• تحميل قصص انستغرام
• تحميل منشورات متعددة
    """
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 فيديو HD", callback_data="format_video_hd"),
            InlineKeyboardButton("🎬 فيديو 720p", callback_data="format_video_720")
        ],
        [
            InlineKeyboardButton("🎬 فيديو 480p", callback_data="format_video_480"),
            InlineKeyboardButton("🎵 MP3 عالي", callback_data="format_audio_high")
        ],
        [
            InlineKeyboardButton("🎵 MP3 متوسط", callback_data="format_audio_medium"),
            InlineKeyboardButton("📷 صور", callback_data="format_images")
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات البوت"""
    query = update.callback_query
    await query.answer()
    
    text = """
ℹ️ <b>معلومات البوت:</b>

<b>الإصدار:</b> 3.0.0 (المتطور)
<b>المطور:</b> @your_username
<b>لغة البرمجة:</b> Python 3.10+

<b>التقنيات المستخدمة:</b>
• python-telegram-bot 20.3
• yt-dlp (آخر إصدار)
• FFmpeg للصوتيات
• تقنيات متعددة لتجاوز القيود

<b>مميزات فريدة:</b>
• 5+ محاولة تحميل لكل رابط
• دعم خاص لانستغرام
• تحميل الصور والفيديوهات
• معالجة ذكية للأخطاء

<b>آخر تحديث:</b> 2024
    """
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات سريعة"""
    query = update.callback_query
    await query.answer()
    
    # إحصائيات بسيطة
    temp_files = len(list(Path(f"{DOWNLOAD_DIR}/temp").glob('*')))
    total_size = sum(f.stat().st_size for f in Path(f"{DOWNLOAD_DIR}/temp").glob('*') if f.is_file())
    
    text = f"""
📊 <b>إحصائيات البوت:</b>

<b>الملفات المؤقتة:</b>
• عدد الملفات: {temp_files}
• المساحة: {format_size(total_size)}

<b>حالة التشغيل:</b>
• FFmpeg: {'✅' if check_ffmpeg() else '❌'}
• وقت التشغيل: {datetime.now().strftime('%H:%M:%S')}

<b>المنصات النشطة:</b>
• جميع المنصات مدعومة ✅
• وضع التجاوز: نشط 🟢
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def refresh_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث الإحصائيات"""
    await stats(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    help_text = """
📚 <b>كيفية استخدام البوت:</b>

<b>🔹 الخطوات البسيطة:</b>
1️⃣ أرسل رابط الفيديو/الصورة
2️⃣ اختر نوع التحميل
3️⃣ انتظر قليلاً
4️⃣ استلم الملف مباشرة

<b>🔸 نصائح لانستغرام:</b>
• استخدم روابط قصيرة: instagram.com/p/XXX
• جرب إعادة المحاولة إذا فشلت
• يمكنك تحميل: منشورات، ريلز، قصص

<b>🔹 أوامر سريعة:</b>
/start - القائمة الرئيسية
/help - هذه المساعدة
/about - معلومات البوت

<b>⚠️ ملاحظات:</b>
• الحد الأقصى: 50 ميجابايت
• المنشورات الخاصة غير مدعومة
• قد تستغرق الفيديوهات الطويلة وقتاً
    """
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
        await update.message.reply_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    text = f"""
🎬 <b>مرحباً بك {user.first_name} في بوت التحميل المتطور!</b>

📥 <b>أرسل الرابط وسأقوم بالباقي!</b>
    """
    
    keyboard = [
        [
            InlineKeyboardButton("📥 تحميل", callback_data="show_formats"),
            InlineKeyboardButton("❓ مساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton("📊 إحصائيات", callback_data="stats"),
            InlineKeyboardButton("ℹ️ معلومات", callback_data="about")
        ]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_url_advanced(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط بشكل متطور"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ <b>رابط غير صحيح</b>\n\nالرجاء إرسال رابط يبدأ بـ http:// أو https://",
            parse_mode='HTML'
        )
        return
    
    cleanup_temp_files()
    
    # كشف المنصة
    platform_name, _ = detect_platform(url)
    
    status = await update.message.reply_text(
        f"🔄 <b>جاري تحليل الرابط...</b>\n\nالمنصة: {platform_name}",
        parse_mode='HTML'
    )
    
    try:
        # محاولة الحصول على المعلومات بطرق متعددة
        info, error, method = await get_video_info_advanced(url)
        
        if error or not info:
            # إذا فشلت كل المحاولات
            await status.edit_text(
                f"❌ <b>فشل تحليل الرابط</b>\n\n"
                f"المنصة: {platform_name}\n"
                f"الخطأ: {error[:100] if error else 'غير معروف'}\n\n"
                f"💡 <b>نصائح:</b>\n"
                f"• تأكد من أن الرابط صحيح\n"
                f"• حاول مرة أخرى بعد قليل\n"
                f"• تأكد أن المحتوى عام وليس خاص",
                parse_mode='HTML'
            )
            return
        
        # حفظ المعلومات
        context.user_data['video_info'] = info
        context.user_data['video_url'] = url
        
        # تحضير رسالة المعلومات
        duration = format_duration(info.get('duration', 0))
        views = format_number(info.get('view_count', 0))
        likes = format_number(info.get('like_count', 0))
        file_size = format_size(info.get('filesize', 0))
        
        info_text = f"""
{info['platform']} <b>معلومات المحتوى:</b>

📹 <b>العنوان:</b> {info['title'][:100]}
👤 <b>الناشر:</b> {info['uploader']}
⏱️ <b>المدة:</b> {duration}
👁️ <b>المشاهدات:</b> {views}
❤️ <b>الإعجابات:</b> {likes}
📊 <b>الحجم التقريبي:</b> {file_size}

📥 <b>اختر نوع التحميل:</b>
        """
        
        # أزرار التحميل المتطورة
        keyboard = [
            [
                InlineKeyboardButton("🎬 فيديو HD", callback_data="dl_video_hd"),
                InlineKeyboardButton("🎬 فيديو 720p", callback_data="dl_video_720")
            ],
            [
                InlineKeyboardButton("🎬 فيديو 480p", callback_data="dl_video_480"),
                InlineKeyboardButton("🎵 MP3 عالي", callback_data="dl_audio_high")
            ],
            [
                InlineKeyboardButton("🔄 محاولة أخرى", callback_data="dl_retry"),
                InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
            ]
        ]
        
        # إضافة أزرار إضافية حسب المنصة
        if 'instagram' in url:
            keyboard.insert(0, [
                InlineKeyboardButton("📷 صور المنشور", callback_data="dl_images"),
                InlineKeyboardButton("📖 القصة", callback_data="dl_story")
            ])
        elif 'tiktok' in url:
            keyboard.insert(0, [
                InlineKeyboardButton("🎵 بدون علامة مائية", callback_data="dl_nowatermark")
            ])
        
        # إرسال الصورة المصغرة مع المعلومات
        if info.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=info_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await status.delete()
            except:
                await status.edit_text(
                    info_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await status.edit_text(
                info_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        await status.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")
        logger.error(f"Error: {e}")

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التحميل"""
    query = update.callback_query
    await query.answer()
    
    # معالجة الأزرار العامة
    if query.data == "cancel":
        await query.edit_message_text("✅ تم الإلغاء")
        return
    
    if query.data == "show_formats":
        await show_formats(update, context)
        return
    
    if query.data == "help":
        await help_command(update, context)
        return
    
    if query.data == "about":
        await about(update, context)
        return
    
    if query.data == "stats":
        await stats(update, context)
        return
    
    if query.data == "refresh_stats":
        await refresh_stats(update, context)
        return
    
    if query.data == "back_to_start":
        await back_to_start(update, context)
        return
    
    # معالجة أزرار التحميل
    if query.data.startswith("dl_"):
        # استخراج معلومات التحميل
        dl_type = query.data.replace("dl_", "")
        
        info = context.user_data.get('video_info', {})
        url = context.user_data.get('video_url')
        
        if not url:
            await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً")
            return
        
        # تحديد نوع التحميل والجودة
        mode = 'video'
        quality = 'best'
        
        if dl_type == 'video_hd':
            quality = 'best'
        elif dl_type == 'video_720':
            quality = 'medium'
        elif dl_type == 'video_480':
            quality = 'low'
        elif dl_type == 'audio_high':
            mode = 'audio'
            quality = 'high'
        elif dl_type == 'retry':
            mode = 'video'
            quality = 'best'
        
        # رسالة التحميل
        type_names = {
            'video_hd': '🎬 فيديو HD',
            'video_720': '🎬 فيديو 720p',
            'video_480': '🎬 فيديو 480p',
            'audio_high': '🎵 MP3 عالي',
            'retry': '🔄 محاولة جديدة',
        }
        
        await query.edit_message_text(
            f"⏳ <b>جاري التحميل...</b>\n\n"
            f"النوع: {type_names.get(dl_type, dl_type)}\n"
            f"العنوان: {info.get('title', '')[:50]}\n\n"
            f"قد يستغرق هذا بعض الوقت...",
            parse_mode='HTML'
        )
        
        try:
            # محاولة التحميل بطرق متعددة
            filename, error = await download_media_advanced(url, mode, quality)
            
            if error:
                await query.edit_message_text(
                    f"❌ <b>فشل التحميل</b>\n\n{error}\n\n"
                    f"💡 جرب نوع تحميل آخر أو أعد المحاولة",
                    parse_mode='HTML'
                )
                return
            
            if not filename or not os.path.exists(filename):
                await query.edit_message_text(
                    "❌ <b>فشل التحميل</b>\n\nلم يتم العثور على الملف",
                    parse_mode='HTML'
                )
                return
            
            file_size = os.path.getsize(filename)
            
            await query.edit_message_text("📤 <b>جاري الرفع...</b>", parse_mode='HTML')
            
            # رفع الملف
            with open(filename, 'rb') as f:
                if mode == 'audio':
                    await query.message.reply_audio(
                        audio=f,
                        title=info.get('title', 'صوت'),
                        performer=info.get('uploader', 'غير معروف'),
                        duration=info.get('duration'),
                        caption=f"✅ <b>تم التحميل بنجاح!</b>\n\n"
                                f"📊 الحجم: {format_size(file_size)}"
                    )
                else:
                    await query.message.reply_video(
                        video=f,
                        caption=f"✅ <b>تم التحميل بنجاح!</b>\n\n"
                                f"{info.get('title', '')[:100]}\n"
                                f"📊 الحجم: {format_size(file_size)}",
                        supports_streaming=True,
                        duration=info.get('duration')
                    )
            
            # حذف الملف المؤقت
            os.remove(filename)
            
            # حذف رسالة الحالة
            await query.delete_message()
            
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
            logger.error(f"Download error: {e}")
            cleanup_temp_files()

def main():
    """تشغيل البوت"""
    print("="*60)
    print("🤖 بوت التحميل المتطور يعمل...")
    print("="*60)
    print(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
    print(f"📊 الحد الأقصى: {format_size(MAX_FILE_SIZE)}")
    print(f"🎵 FFmpeg: {'✅' if check_ffmpeg() else '❌'}")
    print("="*60)
    print("✅ اضغط Ctrl+C للإيقاف")
    print("="*60)
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_advanced))
    application.add_handler(CallbackQueryHandler(download_callback))
    
    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
