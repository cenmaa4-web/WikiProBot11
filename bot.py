import os
import re
import time
import json
import asyncio
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict
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
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت حد تليجرام
MAX_FILE_SIZE_WARNING = 45 * 1024 * 1024  # تحذير عند 45 ميجا
ADMIN_IDS = [123456789]  # ضع معرفات المشرفين هنا

# إعداد المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/temp", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/logs", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/users", exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(f"{DOWNLOAD_DIR}/logs/bot.log", encoding='utf-8'),
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

# ================== قوائم المنصات المدعومة ==================
SUPPORTED_PLATFORMS = {
    'youtube.com': ('📺 YouTube', True),
    'youtu.be': ('📺 YouTube', True),
    'twitter.com': ('🐦 Twitter', True),
    'x.com': ('🐦 Twitter', True),
    'instagram.com': ('📸 Instagram', True),
    'facebook.com': ('📘 Facebook', True),
    'fb.watch': ('📘 Facebook', True),
    'tiktok.com': ('🎵 TikTok', True),
    'reddit.com': ('👽 Reddit', True),
    'pinterest.com': ('📌 Pinterest', True),
    'dailymotion.com': ('🎬 Dailymotion', True),
    'vimeo.com': ('🎥 Vimeo', True),
    'twitch.tv': ('🎮 Twitch', True),
    'tumblr.com': ('📱 Tumblr', True),
    'flickr.com': ('📷 Flickr', True),
    'linkedin.com': ('💼 LinkedIn', True),
}

# ================== دوال المساعدة الأساسية ==================
def get_platform_info(url: str) -> Tuple[str, bool]:
    """استخراج معلومات المنصة من الرابط"""
    parsed_url = urlparse(url.lower())
    domain = parsed_url.netloc.replace('www.', '')
    
    for key, (name, supported) in SUPPORTED_PLATFORMS.items():
        if key in domain or key in url:
            return name, supported
    
    return '🌐 منصة أخرى', False

def clean_filename(filename: str) -> str:
    """تنظيف اسم الملف من الرموز غير المسموحة"""
    # إزالة الرموز غير المسموحة
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # إزالة المسافات الزائدة
    filename = re.sub(r'\s+', ' ', filename).strip()
    # تقصير الاسم الطويل
    if len(filename) > 100:
        filename = filename[:97] + '...'
    return filename

