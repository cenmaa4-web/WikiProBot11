#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تحميل الفيديوهات من جميع المنصات - النسخة النهائية المتكاملة
يدعم: يوتيوب، تيك توك، انستقرام، فيسبوك، تويتر، بنترست، ريديت، وغيرها
المميزات: تحميل فيديو، تحميل صوت MP3، بصمة صوتية، بحث متقدم، إحصائيات
"""

import os
import sys
import logging
import asyncio
import json
import time
import shutil
import tempfile
import urllib.request
import re
import glob
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote, unquote
from typing import Optional, Dict, List, Tuple, Any

# مكتبات تيليجرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

# مكتبة تحميل الفيديوهات
import yt_dlp
from yt_dlp.utils import DownloadError

# ==================== الإعدادات الأساسية ====================

# إعداد التسجيل المتقدم
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# توكن البوت - استخدم المتغير البيئي أو التوكن المباشر
TOKEN = os.environ.get("TOKEN", "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# إنشاء المجلدات المؤقتة
BASE_DIR = tempfile.mkdtemp()
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
THUMBNAIL_DIR = os.path.join(BASE_DIR, 'thumbnails')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')

for dir_path in [DOWNLOAD_DIR, THUMBNAIL_DIR, CACHE_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ==================== قائمة المنصات المدعومة ====================

SUPPORTED_PLATFORMS = {
    'youtube': ['youtube.com', 'youtu.be', 'm.youtube.com', 'youtube-nocookie.com'],
    'tiktok': ['tiktok.com', 'vm.tiktok.com', 'www.tiktok.com'],
    'instagram': ['instagram.com', 'instagr.am', 'www.instagram.com'],
    'facebook': ['facebook.com', 'fb.watch', 'm.facebook.com', 'www.facebook.com'],
    'twitter': ['twitter.com', 'x.com', 'www.twitter.com'],
    'pinterest': ['pinterest.com', 'pin.it', 'www.pinterest.com'],
    'reddit': ['reddit.com', 'redd.it', 'www.reddit.com'],
    'linkedin': ['linkedin.com', 'www.linkedin.com'],
    'dailymotion': ['dailymotion.com', 'dai.ly', 'www.dailymotion.com'],
    'vimeo': ['vimeo.com', 'player.vimeo.com'],
    'twitch': ['twitch.tv', 'clips.twitch.tv', 'www.twitch.tv'],
    'tumblr': ['tumblr.com', 'www.tumblr.com'],
    'vk': ['vk.com', 'vkontakte.ru', 'www.vk.com'],
    'snapchat': ['snapchat.com'],
    'discord': ['discord.com', 'discordapp.com'],
    'spotify': ['spotify.com', 'open.spotify.com'],
    'soundcloud': ['soundcloud.com', 'm.soundcloud.com'],
    'rumble': ['rumble.com', 'www.rumble.com'],
    'odysee': ['odysee.com', 'www.odysee.com'],
    'bitchute': ['bitchute.com', 'www.bitchute.com'],
    'kick': ['kick.com', 'www.kick.com'],
    'threads': ['threads.net', 'www.threads.net'],
    'bluesky': ['bsky.app', 'www.bsky.app'],
    'mastodon': ['mastodon.social'],
}

# دمج جميع المنصات في قائمة واحدة
ALL_PLATFORMS = []
for platform, domains in SUPPORTED_PLATFORMS.items():
    ALL_PLATFORMS.extend(domains)

# ==================== إعدادات التحميل ====================

# إعدادات yt-dlp الأساسية
BASE_YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'socket_timeout': 30,
    'retries': 5,
    'fragment_retries': 5,
    'file_access_retries': 3,
    'extractor_retries': 3,
    'continuedl': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
}

# إعدادات التحميل حسب النوع
DOWNLOAD_CONFIGS = {
    'video': {
        'name': '🎬 فيديو',
        'format': 'best[height<=720][filesize<50M]/best[height<=480]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s_%(id)s.%(ext)s'),
    },
    'audio': {
        'name': '🎵 MP3',
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s_%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    },
    'voice': {
        'name': '🎤 بصمة صوتية',
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s_%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'ogg',
            'preferredquality': '64',
        }],
    }
}

# ==================== الإحصائيات والبيانات ====================

class BotStats:
    """كلاس إحصائيات البوت"""
    
    def __init__(self):
        self.total_downloads = 0
        self.total_searches = 0
        self.total_users = 0
        self.start_time = datetime.now()
        self.user_sessions = {}
        self.download_history = []
        
    def add_download(self, user_id: int, platform: str, size: float):
        self.total_downloads += 1
        self.download_history.append({
            'user_id': user_id,
            'platform': platform,
            'size': size,
            'time': datetime.now()
        })
        # الاحتفاظ بآخر 100 تحميل فقط
        if len(self.download_history) > 100:
            self.download_history = self.download_history[-100:]
    
    def add_search(self):
        self.total_searches += 1
    
    def add_user(self, user_id: int):
        if user_id not in self.user_sessions:
            self.total_users += 1
            self.user_sessions[user_id] = {
                'first_seen': datetime.now(),
                'downloads': 0
            }
    
    def get_uptime(self) -> str:
        delta = datetime.now() - self.start_time
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if days > 0:
            return f"{days} يوم {hours} ساعة"
        return f"{hours} ساعة {minutes} دقيقة"
    
    def get_top_users(self) -> List[Tuple[int, int]]:
        user_downloads = {}
        for download in self.download_history:
            user_id = download['user_id']
            user_downloads[user_id] = user_downloads.get(user_id, 0) + 1
        return sorted(user_downloads.items(), key=lambda x: x[1], reverse=True)[:5]

stats = BotStats()

# ==================== دوال مساعدة ====================

def format_number(num: int) -> str:
    """تنسيق الأرقام (1K, 1M)"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def format_duration(seconds: int) -> str:
    """تنسيق المدة (hh:mm:ss)"""
    if not seconds:
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def detect_platform(url: str) -> Tuple[str, str]:
    """كشف المنصة من الرابط"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    
    for platform, domains in SUPPORTED_PLATFORMS.items():
        for d in domains:
            if d in domain:
                return platform, d
    return 'unknown', domain

def is_youtube_url(url: str) -> bool:
    """التحقق من رابط يوتيوب"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return 'youtube.com' in domain or 'youtu.be' in domain

