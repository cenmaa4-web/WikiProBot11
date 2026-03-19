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
from urllib.parse import urlparse, quote, urlencode
from datetime import datetime, timedelta
import html
import random

# ============= الكود الأصلي بالكامل (نفس الصيغة) =============

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
THUMBNAIL_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'thumbnails')
SEARCH_CACHE_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'search_cache')
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(SEARCH_CACHE_FOLDER, exist_ok=True)
logger.info(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")

# ============= قائمة المنصات الأصلية (بدون تغيير) =============

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

# إضافة منصات جديدة (مع الحفاظ على القائمة)
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
    "tiktok.com/@",
    "youtube.com/shorts",
    "instagram.com/reel",
    "facebook.com/watch",
    "twitter.com/i/status",
]

ALL_SUPPORTED_SITES = SUPPORTED_SITES + EXTRA_SITES

# ============= إعدادات yt-dlp الأصلية =============

YDL_OPTIONS = {
    'format': 'best[height<=720][filesize<50M]',
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

# خيارات بديلة
FALLBACK_OPTIONS = [
    {'format': 'best[height<=480]'},
    {'format': 'best[height<=360]'},
    {'format': 'worst'},
]

# ============= خيارات التحميل المتقدمة =============

DOWNLOAD_OPTIONS = {
    'video': {
        'name': '🎬 تحميل فيديو',
        'format': 'best[height<=1080][filesize<50M]',
        'type': 'video',
        'emoji': '🎬'
    },
    'voice': {
        'name': '🎤 بصمة صوتية',
        'format': 'bestaudio/best',
        'type': 'voice',
        'emoji': '🎤',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'ogg',
            'preferredquality': '64',
        }]
    },
    'audio': {
        'name': '🎵 ملف MP3',
        'format': 'bestaudio/best',
        'type': 'audio',
        'emoji': '🎵',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }
}

# ============= تحسينات البحث المتقدمة =============

SEARCH_ENGINES = {
    'youtube': {
        'name': '📺 يوتيوب',
        'emoji': '📺',
        'color': '🔴',
        'url': 'https://www.youtube.com/results?search_query={}'
    },
    'tiktok': {
        'name': '🎵 تيك توك',
        'emoji': '🎵',
        'color': '⚫',
        'url': 'https://www.tiktok.com/search?q={}'
    },
    'instagram': {
        'name': '📸 انستغرام',
        'emoji': '📸',
        'color': '🟣',
        'url': 'https://www.instagram.com/explore/tags/{}/'
    },
    'twitter': {
        'name': '🐦 تويتر',
        'emoji': '🐦',
        'color': '🔵',
        'url': 'https://twitter.com/search?q={}'
    },
    'pinterest': {
        'name': '📌 بنترست',
        'emoji': '📌',
        'color': '🔴',
        'url': 'https://www.pinterest.com/search/pins/?q={}'
    },
    'reddit': {
        'name': '👽 ريديت',
        'emoji': '👽',
        'color': '🟠',
        'url': 'https://www.reddit.com/search/?q={}'
    }
}

# خيارات البحث المتقدم
SEARCH_FILTERS = {
    'today': 'اليوم',
    'week': 'هذا الأسبوع',
    'month': 'هذا الشهر',
    'year': 'هذه السنة',
    'long': '+10 دقائق',
    'short': '-4 دقائق',
    'hd': 'جودة عالية'
}

user_sessions = {}
download_stats = {
    'total_downloads': 0,
    'total_users': 0,
    'total_searches': 0,
    'start_time': datetime.now()
}

# ============= دوال البحث المحسنة =============