def format_size(size: int) -> str:
    """تحويل الحجم إلى صيغة مقروءة"""
    if size <= 0:
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
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def check_ffmpeg() -> Tuple[bool, str]:
    """التحقق من تثبيت FFmpeg"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=True)
        version_line = result.stdout.split('\n')[0]
        return True, version_line[:50]
    except:
        return False, "غير مثبت"

# ================== إدارة المستخدمين والإحصائيات ==================
def save_user_data(user_id: int, data: dict):
    """حفظ بيانات المستخدم"""
    try:
        filepath = f"{DOWNLOAD_DIR}/users/{user_id}.json"
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        else:
            old_data = {}
        
        old_data.update(data)
        old_data['last_seen'] = datetime.now().isoformat()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

def get_user_data(user_id: int) -> dict:
    """استرجاع بيانات المستخدم"""
    try:
        filepath = f"{DOWNLOAD_DIR}/users/{user_id}.json"
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
    return {}

def get_stats() -> dict:
    """الحصول على إحصائيات عامة"""
    stats = {
        'total_users': 0,
        'total_downloads': 0,
        'total_size': 0,
        'users_today': 0,
        'platforms': defaultdict(int)
    }
    
    try:
        today = datetime.now().date()
        users_dir = Path(f"{DOWNLOAD_DIR}/users")
        
        if users_dir.exists():
            for file in users_dir.glob("*.json"):
                stats['total_users'] += 1
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        stats['total_downloads'] += data.get('downloads', 0)
                        
                        last_seen = data.get('last_seen', '').split('T')[0]
                        if last_seen == today.isoformat():
                            stats['users_today'] += 1
                            
                        for platform in data.get('platforms', []):
                            stats['platforms'][platform] += 1
                except:
                    pass
        
        # حساب حجم الملفات المؤقتة
        temp_dir = Path(f"{DOWNLOAD_DIR}/temp")
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                if file.is_file():
                    stats['total_size'] += file.stat().st_size
                    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
    
    return stats

# ================== دوال التحميل ==================
async def get_video_info(url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """الحصول على معلومات الفيديو بشكل آمن"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None, "لم يتم العثور على معلومات"
            
            platform_name, is_supported = get_platform_info(url)
            
            # تنظيف البيانات
            clean_info = {
                'id': info.get('id', ''),
                'title': info.get('title', 'فيديو بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', info.get('channel', 'غير معروف')),
                'uploader_id': info.get('uploader_id', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'thumbnail': info.get('thumbnail', ''),
                'platform': platform_name,
                'is_supported': is_supported,
                'extractor': info.get('extractor_key', 'unknown'),
                'webpage_url': info.get('webpage_url', url),
                'filesize': info.get('filesize', 0),
                'filesize_approx': info.get('filesize_approx', 0),
                'format': info.get('format', ''),
                'height': info.get('height', 0),
                'width': info.get('width', 0),
                'fps': info.get('fps', 0),
                'tags': info.get('tags', []),
                'categories': info.get('categories', []),
            }
            
            return clean_info, None
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Video unavailable" in error_msg:
            return None, "الفيديو غير متاح"
        elif "Private video" in error_msg:
            return None, "الفيديو خاص"
        elif "Copyright" in error_msg:
            return None, "الفيديو محمي بحقوق النشر"
        else:
            return None, "الرابط غير صالح"
    except Exception as e:
        logger.error(f"Error in get_video_info: {e}")
        return None, f"خطأ: {str(e)[:100]}"

async def download_media(url: str, mode: str = 'video') -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """تحميل الوسائط (فيديو أو صوت)"""
    temp_file = None
    
    try:
        options = YDL_OPTIONS.copy() if mode == 'video' else AUDIO_OPTIONS.copy()
        
        with yt_dlp.YoutubeDL(options) as ydl:
            # استخراج المعلومات أولاً
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None, "لم يتم العثور على معلومات", None
            
            # تقدير الحجم
            estimated_size = info.get('filesize') or info.get('filesize_approx') or 0
            if estimated_size > MAX_FILE_SIZE * 1.2:  # زيادة 20% للتسامح
                return None, f"الملف كبير جداً ({format_size(estimated_size)})", info
            
            # تحميل الملف
            info = ydl.extract_info(url, download=True)
            
            # البحث عن الملف المحمل
            base_filename = options['outtmpl'].replace('%(title)s', info['title']).replace('%(id)s', info['id'])
            base_filename = base_filename.rsplit('.', 1)[0]
            
            # قائمة بالامتدادات الممكنة
            extensions = ['.mp4', '.mkv', '.webm', '.mp3', '.m4a'] if mode == 'video' else ['.mp3', '.m4a']
            
            for ext in extensions:
                test_file = base_filename + ext
                if os.path.exists(test_file):
                    temp_file = test_file
                    break
            
            if not temp_file:
                return None, "لم يتم العثور على الملف المحمل", info
            
            # التحقق من حجم الملف
            file_size = os.path.getsize(temp_file)
            if file_size > MAX_FILE_SIZE:
                os.remove(temp_file)
                return None, f"الملف كبير جداً ({format_size(file_size)})", info
            
            return temp_file, None, info
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Video unavailable" in error_msg:
            return None, "الفيديو غير متاح", None
        elif "Private video" in error_msg:
            return None, "الفيديو خاص", None
        else:
            return None, "خطأ في التحميل", None
    except Exception as e:
        logger.error(f"Error in download_media: {e}")
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        return None, str(e), None

def cleanup_old_files(max_age_hours: int = 1):
    """تنظيف الملفات المؤقتة القديمة"""
    try:
        now = time.time()
        temp_dir = Path(f"{DOWNLOAD_DIR}/temp")
        cleaned = 0
        
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                if file.is_file():
                    # حذف الملفات الأقدم من المدة المحددة
                    if file.stat().st_mtime < now - (max_age_hours * 3600):
                        file.unlink()
                        cleaned += 1
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old files")
                
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

# ================== معالجات البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب المطورة"""
    user = update.effective_user
    ffmpeg_available, ffmpeg_version = check_ffmpeg()
    
    # حفظ بيانات المستخدم
    save_user_data(user.id, {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'language': user.language_code
    })
    
    stats = get_stats()
    
    welcome_text = f"""
🎬 <b>مرحباً بك {user.first_name} في بوت التحميل المتطور!</b>

✨ <b>المميزات الحصرية:</b>
• تحميل من {len(SUPPORTED_PLATFORMS)}+ منصة مختلفة
• اختيار جودة التحميل (HD - 480p - 240p)
• تحميل الصوت فقط بصيغة MP3
• عرض معلومات الفيديو قبل التحميل
• واجهة تفاعلية عربية سهلة
• تنظيف تلقائي للملفات

📥 <b>فقط أرسل الرابط وسأقوم بالباقي!</b>

<b>إحصائيات سريعة:</b>
• المستخدمون: {stats['total_users']}
• التحميلات: {stats['total_downloads']}
• المنصات المدعومة: {len(SUPPORTED_PLATFORMS)}

⚙️ <b>حالة البوت:</b>
• FFmpeg: {'✅ متوفر' if ffmpeg_available else '⚠️ غير متوفر'}
• الحد الأقصى: {format_size(MAX_FILE_SIZE)}
    """
    
    keyboard = [
        [InlineKeyboardButton("📱 قناة البوت", url="https://t.me/your_channel")],
        [InlineKeyboardButton("👨‍💻 المطور", url="https://t.me/your_username")],
        [
            InlineKeyboardButton("ℹ️ معلومات", callback_data="about"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="stats")
        ]
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
    
    ffmpeg_available, ffmpeg_version = check_ffmpeg()
    
    about_text = f"""
ℹ️ <b>معلومات البوت:</b>

<b>الإصدار:</b> 2.5.0
<b>المطور:</b> @your_username
<b>لغة البرمجة:</b> Python 3.10+
<b>المكتبات:</b> python-telegram-bot, yt-dlp

<b>المنصات المدعومة:</b>
{chr(10).join([f'• {name[0]}' for name in SUPPORTED_PLATFORMS.values()][:10])}
والمزيد...

<b>حالة التشغيل:</b>
• FFmpeg: {'✅ متوفر' if ffmpeg_available else '⚠️ غير متوفر'}
• آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    keyboard = [
        [InlineKeyboardButton("📚 المساعدة", callback_data="help")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
    ]
    
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
🎥 <b>عالية (HD)</b> - أفضل جودة متاحة
📺 <b>متوسطة (480p)</b> - جودة متوازنة
📱 <b>منخفضة (240p)</b> - حجم صغير
🎵 <b>صوت فقط (MP3)</b> - للاستماع فقط

<b>🔹 المنصات الرئيسية:</b>
• YouTube (فيديوهات + Shorts + Live)
• Twitter/X (فيديوهات + GIF)
• Instagram (Posts + Reels + Stories)
• Facebook (فيديوهات عامة + Reels)
• TikTok (بدون علامة مائية)
• Reddit (فيديوهات + GIF)
• Twitch (مقاطع + Clips)

<b>⚠️ ملاحظات مهمة:</b>
• الحد الأقصى للحجم: 50 ميجابايت
• قد تستغرق الفيديوهات الطويلة وقتاً أطول
• الفيديوهات الخاصة غير مدعومة
• بعض المواقع قد تمنع التحميل
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

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات"""
    query = update.callback_query
    await query.answer()
    
    stats = get_stats()
    
    stats_text = f"""
📊 <b>إحصائيات البوت:</b>

<b>👥 المستخدمون:</b>
• الإجمالي: {stats['total_users']}
• نشط اليوم: {stats['users_today']}
• إجمالي التحميلات: {stats['total_downloads']}

<b>📁 الملفات المؤقتة:</b>
• المساحة المستخدمة: {format_size(stats['total_size'])}
• متوسط لكل مستخدم: {format_size(stats['total_size'] / max(stats['total_users'], 1))}

<b>🌐 أشهر المنصات:</b>
{chr(10).join([f'• {platform}: {count}' for platform, count in sorted(stats['platforms'].items(), key=lambda x: x[1], reverse=True)[:5]])}

<b>⚙️ حالة البوت:</b>
• آخر تحديث: {datetime.now().strftime('%H:%M:%S')}
• وقت التشغيل: نشط
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        stats_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def refresh_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث الإحصائيات"""
    await stats_callback(update, context)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط المرسل بشكل محسن"""
    url = update.message.text.strip()
    user = update.effective_user
    
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
        
        # تسجيل النشاط
        save_user_data(user.id, {
            'last_url': url,
            'platform': info['platform'],
            'downloads': get_user_data(user.id).get('downloads', 0) + 1
        })
        
        # تحضير رسالة المعلومات
        duration = format_duration(info.get('duration', 0))
        views = format_number(info.get('view_count', 0))
        likes = format_number(info.get('like_count', 0))
        
        # تقدير حجم الفيديو
        estimated_size = max(info.get('filesize', 0), info.get('filesize_approx', 0))
        size_warning = ""
        if estimated_size > MAX_FILE_SIZE_WARNING:
            size_warning = f"⚠️ <b>تنبيه:</b> حجم الفيديو قد يكون كبيراً ({format_size(estimated_size)})\n"
        
        info_text = f"""
{info['platform']} <b>معلومات الفيديو:</b>

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
            except Exception as e:
                logger.error(f"Error sending thumbnail: {e}")
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
    
    # معالجة الأزرار العامة
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
    
    if query.data == "stats":
        await stats_callback(update, context)
        return
    
    if query.data == "refresh_stats":
        await refresh_stats(update, context)
        return
    
    if query.data == "back_to_start":
        await back_to_start(update, context)
        return
    
    # معالجة أزرار الجودة
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
            
            # رفع الملف
            await query.edit_message_text(
                "📤 <b>جاري رفع الملف...</b>",
                parse_mode='HTML'
            )
            
            file_size = os.path.getsize(filename)
            
            with open(filename, 'rb') as file:
                if quality == 'audio':
                    await query.message.reply_audio(
                        audio=file,
                        title=info.get('title', 'صوت'),
                        performer=info.get('uploader', 'غير معروف'),
                        duration=info.get('duration'),
                        caption=f"✅ <b>تم التحميل بنجاح!</b>\n\n"
                                f"🎵 {info.get('title', '')[:100]}\n"
                                f"📊 الحجم: {format_size(file_size)}"
                    )
                else:
                    await query.message.reply_video(
                        video=file,
                        caption=f"✅ <b>تم التحميل بنجاح!</b>\n\n"
                                f"🎬 {info.get('title', '')[:100]}\n"
                                f"📊 الحجم: {format_size(file_size)}",
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
    ffmpeg_available, ffmpeg_version = check_ffmpeg()
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # إضافة معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # تنظيف أولي
    cleanup_old_files()
    
    # تشغيل البوت
    print("="*60)
    print("🤖 بوت التحميل المتطور يعمل بنجاح!")
    print("="*60)
    print(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
    print(f"📊 الحد الأقصى: {format_size(MAX_FILE_SIZE)}")
    print(f"🎵 FFmpeg: {'✅ متوفر' if ffmpeg_available else '❌ غير متوفر'}")
    print(f"🌐 المنصات المدعومة: {len(SUPPORTED_PLATFORMS)}")
    print("="*60)
    print("✅ اضغط Ctrl+C للإيقاف")
    print("="*60)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