def is_supported_url(url: str) -> bool:
    """التحقق من دعم الرابط"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    
    for platform_domains in SUPPORTED_PLATFORMS.values():
        for d in platform_domains:
            if d in domain:
                return True
    return False

async def download_thumbnail(url: str, filename: str) -> Optional[str]:
    """تحميل الصورة المصغرة"""
    try:
        if not url:
            return None
        filepath = os.path.join(THUMBNAIL_DIR, f"{filename}.jpg")
        urllib.request.urlretrieve(url, filepath)
        if os.path.exists(filepath):
            return filepath
    except Exception as e:
        logger.error(f"خطأ في تحميل الصورة: {e}")
    return None

def get_file_size_mb(filepath: str) -> float:
    """حجم الملف بالميجابايت"""
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except:
        return 0

# ==================== دوال التحميل الأساسية ====================

async def download_media(url: str, media_type: str = 'video') -> Tuple[Optional[str], Optional[Dict]]:
    """
    تحميل وسائط من الرابط
    Returns: (filepath, info)
    """
    try:
        loop = asyncio.get_event_loop()
        
        def _download():
            try:
                config = DOWNLOAD_CONFIGS[media_type].copy()
                opts = BASE_YDL_OPTS.copy()
                opts.update(config)
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    
                    # تعديل الامتداد للملفات الصوتية
                    if media_type in ['audio', 'voice']:
                        ext = 'mp3' if media_type == 'audio' else 'ogg'
                        filename = filename.replace('.%(ext)s', f'.{ext}')
                        if not filename.endswith(ext):
                            filename = filename.rsplit('.', 1)[0] + f'.{ext}'
                    
                    # البحث عن الملف إذا لم يوجد
                    if not os.path.exists(filename):
                        files = glob.glob(os.path.join(DOWNLOAD_DIR, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    if os.path.exists(filename):
                        return filename, info
                    return None, None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل: {e}")
                return None, None
        
        return await loop.run_in_executor(None, _download)
        
    except Exception as e:
        logger.error(f"خطأ عام في التحميل: {e}")
        return None, None

async def get_video_info(url: str) -> Optional[Dict]:
    """جلب معلومات الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def _get_info():
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, _get_info)
        
        if info:
            return {
                'title': info.get('title', 'بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'description': info.get('description', '')[:300],
                'thumbnail': info.get('thumbnail', ''),
                'url': url,
                'upload_date': info.get('upload_date', ''),
                'channel_url': info.get('channel_url', ''),
                'tags': info.get('tags', [])[:5],
            }
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب المعلومات: {e}")
        return None

async def search_youtube(query: str, limit: int = 6) -> List[Dict]:
    """البحث المتقدم في يوتيوب"""
    try:
        loop = asyncio.get_event_loop()
        
        def _search():
            search_query = f"ytsearch{limit}:{query}"
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(search_query, download=False)
                results = []
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry and entry.get('id'):
                            results.append({
                                'id': entry.get('id'),
                                'title': entry.get('title', 'بدون عنوان')[:80],
                                'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                'duration': entry.get('duration', 0),
                                'uploader': entry.get('uploader', 'غير معروف')[:30],
                                'views': entry.get('view_count', 0),
                                'thumbnail': entry.get('thumbnail', '')
                            })
                return results
        
        return await loop.run_in_executor(None, _search)
        
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        return []

# ==================== كيبورد البوت ====================

# الكيبورد الرئيسي
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📥 تحميل فيديو"), KeyboardButton("🎵 تحميل صوت")],
        [KeyboardButton("🔍 بحث في يوتيوب"), KeyboardButton("📊 إحصائيات")],
        [KeyboardButton("❓ مساعدة"), KeyboardButton("ℹ️ عن البوت")]
    ],
    resize_keyboard=True,
    input_field_placeholder="أرسل رابط الفيديو أو كلمة البحث..."
)