async def search_videos_advanced(query: str, engine: str = 'youtube', limit: int = 8):
    """بحث متقدم عن الفيديوهات"""
    try:
        # بناء استعلام البحث
        if engine == 'youtube':
            search_query = f"ytsearch{limit}:{query}"
        elif engine == 'tiktok':
            search_query = f"tiktok:{query}"
        elif engine == 'instagram':
            search_query = f"instagram:{query}"
        else:
            search_query = f"ytsearch{limit}:{query}"
        
        with yt_dlp.YoutubeDL({
            'quiet': True, 
            'extract_flat': True,
            'ignoreerrors': True
        }) as ydl:
            info = ydl.extract_info(search_query, download=False)
            
            videos = []
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        video_id = entry.get('id', '')
                        video_url = f"https://youtube.com/watch?v={video_id}" if engine == 'youtube' else entry.get('webpage_url', '')
                        
                        videos.append({
                            'id': video_id,
                            'title': entry.get('title', 'بدون عنوان')[:80],
                            'url': video_url,
                            'duration': entry.get('duration', 0),
                            'uploader': entry.get('uploader', 'غير معروف')[:30],
                            'views': entry.get('view_count', 0),
                            'thumbnail': entry.get('thumbnail', ''),
                            'engine': engine,
                            'engine_name': SEARCH_ENGINES[engine]['name'],
                            'engine_emoji': SEARCH_ENGINES[engine]['emoji'],
                            'published': entry.get('upload_date', ''),
                            'description': entry.get('description', '')[:100]
                        })
            
            # ترتيب النتائج حسب المشاهدات
            videos.sort(key=lambda x: x['views'], reverse=True)
            return videos
            
    except Exception as e:
        logger.error(f"خطأ في البحث المتقدم: {e}")
        return []

async def search_multi_engine(query: str):
    """البحث في عدة منصات"""
    results = {}
    tasks = []
    
    for engine in ['youtube', 'tiktok', 'instagram']:
        task = search_videos_advanced(query, engine, limit=3)
        tasks.append(task)
    
    engine_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, engine in enumerate(['youtube', 'tiktok', 'instagram']):
        if i < len(engine_results) and not isinstance(engine_results[i], Exception):
            results[engine] = engine_results[i]
    
    return results

async def get_trending_videos(category: str = 'music'):
    """الحصول على الفيديوهات الرائجة"""
    try:
        trending_queries = {
            'music': 'ytsearch10:أحدث الأغاني',
            'comedy': 'ytsearch10:مقاطع مضحكة',
            'sports': 'ytsearch10:أهداف مباريات',
            'news': 'ytsearch10:أخبار اليوم',
            'gaming': 'ytsearch10:ألعاب جديدة',
        }
        
        query = trending_queries.get(category, trending_queries['music'])
        
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(query, download=False)
            
            videos = []
            if info and 'entries' in info:
                for entry in info['entries'][:5]:
                    if entry:
                        videos.append({
                            'title': entry.get('title', 'بدون عنوان')[:60],
                            'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                            'uploader': entry.get('uploader', 'غير معروف')[:30],
                            'thumbnail': entry.get('thumbnail', '')
                        })
            return videos
    except Exception as e:
        logger.error(f"خطأ في جلب الرائج: {e}")
        return []

async def download_thumbnail(url: str, video_id: str) -> str:
    """تحميل الصورة المصغرة"""
    try:
        if not url:
            return None
            
        filename = os.path.join(THUMBNAIL_FOLDER, f"{video_id}.jpg")
        
        # استخدام yt-dlp لتحميل الصورة
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'thumbnail' in info:
                    import urllib.request
                    urllib.request.urlretrieve(info['thumbnail'], filename)
                    if os.path.exists(filename):
                        return filename
        except:
            pass
            
        # محاولة بديلة
        if url.startswith(('http://', 'https://')):
            import urllib.request
            urllib.request.urlretrieve(url, filename)
            if os.path.exists(filename):
                return filename
                
    except Exception as e:
        logger.error(f"خطأ في تحميل الصورة: {e}")
    return None

