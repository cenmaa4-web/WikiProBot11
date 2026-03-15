#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي المتكامل
Version: 7.0.0
Author: Professional Developer
"""

import os
import sys
import json
import logging
import asyncio
import subprocess
import re
import time
import random
import string
import hashlib
import html
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import defaultdict, deque
from urllib.parse import urlparse, quote, unquote
import shutil
import platform
import signal
import gc
import math
import socket
import secrets

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes,
    ConversationHandler
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن الصحيح هنا
BOT_VERSION = "7.0.0"
BOT_RELEASE_DATE = "2024-03-16"

# ==================== إنشاء المجلدات ====================
BASE_DIR = Path(__file__).parent.absolute()
DOWNLOAD_DIR = BASE_DIR / "downloads"
THUMBNAIL_DIR = BASE_DIR / "thumbnails"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"
CACHE_DIR = BASE_DIR / "cache"

for directory in [DOWNLOAD_DIR, THUMBNAIL_DIR, LOGS_DIR, DATA_DIR, TEMP_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ملفات البيانات
USERS_FILE = DATA_DIR / "users.json"
STATS_FILE = DATA_DIR / "stats.json"
DOWNLOADS_FILE = DATA_DIR / "downloads.json"
CONFIG_FILE = DATA_DIR / "config.json"
FAVORITES_FILE = DATA_DIR / "favorites.json"
WATCH_LATER_FILE = DATA_DIR / "watch_later.json"
HISTORY_FILE = DATA_DIR / "history.json"
ERRORS_FILE = DATA_DIR / "errors.json"

# ==================== إعداد التسجيل ====================
LOG_FILE = LOGS_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
ERROR_LOG_FILE = LOGS_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== الإعدادات العامة ====================
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2 GB
MAX_DURATION = 43200  # 12 ساعة
MAX_SEARCH_RESULTS = 10
MAX_HISTORY_ITEMS = 200
MAX_FAVORITES = 100
MAX_WATCH_LATER = 100
CONCURRENT_DOWNLOADS = 3
RATE_LIMIT = 15  # طلب في الثانية
RATE_LIMIT_WINDOW = 60  # ثانية
DOWNLOAD_TIMEOUT = 300  # 5 دقائق
CACHE_TTL = 3600  # ساعة واحدة

# حالات المحادثة
(
    MAIN_MENU, 
    BROWSE_MENU, 
    SEARCH_MENU, 
    DOWNLOAD_MENU, 
    QUALITY_SELECTION, 
    FORMAT_SELECTION,
    SETTINGS_MENU, 
    FAVORITES_MENU, 
    WATCH_LATER_MENU, 
    HISTORY_MENU,
    PLAYLIST_MENU,
    ADMIN_MENU
) = range(12)

# ==================== جودات الفيديو ====================
VIDEO_QUALITIES = {
    '144': {'name': '144p', 'name_ar': '١٤٤ بكسل', 'emoji': '📱', 'height': 144, 'bitrate': '100k'},
    '240': {'name': '240p', 'name_ar': '٢٤٠ بكسل', 'emoji': '📱', 'height': 240, 'bitrate': '200k'},
    '360': {'name': '360p', 'name_ar': '٣٦٠ بكسل', 'emoji': '📺', 'height': 360, 'bitrate': '500k'},
    '480': {'name': '480p', 'name_ar': '٤٨٠ بكسل', 'emoji': '📺', 'height': 480, 'bitrate': '1000k'},
    '720': {'name': '720p HD', 'name_ar': '٧٢٠ بكسل', 'emoji': '🎬', 'height': 720, 'bitrate': '2500k'},
    '1080': {'name': '1080p FHD', 'name_ar': '١٠٨٠ بكسل', 'emoji': '🎥', 'height': 1080, 'bitrate': '5000k'},
    '1440': {'name': '2K QHD', 'name_ar': '٢ كيه', 'emoji': '🎥', 'height': 1440, 'bitrate': '10000k'},
    '2160': {'name': '4K UHD', 'name_ar': '٤ كيه', 'emoji': '🎥', 'height': 2160, 'bitrate': '20000k'},
    'best': {'name': 'Best Quality', 'name_ar': 'أفضل جودة', 'emoji': '🏆', 'height': 9999, 'bitrate': 'best'}
}

# ==================== صيغ التحميل ====================
DOWNLOAD_FORMATS = {
    'mp4': {'name': 'MP4 Video', 'name_ar': 'فيديو MP4', 'emoji': '🎬', 'ext': 'mp4', 'mime': 'video/mp4'},
    'mp3': {'name': 'MP3 Audio', 'name_ar': 'صوت MP3', 'emoji': '🎵', 'ext': 'mp3', 'mime': 'audio/mpeg'},
    'webm': {'name': 'WEBM', 'name_ar': 'ويب إم', 'emoji': '🌐', 'ext': 'webm', 'mime': 'video/webm'},
    'mkv': {'name': 'MKV', 'name_ar': 'إم كيه في', 'emoji': '📦', 'ext': 'mkv', 'mime': 'video/x-matroska'},
    'avi': {'name': 'AVI', 'name_ar': 'إيه في آي', 'emoji': '💾', 'ext': 'avi', 'mime': 'video/x-msvideo'},
    'mov': {'name': 'MOV', 'name_ar': 'إم أو في', 'emoji': '🍎', 'ext': 'mov', 'mime': 'video/quicktime'},
    'flv': {'name': 'FLV', 'name_ar': 'إف إل في', 'emoji': '⚡', 'ext': 'flv', 'mime': 'video/x-flv'},
    'wav': {'name': 'WAV', 'name_ar': 'دبليو إيه في', 'emoji': '🎼', 'ext': 'wav', 'mime': 'audio/wav'},
    'flac': {'name': 'FLAC', 'name_ar': 'إف إل إيه سي', 'emoji': '💿', 'ext': 'flac', 'mime': 'audio/flac'},
    'ogg': {'name': 'OGG', 'name_ar': 'أو جي جي', 'emoji': '🔊', 'ext': 'ogg', 'mime': 'audio/ogg'},
    'm4a': {'name': 'M4A', 'name_ar': 'إم ٤ إيه', 'emoji': '🎧', 'ext': 'm4a', 'mime': 'audio/mp4'},
}

# ==================== فئات الفيديو ====================
VIDEO_CATEGORIES = {
    'trending': {'name': '🔥 Trending', 'name_ar': 'الأكثر مشاهدة', 'query': 'trending', 'emoji': '🔥'},
    'music': {'name': '🎵 Music', 'name_ar': 'موسيقى', 'query': 'music video', 'emoji': '🎵'},
    'gaming': {'name': '🎮 Gaming', 'name_ar': 'ألعاب', 'query': 'gaming', 'emoji': '🎮'},
    'news': {'name': '📰 News', 'name_ar': 'أخبار', 'query': 'news today', 'emoji': '📰'},
    'sports': {'name': '⚽ Sports', 'name_ar': 'رياضة', 'query': 'sports highlights', 'emoji': '⚽'},
    'education': {'name': '📚 Education', 'name_ar': 'تعليم', 'query': 'educational', 'emoji': '📚'},
    'technology': {'name': '💻 Technology', 'name_ar': 'تكنولوجيا', 'query': 'tech reviews', 'emoji': '💻'},
    'entertainment': {'name': '🎭 Entertainment', 'name_ar': 'ترفيه', 'query': 'entertainment', 'emoji': '🎭'},
    'comedy': {'name': '😄 Comedy', 'name_ar': 'كوميديا', 'query': 'comedy', 'emoji': '😄'},
    'movies': {'name': '🎬 Movies', 'name_ar': 'أفلام', 'query': 'movie trailers', 'emoji': '🎬'},
    'animation': {'name': '🖌️ Animation', 'name_ar': 'أنميشن', 'query': 'animation', 'emoji': '🖌️'},
    'documentary': {'name': '📽️ Documentary', 'name_ar': 'وثائقيات', 'query': 'documentary', 'emoji': '📽️'},
    'cooking': {'name': '🍳 Cooking', 'name_ar': 'طبخ', 'query': 'cooking recipes', 'emoji': '🍳'},
    'travel': {'name': '✈️ Travel', 'name_ar': 'سفر', 'query': 'travel vlog', 'emoji': '✈️'},
    'fashion': {'name': '👗 Fashion', 'name_ar': 'موضة', 'query': 'fashion', 'emoji': '👗'},
    'beauty': {'name': '💄 Beauty', 'name_ar': 'تجميل', 'query': 'beauty tips', 'emoji': '💄'},
    'fitness': {'name': '💪 Fitness', 'name_ar': 'لياقة', 'query': 'fitness workout', 'emoji': '💪'},
    'science': {'name': '🔬 Science', 'name_ar': 'علوم', 'query': 'science', 'emoji': '🔬'},
    'history': {'name': '📜 History', 'name_ar': 'تاريخ', 'query': 'history', 'emoji': '📜'},
    'art': {'name': '🎨 Art', 'name_ar': 'فن', 'query': 'art tutorial', 'emoji': '🎨'},
}

# ==================== المنصات المدعومة ====================
SUPPORTED_PLATFORMS = {
    'youtube': {'name': 'YouTube', 'name_ar': 'يوتيوب', 'emoji': '📺', 'pattern': r'(youtube\.com|youtu\.be)'},
    'instagram': {'name': 'Instagram', 'name_ar': 'انستغرام', 'emoji': '📷', 'pattern': r'(instagram\.com)'},
    'facebook': {'name': 'Facebook', 'name_ar': 'فيسبوك', 'emoji': '📘', 'pattern': r'(facebook\.com|fb\.watch)'},
    'twitter': {'name': 'Twitter', 'name_ar': 'تويتر', 'emoji': '🐦', 'pattern': r'(twitter\.com|x\.com)'},
    'tiktok': {'name': 'TikTok', 'name_ar': 'تيك توك', 'emoji': '🎵', 'pattern': r'(tiktok\.com)'},
    'reddit': {'name': 'Reddit', 'name_ar': 'ريديت', 'emoji': '👽', 'pattern': r'(reddit\.com)'},
    'vimeo': {'name': 'Vimeo', 'name_ar': 'فيميو', 'emoji': '🎥', 'pattern': r'(vimeo\.com)'},
    'twitch': {'name': 'Twitch', 'name_ar': 'تويش', 'emoji': '🎮', 'pattern': r'(twitch\.tv)'},
    'dailymotion': {'name': 'Dailymotion', 'name_ar': 'ديلي موشن', 'emoji': '📺', 'pattern': r'(dailymotion\.com)'},
    'soundcloud': {'name': 'SoundCloud', 'name_ar': 'ساوند كلاود', 'emoji': '🎵', 'pattern': r'(soundcloud\.com)'},
    'pinterest': {'name': 'Pinterest', 'name_ar': 'بنترست', 'emoji': '📌', 'pattern': r'(pinterest\.com)'},
    'linkedin': {'name': 'LinkedIn', 'name_ar': 'لينكد إن', 'emoji': '💼', 'pattern': r'(linkedin\.com)'},
}

# ==================== دوال مساعدة ====================
def format_time(seconds: int) -> str:
    """تنسيق الوقت"""
    if not seconds:
        return "00:00"
    try:
        seconds = int(seconds)
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if days > 0:
            return f"{days}يوم {hours:02d}:{minutes:02d}:{secs:02d}"
        elif hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    except:
        return "00:00"

def format_size(size_bytes: int) -> str:
    """تنسيق الحجم"""
    if size_bytes == 0:
        return "0 B"
    try:
        size_names = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.2f} {size_names[i]}"
    except:
        return "0 B"

def format_number(num: int) -> str:
    """تنسيق الأرقام"""
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def get_platform_info(url: str) -> Dict:
    """الحصول على معلومات المنصة من الرابط"""
    url_lower = url.lower()
    for platform_id, info in SUPPORTED_PLATFORMS.items():
        if re.search(info['pattern'], url_lower):
            return {
                'id': platform_id,
                'name': info['name'],
                'name_ar': info['name_ar'],
                'emoji': info['emoji']
            }
    return {
        'id': 'unknown',
        'name': 'Unknown',
        'name_ar': 'غير معروفة',
        'emoji': '🌐'
    }

def escape_markdown(text: str) -> str:
    """تنظيف النص من أحرف الماركداون"""
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def create_progress_bar(percentage: float, width: int = 10) -> str:
    """إنشاء شريط تقدم"""
    filled = int(width * percentage / 100)
    empty = width - filled
    return '█' * filled + '░' * empty

def generate_id() -> str:
    """توليد معرف فريد"""
    return hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest()[:8]

# ==================== مدير قاعدة البيانات ====================
class DatabaseManager:
    def __init__(self):
        self.data = {}
        self.locks = defaultdict(asyncio.Lock)
        self.cache = {}
        self.cache_ttl = 300  # 5 دقائق
        self.load_all()
    
    def load_all(self):
        """تحميل جميع قواعد البيانات"""
        for file_path in [USERS_FILE, STATS_FILE, DOWNLOADS_FILE, CONFIG_FILE, 
                          FAVORITES_FILE, WATCH_LATER_FILE, HISTORY_FILE, ERRORS_FILE]:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.data[str(file_path)] = json.load(f)
                except Exception as e:
                    logger.error(f"خطأ في تحميل {file_path}: {e}")
                    self.data[str(file_path)] = {}
            else:
                self.data[str(file_path)] = {}
    
    async def save(self, file_path: Path):
        """حفظ قاعدة البيانات"""
        async with self.locks[str(file_path)]:
            try:
                # حفظ في ملف مؤقت أولاً
                temp_file = file_path.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data.get(str(file_path), {}), f, ensure_ascii=False, indent=2, default=str)
                
                # نقل الملف المؤقت إلى الملف الأصلي
                temp_file.replace(file_path)
                
            except Exception as e:
                logger.error(f"خطأ في حفظ {file_path}: {e}")
    
    async def get(self, file_path: Path, key: str = None, default: Any = None) -> Any:
        """الحصول على قيمة"""
        # التحقق من الكاش
        cache_key = f"{file_path}_{key}"
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return data
        
        data = self.data.get(str(file_path), {})
        if key is None:
            result = data
        else:
            result = data.get(key, default)
        
        # تحديث الكاش
        self.cache[cache_key] = (time.time(), result)
        return result
    
    async def set(self, file_path: Path, key: str, value: Any):
        """تعيين قيمة"""
        if str(file_path) not in self.data:
            self.data[str(file_path)] = {}
        self.data[str(file_path)][key] = value
        await self.save(file_path)
        
        # تحديث الكاش
        cache_key = f"{file_path}_{key}"
        self.cache[cache_key] = (time.time(), value)
    
    async def update(self, file_path: Path, key: str, updates: Dict):
        """تحديث قيمة"""
        current = await self.get(file_path, key, {})
        if isinstance(current, dict):
            current.update(updates)
            await self.set(file_path, key, current)
    
    async def delete(self, file_path: Path, key: str):
        """حذف قيمة"""
        if str(file_path) in self.data and key in self.data[str(file_path)]:
            del self.data[str(file_path)][key]
            await self.save(file_path)
            
            # حذف من الكاش
            cache_key = f"{file_path}_{key}"
            if cache_key in self.cache:
                del self.cache[cache_key]
    
    async def increment(self, file_path: Path, key: str, field: str, amount: int = 1):
        """زيادة قيمة رقمية"""
        data = await self.get(file_path, key, {})
        if isinstance(data, dict):
            data[field] = data.get(field, 0) + amount
            await self.set(file_path, key, data)
    
    async def get_all(self, file_path: Path) -> Dict:
        """الحصول على جميع البيانات"""
        return self.data.get(str(file_path), {})
    
    async def query(self, file_path: Path, condition: callable) -> List[Tuple[str, Any]]:
        """الاستعلام عن البيانات بشرط"""
        data = self.data.get(str(file_path), {})
        return [(k, v) for k, v in data.items() if condition(k, v)]
    
    async def backup(self) -> Path:
        """إنشاء نسخة احتياطية"""
        backup_dir = BASE_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        
        for file_path in [USERS_FILE, STATS_FILE, DOWNLOADS_FILE, CONFIG_FILE,
                          FAVORITES_FILE, WATCH_LATER_FILE, HISTORY_FILE]:
            if file_path.exists():
                shutil.copy2(file_path, backup_path / file_path.name)
        
        logger.info(f"تم إنشاء نسخة احتياطية في {backup_path}")
        return backup_path
    
    async def cleanup_cache(self):
        """تنظيف الكاش القديم"""
        now = time.time()
        expired = [k for k, (t, _) in self.cache.items() if now - t > self.cache_ttl * 2]
        for k in expired:
            del self.cache[k]

# ==================== مدير المستخدمين ====================
class UserManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.active_users = defaultdict(int)
    
    async def get_user(self, user_id: int) -> Dict:
        """الحصول على بيانات المستخدم"""
        user_id = str(user_id)
        
        # الحصول من قاعدة البيانات
        user_data = await self.db.get(USERS_FILE, user_id, {})
        
        # إنشاء مستخدم جديد إذا لم يكن موجوداً
        if not user_data:
            user_data = {
                'user_id': user_id,
                'joined_date': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'username': None,
                'first_name': None,
                'last_name': None,
                'language_code': 'ar',
                'is_premium': False,
                'is_banned': False,
                'is_admin': False,
                'download_count': 0,
                'total_downloads': 0,
                'total_size': 0,
                'favorites_count': 0,
                'watch_later_count': 0,
                'search_count': 0,
                'settings': {
                    'default_quality': 'best',
                    'default_format': 'mp4',
                    'auto_delete': True,
                    'notifications': True,
                    'dark_mode': True,
                    'save_history': True,
                    'language': 'ar',
                    'thumbnail_enabled': True,
                    'metadata_enabled': True
                },
                'stats': {
                    'videos_downloaded': 0,
                    'audios_downloaded': 0,
                    'playlists_downloaded': 0,
                    'searches_performed': 0,
                    'favorites_added': 0,
                    'watch_later_added': 0
                },
                'daily_limits': {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'downloads': 0,
                    'size': 0,
                    'searches': 0
                },
                'badges': ['new'],
                'achievements': [],
                'points': 0,
                'level': 1,
                'xp': 0,
                'next_level_xp': 100
            }
            await self.db.set(USERS_FILE, user_id, user_data)
        
        # تحديث آخر نشاط
        self.active_users[user_id] = time.time()
        
        return user_data
    
    async def update_user(self, user_id: int, updates: Dict):
        """تحديث بيانات المستخدم"""
        user_id = str(user_id)
        await self.db.update(USERS_FILE, user_id, updates)
    
    async def add_to_history(self, user_id: int, video_info: Dict):
        """إضافة فيديو للسجل"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        if not user_data.get('settings', {}).get('save_history', True):
            return
        
        history_file = HISTORY_FILE
        history = await self.db.get(history_file, user_id, [])
        
        history.append({
            'id': generate_id(),
            'date': datetime.now().isoformat(),
            'title': video_info.get('title', 'Unknown'),
            'url': video_info.get('url', ''),
            'platform': video_info.get('extractor', 'Unknown'),
            'duration': video_info.get('duration', 0),
            'thumbnail': video_info.get('thumbnail', ''),
            'uploader': video_info.get('uploader', 'Unknown'),
            'views': video_info.get('view_count', 0)
        })
        
        # الاحتفاظ بآخر 200 عنصر
        if len(history) > MAX_HISTORY_ITEMS:
            history = history[-MAX_HISTORY_ITEMS:]
        
        await self.db.set(history_file, user_id, history)
    
    async def get_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """الحصول على سجل المستخدم"""
        user_id = str(user_id)
        history = await self.db.get(HISTORY_FILE, user_id, [])
        return history[-limit:]
    
    async def add_to_favorites(self, user_id: int, video_info: Dict) -> bool:
        """إضافة فيديو للمفضلة"""
        user_id = str(user_id)
        
        favorites = await self.db.get(FAVORITES_FILE, user_id, [])
        url = video_info.get('url', '')
        
        # التحقق من عدم التكرار
        if not any(f.get('url') == url for f in favorites):
            if len(favorites) >= MAX_FAVORITES:
                return False
            
            favorites.append({
                'id': generate_id(),
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'thumbnail': video_info.get('thumbnail', ''),
                'uploader': video_info.get('uploader', 'Unknown'),
                'notes': ''
            })
            
            await self.db.set(FAVORITES_FILE, user_id, favorites)
            
            # تحديث إحصائيات المستخدم
            user_data = await self.get_user(user_id)
            stats = user_data.get('stats', {})
            stats['favorites_added'] = stats.get('favorites_added', 0) + 1
            await self.update_user(user_id, {
                'favorites_count': len(favorites),
                'stats': stats
            })
            
            return True
        return False
    
    async def remove_from_favorites(self, user_id: int, url: str):
        """إزالة فيديو من المفضلة"""
        user_id = str(user_id)
        
        favorites = await self.db.get(FAVORITES_FILE, user_id, [])
        favorites = [f for f in favorites if f.get('url') != url]
        
        await self.db.set(FAVORITES_FILE, user_id, favorites)
        await self.update_user(user_id, {'favorites_count': len(favorites)})
    
    async def get_favorites(self, user_id: int) -> List[Dict]:
        """الحصول على قائمة المفضلة"""
        user_id = str(user_id)
        return await self.db.get(FAVORITES_FILE, user_id, [])
    
    async def add_to_watch_later(self, user_id: int, video_info: Dict) -> bool:
        """إضافة فيديو للمشاهدة لاحقاً"""
        user_id = str(user_id)
        
        watch_later = await self.db.get(WATCH_LATER_FILE, user_id, [])
        url = video_info.get('url', '')
        
        if not any(w.get('url') == url for w in watch_later):
            if len(watch_later) >= MAX_WATCH_LATER:
                return False
            
            watch_later.append({
                'id': generate_id(),
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'thumbnail': video_info.get('thumbnail', ''),
                'uploader': video_info.get('uploader', 'Unknown'),
                'priority': 'medium',
                'reminder': None
            })
            
            await self.db.set(WATCH_LATER_FILE, user_id, watch_later)
            
            # تحديث إحصائيات المستخدم
            user_data = await self.get_user(user_id)
            stats = user_data.get('stats', {})
            stats['watch_later_added'] = stats.get('watch_later_added', 0) + 1
            await self.update_user(user_id, {
                'watch_later_count': len(watch_later),
                'stats': stats
            })
            
            return True
        return False
    
    async def get_watch_later(self, user_id: int) -> List[Dict]:
        """الحصول على قائمة المشاهدة لاحقاً"""
        user_id = str(user_id)
        return await self.db.get(WATCH_LATER_FILE, user_id, [])
    
    async def add_xp(self, user_id: int, xp: int):
        """إضافة نقاط خبرة للمستخدم"""
        user_data = await self.get_user(user_id)
        
        current_xp = user_data.get('xp', 0)
        current_level = user_data.get('level', 1)
        next_level_xp = user_data.get('next_level_xp', 100)
        
        new_xp = current_xp + xp
        new_level = current_level
        
        # التحقق من زيادة المستوى
        while new_xp >= next_level_xp:
            new_level += 1
            new_xp -= next_level_xp
            next_level_xp = int(next_level_xp * 1.5)
        
        await self.update_user(user_id, {
            'xp': new_xp,
            'level': new_level,
            'next_level_xp': next_level_xp
        })
    
    async def check_daily_limit(self, user_id: int, file_size: int) -> Tuple[bool, str]:
        """التحقق من الحدود اليومية"""
        user_data = await self.get_user(user_id)
        
        today = datetime.now().strftime('%Y-%m-%d')
        limits = user_data.get('daily_limits', {})
        
        if limits.get('date') != today:
            limits = {
                'date': today,
                'downloads': 0,
                'size': 0,
                'searches': 0
            }
        
        # حدود المستخدم العادي
        MAX_DAILY_DOWNLOADS = 50
        MAX_DAILY_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
        MAX_DAILY_SEARCHES = 100
        
        # حدود المستخدم المميز
        if user_data.get('is_premium'):
            MAX_DAILY_DOWNLOADS = 200
            MAX_DAILY_SIZE = 20 * 1024 * 1024 * 1024  # 20 GB
            MAX_DAILY_SEARCHES = 500
        
        if limits['downloads'] >= MAX_DAILY_DOWNLOADS:
            return False, "لقد تجاوزت الحد اليومي للتحميلات"
        
        if limits['size'] + file_size > MAX_DAILY_SIZE:
            return False, "لقد تجاوزت الحد اليومي للحجم"
        
        return True, "ok"
    
    async def increment_daily_usage(self, user_id: int, file_size: int):
        """زيادة الاستخدام اليومي"""
        user_data = await self.get_user(user_id)
        
        today = datetime.now().strftime('%Y-%m-%d')
        limits = user_data.get('daily_limits', {})
        
        if limits.get('date') != today:
            limits = {
                'date': today,
                'downloads': 1,
                'size': file_size,
                'searches': 0
            }
        else:
            limits['downloads'] += 1
            limits['size'] += file_size
        
        await self.update_user(user_id, {'daily_limits': limits})