# الكيبورد للبحث
SEARCH_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 بحث جديد"), KeyboardButton("📊 إحصائيات")],
        [KeyboardButton("🏠 القائمة الرئيسية")]
    ],
    resize_keyboard=True
)

# ==================== دوال عرض الرسائل ====================

async def send_youtube_menu(update: Update, url: str, info: Dict):
    """إرسال قائمة يوتيوب مع الصورة والأزرار"""
    
    # تجهيز الأزرار
    keyboard = [
        [
            InlineKeyboardButton("🎬 فيديو", callback_data=f"dl_video_{url}"),
            InlineKeyboardButton("🎵 MP3", callback_data=f"dl_audio_{url}"),
            InlineKeyboardButton("🎤 بصمة", callback_data=f"dl_voice_{url}")
        ],
        [
            InlineKeyboardButton("👁️ مشاهدة", url=url),
            InlineKeyboardButton("🔍 مشابهة", callback_data=f"similar_{url}")
        ],
        [
            InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{url}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # تجهيز النص
    duration = format_duration(info['duration'])
    views = format_number(info['views'])
    likes = format_number(info['likes'])
    
    caption = (
        f"🎬 **{info['title'][:100]}**\n\n"
        f"👤 **{info['uploader']}**\n"
        f"⏱️ **المدة:** {duration}\n"
        f"👁️ **المشاهدات:** {views}\n"
        f"❤️ **الإعجابات:** {likes}\n\n"
        f"📥 **اختر نوع التحميل:**"
    )
    
    # إرسال الصورة إن وجدت
    if info['thumbnail']:
        thumb_path = await download_thumbnail(info['thumbnail'], f"yt_{int(time.time())}")
        if thumb_path:
            with open(thumb_path, 'rb') as thumb:
                await update.message.reply_photo(
                    photo=thumb,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            os.remove(thumb_path)
            return
    
    # إرسال نص فقط إذا لم توجد صورة
    await update.message.reply_text(
        caption,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def send_search_result(update: Update, video: Dict, index: int):
    """إرسال نتيجة بحث"""
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 فيديو", callback_data=f"dl_video_{video['url']}"),
            InlineKeyboardButton("🎵 MP3", callback_data=f"dl_audio_{video['url']}"),
            InlineKeyboardButton("🎤 بصمة", callback_data=f"dl_voice_{video['url']}")
        ],
        [
            InlineKeyboardButton("👁️ مشاهدة", url=video['url'])
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    duration = format_duration(video['duration'])
    views = format_number(video['views'])
    
    caption = (
        f"{index}. **{video['title']}**\n"
        f"👤 {video['uploader']} | ⏱️ {duration} | 👁️ {views}"
    )
    
    if video['thumbnail']:
        thumb_path = await download_thumbnail(video['thumbnail'], f"search_{index}_{int(time.time())}")
        if thumb_path:
            with open(thumb_path, 'rb') as thumb:
                await update.message.reply_photo(
                    photo=thumb,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            os.remove(thumb_path)
            return
    
    await update.message.reply_text(
        caption,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ==================== معالجة الروابط ====================

async def handle_youtube_link(update: Update, url: str):
    """معالجة رابط يوتيوب"""
    msg = await update.message.reply_text("⏳ **جاري تحضير الفيديو...**", parse_mode='Markdown')
    
    info = await get_video_info(url)
    
    if not info:
        await msg.edit_text("❌ **فشل في جلب معلومات الفيديو**\nتأكد من الرابط", parse_mode='Markdown')
        return
    
    await msg.delete()
    await send_youtube_menu(update, url, info)

async def handle_direct_link(update: Update, url: str):
    """معالجة الروابط المباشرة"""
    msg = await update.message.reply_text("⏳ **جاري تحميل الفيديو...**", parse_mode='Markdown')
    
    file_path, info = await download_media(url, 'video')
    
    if not file_path:
        await msg.edit_text("❌ **فشل التحميل**\nتأكد من الرابط", parse_mode='Markdown')
        return
    
    size = get_file_size_mb(file_path)
    
    if size > 50:
        await msg.edit_text(f"❌ **الفيديو كبير جداً**\nالحجم: {size:.1f} MB", parse_mode='Markdown')
        os.remove(file_path)
        return
    
    await msg.delete()
    
    with open(file_path, 'rb') as f:
        await update.message.reply_video(
            video=f,
            caption=f"✅ **تم التحميل بنجاح!**\n📊 {size:.1f} MB",
            supports_streaming=True
        )
    
    os.remove(file_path)
    
    platform, _ = detect_platform(url)
    stats.add_download(update.effective_user.id, platform, size)

# ==================== البحث ====================

async def handle_search(update: Update, query: str):
    """معالجة البحث"""
    stats.add_search()
    
    msg = await update.message.reply_text(f"🔍 **جاري البحث عن:** {query}", parse_mode='Markdown')
    
    videos = await search_youtube(query)
    
    if not videos:
        await msg.edit_text("❌ **لا توجد نتائج**\nجرب كلمات أخرى", parse_mode='Markdown')
        return
    
    await msg.delete()
    
    for i, video in enumerate(videos, 1):
        await send_search_result(update, video, i)

# ==================== معالجة الأزرار ====================

async def handle_download_button(update: Update, media_type: str, url: str):
    """معالجة أزرار التحميل"""
    query = update.callback_query
    await query.edit_message_caption(
        caption=f"⏳ **جاري تحميل {DOWNLOAD_CONFIGS[media_type]['name']}...**",
        parse_mode='Markdown'
    )
    
    file_path, info = await download_media(url, media_type)
    
    if not file_path:
        await query.edit_message_caption(
            caption="❌ **فشل التحميل**\nحاول مرة أخرى",
            parse_mode='Markdown'
        )
        return
    
    size = get_file_size_mb(file_path)
    
    with open(file_path, 'rb') as f:
        if media_type == 'video':
            await query.message.reply_video(
                video=f,
                caption=f"✅ **تم التحميل!**\n📊 {size:.1f} MB",
                supports_streaming=True
            )
        elif media_type == 'audio':
            await query.message.reply_audio(
                audio=f,
                caption=f"✅ **ملف MP3**\n📊 {size:.1f} MB"
            )
        elif media_type == 'voice':
            await query.message.reply_voice(
                voice=f,
                caption=f"✅ **بصمة صوتية**\n📊 {size:.1f} MB"
            )
    
    os.remove(file_path)
    
    platform, _ = detect_platform(url)
    stats.add_download(query.from_user.id, platform, size)
    
    # استعادة الرسالة الأصلية
    await query.edit_message_caption(
        caption=query.message.caption_html,
        parse_mode='HTML'
    )

async def handle_similar_button(update: Update, url: str):
    """معالجة زر الفيديوهات المشابهة"""
    query = update.callback_query
    await query.edit_message_caption(
        caption="🔍 **جاري البحث عن فيديوهات مشابهة...**",
        parse_mode='Markdown'
    )
    
    info = await get_video_info(url)
    if info:
        # استخراج كلمات مفتاحية من العنوان
        keywords = info['title'].split()[:4]
        search_query = ' '.join(keywords)
        
        # إرسال نتائج البحث
        videos = await search_youtube(search_query, limit=4)
        
        if videos:
            await query.message.reply_text("🔍 **نتائج مشابهة:**", parse_mode='Markdown')
            for i, video in enumerate(videos, 1):
                await send_search_result(update, video, i)
        
        await query.edit_message_caption(
            caption=query.message.caption_html,
            parse_mode='HTML'
        )
    else:
        await query.edit_message_caption(
            caption="❌ **لا يمكن العثور على فيديوهات مشابهة**",
            parse_mode='Markdown'
        )

async def handle_info_button(update: Update, url: str):
    """معالجة زر المعلومات"""
    query = update.callback_query
    await query.edit_message_caption(
        caption="⏳ **جاري جلب المعلومات...**",
        parse_mode='Markdown'
    )
    
    info = await get_video_info(url)
    
    if info:
        duration = format_duration(info['duration'])
        views = format_number(info['views'])
        likes = format_number(info['likes'])
        
        info_text = (
            f"ℹ️ **معلومات الفيديو**\n\n"
            f"**العنوان:** {info['title']}\n\n"
            f"**الناشر:** {info['uploader']}\n"
            f"**المدة:** {duration}\n"
            f"**المشاهدات:** {views}\n"
            f"**الإعجابات:** {likes}\n"
            f"**تاريخ الرفع:** {info['upload_date']}\n\n"
            f"**الوسوم:** {', '.join(info['tags']) if info['tags'] else 'لا يوجد'}\n\n"
            f"**الوصف:**\n{info['description'][:200]}..."
        )
        
        await query.edit_message_caption(
            caption=info_text,
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_caption(
            caption="❌ **لا يمكن جلب المعلومات**",
            parse_mode='Markdown'
        )

# ==================== معالج الأزرار الرئيسي ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج جميع الأزرار"""
    query = update.callback_query
    data = query.data
    
    if data.startswith('dl_'):
        parts = data.split('_', 2)
        if len(parts) >= 3:
            media_type = parts[1]
            url = parts[2]
            await handle_download_button(update, media_type, url)
    
    elif data.startswith('similar_'):
        url = data.replace('similar_', '')
        await handle_similar_button(update, url)
    
    elif data.startswith('info_'):
        url = data.replace('info_', '')
        await handle_info_button(update, url)

# ==================== معالج أزرار الكيبورد ====================

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار الـ Reply Keyboard"""
    text = update.message.text
    
    if text == "📥 تحميل فيديو":
        await update.message.reply_text(
            "📥 **أرسل رابط الفيديو:**\n\n"
            "يدعم: يوتيوب، تيك توك، انستقرام، فيسبوك، بنترست، تويتر",
            parse_mode='Markdown'
        )
    
    elif text == "🎵 تحميل صوت":
        await update.message.reply_text(
            "🎵 **أرسل رابط يوتيوب:**\n\n"
            "سيتم تحويل الفيديو إلى MP3",
            parse_mode='Markdown'
        )
    
    elif text == "🔍 بحث في يوتيوب":
        await update.message.reply_text(
            "🔍 **اكتب كلمة البحث:**\n\n"
            "مثال: 'أغاني حزينة' أو 'مقاطع مضحكة'",
            parse_mode='Markdown',
            reply_markup=SEARCH_KEYBOARD
        )
    
    elif text == "📊 إحصائيات":
        uptime = stats.get_uptime()
        top_users = stats.get_top_users()
        
        stats_text = (
            f"📊 **إحصائيات البوت**\n\n"
            f"📥 **التحميلات:** {stats.total_downloads}\n"
            f"🔍 **عمليات البحث:** {stats.total_searches}\n"
            f"👥 **المستخدمين:** {stats.total_users}\n"
            f"⏱️ **وقت التشغيل:** {uptime}\n"
            f"🌐 **المنصات المدعومة:** {len(ALL_PLATFORMS)}\n\n"
        )
        
        if top_users:
            stats_text += "🏆 **أكثر المستخدمين نشاطاً:**\n"
            for i, (user_id, count) in enumerate(top_users, 1):
                stats_text += f"{i}. ID: {user_id} - {count} تحميل\n"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    elif text == "❓ مساعدة":
        help_text = (
            "🆘 **المساعدة**\n\n"
            "**📥 تحميل فيديو:**\n"
            "• أرسل رابط الفيديو مباشرة\n"
            "• يدعم جميع المنصات\n\n"
            "**🎵 تحميل صوت:**\n"
            "• أرسل رابط يوتيوب\n"
            "• يحول إلى MP3\n\n"
            "**🔍 بحث في يوتيوب:**\n"
            "• اكتب كلمة البحث\n"
            "• تظهر 6 نتائج مع صور\n\n"
            "**📊 الإحصائيات:**\n"
            "• عرض إحصائيات البوت\n\n"
            "**ℹ️ عن البوت:**\n"
            "• معلومات عن الإصدار"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    elif text == "ℹ️ عن البوت":
        about_text = (
            "ℹ️ **عن البوت**\n\n"
            "**الاسم:** بوت تحميل الفيديوهات\n"
            "**الإصدار:** 5.0 (النهائي المتكامل)\n"
            "**المنصات:** {}\n\n"
            "**المميزات:**\n"
            "• تحميل فيديو من جميع المنصات\n"
            "• تحميل MP3 من يوتيوب\n"
            "• بصمة صوتية\n"
            "• بحث متقدم في يوتيوب\n"
            "• إحصائيات دقيقة\n\n"
            "🚀 **استمتع بالتحميل السريع!**".format(len(ALL_PLATFORMS))
        )
        await update.message.reply_text(about_text, parse_mode='Markdown')
    
    elif text == "🔍 بحث جديد":
        await update.message.reply_text(
            "🔍 **اكتب كلمة البحث:**",
            parse_mode='Markdown'
        )
    
    elif text == "🏠 القائمة الرئيسية":
        await update.message.reply_text(
            "🏠 **القائمة الرئيسية**",
            parse_mode='Markdown',
            reply_markup=MAIN_KEYBOARD
        )

# ==================== المعالج الرئيسي للرسائل ====================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالج الرئيسي لجميع الرسائل"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # تسجيل المستخدم
    stats.add_user(user_id)
    
    # أزرار الكيبورد
    if text in ["📥 تحميل فيديو", "🎵 تحميل صوت", "🔍 بحث في يوتيوب", 
                "📊 إحصائيات", "❓ مساعدة", "ℹ️ عن البوت",
                "🔍 بحث جديد", "🏠 القائمة الرئيسية"]:
        await reply_keyboard_handler(update, context)
        return
    
    # روابط
    if text.startswith(('http://', 'https://')):
        if not is_supported_url(text):
            await update.message.reply_text(
                "⚠️ **الرابط غير مدعوم**\n\n"
                f"المنصات المدعومة: {', '.join([p for p in SUPPORTED_PLATFORMS.keys()])}",
                parse_mode='Markdown',
                reply_markup=MAIN_KEYBOARD
            )
            return
        
        if is_youtube_url(text):
            await handle_youtube_link(update, text)
        else:
            await handle_direct_link(update, text)
        return
    
    # بحث
    if len(text) >= 3:
        await handle_search(update, text)
    else:
        await update.message.reply_text(
            "❌ **كلمة البحث قصيرة جداً**\nاكتب كلمة أطول من حرفين",
            parse_mode='Markdown',
            reply_markup=MAIN_KEYBOARD
        )

# ==================== أوامر البوت ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    user_id = update.effective_user.id
    stats.add_user(user_id)
    
    welcome_text = (
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات!**\n\n"
        "📥 **أرسل رابط الفيديو أو استخدم الأزرار أدناه**\n\n"
        f"✅ **المنصات المدعومة:** {len(SUPPORTED_PLATFORMS)} منصة\n"
        "• يوتيوب - تيك توك - انستقرام\n"
        "• فيسبوك - تويتر - بنترست\n"
        "• ريديت - لينكدإن - دايليموشن\n"
        "• فيميو - تويش - وغيرها\n\n"
        "✨ **جرب الآن!**"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /help"""
    help_text = (
        "🆘 **المساعدة**\n\n"
        "**📥 تحميل فيديو:**\n"
        "أرسل رابط الفيديو مباشرة\n\n"
        "**🎵 تحميل صوت:**\n"
        "أرسل رابط يوتيوب للتحويل إلى MP3\n\n"
        "**🔍 بحث في يوتيوب:**\n"
        "اكتب كلمة البحث\n\n"
        "**📊 إحصائيات:**\n"
        "عرض إحصائيات البوت\n\n"
        "**الأوامر:**\n"
        "/start - البداية\n"
        "/help - المساعدة\n"
        "/stats - الإحصائيات"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=MAIN_KEYBOARD)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /stats"""
    uptime = stats.get_uptime()
    top_users = stats.get_top_users()
    
    stats_text = (
        f"📊 **إحصائيات البوت**\n\n"
        f"📥 **التحميلات:** {stats.total_downloads}\n"
        f"🔍 **عمليات البحث:** {stats.total_searches}\n"
        f"👥 **المستخدمين:** {stats.total_users}\n"
        f"⏱️ **وقت التشغيل:** {uptime}\n"
        f"🌐 **المنصات المدعومة:** {len(ALL_PLATFORMS)}\n"
    )
    
    if top_users:
        stats_text += "\n🏆 **أكثر المستخدمين نشاطاً:**\n"
        for i, (user_id, count) in enumerate(top_users, 1):
            stats_text += f"{i}. ID: {user_id} - {count} تحميل\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown', reply_markup=MAIN_KEYBOARD)

# ==================== معالجة الأخطاء ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    logger.error(f"خطأ: {context.error}")
    
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ **حدث خطأ في البوت**\nالرجاء المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    except:
        pass

# ==================== التنظيف والإغلاق ====================

def cleanup():
    """تنظيف الملفات المؤقتة"""
    try:
        shutil.rmtree(BASE_DIR)
        logger.info("✅ تم تنظيف الملفات المؤقتة")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

# ==================== التشغيل الرئيسي ====================

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    print("\n" + "="*70)
    print("🤖 بوت تحميل الفيديوهات - النسخة النهائية المتكاملة".center(70))
    print("="*70)
    print(f"📁 المجلد المؤقت: {BASE_DIR}")
    print(f"🌐 المنصات المدعومة: {len(SUPPORTED_PLATFORMS)} منصة")
    print(f"📝 التوكن: {TOKEN[:20]}...")
    print("="*70 + "\n")
    
    logger.info("🚀 بدء تشغيل البوت...")
    
    try:
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة الأوامر
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # إضافة معالج الرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        # إضافة معالج الأزرار
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # تشغيل البوت
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except KeyboardInterrupt:
        logger.info("👋 إيقاف البوت...")
    except Exception as e:
        logger.error(f"خطأ fatal: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