def format_number(num):
    """تنسيق الأرقام"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def format_duration(seconds):
    """تنسيق المدة"""
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    if hours > 0:
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

# ============= الدوال الأصلية (نفس الصيغة) =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب المحسنة"""
    user = update.effective_user
    welcome_msg = (
        f"🎥 **مرحباً {user.first_name}!**\n\n"
        "أنا **البوت الذهبي** لتحميل الفيديوهات ✨\n\n"
        "📥 **أرسل لي:**\n"
        "• رابط فيديو للتحميل\n"
        "• كلمة للبحث (مثل: 'موسيقى')\n\n"
        "🔍 **ميزات البحث:**\n"
        "• بحث في يوتيوب - تيك توك - انستغرام\n"
        "• نتائج مرتبة حسب المشاهدات\n"
        "• صور مصغرة ومعلومات كاملة\n"
        "• فلترة حسب التاريخ والجودة\n\n"
        "⚡ **التحميل:**\n"
        "• فيديو بأعلى جودة\n"
        "• بصمة صوتية\n"
        "• ملف MP3\n\n"
        "🌟 **استمتع بتجربة فريدة!**"
    )
    
    # أزرار تفاعلية محسنة
    keyboard = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
            InlineKeyboardButton("❓ المساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton("🔍 بحث متقدم", callback_data="search_menu"),
            InlineKeyboardButton("📈 الأكثر مشاهدة", callback_data="trending")
        ],
        [
            InlineKeyboardButton("🌐 جميع المنصات", callback_data="all_platforms"),
            InlineKeyboardButton("⚡ تحميل سريع", callback_data="quick_download")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=reply_markup)
    download_stats['total_users'] += 1

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مساعدة محسنة"""
    help_msg = (
        "🆘 **دليل استخدام البوت:**\n\n"
        "**1️⃣ تحميل فيديو:**\n"
        "• أرسل الرابط مباشرة\n"
        "• اختر نوع التحميل:\n"
        "  🎬 فيديو - أعلى جودة\n"
        "  🎤 بصمة صوتية - رسالة صوتية\n"
        "  🎵 MP3 - ملف صوتي\n\n"
        "**2️⃣ البحث:**\n"
        "• اكتب كلمة مفتاحية\n"
        "• اختر منصة البحث\n"
        "• استخدم الفلاتر:\n"
        "  📅 اليوم - هذا الأسبوع - هذا الشهر\n"
        "  🎥 جودة عالية - مدة طويلة\n\n"
        "**3️⃣ الأوامر:**\n"
        "/start - الصفحة الرئيسية\n"
        "/stats - الإحصائيات\n"
        "/search [كلمة] - بحث سريع\n"
        "/trending - الأكثر مشاهدة\n"
        "/popular - الأكثر رواجاً\n\n"
        "**4️⃣ نصائح:**\n"
        "• للبحث عن موسيقى: 'أغاني حزينة'\n"
        "• للأفلام: 'أفلام كرتون'\n"
        "• للمباريات: 'أهداف مباراة'\n"
        "• للكوميديا: 'مقاطع مضحكة'"
    )
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات محسنة"""
    uptime = datetime.now() - download_stats['start_time']
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    # حساب المساحة
    total_size = 0
    for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
        for file in files:
            total_size += os.path.getsize(os.path.join(root, file))
    total_size_mb = total_size / (1024 * 1024)
    
    stats_msg = (
        "📊 **إحصائيات البوت الذهبي:**\n\n"
        f"✅ **الحالة:** يعمل بكفاءة\n"
        f"⏱️ **وقت التشغيل:** {int(hours)} ساعة {int(minutes)} دقيقة\n"
        f"📥 **إجمالي التحميلات:** {download_stats['total_downloads']}\n"
        f"🔍 **إجمالي عمليات البحث:** {download_stats['total_searches']}\n"
        f"👥 **المستخدمين:** {download_stats['total_users']}\n"
        f"🌐 **المنصات المدعومة:** {len(ALL_SUPPORTED_SITES)}\n"
        f"📁 **المساحة المستخدمة:** {total_size_mb:.1f} MB\n"
        f"⚡ **الإصدار:** 5.0 (النسخة الذهبية)\n\n"
        "🚀 **شكراً لثقتك بالبوت!**"
    )
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