# ==================== مدير الإحصائيات ====================
class StatsManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.daily_stats = defaultdict(lambda: defaultdict(int))
        self.hourly_stats = defaultdict(lambda: defaultdict(int))
    
    async def get_global_stats(self) -> Dict:
        """الحصول على الإحصائيات العامة"""
        return await self.db.get(STATS_FILE, 'global', {})
    
    async def get_detailed_stats(self) -> Dict:
        """الحصول على إحصائيات مفصلة"""
        users = await self.db.get_all(USERS_FILE)
        downloads = await self.db.get_all(DOWNLOADS_FILE)
        
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        stats = {
            'total_users': len(users),
            'active_today': 0,
            'active_week': 0,
            'active_month': 0,
            'premium_users': 0,
            'banned_users': 0,
            'total_downloads': 0,
            'total_size': 0,
            'today_downloads': 0,
            'today_size': 0,
            'week_downloads': 0,
            'week_size': 0,
            'month_downloads': 0,
            'month_size': 0,
            'avg_download_size': 0,
            'peak_hour': 0,
            'platform_stats': {},
            'quality_stats': {},
            'format_stats': {},
            'hourly_stats': {i: 0 for i in range(24)},
            'daily_stats': {},
            'monthly_stats': {}
        }
        
        # إحصائيات المستخدمين
        for user_id, user in users.items():
            if user.get('is_premium'):
                stats['premium_users'] += 1
            if user.get('is_banned'):
                stats['banned_users'] += 1
            
            last_active = user.get('last_active', '')
            if last_active:
                if last_active.startswith(today):
                    stats['active_today'] += 1
                if last_active >= week_ago:
                    stats['active_week'] += 1
                if last_active >= month_ago:
                    stats['active_month'] += 1
        
        # إحصائيات التحميلات
        for dl_id, dl in downloads.items():
            stats['total_downloads'] += 1
            stats['total_size'] += dl.get('size', 0)
            
            dl_date = dl.get('date', '')[:10]
            if dl_date == today:
                stats['today_downloads'] += 1
                stats['today_size'] += dl.get('size', 0)
            if dl_date >= (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'):
                stats['week_downloads'] += 1
                stats['week_size'] += dl.get('size', 0)
            if dl_date >= (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'):
                stats['month_downloads'] += 1
                stats['month_size'] += dl.get('size', 0)
            
            # إحصائيات المنصات
            platform = dl.get('platform', 'unknown')
            stats['platform_stats'][platform] = stats['platform_stats'].get(platform, 0) + 1
            
            # إحصائيات الجودات
            quality = dl.get('quality', 'unknown')
            stats['quality_stats'][quality] = stats['quality_stats'].get(quality, 0) + 1
            
            # إحصائيات الصيغ
            fmt = dl.get('format', 'unknown')
            stats['format_stats'][fmt] = stats['format_stats'].get(fmt, 0) + 1
            
            # إحصائيات الساعات
            try:
                hour = int(dl.get('date', '12:00').split('T')[1].split(':')[0])
                stats['hourly_stats'][hour] += 1
                if stats['hourly_stats'][hour] > stats['hourly_stats'].get(stats['peak_hour'], 0):
                    stats['peak_hour'] = hour
            except:
                pass
            
            # إحصائيات الأيام
            stats['daily_stats'][dl_date] = stats['daily_stats'].get(dl_date, 0) + 1
            
            # إحصائيات الشهور
            month = dl_date[:7]
            stats['monthly_stats'][month] = stats['monthly_stats'].get(month, 0) + 1
        
        # متوسط حجم التحميل
        if stats['total_downloads'] > 0:
            stats['avg_download_size'] = stats['total_size'] / stats['total_downloads']
        
        return stats
    
    async def log_download(self, user_id: int, video_info: Dict, quality: str, format: str, size: int):
        """تسجيل عملية تحميل"""
        download_id = f"{user_id}_{int(time.time())}_{random.randint(1000, 9999)}"
        
        download_data = {
            'id': download_id,
            'user_id': user_id,
            'date': datetime.now().isoformat(),
            'title': video_info.get('title', 'Unknown'),
            'url': video_info.get('url', ''),
            'platform': video_info.get('extractor', 'Unknown'),
            'quality': quality,
            'format': format,
            'size': size,
            'duration': video_info.get('duration', 0),
            'success': True
        }
        
        await self.db.set(DOWNLOADS_FILE, download_id, download_data)
        
        # تحديث الإحصائيات اليومية
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_stats[today]['downloads'] += 1
        self.daily_stats[today]['size'] += size
        
        # تحديث الإحصائيات العامة
        stats = await self.get_global_stats()
        stats['total_downloads'] = stats.get('total_downloads', 0) + 1
        stats['total_size'] = stats.get('total_size', 0) + size
        stats['last_updated'] = datetime.now().isoformat()
        await self.db.set(STATS_FILE, 'global', stats)
    
    async def log_error(self, error_type: str, error_msg: str, user_id: int = None):
        """تسجيل خطأ"""
        error_id = f"error_{int(time.time())}_{random.randint(1000, 9999)}"
        
        error_data = {
            'id': error_id,
            'date': datetime.now().isoformat(),
            'type': error_type,
            'message': error_msg,
            'user_id': user_id
        }
        
        errors = await self.db.get(ERRORS_FILE, 'errors', [])
        errors.append(error_data)
        
        # الاحتفاظ بآخر 1000 خطأ
        if len(errors) > 1000:
            errors = errors[-1000:]
        
        await self.db.set(ERRORS_FILE, 'errors', errors)
        
        # تسجيل في ملف الأخطاء
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()} - {error_type} - {error_msg} - User: {user_id}\n")

# ==================== معالج الفيديو ====================
class VideoProcessor:
    def __init__(self, stats_manager: StatsManager):
        self.stats_manager = stats_manager
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'extract_flat': False,
            'force_generic_extractor': False
        }
        self.active_downloads = {}
        self.cache = {}
        self.cache_ttl = CACHE_TTL
    
    def get_platform(self, url: str) -> str:
        """تحديد المنصة من الرابط"""
        url_lower = url.lower()
        for platform_id, info in SUPPORTED_PLATFORMS.items():
            if re.search(info['pattern'], url_lower):
                return platform_id
        return 'unknown'
    
    def get_video_info(self, url: str) -> Optional[Dict]:
        """الحصول على معلومات الفيديو"""
        # التحقق من الكاش
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return data
        
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                platform = self.get_platform(url)
                
                result = {
                    'id': info.get('id', ''),
                    'title': info.get('title', 'Unknown'),
                    'description': info.get('description', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'uploader_id': info.get('uploader_id', ''),
                    'uploader_url': info.get('uploader_url', ''),
                    'channel': info.get('channel', 'Unknown'),
                    'channel_id': info.get('channel_id', ''),
                    'channel_url': info.get('channel_url', ''),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'comment_count': info.get('comment_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'thumbnails': info.get('thumbnails', []),
                    'url': info.get('webpage_url', url),
                    'extractor': platform,
                    'extractor_full': info.get('extractor', 'unknown'),
                    'tags': info.get('tags', []),
                    'categories': info.get('categories', []),
                    'upload_date': info.get('upload_date', ''),
                    'release_date': info.get('release_date', ''),
                    'width': info.get('width', 0),
                    'height': info.get('height', 0),
                    'fps': info.get('fps', 0),
                    'filesize': info.get('filesize', 0),
                    'filesize_approx': info.get('filesize_approx', 0),
                    'format': info.get('format', ''),
                    'format_id': info.get('format_id', ''),
                    'resolution': info.get('resolution', ''),
                    'vcodec': info.get('vcodec', ''),
                    'acodec': info.get('acodec', ''),
                    'abr': info.get('abr', 0),
                    'vbr': info.get('vbr', 0),
                    'age_limit': info.get('age_limit', 0),
                    'is_live': info.get('is_live', False),
                    'was_live': info.get('was_live', False)
                }
                
                # تخزين في الكاش
                self.cache[cache_key] = (time.time(), result)
                
                # تنظيف الكاش القديم
                if len(self.cache) > 1000:
                    oldest = min(self.cache.keys(), key=lambda k: self.cache[k][0])
                    del self.cache[oldest]
                
                return result
                
        except Exception as e:
            logger.error(f"خطأ في جلب معلومات الفيديو: {e}")
            return None
    
    def search_videos(self, query: str, limit: int = 10) -> List[Dict]:
        """البحث عن فيديوهات"""
        try:
            search_opts = {**self.ydl_opts, 'extract_flat': True}
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry and entry.get('id'):
                            video_id = entry.get('id', '')
                            videos.append({
                                'id': video_id,
                                'title': entry.get('title', 'Unknown'),
                                'url': f"https://youtube.com/watch?v={video_id}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                'channel': entry.get('uploader', 'Unknown'),
                                'views': entry.get('view_count', 0),
                                'upload_date': entry.get('upload_date', ''),
                                'description': entry.get('description', '')[:200]
                            })
                return videos
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []
    
    def get_trending(self, category: str = 'trending', limit: int = 10) -> List[Dict]:
        """الحصول على الفيديوهات الرائجة"""
        search_queries = {
            'trending': 'trending',
            'music': 'music video',
            'gaming': 'gaming',
            'news': 'news today',
            'sports': 'sports highlights',
            'education': 'educational',
            'technology': 'tech reviews',
            'entertainment': 'entertainment',
            'comedy': 'comedy',
            'movies': 'movie trailers',
            'animation': 'animation',
            'documentary': 'documentary',
            'cooking': 'cooking recipes',
            'travel': 'travel vlog',
            'fashion': 'fashion',
            'beauty': 'beauty tips',
            'fitness': 'fitness workout',
            'science': 'science',
            'history': 'history',
            'art': 'art tutorial'
        }
        
        query = search_queries.get(category, 'trending')
        return self.search_videos(query, limit)
    
    def download_video(self, url: str, quality: str = 'best', format: str = 'mp4', 
                      user_id: int = None, progress_callback=None) -> Dict:
        """تحميل الفيديو"""
        try:
            # تحديد صيغة التحميل
            if quality == 'best':
                if format == 'mp3':
                    format_spec = 'bestaudio/best'
                else:
                    format_spec = 'best[ext=mp4]/best'
            else:
                height = VIDEO_QUALITIES.get(quality, {}).get('height', 720)
                if format == 'mp3':
                    format_spec = 'bestaudio/best'
                else:
                    format_spec = f'best[height<={height}][ext=mp4]/best'
            
            # اسم الملف
            timestamp = int(time.time())
            random_id = random.randint(1000, 9999)
            filename = DOWNLOAD_DIR / f"video_{timestamp}_{random_id}.%(ext)s"
            
            ydl_opts = {
                **self.ydl_opts,
                'format': format_spec,
                'outtmpl': str(filename),
                'progress_hooks': [progress_callback] if progress_callback else []
            }
            
            # إضافة معالج الصوت لـ MP3
            if format == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            # إضافة معالج للصور المصغرة والبيانات الوصفية
            ydl_opts['writethumbnail'] = True
            ydl_opts['embedthumbnail'] = True
            ydl_opts['addmetadata'] = True
            ydl_opts['embedmetadata'] = True
            
            # تتبع التحميل
            download_id = f"{user_id}_{timestamp}" if user_id else f"anon_{timestamp}"
            self.active_downloads[download_id] = {
                'url': url,
                'quality': quality,
                'format': format,
                'start_time': time.time(),
                'status': 'downloading',
                'progress': 0
            }
            
            # التحميل
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
                
                # تعديل اسم الملف للصيغ المختلفة
                if format == 'mp3':
                    file = str(file).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                else:
                    for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv']:
                        test_file = str(file).replace('%(ext)s', ext)
                        if Path(test_file).exists():
                            file = test_file
                            break
                
                if Path(file).exists():
                    size = Path(file).stat().st_size
                    self.active_downloads[download_id]['status'] = 'completed'
                    self.active_downloads[download_id]['file'] = file
                    self.active_downloads[download_id]['size'] = size
                    self.active_downloads[download_id]['end_time'] = time.time()
                    
                    return {
                        'success': True,
                        'file': file,
                        'size': size,
                        'title': info.get('title', 'Video'),
                        'duration': info.get('duration', 0),
                        'info': info,
                        'download_id': download_id
                    }
                
                return {'success': False, 'error': 'الملف غير موجود'}
                
        except Exception as e:
            logger.error(f"خطأ في التحميل: {e}")
            if 'download_id' in locals():
                self.active_downloads[download_id]['status'] = 'error'
                self.active_downloads[download_id]['error'] = str(e)
            return {'success': False, 'error': str(e)}
    
    def get_download_status(self, download_id: str) -> Optional[Dict]:
        """الحصول على حالة التحميل"""
        return self.active_downloads.get(download_id)
    
    def cancel_download(self, download_id: str) -> bool:
        """إلغاء التحميل"""
        if download_id in self.active_downloads:
            self.active_downloads[download_id]['status'] = 'cancelled'
            return True
        return False

# ==================== البوت الرئيسي ====================
class VideoBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.stats_manager = StatsManager(self.db)
        self.user_manager = UserManager(self.db)
        self.processor = VideoProcessor(self.stats_manager)
        self.user_sessions = {}
        self.user_temps = {}
        self.browse_sessions = {}
        self.start_time = datetime.now()
        self.rate_limiter = defaultdict(list)
        self.message_counter = 0
        
        # التحقق من FFmpeg
        self.check_ffmpeg()
        
        print("=" * 70)
        print("🚀 بوت تحميل الفيديوهات المتطور - الإصدار 7.0")
        print("=" * 70)
        print(f"📌 التوكن: {BOT_TOKEN[:15]}...")
        print(f"📌 الإصدار: {BOT_VERSION}")
        print(f"📌 الوقت: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print("✅ البوت جاهز للعمل!")
        print("📌 أرسل /start في تليجرام للبدء")
        print("=" * 70)
    
    def check_ffmpeg(self):
        """التحقق من تثبيت FFmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.split('\n')[0][:50]
                print(f"✅ FFmpeg: {version}")
            else:
                print("⚠️ FFmpeg: غير مثبت (بعض الصيغ قد لا تعمل)")
        except:
            print("⚠️ FFmpeg: غير مثبت (بعض الصيغ قد لا تعمل)")
    
    def check_rate_limit(self, user_id: int) -> bool:
        """التحقق من حد الطلبات"""
        now = time.time()
        user_requests = self.rate_limiter[user_id]
        
        # إزالة الطلبات القديمة
        while user_requests and user_requests[0] < now - RATE_LIMIT_WINDOW:
            user_requests.pop(0)
        
        # التحقق من العدد
        if len(user_requests) >= RATE_LIMIT:
            return False
        
        user_requests.append(now)
        return True
    
    async def send_typing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إرسال إشارة الكتابة"""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )
    
    async def send_uploading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إرسال إشارة رفع ملف"""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.UPLOAD_VIDEO
        )
    
    # ==================== أوامر البوت ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر البدء"""
        user = update.effective_user
        self.message_counter += 1
        
        await self.send_typing(update, context)
        
        # التحقق من حد الطلبات
        if not self.check_rate_limit(user.id):
            await update.message.reply_text("⏳ الكثير من الطلبات. الرجاء الانتظار قليلاً.")
            return
        
        # الحصول على بيانات المستخدم
        user_data = await self.user_manager.get_user(user.id)
        
        # تحديث آخر نشاط
        await self.user_manager.update_user(user.id, {
            'last_active': datetime.now().isoformat(),
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        })
        
        # إضافة نقاط خبرة
        await self.user_manager.add_xp(user.id, 1)
        
        # إحصائيات
        stats = await self.stats_manager.get_global_stats()
        users_count = len(await self.db.get_all(USERS_FILE))
        downloads_count = stats.get('total_downloads', 0)
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        welcome_text = f"""
🎬 *مرحباً {escape_markdown(user.first_name)}!*

أنا بوت تحميل الفيديوهات المتطور الإصدار {BOT_VERSION} 🚀

📥 *أرسل رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات المتطورة:*
• تحميل من {len(SUPPORTED_PLATFORMS)}+ منصة
• {len(VIDEO_QUALITIES)} جودة مختلفة (144p - 4K)
• {len(DOWNLOAD_FORMATS)} صيغة مختلفة
• {len(VIDEO_CATEGORIES)} فئة للتصفح
• بحث متقدم مع صور مصغرة
• إضافة للمفضلة والمشاهدة لاحقاً
• إحصائيات شخصية وسجل النشاط
• إعدادات مخصصة لكل مستخدم

📊 *إحصائيات البوت:*
👥 المستخدمين: {users_count:,}
📥 التحميلات: {downloads_count:,}
⏰ مدة التشغيل: {days}يوم {hours:02d}:{minutes:02d}
⚡ الرسائل: {self.message_counter}

🔰 *الأوامر المتاحة:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/favorites - المفضلة
/watchlater - المشاهدة لاحقاً
/history - سجل النشاط
/stats - إحصائياتي
/settings - الإعدادات
/help - المساعدة
/about - عن البوت

👇 *اختر ما تريد:*
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🔥 تصفح", callback_data="browse"),
                InlineKeyboardButton("🔍 بحث", callback_data="search")
            ],
            [
                InlineKeyboardButton("⭐ المفضلة", callback_data="favorites"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="watchlater")
            ],
            [
                InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
                InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📜 السجل", callback_data="history"),
                InlineKeyboardButton("❓ مساعدة", callback_data="help")
            ]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر المساعدة"""
        await self.send_typing(update, context)
        
        text = f"""
❓ *المساعدة*

📥 *لتحميل فيديو:*
• أرسل رابط الفيديو مباشرة
• اختر الجودة المناسبة
• اختر الصيغة المطلوبة
• انتظر التحميل
• استلم الفيديو

🔍 *للبحث عن فيديوهات:*
• اكتب أي كلمة للبحث
• تصفح النتائج مع الصور
• اختر الفيديو المناسب
• حمله أو شاهده مباشرة

🔥 *للتصفح:*
• استخدم قائمة التصفح
• اختر الفئة المناسبة
• تصفح الفيديوهات مع الصور

⭐ *للمفضلة:*
• أضف فيديوهات للمفضلة
• رجع لها في أي وقت
• نظم قائمتك المفضلة

⏰ *للمشاهدة لاحقاً:*
• احفظ فيديوهات لمشاهدتها لاحقاً
• لا تفوت فيديوهات مهمة
• نظم وقت مشاهدتك

⚙️ *للإعدادات:*
• خصص البوت حسب رغبتك
• اختر الجودة الافتراضية
• ضبط الإشعارات والمظهر

🌐 *المنصات المدعومة:* 
{', '.join([f"{p['emoji']} {p['name_ar']}" for p in SUPPORTED_PLATFORMS.values()][:10])}
والمزيد...

⚡ *الأوامر المتاحة:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/favorites - المفضلة
/watchlater - المشاهدة لاحقاً
/history - سجل النشاط
/stats - إحصائياتي
/settings - الإعدادات
/help - المساعدة
/about - عن البوت

📌 *للدعم والاستفسارات:* @YourSupport
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عن البوت"""
        await self.send_typing(update, context)
        
        stats = await self.stats_manager.get_detailed_stats()
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        text = f"""
ℹ️ *عن البوت*

🤖 *الاسم:* بوت تحميل الفيديوهات المتطور
📊 *الإصدار:* {BOT_VERSION}
📅 *تاريخ الإصدار:* {BOT_RELEASE_DATE}
👨‍💻 *المطور:* @YourUsername

✨ *المميزات:*
• تحميل من {len(SUPPORTED_PLATFORMS)}+ منصة
• {len(VIDEO_QUALITIES)} جودة مختلفة (حتى 4K)
• {len(DOWNLOAD_FORMATS)} صيغة مختلفة
• {len(VIDEO_CATEGORIES)} فئة للتصفح
• نظام مفضلة ومشاهدة لاحقاً
• إحصائيات متقدمة
• سجل نشاط كامل
• إعدادات مخصصة

📊 *إحصائيات عامة:*
👥 المستخدمين: {stats['total_users']:,}
📥 التحميلات: {stats['total_downloads']:,}
📦 حجم التحميلات: {format_size(stats['total_size'])}
🔥 النشطون اليوم: {stats['active_today']}
⭐ المستخدمين المميزين: {stats['premium_users']}

⏰ *مدة التشغيل:* {days}يوم {hours:02d}:{minutes:02d}
⚡ *الرسائل المعالجة:* {self.message_counter}

❤️ *شكراً لاستخدامك البوت!*
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تصفح الفئات"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        row = []
        
        for i, (cat_id, cat_info) in enumerate(VIDEO_CATEGORIES.items(), 1):
            button = InlineKeyboardButton(
                f"{cat_info['emoji']} {cat_info['name_ar']}",
                callback_data=f"cat_{cat_id}"
            )
            row.append(button)
            
            if i % 2 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🔥 *تصفح الفيديوهات*\n\nاختر الفئة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """تصفح فئة محددة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text(
            f"⏳ جاري تحميل {VIDEO_CATEGORIES[category]['name_ar']}...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        videos = self.processor.get_trending(category, limit=8)
        
        if not videos:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات في هذه الفئة",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="browse")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # حفظ في الجلسة
        if user_id not in self.browse_sessions:
            self.browse_sessions[user_id] = {}
        self.browse_sessions[user_id][category] = videos
        self.browse_sessions[user_id]['current_page'] = 0
        self.browse_sessions[user_id]['current_category'] = category
        
        await self.show_video(update, context, category, 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, index: int):
        """عرض فيديو مع الصورة والوصف"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        videos = self.browse_sessions.get(user_id, {}).get(category, [])
        if not videos or index >= len(videos):
            await query.edit_message_text("❌ لا يوجد فيديو")
            return
        
        video = videos[index]
        
        duration = format_time(video.get('duration', 0))
        views = format_number(video.get('views', 0))
        
        text = f"""
🎬 *{escape_markdown(video['title'][:100])}*

📺 *القناة:* {escape_markdown(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        # أزرار التنقل
        keyboard = []
        
        # أزرار الفيديو
        keyboard.append([
            InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
            InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("⭐ مفضلة", callback_data=f"fav_{video['url']}"),
            InlineKeyboardButton("⏰ للمشاهدة", callback_data=f"wl_{video['url']}")
        ])
        
        # أزرار التنقل بين الفيديوهات
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"nav_{category}_{index-1}"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"nav_{category}_{index+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton(
                f"📄 الصفحة {index + 1}/{len(videos)}", 
                callback_data="page_info"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع للفئات", callback_data="browse")])
        
        # إرسال الصورة
        try:
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=user_id,
                photo=video['thumbnail'],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الصورة: {e}")
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        self.message_counter += 1
        
        # التحقق من حد الطلبات
        if not self.check_rate_limit(user_id):
            await update.message.reply_text("⏳ الكثير من الطلبات. الرجاء الانتظار قليلاً.")
            return
        
        # تحديث آخر نشاط
        await self.user_manager.update_user(user_id, {
            'last_active': datetime.now().isoformat()
        })
        
        print(f"📩 رسالة من {user_id}: {text[:50]}...")
        
        # التحقق من الرابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة رابط فيديو"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        user_id = update.effective_user.id
        
        platform_info = get_platform_info(url)
        
        info = self.processor.get_video_info(url)
        
        if not info:
            await self.stats_manager.log_error('url_error', 'فشل في جلب المعلومات', user_id)
            await msg.edit_text(
                f"{platform_info['emoji']} ❌ تعذر الحصول على معلومات الفيديو من {platform_info['name_ar']}",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # التحقق من المدة
        if info['duration'] > MAX_DURATION:
            await msg.edit_text(
                f"❌ عذراً، مدة الفيديو ({format_time(info['duration'])}) تتجاوز الحد المسموح ({format_time(MAX_DURATION)})"
            )
            return
        
        # حفظ في الجلسة
        self.user_sessions[user_id] = {
            'url': url,
            'info': info,
            'timestamp': time.time()
        }
        
        # إضافة للسجل
        await self.user_manager.add_to_history(user_id, info)
        
        # إضافة نقاط خبرة
        await self.user_manager.add_xp(user_id, 5)
        
        duration = format_time(info['duration'])
        views = format_number(info['view_count'])
        likes = format_number(info['like_count'])
        
        text = f"""
{platform_info['emoji']} *معلومات الفيديو من {platform_info['name_ar']}*

🎬 *العنوان:* {escape_markdown(info['title'][:200])}
👤 *الرافع:* {escape_markdown(info['uploader'])}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}
👍 *الإعجابات:* {likes}

🔗 [شاهد على يوتيوب]({info['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=info['url']),
                InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
            ],
            [
                InlineKeyboardButton("⭐ مفضلة", callback_data="add_favorite"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="add_watchlater")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        # إرسال الصورة
        try:
            await msg.delete()
            await update.message.reply_photo(
                photo=info['thumbnail'],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الصورة: {e}")
            await msg.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        user_id = update.effective_user.id
        
        # تحديث إحصائيات البحث
        user_data = await self.user_manager.get_user(user_id)
        stats = user_data.get('stats', {})
        stats['searches_performed'] = stats.get('searches_performed', 0) + 1
        await self.user_manager.update_user(user_id, {
            'search_count': user_data.get('search_count', 0) + 1,
            'stats': stats
        })
        
        # إضافة نقاط خبرة
        await self.user_manager.add_xp(user_id, 2)
        
        videos = self.processor.search_videos(query, limit=8)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج للبحث عن: '{query}'",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # حفظ نتائج البحث
        if user_id not in self.browse_sessions:
            self.browse_sessions[user_id] = {}
        self.browse_sessions[user_id]['search'] = videos
        self.browse_sessions[user_id]['current_page'] = 0
        self.browse_sessions[user_id]['current_category'] = 'search'
        
        await msg.delete()
        await self.show_video(update, context, 'search', 0)
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة التحميل"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id, {})
        info = session.get('info', {})
        
        if not info:
            await query.edit_message_text(
                "❌ لا توجد معلومات فيديو. أرسل رابط فيديو أولاً.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = f"""
📥 *اختر جودة التحميل*

🎬 *العنوان:* {escape_markdown(info.get('title', '')[:100])}
⏱ *المدة:* {format_time(info.get('duration', 0))}

👇 *اختر الجودة:*
        """
        
        keyboard = []
        row = []
        
        for i, (q_id, q_info) in enumerate(VIDEO_QUALITIES.items(), 1):
            button = InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name_ar']}",
                callback_data=f"quality_{q_id}"
            )
            row.append(button)
            
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        """اختيار الجودة"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id, {})
        info = session.get('info', {})
        
        text = f"""
📥 *اختر الصيغة*

⚡ *الجودة:* {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name_ar']}
🎬 *العنوان:* {escape_markdown(info.get('title', '')[:100])}

👇 *اختر الصيغة:*
        """
        
        keyboard = []
        row = []
        
        for i, (f_id, f_info) in enumerate(DOWNLOAD_FORMATS.items(), 1):
            button = InlineKeyboardButton(
                f"{f_info['emoji']} {f_info['name_ar']}",
                callback_data=f"format_{quality}_{f_id}"
            )
            row.append(button)
            
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="download_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, format: str):
        """بدء التحميل"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.user_sessions.get(user_id, {})
        url = session.get('url')
        info = session.get('info', {})
        title = info.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text(
                "❌ لا يوجد رابط فيديو",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # التحقق من الحدود اليومية
        can_download, message = await self.user_manager.check_daily_limit(user_id, 0)
        if not can_download:
            await query.edit_message_text(message)
            return
        
        # إرسال إشارة الرفع
        await self.send_uploading(update, context)
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n"
            f"🎬 {escape_markdown(title[:50])}\n"
            f"⚡ {VIDEO_QUALITIES[quality]['name_ar']} | {DOWNLOAD_FORMATS[format]['name_ar']}\n\n"
            f"⏳ الرجاء الانتظار...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # دالة تتبع التقدم
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percentage = (downloaded / total) * 100
                    if int(percentage) % 25 == 0:  # تحديث كل 25%
                        progress_bar = create_progress_bar(percentage)
                        speed = d.get('speed', 0)
                        speed_str = format_size(speed) + '/s' if speed else '?'
                        eta = d.get('eta', 0)
                        
                        text = (
                            f"⬇️ *جاري التحميل...*\n\n"
                            f"📊 {progress_bar} {percentage:.1f}%\n"
                            f"⚡ السرعة: {speed_str}\n"
                            f"⏱ المتبقي: {format_time(eta)}\n"
                            f"📦 تم: {format_size(downloaded)} / {format_size(total)}"
                        )
                        asyncio.create_task(query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN))
        
        result = self.processor.download_video(url, quality, format, user_id, progress_hook)
        
        if result['success']:
            file = result['file']
            size = result['size']
            
            # تحديث الإحصائيات
            await self.user_manager.increment_daily_usage(user_id, size)
            await self.user_manager.update_user(user_id, {
                'download_count': (await self.user_manager.get_user(user_id)).get('download_count', 0) + 1,
                'total_downloads': (await self.user_manager.get_user(user_id)).get('total_downloads', 0) + 1,
                'total_size': (await self.user_manager.get_user(user_id)).get('total_size', 0) + size
            })
            
            stats = await self.user_manager.get_user(user_id)
            stats = stats.get('stats', {})
            if format == 'mp3':
                stats['audios_downloaded'] = stats.get('audios_downloaded', 0) + 1
            else:
                stats['videos_downloaded'] = stats.get('videos_downloaded', 0) + 1
            await self.user_manager.update_user(user_id, {'stats': stats})
            
            # تسجيل التحميل
            await self.stats_manager.log_download(user_id, info, quality, format, size)
            
            # إضافة نقاط خبرة
            xp = size // (1024 * 1024)  # 1 XP لكل MB
            await self.user_manager.add_xp(user_id, max(1, xp))
            
            # إرسال الملف
            caption = f"✅ *تم التحميل بنجاح!*\n\n📦 الحجم: {format_size(size)}"
            
            with open(file, 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        title=title[:100],
                        performer=info.get('uploader', ''),
                        duration=info.get('duration', 0)
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        supports_streaming=True,
                        duration=info.get('duration', 0),
                        width=info.get('width', 0),
                        height=info.get('height', 0)
                    )
            
            # حذف الملف
            Path(file).unlink()
            await query.delete()
            
        else:
            await self.stats_manager.log_error('download_error', result.get('error', 'خطأ غير معروف'), user_id)
            await query.edit_message_text(
                f"❌ فشل التحميل: {result.get('error', 'خطأ غير معروف')}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المفضلة"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        favorites = await self.user_manager.get_favorites(user_id)
        
        if not favorites:
            await query.edit_message_text(
                "⭐ *المفضلة*\n\nلا توجد فيديوهات في المفضلة بعد.\n\nأضف فيديوهات للمفضلة بالضغط على ⭐ أثناء مشاهدة أي فيديو.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "⭐ *المفضلة*\n\n"
        keyboard = []
        
        for i, fav in enumerate(reversed(favorites[-10:]), 1):
            title = fav.get('title', '')[:50]
            duration = format_time(fav.get('duration', 0))
            platform = fav.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {escape_markdown(title)} - {duration}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"fav_{fav['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_watch_later(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المشاهدة لاحقاً"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        watch_later = await self.user_manager.get_watch_later(user_id)
        
        if not watch_later:
            await query.edit_message_text(
                "⏰ *للمشاهدة لاحقاً*\n\nلا توجد فيديوهات في القائمة.\n\nأضف فيديوهات بالضغط على ⏰ أثناء مشاهدة أي فيديو.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "⏰ *للمشاهدة لاحقاً*\n\n"
        keyboard = []
        
        for i, item in enumerate(reversed(watch_later[-10:]), 1):
            title = item.get('title', '')[:50]
            duration = format_time(item.get('duration', 0))
            platform = item.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {escape_markdown(title)} - {duration}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"wl_{item['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض سجل النشاط"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        history = await self.user_manager.get_history(user_id, limit=20)
        
        if not history:
            await query.edit_message_text(
                "📜 *سجل النشاط*\n\nلا يوجد سجل بعد.\n\nشاهد أو حمل بعض الفيديوهات لتظهر هنا.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "📜 *آخر 20 نشاط*\n\n"
        
        for i, item in enumerate(reversed(history), 1):
            date = item.get('date', '')[:10]
            title = item.get('title', '')[:40]
            platform = item.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {escape_markdown(title)}\n   📅 {date}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض إحصائيات المستخدم"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user_data = await self.user_manager.get_user(user_id)
        
        # حساب الإحصائيات
        joined = datetime.fromisoformat(user_data.get('joined_date', datetime.now().isoformat()))
        days_active = (datetime.now() - joined).days
        
        downloads = user_data.get('download_count', 0)
        total_size = user_data.get('total_size', 0)
        favorites = len(await self.user_manager.get_favorites(user_id))
        watch_later = len(await self.user_manager.get_watch_later(user_id))
        history = len(await self.user_manager.get_history(user_id))
        
        stats = user_data.get('stats', {})
        videos_downloaded = stats.get('videos_downloaded', 0)
        audios_downloaded = stats.get('audios_downloaded', 0)
        searches = stats.get('searches_performed', 0)
        
        level = user_data.get('level', 1)
        xp = user_data.get('xp', 0)
        next_xp = user_data.get('next_level_xp', 100)
        xp_progress = (xp / next_xp) * 100 if next_xp > 0 else 0
        progress_bar = create_progress_bar(xp_progress)
        
        stats_text = f"""
📊 *إحصائياتك الشخصية*

👤 *المستخدم:* {escape_markdown(user_data.get('first_name', 'Unknown'))}
📅 *عضو منذ:* {days_active} يوم
⭐ *المستوى:* {level} {progress_bar} {xp}/{next_xp} XP

📥 *التحميلات:*
• إجمالي: {downloads:,}
• فيديوهات: {videos_downloaded:,}
• صوتيات: {audios_downloaded:,}
• الحجم: {format_size(total_size)}

🎬 *المحتوى:*
• المفضلة: {favorites}
• للمشاهدة: {watch_later}
• السجل: {history}
• عمليات البحث: {searches}

⚙️ *الإعدادات:*
• الجودة الافتراضية: {VIDEO_QUALITIES.get(user_data.get('settings', {}).get('default_quality', 'best'), {}).get('name_ar', 'أفضل جودة')}
• الصيغة الافتراضية: {DOWNLOAD_FORMATS.get(user_data.get('settings', {}).get('default_format', 'mp4'), {}).get('name_ar', 'MP4')}
• حفظ السجل: {'✅' if user_data.get('settings', {}).get('save_history', True) else '❌'}
        """
        
        keyboard = [
            [InlineKeyboardButton("📥 سجل التحميلات", callback_data="history")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإعدادات"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user_data = await self.user_manager.get_user(user_id)
        settings = user_data.get('settings', {})
        
        settings_text = f"""
⚙️ *الإعدادات الشخصية*

🔰 *الإعدادات الحالية:*

🎬 *الجودة الافتراضية:* {VIDEO_QUALITIES.get(settings.get('default_quality', 'best'), {}).get('name_ar', 'أفضل جودة')}
📁 *الصيغة الافتراضية:* {DOWNLOAD_FORMATS.get(settings.get('default_format', 'mp4'), {}).get('name_ar', 'MP4')}
🗑 *الحذف التلقائي:* {'✅' if settings.get('auto_delete', True) else '❌'}
🔔 *الإشعارات:* {'✅' if settings.get('notifications', True) else '❌'}
🌙 *الوضع الليلي:* {'✅' if settings.get('dark_mode', True) else '❌'}
📝 *حفظ السجل:* {'✅' if settings.get('save_history', True) else '❌'}

👇 *اختر الإعداد لتعديله:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 الجودة الافتراضية", callback_data="set_default_quality")],
            [InlineKeyboardButton("📁 الصيغة الافتراضية", callback_data="set_default_format")],
            [InlineKeyboardButton("🗑 الحذف التلقائي", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton("🔔 الإشعارات", callback_data="toggle_notifications")],
            [InlineKeyboardButton("🌙 الوضع الليلي", callback_data="toggle_dark_mode")],
            [InlineKeyboardButton("📝 حفظ السجل", callback_data="toggle_save_history")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_default_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تعيين الجودة الافتراضية"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        row = []
        
        for i, (q_id, q_info) in enumerate(VIDEO_QUALITIES.items(), 1):
            row.append(InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name_ar']}",
                callback_data=f"save_quality_{q_id}"
            ))
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="settings")])
        
        await query.edit_message_text(
            "🎬 *اختر الجودة الافتراضية:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_default_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تعيين الصيغة الافتراضية"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        row = []
        
        for i, (f_id, f_info) in enumerate(DOWNLOAD_FORMATS.items(), 1):
            row.append(InlineKeyboardButton(
                f"{f_info['emoji']} {f_info['name_ar']}",
                callback_data=f"save_format_{f_id}"
            ))
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="settings")])
        
        await query.edit_message_text(
            "📁 *اختر الصيغة الافتراضية:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== معالج الأزرار ====================
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة جميع الأزرار"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        print(f"🔘 كلك: {data} من {user_id}")
        await query.answer()
        
        # التحقق من حد الطلبات
        if not self.check_rate_limit(user_id):
            await query.edit_message_text("⏳ الكثير من الطلبات. الرجاء الانتظار قليلاً.")
            return
        
        # أزرار القائمة الرئيسية
        if data == "main_menu":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "search":
            await query.edit_message_text(
                "🔍 *بحث*\n\nأرسل كلمة البحث الآن:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "favorites":
            await self.show_favorites(update, context)
        
        elif data == "watchlater":
            await self.show_watch_later(update, context)
        
        elif data == "history":
            await self.show_history(update, context)
        
        elif data == "stats":
            await self.show_stats(update, context)
        
        elif data == "settings":
            await self.settings(update, context)
        
        elif data == "help":
            await self.help(update, context)
        
        elif data == "about":
            await self.about(update, context)
        
        # أزرار التصفح
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            await self.browse_category(update, context, category)
        
        elif data.startswith("nav_"):
            parts = data.replace("nav_", "").split("_")
            category = parts[0]
            index = int(parts[1])
            self.browse_sessions[user_id]['current_page'] = index
            await self.show_video(update, context, category, index)
        
        elif data == "page_info":
            await query.answer("استخدم أزرار التنقل للتصفح بين الفيديوهات")
        
        # أزرار التحميل
        elif data == "download_menu":
            await self.download_menu(update, context)
        
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            await self.select_quality(update, context, quality)
        
        elif data.startswith("format_"):
            parts = data.replace("format_", "").split("_")
            quality = parts[0]
            format_type = parts[1]
            await self.start_download(update, context, quality, format_type)
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.handle_url(update, context, url)
        
        # أزرار المفضلة والمشاهدة لاحقاً
        elif data.startswith("fav_"):
            url = data.replace("fav_", "")
            # الحصول على معلومات الفيديو
            info = {'url': url, 'title': 'فيديو', 'extractor': 'youtube'}
            added = await self.user_manager.add_to_favorites(user_id, info)
            if added:
                await query.answer("✅ أضيف إلى المفضلة!")
                await self.user_manager.add_xp(user_id, 3)
            else:
                await query.answer("❌ موجود مسبقاً في المفضلة")
        
        elif data.startswith("wl_"):
            url = data.replace("wl_", "")
            info = {'url': url, 'title': 'فيديو', 'extractor': 'youtube'}
            added = await self.user_manager.add_to_watch_later(user_id, info)
            if added:
                await query.answer("✅ أضيف إلى قائمة المشاهدة لاحقاً!")
                await self.user_manager.add_xp(user_id, 2)
            else:
                await query.answer("❌ موجود مسبقاً في القائمة")
        
        elif data == "add_favorite":
            session = self.user_sessions.get(user_id, {})
            info = session.get('info', {})
            if info:
                added = await self.user_manager.add_to_favorites(user_id, info)
                if added:
                    await query.answer("✅ أضيف إلى المفضلة!")
                    await self.user_manager.add_xp(user_id, 3)
                else:
                    await query.answer("❌ موجود مسبقاً في المفضلة")
        
        elif data == "add_watchlater":
            session = self.user_sessions.get(user_id, {})
            info = session.get('info', {})
            if info:
                added = await self.user_manager.add_to_watch_later(user_id, info)
                if added:
                    await query.answer("✅ أضيف إلى قائمة المشاهدة لاحقاً!")
                    await self.user_manager.add_xp(user_id, 2)
                else:
                    await query.answer("❌ موجود مسبقاً في القائمة")
        
        # أزرار الإعدادات
        elif data == "set_default_quality":
            await self.set_default_quality(update, context)
        
        elif data.startswith("save_quality_"):
            quality = data.replace("save_quality_", "")
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            settings['default_quality'] = quality
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ تم حفظ الجودة الافتراضية: {VIDEO_QUALITIES[quality]['name_ar']}")
            await self.settings(update, context)
        
        elif data == "set_default_format":
            await self.set_default_format(update, context)
        
        elif data.startswith("save_format_"):
            format_type = data.replace("save_format_", "")
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            settings['default_format'] = format_type
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ تم حفظ الصيغة الافتراضية: {DOWNLOAD_FORMATS[format_type]['name_ar']}")
            await self.settings(update, context)
        
        elif data == "toggle_auto_delete":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('auto_delete', True)
            settings['auto_delete'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} الحذف التلقائي")
            await self.settings(update, context)
        
        elif data == "toggle_notifications":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('notifications', True)
            settings['notifications'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} الإشعارات")
            await self.settings(update, context)
        
        elif data == "toggle_dark_mode":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('dark_mode', True)
            settings['dark_mode'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} الوضع الليلي")
            await self.settings(update, context)
        
        elif data == "toggle_save_history":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('save_history', True)
            settings['save_history'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} حفظ السجل")
            await self.settings(update, context)
    
    # ==================== معالج الأخطاء ====================
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأخطاء العام"""
        error = context.error
        logger.error(f"خطأ: {error}")
        
        # تسجيل الخطأ
        user_id = update.effective_user.id if update and update.effective_user else None
        await self.stats_manager.log_error('bot_error', str(error)[:200], user_id)
        
        # إعلام المستخدم
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى لاحقاً.\n\n"
                    "إذا استمرت المشكلة، تواصل مع الدعم الفني."
                )
        except:
            pass
    
    # ==================== تشغيل البوت ====================
    
    def run(self):
        """تشغيل البوت"""
        try:
            # إنشاء التطبيق
            app = Application.builder().token(BOT_TOKEN).build()
            
            # إضافة معالجات الأوامر
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("help", self.help))
            app.add_handler(CommandHandler("about", self.about))
            app.add_handler(CommandHandler("browse", self.browse))
            app.add_handler(CommandHandler("favorites", self.show_favorites))
            app.add_handler(CommandHandler("watchlater", self.show_watch_later))
            app.add_handler(CommandHandler("history", self.show_history))
            app.add_handler(CommandHandler("stats", self.show_stats))
            app.add_handler(CommandHandler("settings", self.settings))
            
            # معالج الرسائل
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # معالج الأزرار
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # معالج الأخطاء
            app.add_error_handler(self.error_handler)
            
            # تشغيل البوت
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ خطأ في تشغيل البوت: {e}")
            traceback.print_exc()

# ==================== MAIN ====================
if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