def is_supported_url(url):
    """التحقق من الرابط"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    if domain.startswith('www.'):
        domain = domain[4:]
    
    for site in ALL_SUPPORTED_SITES:
        if site in domain:
            return True
    
    shorteners = ['bit.ly', 'tinyurl', 'shorturl', 'ow.ly', 'is.gd', 'youtu.be']
    if any(shortener in domain for shortener in shorteners):
        return True
    
    return False

async def download_media(url, download_type='video'):
    """تحميل الوسائط"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            try:
                options = YDL_OPTIONS.copy()
                
                if download_type in DOWNLOAD_OPTIONS:
                    opt = DOWNLOAD_OPTIONS[download_type]
                    options['format'] = opt['format']
                    if 'postprocessors' in opt:
                        options['postprocessors'] = opt['postprocessors']
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # البحث عن الملف
                    filename = None
                    
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                filename = download['filepath']
                                break
                    
                    if not filename or not os.path.exists(filename):
                        test_filename = ydl.prepare_filename(info)
                        if download_type in ['voice', 'audio']:
                            test_filename = test_filename.rsplit('.', 1)[0] + '.mp3'
                            if os.path.exists(test_filename):
                                filename = test_filename
                        elif os.path.exists(test_filename):
                            filename = test_filename
                    
                    if not filename or not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    if filename and os.path.exists(filename):
                        return filename, info
                    return None, None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل: {e}")
                return None, None
        
        result, info = await loop.run_in_executor(None, download_sync)
        return result, info
        
    except Exception as e:
        logger.error(f"خطأ عام: {e}")
        return None, None

async def get_video_info(url):
    """الحصول على معلومات الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def get_info():
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, get_info)
        
        if info:
            return {
                'title': info.get('title', 'بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'description': info.get('description', ''),
                'thumbnail': info.get('thumbnail', ''),
                'url': url,
                'upload_date': info.get('upload_date', ''),
                'channel_url': info.get('channel_url', '')
            }
        return None
        
    except Exception as e:
        logger.error(f"خطأ في جلب المعلومات: {e}")
        return None

# ============= معالج الرسائل المحسن =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل"""
    text = update.message.text.strip()
    
    if text.startswith(('http://', 'https://')):
        await handle_url(update, context, text)
    else:
        await handle_search(update, context, text)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """معالجة الروابط"""
    if not is_supported_url(url):
        await update.message.reply_text(
            "⚠️ **الرابط غير مدعوم**\n"
            "جرب البحث بالكلمات بدلاً من ذلك",
            parse_mode='Markdown'
        )
        return
    
    progress_msg = await update.message.reply_text(
        "⏳ **جاري تحضير الفيديو...**",
        parse_mode='Markdown'
    )
    
    try:
        info = await get_video_info(url)
        
        if info:
            thumb_path = None
            if info['thumbnail']:
                thumb_path = await download_thumbnail(info['thumbnail'], str(int(time.time())))
            
            # أزرار التحميل المحسنة
            keyboard = [
                [
                    InlineKeyboardButton("🎬 فيديو", callback_data=f"dl_video_{url}"),
                    InlineKeyboardButton("🎤 بصمة", callback_data=f"dl_voice_{url}"),
                    InlineKeyboardButton("🎵 MP3", callback_data=f"dl_audio_{url}")
                ],
                [
                    InlineKeyboardButton("👁️ مشاهدة", callback_data=f"watch_{url}"),
                    InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{url}"),
                    InlineKeyboardButton("🔍 مشابهة", callback_data=f"similar_{url}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            duration_str = format_duration(info['duration'])
            views_str = format_number(info['views'])
            
            caption = (
                f"🎬 **{info['title'][:100]}**\n\n"
                f"👤 **{info['uploader']}**\n"
                f"⏱️ **المدة:** {duration_str}\n"
                f"👁️ **المشاهدات:** {views_str}\n"
                f"❤️ **الإعجابات:** {format_number(info['likes'])}\n\n"
                f"📥 **اختر نوع التحميل:**"
            )
            
            await progress_msg.delete()
            
            if thumb_path and os.path.exists(thumb_path):
                with open(thumb_path, 'rb') as thumb_file:
                    await update.message.reply_photo(
                        photo=thumb_file,
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                try:
                    os.remove(thumb_path)
                except:
                    pass
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        else:
            await progress_msg.edit_text("❌ **فشل في جلب المعلومات**", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """معالجة البحث المحسن"""
    download_stats['total_searches'] += 1
    
    # قائمة منصات البحث
    keyboard = [
        [
            InlineKeyboardButton("📺 يوتيوب", callback_data=f"search_youtube_{query}"),
            InlineKeyboardButton("🎵 تيك توك", callback_data=f"search_tiktok_{query}"),
        ],
        [
            InlineKeyboardButton("📸 انستغرام", callback_data=f"search_instagram_{query}"),
            InlineKeyboardButton("🔍 بحث في الكل", callback_data=f"search_all_{query}"),
        ],
        [
            InlineKeyboardButton("📅 فلترة", callback_data=f"filter_{query}"),
            InlineKeyboardButton("📈 الأكثر مشاهدة", callback_data=f"trending_{query}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔍 **نتائج البحث عن:** {query}\n\n"
        f"اختر منصة البحث:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def perform_search(update: Update, query: str, engine: str):
    """تنفيذ البحث وعرض النتائج"""
    progress_msg = await update.effective_message.reply_text(
        f"🔍 **جاري البحث في {SEARCH_ENGINES[engine]['name']}...**",
        parse_mode='Markdown'
    )
    
    try:
        videos = await search_videos_advanced(query, engine, limit=8)
        
        if videos:
            await progress_msg.delete()
            
            for i, video in enumerate(videos, 1):
                thumb_path = None
                if video['thumbnail']:
                    thumb_path = await download_thumbnail(
                        video['thumbnail'], 
                        f"{engine}_{i}_{int(time.time())}"
                    )
                
                duration_str = format_duration(video['duration'])
                views_str = format_number(video['views'])
                
                # أزرار لكل فيديو
                keyboard = [
                    [
                        InlineKeyboardButton("🎬 فيديو", callback_data=f"dl_video_{video['url']}"),
                        InlineKeyboardButton("🎵 MP3", callback_data=f"dl_audio_{video['url']}"),
                    ],
                    [
                        InlineKeyboardButton("👁️ مشاهدة", callback_data=f"watch_{video['url']}"),
                        InlineKeyboardButton("ℹ️ تفاصيل", callback_data=f"info_{video['url']}"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                caption = (
                    f"{i}. **{video['title']}**\n"
                    f"👤 {video['uploader']} | ⏱️ {duration_str} | 👁️ {views_str}\n"
                )
                
                if thumb_path and os.path.exists(thumb_path):
                    with open(thumb_path, 'rb') as thumb_file:
                        await update.effective_message.reply_photo(
                            photo=thumb_file,
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    try:
                        os.remove(thumb_path)
                    except:
                        pass
                else:
                    await update.effective_message.reply_text(
                        caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
        else:
            await progress_msg.edit_text(
                "❌ **لا توجد نتائج**\nجرب كلمات أخرى",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

# ============= معالج الأزرار المحسن =============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار المحسنة"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # أزرار التحميل
    if data.startswith('dl_'):
        parts = data.split('_', 2)
        dl_type = parts[1]
        url = parts[2]
        
        await query.edit_message_caption(
            caption=f"⏳ **جاري التحميل...**\n{DOWNLOAD_OPTIONS[dl_type]['emoji']} {DOWNLOAD_OPTIONS[dl_type]['name']}"
        )
        
        try:
            file_path, info = await download_media(url, dl_type)
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                
                with open(file_path, 'rb') as file:
                    if dl_type == 'video':
                        await query.message.reply_video(
                            video=file,
                            caption=f"✅ **تم التحميل!**\n📊 {file_size:.1f} MB | {info.get('title', '')[:50]}",
                            supports_streaming=True
                        )
                    elif dl_type == 'voice':
                        await query.message.reply_voice(
                            voice=file,
                            caption=f"✅ **بصمة صوتية**\n📊 {file_size:.1f} MB"
                        )
                    elif dl_type == 'audio':
                        await query.message.reply_audio(
                            audio=file,
                            caption=f"✅ **ملف MP3**\n📊 {file_size:.1f} MB",
                            title=info.get('title', 'صوت')[:50],
                            performer=info.get('uploader', 'غير معروف')[:30]
                        )
                
                os.remove(file_path)
                download_stats['total_downloads'] += 1
                
                # إعادة الصورة الأصلية
                await query.edit_message_caption(
                    caption=query.message.caption_html,
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_caption(
                    caption="❌ **فشل التحميل**\nحاول مرة أخرى"
                )
                
        except Exception as e:
            logger.error(f"خطأ: {e}")
            await query.edit_message_caption(
                caption=f"❌ **خطأ:** {str(e)[:100]}"
            )
    
    # أزرار البحث
    elif data.startswith('search_'):
        parts = data.split('_', 2)
        engine = parts[1]
        query_text = parts[2]
        
        if engine == 'all':
            # بحث في كل المنصات
            await query.edit_message_text(
                f"🔍 **جاري البحث في جميع المنصات عن:** {query_text}",
                parse_mode='Markdown'
            )
            
            results = await search_multi_engine(query_text)
            
            response = f"🔍 **نتائج البحث عن:** {query_text}\n\n"
            
            for engine, videos in results.items():
                if videos:
                    response += f"{SEARCH_ENGINES[engine]['emoji']} **{SEARCH_ENGINES[engine]['name']}:**\n"
                    for video in videos[:3]:
                        response += f"• {video['title'][:50]}...\n"
                    response += "\n"
            
            response += "\nاختر منصة للتفاصيل:"
            
            keyboard = []
            for engine in results.keys():
                if results[engine]:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{SEARCH_ENGINES[engine]['emoji']} {SEARCH_ENGINES[engine]['name']}", 
                            callback_data=f"search_{engine}_{query_text}"
                        )
                    ])
            
            await query.edit_message_text(
                response,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await perform_search(update, query_text, engine)
    
    # مشاهدة مباشرة
    elif data.startswith('watch_'):
        url = data.replace('watch_', '')
        await query.edit_message_caption(
            caption=f"👁️ **مشاهدة مباشرة:**\n[اضغط هنا]({url})",
            parse_mode='Markdown'
        )
    
    # معلومات الفيديو
    elif data.startswith('info_'):
        url = data.replace('info_', '')
        await query.edit_message_caption(
            caption="⏳ **جلب المعلومات...**"
        )
        
        info = await get_video_info(url)
        if info:
            duration_str = format_duration(info['duration'])
            
            info_text = (
                f"ℹ️ **معلومات الفيديو**\n\n"
                f"**العنوان:** {info['title'][:200]}\n"
                f"**الناشر:** {info['uploader']}\n"
                f"**المدة:** {duration_str}\n"
                f"**المشاهدات:** {format_number(info['views'])}\n"
                f"**الإعجابات:** {format_number(info['likes'])}\n"
                f"**تاريخ الرفع:** {info['upload_date']}\n\n"
                f"**الوصف:**\n{info['description'][:300]}"
            )
            await query.edit_message_caption(caption=info_text)
        else:
            await query.edit_message_caption(caption="❌ **لا يمكن جلب المعلومات**")
    
    # فيديوهات مشابهة
    elif data.startswith('similar_'):
        url = data.replace('similar_', '')
        await query.edit_message_caption(
            caption="🔍 **جاري البحث عن فيديوهات مشابهة...**"
        )
        
        info = await get_video_info(url)
        if info:
            # استخراج كلمات مفتاحية من العنوان
            keywords = info['title'].split()[:3]
            search_query = ' '.join(keywords)
            await handle_search(update, context, search_query)
            await query.message.delete()
        else:
            await query.edit_message_caption(caption="❌ **لا يمكن العثور على فيديوهات مشابهة**")
    
    # القائمة الرئيسية
    elif data == "stats":
        await stats_command(update, context)
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "search_menu":
        search_text = (
            "🔍 **قائمة البحث المتقدم:**\n\n"
            "• اكتب كلمة للبحث\n"
            "• اختر المنصة:\n"
            "  📺 يوتيوب - مقاطع فيديو\n"
            "  🎵 تيك توك - مقاطع قصيرة\n"
            "  📸 انستغرام - ريلز\n\n"
            "• استخدم الفلاتر:\n"
            "  /search [كلمة] - بحث سريع\n"
            "  /trending - الأكثر مشاهدة\n"
            "  /popular - الأكثر رواجاً"
        )
        await query.edit_message_text(search_text, parse_mode='Markdown')
    
    elif data == "trending":
        await query.edit_message_text(
            "📈 **جاري جلب الأكثر مشاهدة...**",
            parse_mode='Markdown'
        )
        
        videos = await get_trending_videos('music')
        
        if videos:
            response = "📈 **الأكثر مشاهدة اليوم:**\n\n"
            for i, video in enumerate(videos, 1):
                response += f"{i}. **{video['title']}**\n"
                response += f"   👤 {video['uploader']}\n\n"
            
            await query.edit_message_text(response, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ **لا توجد نتائج**", parse_mode='Markdown')
    
    elif data == "all_platforms":
        platforms_text = "**🌐 جميع المنصات المدعومة:**\n\n"
        cols = 3
        for i, site in enumerate(sorted(ALL_SUPPORTED_SITES), 1):
            platforms_text += f"{i}. {site}\n"
        await query.edit_message_text(platforms_text, parse_mode='Markdown')
    
    elif data == "quick_download":
        quick_text = (
            "⚡ **تحميل سريع:**\n\n"
            "• أرسل الرابط مباشرة\n"
            "• سيتم التحميل بأعلى جودة\n"
            "• اختر:\n"
            "  🎬 فيديو - تلقائياً\n"
            "  🎤 بصمة - رسالة صوتية\n"
            "  🎵 MP3 - ملف موسيقى"
        )
        await query.edit_message_text(quick_text, parse_mode='Markdown')
    
    elif data.startswith('filter_'):
        query_text = data.replace('filter_', '')
        
        filter_keyboard = [
            [
                InlineKeyboardButton("📅 اليوم", callback_data=f"search_youtube_{query_text} today"),
                InlineKeyboardButton("📅 هذا الأسبوع", callback_data=f"search_youtube_{query_text} week"),
            ],
            [
                InlineKeyboardButton("🎥 جودة عالية", callback_data=f"search_youtube_{query_text} hd"),
                InlineKeyboardButton("⏱️ +10 دقائق", callback_data=f"search_youtube_{query_text} long"),
            ],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data=f"search_menu"),
            ]
        ]
        await query.edit_message_text(
            f"🔍 **اختر فلتر للبحث:** {query_text}",
            reply_markup=InlineKeyboardMarkup(filter_keyboard),
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ **حدث خطأ في البوت**\n"
                "الرجاء المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    except:
        pass

def cleanup():
    """تنظيف الملفات المؤقتة"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم التنظيف")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت الذهبي...")
    
    try:
        application = Application.builder().token(TOKEN).build()
        
        # الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("search", handle_message))
        application.add_handler(CommandHandler("trending", handle_message))
        application.add_handler(CommandHandler("popular", handle_message))
        
        # معالج الرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # معالج الأزرار
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # معالج الأخطاء
        application.add_error_handler(error_handler)
        
        print("\n" + "="*70)
        print("🤖 البوت الذهبي - النسخة النهائية الخارقة".center(70))
        print("="*70)
        print(f"📝 التوكن: {TOKEN[:15]}...")
        print(f"📁 المجلد: {DOWNLOAD_FOLDER}")
        print(f"🌐 المنصات: {len(ALL_SUPPORTED_SITES)}")
        print(f"🔍 محرك بحث: يوتيوب - تيك توك - انستغرام")
        print(f"⚡ الإصدار: 5.0 (النهائي)")
        print("="*70 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
