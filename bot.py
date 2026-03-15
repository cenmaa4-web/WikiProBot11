import os
import logging
import re
import json
import asyncio
import aiohttp
import subprocess
import sys
import time
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from urllib.parse import urlparse, quote
import html
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ParseMode
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes,
    ConversationHandler,
    PreCheckoutQueryHandler,
    ShippingQueryHandler
)
from telegram.constants import ParseMode, ChatAction
import yt_dlp

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
BOT_USERNAME = "@YourBotUsername"  # اسم المستخدم للبوت
OWNER_ID = 123456789  # ضع معرف المطور هنا

# مجلدات التخزين
DOWNLOAD_FOLDER = "downloads"
THUMBNAIL_FOLDER = "thumbnails"
LOGS_FOLDER = "logs"
DATABASE_FOLDER = "database"
TEMP_FOLDER = "temp"
COOKIES_FOLDER = "cookies"

# إنشاء جميع المجلدات
for folder in [DOWNLOAD_FOLDER, THUMBNAIL_FOLDER, LOGS_FOLDER, DATABASE_FOLDER, TEMP_FOLDER, COOKIES_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ملفات قاعدة البيانات
USERS_FILE = os.path.join(DATABASE_FOLDER, "users.json")
STATS_FILE = os.path.join(DATABASE_FOLDER, "stats.json")
DOWNLOADS_FILE = os.path.join(DATABASE_FOLDER, "downloads.json")
BANNED_FILE = os.path.join(DATABASE_FOLDER, "banned.json")
CHANNELS_FILE = os.path.join(DATABASE_FOLDER, "channels.json")
COOKIES_FILE = os.path.join(COOKIES_FOLDER, "cookies.txt")

# الإعدادات العامة
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2 GB (حد تليجرام الجديد)
MAX_DURATION = 10800  # 3 ساعات
MAX_SEARCH_RESULTS = 20
MAX_HISTORY_ITEMS = 100
BOT_VERSION = "4.0.0"
BOT_RELEASE_DATE = "2024-03-15"

# حالات المحادثة
(
    MAIN_MENU,
    BROWSE_MENU,
    SEARCH_MENU,
    DOWNLOAD_MENU,
    QUALITY_SELECTION,
    FORMAT_SELECTION,
    PLAYLIST_SELECTION,
    SETTINGS_MENU,
    FAVORITES_MENU,
    HISTORY_MENU,
    CHANNEL_MENU,
    PLAYLIST_CREATION,
    PLAYLIST_EDITING,
    ADMIN_MENU,
    BROADCAST_MENU,
    STATS_MENU
) = range(16)

# إعداد التسجيل المتقدم
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(filename)s:%(lineno)d',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.join(LOGS_FOLDER, f'bot_{datetime.now().strftime("%Y%m%d")}.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== جودات الفيديو المتقدمة ====================
VIDEO_QUALITIES = {
    '144': {
        'name': '144p',
        'desc': 'منخفضة جداً',
        'emoji': '📱',
        'height': 144,
        'bitrate': '100k',
        'filesize_factor': 0.1
    },
    '240': {
        'name': '240p',
        'desc': 'منخفضة',
        'emoji': '📱',
        'height': 240,
        'bitrate': '200k',
        'filesize_factor': 0.15
    },
    '360': {
        'name': '360p',
        'desc': 'متوسطة',
        'emoji': '📺',
        'height': 360,
        'bitrate': '500k',
        'filesize_factor': 0.25
    },
    '480': {
        'name': '480p',
        'desc': 'جيدة',
        'emoji': '📺',
        'height': 480,
        'bitrate': '1000k',
        'filesize_factor': 0.4
    },
    '720': {
        'name': '720p HD',
        'desc': 'عالية',
        'emoji': '🎬',
        'height': 720,
        'bitrate': '2500k',
        'filesize_factor': 0.6
    },
    '1080': {
        'name': '1080p Full HD',
        'desc': 'عالية جداً',
        'emoji': '🎥',
        'height': 1080,
        'bitrate': '5000k',
        'filesize_factor': 1.0
    },
    '1440': {
        'name': '2K Quad HD',
        'desc': 'فائقة',
        'emoji': '🎥',
        'height': 1440,
        'bitrate': '10000k',
        'filesize_factor': 1.8
    },
    '2160': {
        'name': '4K Ultra HD',
        'desc': 'فائقة جداً',
        'emoji': '🎥',
        'height': 2160,
        'bitrate': '20000k',
        'filesize_factor': 3.0
    },
    '4320': {
        'name': '8K Ultra HD',
        'desc': 'احترافية',
        'emoji': '🎥',
        'height': 4320,
        'bitrate': '40000k',
        'filesize_factor': 6.0
    },
    'best': {
        'name': 'أفضل جودة',
        'desc': 'تلقائي',
        'emoji': '🏆',
        'height': 9999,
        'bitrate': 'best',
        'filesize_factor': 2.0
    }
}

# ==================== صيغ التحميل المتقدمة ====================
DOWNLOAD_FORMATS = {
    'mp4': {
        'name': 'MP4',
        'desc': 'فيديو عادي',
        'emoji': '🎬',
        'ext': 'mp4',
        'mime': 'video/mp4',
        'codec': 'h264',
        'audio_codec': 'aac'
    },
    'webm': {
        'name': 'WEBM',
        'desc': 'فيديو مضغوط',
        'emoji': '🎥',
        'ext': 'webm',
        'mime': 'video/webm',
        'codec': 'vp9',
        'audio_codec': 'opus'
    },
    'mkv': {
        'name': 'MKV',
        'desc': 'جودة عالية',
        'emoji': '📦',
        'ext': 'mkv',
        'mime': 'video/x-matroska',
        'codec': 'h264/h265',
        'audio_codec': 'aac/mp3'
    },
    'avi': {
        'name': 'AVI',
        'desc': 'صيغة قديمة',
        'emoji': '💾',
        'ext': 'avi',
        'mime': 'video/x-msvideo',
        'codec': 'mpeg4',
        'audio_codec': 'mp3'
    },
    'mov': {
        'name': 'MOV',
        'desc': 'أبل',
        'emoji': '🍎',
        'ext': 'mov',
        'mime': 'video/quicktime',
        'codec': 'h264',
        'audio_codec': 'aac'
    },
    'wmv': {
        'name': 'WMV',
        'desc': 'ويندوز',
        'emoji': '🪟',
        'ext': 'wmv',
        'mime': 'video/x-ms-wmv',
        'codec': 'wmv',
        'audio_codec': 'wma'
    },
    'flv': {
        'name': 'FLV',
        'desc': 'فلاش',
        'emoji': '⚡',
        'ext': 'flv',
        'mime': 'video/x-flv',
        'codec': 'h263',
        'audio_codec': 'mp3'
    },
    '3gp': {
        'name': '3GP',
        'desc': 'جوال',
        'emoji': '📱',
        'ext': '3gp',
        'mime': 'video/3gpp',
        'codec': 'h263',
        'audio_codec': 'amr'
    },
    'mp3': {
        'name': 'MP3',
        'desc': 'صوت فقط',
        'emoji': '🎵',
        'ext': 'mp3',
        'mime': 'audio/mpeg',
        'codec': 'mp3',
        'bitrate': '320k'
    },
    'm4a': {
        'name': 'M4A',
        'desc': 'صوت عالي',
        'emoji': '🎧',
        'ext': 'm4a',
        'mime': 'audio/mp4',
        'codec': 'aac',
        'bitrate': '256k'
    },
    'wav': {
        'name': 'WAV',
        'desc': 'صوت خام',
        'emoji': '🎼',
        'ext': 'wav',
        'mime': 'audio/wav',
        'codec': 'pcm',
        'bitrate': '1411k'
    },
    'flac': {
        'name': 'FLAC',
        'desc': 'صوت بدون فقد',
        'emoji': '💿',
        'ext': 'flac',
        'mime': 'audio/flac',
        'codec': 'flac',
        'bitrate': '1000k'
    },
    'ogg': {
        'name': 'OGG',
        'desc': 'صوت مفتوح',
        'emoji': '🔊',
        'ext': 'ogg',
        'mime': 'audio/ogg',
        'codec': 'vorbis',
        'bitrate': '192k'
    }
}

# ==================== فئات الفيديو المتقدمة ====================
VIDEO_CATEGORIES = {
    'trending': {
        'name': '🔥 الأكثر مشاهدة',
        'emoji': '🔥',
        'color': 'red',
        'query': 'trending',
        'icon': '📈'
    },
    'music': {
        'name': '🎵 موسيقى',
        'emoji': '🎵',
        'color': 'purple',
        'query': 'music video',
        'icon': '🎤'
    },
    'gaming': {
        'name': '🎮 ألعاب',
        'emoji': '🎮',
        'color': 'blue',
        'query': 'gaming',
        'icon': '🕹️'
    },
    'news': {
        'name': '📰 أخبار',
        'emoji': '📰',
        'color': 'yellow',
        'query': 'news today',
        'icon': '📺'
    },
    'sports': {
        'name': '⚽ رياضة',
        'emoji': '⚽',
        'color': 'green',
        'query': 'sports highlights',
        'icon': '🏆'
    },
    'education': {
        'name': '📚 تعليم',
        'emoji': '📚',
        'color': 'brown',
        'query': 'educational',
        'icon': '🎓'
    },
    'technology': {
        'name': '💻 تكنولوجيا',
        'emoji': '💻',
        'color': 'cyan',
        'query': 'tech reviews',
        'icon': '⚙️'
    },
    'entertainment': {
        'name': '🎭 ترفيه',
        'emoji': '🎭',
        'color': 'pink',
        'query': 'entertainment',
        'icon': '🎪'
    },
    'comedy': {
        'name': '😄 كوميديا',
        'emoji': '😄',
        'color': 'orange',
        'query': 'comedy',
        'icon': '🎭'
    },
    'movies': {
        'name': '🎬 أفلام',
        'emoji': '🎬',
        'color': 'red',
        'query': 'movie trailers',
        'icon': '🍿'
    },
    'animation': {
        'name': '🖌️ أنميشن',
        'emoji': '🖌️',
        'color': 'rainbow',
        'query': 'animation',
        'icon': '🎨'
    },
    'documentary': {
        'name': '📽️ وثائقيات',
        'emoji': '📽️',
        'color': 'brown',
        'query': 'documentary',
        'icon': '🌍'
    },
    'cooking': {
        'name': '🍳 طبخ',
        'emoji': '🍳',
        'color': 'orange',
        'query': 'cooking recipes',
        'icon': '🥘'
    },
    'travel': {
        'name': '✈️ سفر',
        'emoji': '✈️',
        'color': 'blue',
        'query': 'travel vlog',
        'icon': '🌍'
    },
    'fashion': {
        'name': '👗 موضة',
        'emoji': '👗',
        'color': 'pink',
        'query': 'fashion',
        'icon': '💄'
    },
    'beauty': {
        'name': '💄 تجميل',
        'emoji': '💄',
        'color': 'pink',
        'query': 'beauty tips',
        'icon': '✨'
    },
    'fitness': {
        'name': '💪 لياقة',
        'emoji': '💪',
        'color': 'green',
        'query': 'fitness workout',
        'icon': '🏋️'
    },
    'science': {
        'name': '🔬 علوم',
        'emoji': '🔬',
        'color': 'cyan',
        'query': 'science experiments',
        'icon': '🧪'
    },
    'history': {
        'name': '📜 تاريخ',
        'emoji': '📜',
        'color': 'brown',
        'query': 'history documentary',
        'icon': '🏛️'
    },
    'art': {
        'name': '🎨 فن',
        'emoji': '🎨',
        'color': 'rainbow',
        'query': 'art tutorial',
        'icon': '🖼️'
    }
}

# ==================== المنصات المدعومة ====================
SUPPORTED_PLATFORMS = {
    'youtube': {
        'name': 'يوتيوب',
        'emoji': '📺',
        'color': 'red',
        'url_pattern': r'(youtube\.com|youtu\.be)',
        'quality': '4K',
        'speed': 'سريع',
        'login': 'لا يحتاج'
    },
    'instagram': {
        'name': 'انستغرام',
        'emoji': '📷',
        'color': 'purple',
        'url_pattern': r'(instagram\.com)',
        'quality': '1080p',
        'speed': 'متوسط',
        'login': 'يحتاج أحياناً'
    },
    'facebook': {
        'name': 'فيسبوك',
        'emoji': '📘',
        'color': 'blue',
        'url_pattern': r'(facebook\.com|fb\.watch)',
        'quality': '720p',
        'speed': 'متوسط',
        'login': 'لا يحتاج'
    },
    'twitter': {
        'name': 'تويتر',
        'emoji': '🐦',
        'color': 'cyan',
        'url_pattern': r'(twitter\.com|x\.com)',
        'quality': '720p',
        'speed': 'سريع',
        'login': 'لا يحتاج'
    },
    'tiktok': {
        'name': 'تيك توك',
        'emoji': '🎵',
        'color': 'black',
        'url_pattern': r'(tiktok\.com)',
        'quality': '1080p',
        'speed': 'سريع',
        'login': 'لا يحتاج'
    },
    'reddit': {
        'name': 'ريديت',
        'emoji': '👽',
        'color': 'orange',
        'url_pattern': r'(reddit\.com)',
        'quality': '720p',
        'speed': 'متوسط',
        'login': 'لا يحتاج'
    },
    'pinterest': {
        'name': 'بنترست',
        'emoji': '📌',
        'color': 'red',
        'url_pattern': r'(pinterest\.com)',
        'quality': '720p',
        'speed': 'متوسط',
        'login': 'لا يحتاج'
    },
    'vimeo': {
        'name': 'فيميو',
        'emoji': '🎥',
        'color': 'cyan',
        'url_pattern': r'(vimeo\.com)',
        'quality': '4K',
        'speed': 'سريع',
        'login': 'لا يحتاج'
    },
    'twitch': {
        'name': 'تويش',
        'emoji': '🎮',
        'color': 'purple',
        'url_pattern': r'(twitch\.tv)',
        'quality': '1080p',
        'speed': 'سريع',
        'login': 'يحتاج أحياناً'
    },
    'dailymotion': {
        'name': 'ديلي موشن',
        'emoji': '📺',
        'color': 'blue',
        'url_pattern': r'(dailymotion\.com)',
        'quality': '1080p',
        'speed': 'متوسط',
        'login': 'لا يحتاج'
    },
    'soundcloud': {
        'name': 'ساوند كلاود',
        'emoji': '🎵',
        'color': 'orange',
        'url_pattern': r'(soundcloud\.com)',
        'quality': 'صوت',
        'speed': 'سريع',
        'login': 'لا يحتاج'
    },
    'spotify': {
        'name': 'سبوتيفاي',
        'emoji': '🎧',
        'color': 'green',
        'url_pattern': r'(spotify\.com)',
        'quality': 'صوت',
        'speed': 'سريع',
        'login': 'يحتاج'
    }
}

# ==================== إدارة قاعدة البيانات ====================
class DatabaseManager:
    """مدير قاعدة البيانات المتقدم"""
    
    def __init__(self):
        self.data = {}
        self.locks = defaultdict(asyncio.Lock)
        self.load_all()
    
    def load_all(self):
        """تحميل جميع قواعد البيانات"""
        for file_name in [USERS_FILE, STATS_FILE, DOWNLOADS_FILE, BANNED_FILE, CHANNELS_FILE]:
            if os.path.exists(file_name):
                try:
                    with open(file_name, 'r', encoding='utf-8') as f:
                        self.data[file_name] = json.load(f)
                except:
                    self.data[file_name] = {}
            else:
                self.data[file_name] = {}
    
    async def save(self, file_path: str):
        """حفظ قاعدة بيانات مع قفل"""
        async with self.locks[file_path]:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data[file_path], f, ensure_ascii=False, indent=2, default=str)
    
    def get(self, file_path: str, key: str = None, default=None):
        """الحصول على قيمة"""
        if key:
            return self.data.get(file_path, {}).get(key, default)
        return self.data.get(file_path, default)
    
    async def set(self, file_path: str, key: str, value: Any):
        """تعيين قيمة"""
        if file_path not in self.data:
            self.data[file_path] = {}
        self.data[file_path][key] = value
        await self.save(file_path)
    
    async def update(self, file_path: str, key: str, updates: Dict):
        """تحديث قيمة"""
        current = self.get(file_path, key, {})
        current.update(updates)
        await self.set(file_path, key, current)
    
    async def delete(self, file_path: str, key: str):
        """حذف قيمة"""
        if file_path in self.data and key in self.data[file_path]:
            del self.data[file_path][key]
            await self.save(file_path)

# ==================== إدارة المستخدمين المتقدمة ====================
class UserManager:
    """Advanced user manager with caching"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def get_user(self, user_id: int) -> Dict:
        """Get user data with cache"""
        user_id = str(user_id)
        
        # Check cache
        if user_id in self.cache:
            cache_time, data = self.cache[user_id]
            if time.time() - cache_time < self.cache_ttl:
                return data
        
        # Get from database
        user_data = self.db.get(USERS_FILE, user_id, {})
        
        # Create new user if not exists
        if not user_data:
            user_data = await self.create_user(user_id)
        
        # Update cache
        self.cache[user_id] = (time.time(), user_data)
        
        return user_data
    
    async def create_user(self, user_id: str, username: str = None, first_name: str = None) -> Dict:
        """Create new user"""
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'joined_date': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'language': 'ar',
            'is_banned': False,
            'is_admin': False,
            'is_premium': False,
            'premium_until': None,
            'download_count': 0,
            'total_downloads': 0,
            'total_size': 0,
            'favorites': [],
            'watch_later': [],
            'playlists': {},
            'history': [],
            'search_history': [],
            'settings': {
                'default_quality': 'best',
                'default_format': 'mp4',
                'auto_delete': True,
                'notifications': True,
                'dark_mode': True,
                'save_history': True,
                'auto_download': False,
                'max_quality': '1080p',
                'preferred_codec': 'h264',
                'download_path': DOWNLOAD_FOLDER,
                'thumbnail_enabled': True,
                'metadata_enabled': True
            },
            'stats': {
                'videos_downloaded': 0,
                'audio_downloaded': 0,
                'playlists_downloaded': 0,
                'total_watch_time': 0,
                'favorites_added': 0,
                'searches_performed': 0
            },
            'daily_limits': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'downloads': 0,
                'size': 0
            },
            'referrals': [],
            'referral_code': self.generate_referral_code(),
            'referred_by': None,
            'badges': ['new'],
            'achievements': []
        }
        
        await self.db.set(USERS_FILE, user_id, user_data)
        await self.update_stats('new_users')
        
        return user_data
    
    def generate_referral_code(self) -> str:
        """Generate unique referral code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    async def update_user(self, user_id: int, updates: Dict):
        """Update user data"""
        user_id = str(user_id)
        await self.db.update(USERS_FILE, user_id, updates)
        
        # Update cache
        if user_id in self.cache:
            cache_time, data = self.cache[user_id]
            data.update(updates)
            self.cache[user_id] = (time.time(), data)
    
    async def update_stats(self, stat_name: str, value: int = 1):
        """Update global statistics"""
        stats = self.db.get(STATS_FILE, 'global', {})
        stats[stat_name] = stats.get(stat_name, 0) + value
        stats['last_updated'] = datetime.now().isoformat()
        await self.db.set(STATS_FILE, 'global', stats)
    
    async def add_to_history(self, user_id: int, video_info: Dict):
        """Add video to history"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        if not user_data.get('settings', {}).get('save_history', True):
            return
        
        history = user_data.get('history', [])
        history.append({
            'date': datetime.now().isoformat(),
            'title': video_info.get('title', 'Unknown'),
            'url': video_info.get('webpage_url', ''),
            'platform': video_info.get('extractor', 'Unknown'),
            'duration': video_info.get('duration', 0),
            'thumbnail': video_info.get('thumbnail', '')
        })
        
        # Keep last 100 items
        if len(history) > MAX_HISTORY_ITEMS:
            history = history[-MAX_HISTORY_ITEMS:]
        
        await self.update_user(user_id, {'history': history})
    
    async def add_to_favorites(self, user_id: int, video_info: Dict):
        """Add video to favorites"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        favorites = user_data.get('favorites', [])
        
        # Check for duplicates
        url = video_info.get('webpage_url', '')
        if not any(f.get('url') == url for f in favorites):
            favorites.append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'thumbnail': video_info.get('thumbnail', '')
            })
            
            # Update stats
            user_data['stats']['favorites_added'] += 1
            
            await self.update_user(user_id, {
                'favorites': favorites,
                'stats': user_data['stats']
            })
            return True
        return False
    
    async def remove_from_favorites(self, user_id: int, url: str):
        """Remove video from favorites"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        favorites = user_data.get('favorites', [])
        favorites = [f for f in favorites if f.get('url') != url]
        
        await self.update_user(user_id, {'favorites': favorites})
    
    async def add_to_watch_later(self, user_id: int, video_info: Dict):
        """Add video to watch later"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        watch_later = user_data.get('watch_later', [])
        
        # Check for duplicates
        url = video_info.get('webpage_url', '')
        if not any(w.get('url') == url for w in watch_later):
            watch_later.append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'thumbnail': video_info.get('thumbnail', '')
            })
            
            await self.update_user(user_id, {'watch_later': watch_later})
            return True
        return False
    
    async def check_daily_limit(self, user_id: int, file_size: int) -> Tuple[bool, str]:
        """Check daily download limits"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        today = datetime.now().strftime('%Y-%m-%d')
        limits = user_data.get('daily_limits', {})
        
        # Reset if new day
        if limits.get('date') != today:
            limits = {
                'date': today,
                'downloads': 0,
                'size': 0
            }
        
        # Regular user limits
        MAX_DAILY_DOWNLOADS = 50
        MAX_DAILY_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
        
        # Premium user limits
        if user_data.get('is_premium'):
            MAX_DAILY_DOWNLOADS = 200
            MAX_DAILY_SIZE = 20 * 1024 * 1024 * 1024  # 20 GB
        
        if limits['downloads'] >= MAX_DAILY_DOWNLOADS:
            return False, "❌ You have exceeded the daily download limit"
        
        if limits['size'] + file_size > MAX_DAILY_SIZE:
            return False, "❌ You have exceeded the daily size limit"
        
        return True, "ok"
    
    async def increment_daily_usage(self, user_id: int, file_size: int):
        """Increment daily usage counters"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        today = datetime.now().strftime('%Y-%m-%d')
        limits = user_data.get('daily_limits', {})
        
        if limits.get('date') != today:
            limits = {
                'date': today,
                'downloads': 1,
                'size': file_size
            }
        else:
            limits['downloads'] += 1
            limits['size'] += file_size
        
        await self.update_user(user_id, {'daily_limits': limits})
# ==================== إدارة الإحصائيات ====================
class StatsManager:
    """مدير الإحصائيات المتقدم"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def get_global_stats(self) -> Dict:
        """الحصول على الإحصائيات العامة"""
        return self.db.get(STATS_FILE, 'global', {})
    
    async def get_detailed_stats(self) -> Dict:
        """الحصول على إحصائيات مفصلة"""
        users = self.db.get(USERS_FILE, {})
        downloads = self.db.get(DOWNLOADS_FILE, {})
        
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        week_ago = (now - timedelta(days=7)).isoformat()
        
        stats = {
            'total_users': len(users),
            'active_today': 0,
            'active_week': 0,
            'premium_users': 0,
            'banned_users': 0,
            'total_downloads': 0,
            'total_size': 0,
            'today_downloads': 0,
            'today_size': 0,
            'platform_stats': {},
            'quality_stats': {},
            'format_stats': {},
            'hourly_stats': {i: 0 for i in range(24)},
            'daily_stats': {}
        }
        
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
        
        for dl_id, dl in downloads.items():
            stats['total_downloads'] += 1
            stats['total_size'] += dl.get('size', 0)
            
            if dl.get('date', '').startswith(today):
                stats['today_downloads'] += 1
                stats['today_size'] += dl.get('size', 0)
            
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
            except:
                pass
        
        return stats
    
    async def log_download(self, user_id: int, video_info: Dict, quality: str, format: str, size: int):
        """تسجيل عملية تحميل"""
        download_id = f"{user_id}_{int(time.time())}"
        
        download_data = {
            'user_id': user_id,
            'date': datetime.now().isoformat(),
            'title': video_info.get('title', 'Unknown'),
            'url': video_info.get('webpage_url', ''),
            'platform': video_info.get('extractor', 'Unknown'),
            'quality': quality,
            'format': format,
            'size': size,
            'duration': video_info.get('duration', 0)
        }
        
        await self.db.set(DOWNLOADS_FILE, download_id, download_data)
        await self.db.update(STATS_FILE, 'global', {
            'total_downloads': self.db.get(STATS_FILE, 'global', {}).get('total_downloads', 0) + 1,
            'total_size': self.db.get(STATS_FILE, 'global', {}).get('total_size', 0) + size
        })

# ==================== معالج الفيديو المتقدم ====================
class VideoProcessor:
    """معالج الفيديو المتقدم مع دعم yt-dlp"""
    
    def __init__(self):
        self.ydl_opts_base = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'no_color': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'extract_flat': False,
            'force_generic_extractor': False,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'file_access_retries': 5,
            'extractor_retries': 5,
            'skip_unavailable_fragments': True,
        }
        
        if os.path.exists(COOKIES_FILE):
            self.ydl_opts_base['cookiefile'] = COOKIES_FILE
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """الحصول على معلومات الفيديو"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts_base) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: ydl.extract_info(url, download=False)
                )
                return self.process_video_info(info)
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def process_video_info(self, info: Dict) -> Dict:
        """معالجة معلومات الفيديو"""
        # المعلومات الأساسية
        video_info = {
            'id': info.get('id', ''),
            'title': info.get('title', 'غير معروف'),
            'description': info.get('description', 'لا يوجد وصف'),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'غير معروف'),
            'uploader_id': info.get('uploader_id', ''),
            'uploader_url': info.get('uploader_url', ''),
            'channel': info.get('channel', 'غير معروف'),
            'channel_id': info.get('channel_id', ''),
            'channel_url': info.get('channel_url', ''),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'dislike_count': info.get('dislike_count', 0),
            'comment_count': info.get('comment_count', 0),
            'average_rating': info.get('average_rating', 0),
            'age_limit': info.get('age_limit', 0),
            'webpage_url': info.get('webpage_url', ''),
            'thumbnail': info.get('thumbnail', ''),
            'thumbnails': info.get('thumbnails', []),
            'upload_date': info.get('upload_date', ''),
            'release_date': info.get('release_date', ''),
            'modified_date': info.get('modified_date', ''),
            'categories': info.get('categories', []),
            'tags': info.get('tags', []),
            'extractor': info.get('extractor', ''),
            'extractor_key': info.get('extractor_key', ''),
            'format': info.get('format', ''),
            'format_id': info.get('format_id', ''),
            'width': info.get('width', 0),
            'height': info.get('height', 0),
            'fps': info.get('fps', 0),
            'vcodec': info.get('vcodec', ''),
            'acodec': info.get('acodec', ''),
            'abr': info.get('abr', 0),
            'vbr': info.get('vbr', 0),
            'filesize': info.get('filesize', 0),
            'filesize_approx': info.get('filesize_approx', 0),
            'protocol': info.get('protocol', ''),
            'resolution': info.get('resolution', ''),
            'quality': info.get('quality', 0),
            'has_subtitles': bool(info.get('subtitles')),
            'has_automatic_subtitles': bool(info.get('automatic_captions')),
            'is_live': info.get('is_live', False),
            'was_live': info.get('was_live', False),
            'playlist': info.get('playlist', None),
            'playlist_index': info.get('playlist_index', 0),
            'requested_subtitles': info.get('requested_subtitles', None),
        }
        
        # إضافة الصيغ المتاحة
        video_info['formats'] = []
        if 'formats' in info:
            for f in info['formats']:
                if f.get('height') or f.get('format_note') == 'audio only':
                    format_info = {
                        'format_id': f.get('format_id', ''),
                        'format_note': f.get('format_note', ''),
                        'ext': f.get('ext', ''),
                        'width': f.get('width', 0),
                        'height': f.get('height', 0),
                        'fps': f.get('fps', 0),
                        'vcodec': f.get('vcodec', 'none'),
                        'acodec': f.get('acodec', 'none'),
                        'abr': f.get('abr', 0),
                        'vbr': f.get('vbr', 0),
                        'filesize': f.get('filesize', 0),
                        'filesize_approx': f.get('filesize_approx', 0),
                        'format': f.get('format', ''),
                        'url': f.get('url', ''),
                        'protocol': f.get('protocol', ''),
                        'language': f.get('language', None),
                        'preference': f.get('preference', None),
                        'quality': f.get('quality', None)
                    }
                    video_info['formats'].append(format_info)
        
        return video_info
    
    async def search_videos(self, query: str, limit: int = 10) -> List[Dict]:
        """البحث عن فيديوهات"""
        try:
            ydl_opts = {
                **self.ydl_opts_base,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                )
                
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry:
                            videos.append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', ''),
                                'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{entry.get('id', '')}/maxresdefault.jpg",
                                'channel': entry.get('uploader', ''),
                                'views': entry.get('view_count', 0),
                                'upload_date': entry.get('upload_date', '')
                            })
                return videos
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def get_trending(self, category: str = 'trending', limit: int = 10) -> List[Dict]:
        """الحصول على الفيديوهات الأكثر مشاهدة"""
        try:
            ydl_opts = {
                **self.ydl_opts_base,
                'extract_flat': True,
            }
            
            search_queries = {
                'trending': 'trending',
                'music': 'music video',
                'gaming': 'gaming',
                'news': 'news',
                'sports': 'sports',
                'education': 'educational'
            }
            
            query = search_queries.get(category, 'trending')
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                )
                
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry:
                            videos.append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', ''),
                                'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{entry.get('id', '')}/maxresdefault.jpg",
                                'channel': entry.get('uploader', ''),
                                'views': entry.get('view_count', 0)
                            })
                return videos
        except Exception as e:
            logger.error(f"Trending error: {e}")
            return []
    
    async def download_video(self, url: str, quality: str = 'best', format: str = 'mp4', 
                            progress_callback=None) -> Optional[Dict]:
        """تحميل الفيديو"""
        try:
            # إعدادات التحميل
            if quality == 'best':
                format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                height = VIDEO_QUALITIES.get(quality, {}).get('height', 720)
                format_spec = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'
            
            if format == 'mp3':
                format_spec = 'bestaudio/best'
            
            filename = os.path.join(
                DOWNLOAD_FOLDER,
                f"video_{int(time.time())}_{random.randint(1000, 9999)}.%(ext)s"
            )
            
            ydl_opts = {
                **self.ydl_opts_base,
                'format': format_spec,
                'outtmpl': filename,
                'progress_hooks': [progress_callback] if progress_callback else [],
                'writethumbnail': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['ar', 'en'],
                'embedsubs': True,
                'embedthumbnail': True,
                'embedmetadata': True,
                'addmetadata': True,
                'xattrs': True,
            }
            
            # إضافة postprocessors للصوت
            if format == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            # التحميل
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=True)
                )
                
                # الحصول على اسم الملف
                file = ydl.prepare_filename(info)
                
                # تعديل الامتداد
                if format == 'mp3':
                    file = file.replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                else:
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test_file = file.replace('%(ext)s', ext)
                        if os.path.exists(test_file):
                            file = test_file
                            break
                
                if os.path.exists(file):
                    size = os.path.getsize(file)
                    
                    return {
                        'success': True,
                        'file': file,
                        'size': size,
                        'info': self.process_video_info(info),
                        'title': info.get('title', ''),
                        'duration': info.get('duration', 0)
                    }
                
                return {'success': False, 'error': 'File not found'}
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            return {'success': False, 'error': str(e)}

# ==================== البوت الرئيسي ====================
class VideoDownloaderBot:
    """البوت الرئيسي المتكامل"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.user_manager = UserManager(self.db)
        self.stats_manager = StatsManager(self.db)
        self.video_processor = VideoProcessor()
        self.user_sessions = {}
        self.active_downloads = {}
        self.start_time = datetime.now()
        
        # التحقق من FFmpeg
        self.check_ffmpeg()
        
        logger.info("✅ تم تهيئة البوت بنجاح")
    
    def check_ffmpeg(self):
        """التحقق من تثبيت FFmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                logger.info(f"✅ FFmpeg: {version[:50]}...")
            else:
                logger.warning("⚠️ FFmpeg غير مثبت بشكل صحيح")
        except FileNotFoundError:
            logger.warning("⚠️ FFmpeg غير مثبت - بعض الميزات قد لا تعمل")
    
    # ========== دوال المساعدة ==========
    def format_time(self, seconds: int) -> str:
        """تنسيق الوقت بشكل احترافي"""
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
    
    def format_size(self, size_bytes: int) -> str:
        """تنسيق الحجم بشكل احترافي"""
        if size_bytes == 0:
            return "0 B"
        
        try:
            size_names = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
            i = 0
            while size_bytes >= 1024 and i < len(size_names) - 1:
                size_bytes /= 1024.0
                i += 1
            return f"{size_bytes:.2f} {size_names[i]}"
        except:
            return "Unknown"
    
    def format_number(self, number: int) -> str:
        """تنسيق الأرقام"""
        if number >= 1_000_000_000:
            return f"{number/1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        return str(number)
    
    def get_platform_info(self, url: str) -> Dict:
        """الحصول على معلومات المنصة من الرابط"""
        for platform_id, info in SUPPORTED_PLATFORMS.items():
            if re.search(info['url_pattern'], url, re.I):
                return {
                    'id': platform_id,
                    **info
                }
        return {
            'id': 'unknown',
            'name': 'غير معروفة',
            'emoji': '🌐',
            'color': 'gray',
            'quality': 'غير معروف',
            'speed': 'غير معروف',
            'login': 'غير معروف'
        }
    
    def create_progress_bar(self, percentage: float, width: int = 10) -> str:
        """إنشاء شريط تقدم"""
        filled = int(width * percentage / 100)
        empty = width - filled
        return '█' * filled + '░' * empty
    
    # ========== معالج الأوامر الرئيسية ==========
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start"""
        user = update.effective_user
        user_data = await self.user_manager.get_user(user.id)
        
        # تحديث المعلومات
        await self.user_manager.update_user(user.id, {
            'username': user.username,
            'first_name': user.first_name,
            'last_active': datetime.now().isoformat()
        })
        
        # إحصائيات البوت
        uptime = datetime.now() - self.start_time
        users_count = len(self.db.get(USERS_FILE, {}))
        downloads_count = self.stats_manager.db.get(STATS_FILE, 'global', {}).get('total_downloads', 0)
        
        welcome_text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات الاحترافي الإصدار {BOT_VERSION} 🚀

📥 *أرسل لي رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات المتطورة:*
• تحميل من {len(SUPPORTED_PLATFORMS)}+ منصة
• جودات متعددة (144p - 8K)
• صيغ متعددة (MP4, MP3, MKV, وغيرها)
• مشاهدة مباشرة مع رابط يوتيوب
• تصفح الفيديوهات بفئات متعددة
• إضافة للمفضلة والمشاهدة لاحقاً
• إحصائيات شخصية متقدمة
• إعدادات مخصصة لكل مستخدم
• نظام إحالة ومكافآت
• إنجازات وشارات

📊 *إحصائيات البوت:*
👥 المستخدمين: {users_count:,}
📥 التحميلات: {downloads_count:,}
⏰ مدة التشغيل: {self.format_time(int(uptime.total_seconds()))}

🔰 *الأوامر المتاحة:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/search - بحث متقدم
/trending - الأكثر مشاهدة
/favorites - المفضلة
/watchlater - المشاهدة لاحقاً
/history - سجل النشاط
/stats - إحصائياتي
/settings - الإعدادات
/profile - ملفي الشخصي
/referrals - نظام الإحالة
/help - المساعدة
/about - عن البوت

👇 *اختر ما تريد فعله:*
        """
        
        # القائمة الرئيسية
        keyboard = [
            [
                InlineKeyboardButton("🔥 تصفح", callback_data="browse"),
                InlineKeyboardButton("🔍 بحث", callback_data="search"),
                InlineKeyboardButton("📥 تحميل", callback_data="download")
            ],
            [
                InlineKeyboardButton("⭐ المفضلة", callback_data="favorites"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="watchlater"),
                InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")
            ],
            [
                InlineKeyboardButton("⚙️ إعدادات", callback_data="settings"),
                InlineKeyboardButton("👤 ملفي", callback_data="profile"),
                InlineKeyboardButton("❓ مساعدة", callback_data="help")
            ]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج التصفح"""
        query = update.callback_query
        await query.answer()
        
        # إنشاء أزرار الفئات
        keyboard = []
        row = []
        
        for i, (cat_id, cat_info) in enumerate(VIDEO_CATEGORIES.items(), 1):
            button = InlineKeyboardButton(
                f"{cat_info['emoji']} {cat_info['name']}",
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
            "🔥 *تصفح الفيديوهات*\n\nاختر الفئة التي تريد تصفحها:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """معالج تصفح فئة معينة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text(
            f"⏳ جاري تحميل {VIDEO_CATEGORIES[category]['name']}...",
            parse_mode='Markdown'
        )
        
        # الحصول على الفيديوهات
        videos = await self.video_processor.get_trending(category, limit=10)
        
        if not videos:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات في هذه الفئة",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="browse")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        # حفظ في الجلسة
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        self.user_sessions[user_id]['browse'] = {
            'category': category,
            'videos': videos,
            'page': 0
        }
        
        # عرض أول فيديو
        await self.show_video(update, context, videos[0], 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                        video: Dict, index: int, total: int = None):
        """عرض فيديو مع الصورة والوصف"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        # معلومات إضافية
        duration = self.format_time(video.get('duration', 0))
        views = self.format_number(video.get('views', 0))
        
        # نص الوصف
        text = f"""
🎬 *{html.escape(video['title'][:200])}*

📺 *القناة:* {html.escape(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 *رابط المشاهدة على يوتيوب:*
[اضغط هنا للمشاهدة]({video['url']})

📝 *لتحميل الفيديو:* استخدم الأزرار أدناه
        """
        
        # أزرار الفيديو
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data=f"fav_{video['url']}_{video['title'][:50]}"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data=f"wl_{video['url']}_{video['title'][:50]}")
            ]
        ]
        
        # أزرار التنقل
        nav_buttons = []
        session = self.user_sessions.get(user_id, {}).get('browse', {})
        videos = session.get('videos', [])
        
        if videos:
            if index > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"nav_prev"))
            if index < len(videos) - 1:
                nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"nav_next"))
            
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
                parse_mode='Markdown'
            )
        except Exception as e:
            # إذا فشل إرسال الصورة
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الرسائل النصية"""
        text = update.message.text
        user = update.effective_user
        
        # تحديث آخر نشاط
        await self.user_manager.update_user(user.id, {
            'last_active': datetime.now().isoformat()
        })
        
        # التحقق من رابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالج روابط الفيديو"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        # معلومات المنصة
        platform = self.get_platform_info(url)
        
        try:
            # الحصول على معلومات الفيديو
            info = await self.video_processor.get_video_info(url)
            
            if not info:
                await msg.edit_text(
                    f"❌ تعذر الحصول على معلومات الفيديو\n\n"
                    f"المنصة: {platform['emoji']} {platform['name']}\n"
                    f"الرابط: {url[:50]}..."
                )
                return
            
            # التحقق من المدة
                        if info['duration'] > MAX_DURATION:
                await msg.edit_text(
                    f"❌ عذراً، مدة الفيديو ({self.format_time(info['duration'])}) تتجاوز الحد المسموح ({self.format_time(MAX_DURATION)})"
                )
                return
            
            # حفظ المعلومات في الجلسة
            user_id = update.effective_user.id
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id]['current_video'] = info
            
            # نص معلومات الفيديو
            text = f"""
{platform['emoji']} *معلومات الفيديو*

📹 *العنوان:* {html.escape(info['title'][:200])}
⏱ *المدة:* {self.format_time(info['duration'])}
📊 *المنصة:* {platform['emoji']} {platform['name']}
👤 *الرافع:* {html.escape(info['uploader'])}
👁 *المشاهدات:* {self.format_number(info['view_count'])}
👍 *الإعجابات:* {self.format_number(info['like_count'])}
📅 *تاريخ الرفع:* {info['upload_date'] or 'غير معروف'}

🔗 *رابط المشاهدة:*
[اضغط هنا للمشاهدة]({info['webpage_url']})

📥 *لتحميل الفيديو:* استخدم الأزرار أدناه
            """
            
            # أزرار الفيديو
            keyboard = [
                [
                    InlineKeyboardButton("▶️ مشاهدة", url=info['webpage_url']),
                    InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
                ],
                [
                    InlineKeyboardButton("⭐ للمفضلة", callback_data=f"add_favorite"),
                    InlineKeyboardButton("⏰ للمشاهدة", callback_data=f"add_watchlater")
                ],
                [
                    InlineKeyboardButton("ℹ️ معلومات إضافية", callback_data="more_info"),
                    InlineKeyboardButton("🔄 جودات متاحة", callback_data="available_qualities")
                ],
                [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
            ]
            
            # إرسال الصورة المصغرة
            try:
                await msg.delete()
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except:
                await msg.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            
            # إضافة للسجل
            await self.user_manager.add_to_history(user_id, info)
            
        except Exception as e:
            logger.error(f"URL handling error: {e}")
            await msg.edit_text(
                f"❌ خطأ في معالجة الرابط: {str(e)[:200]}\n\n"
                f"المنصة: {platform['emoji']} {platform['name']}\n"
                f"الرابط: {url[:50]}..."
            )
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالج البحث"""
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        
        try:
            # البحث عن فيديوهات
            videos = await self.video_processor.search_videos(query, limit=10)
            
            if not videos:
                await msg.edit_text(
                    f"❌ لا توجد نتائج للبحث: '{query}'",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                    ]])
                )
                return
            
            # حفظ نتائج البحث
            user_id = update.effective_user.id
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id]['search_results'] = videos
            self.user_sessions[user_id]['search_page'] = 0
            
            # عرض أول نتيجة
            await self.show_search_result(update, context, videos[0], 0)
            await msg.delete()
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await msg.edit_text(f"❌ خطأ في البحث: {str(e)[:200]}")
    
    async def show_search_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                video: Dict, index: int):
        """عرض نتيجة بحث"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        duration = self.format_time(video.get('duration', 0))
        views = self.format_number(video.get('views', 0))
        
        text = f"""
🔍 *نتيجة البحث ({index + 1})*

🎬 *{html.escape(video['title'][:200])}*

📺 *القناة:* {html.escape(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 *رابط المشاهدة:*
[اضغط هنا للمشاهدة]({video['url']})
        """
        
        # أزرار التنقل
        keyboard = []
        videos = self.user_sessions.get(user_id, {}).get('search_results', [])
        
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="search_prev"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data="search_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.extend([
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ],
            [InlineKeyboardButton("🔙 بحث جديد", callback_data="search")]
        ])
        
        try:
            if query:
                await query.message.delete()
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=video['thumbnail'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_photo(
                    photo=video['thumbnail'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except:
            if query:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة التحميل"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
        
        if not video_info:
            await query.edit_message_text(
                "❌ لا توجد معلومات فيديو. أرسل رابط فيديو أولاً.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]])
            )
            return
        
        text = f"""
📥 *اختر خيارات التحميل*

🎬 *الفيديو:* {html.escape(video_info.get('title', '')[:100])}
⏱ *المدة:* {self.format_time(video_info.get('duration', 0))}

👇 *اختر الجودة المطلوبة:*
        """
        
        # أزرار الجودات
        keyboard = []
        row = []
        
        for i, (quality_id, quality_info) in enumerate(VIDEO_QUALITIES.items(), 1):
            button = InlineKeyboardButton(
                f"{quality_info['emoji']} {quality_info['name']}",
                callback_data=f"quality_{quality_id}"
            )
            row.append(button)
            
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_video")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        """اختيار الجودة"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
        
        text = f"""
📥 *اختر الصيغة*

🎬 *الجودة:* {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}
⏱ *المدة:* {self.format_time(video_info.get('duration', 0))}

👇 *اختر الصيغة المطلوبة:*
        """
        
        # أزرار الصيغ
        keyboard = []
        row = []
        
        for i, (format_id, format_info) in enumerate(DOWNLOAD_FORMATS.items(), 1):
            button = InlineKeyboardButton(
                f"{format_info['emoji']} {format_info['name']}",
                callback_data=f"format_{quality}_{format_id}"
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
            parse_mode='Markdown'
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                            quality: str, format: str):
        """بدء التحميل"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
        url = video_info.get('webpage_url', '')
        
        if not url:
            await query.edit_message_text("❌ لا يوجد رابط فيديو")
            return
        
        # التحقق من الحدود اليومية
        can_download, message = await self.user_manager.check_daily_limit(user_id, 0)
        if not can_download:
            await query.edit_message_text(message)
            return
        
        # رسالة بدء التحميل
        progress_msg = await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n"
            f"🎬 {html.escape(video_info.get('title', '')[:100])}\n"
            f"⚡ الجودة: {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}\n"
            f"📁 الصيغة: {DOWNLOAD_FORMATS[format]['emoji']} {DOWNLOAD_FORMATS[format]['name']}\n\n"
            f"⏳ يرجى الانتظار...",
            parse_mode='Markdown'
        )
        
        try:
            # دالة تتبع التقدم
            def progress_hook(d):
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    if total > 0:
                        percentage = (downloaded / total) * 100
                        speed = d.get('speed', 0)
                        speed_str = self.format_size(speed) + '/s' if speed else '?'
                        eta = d.get('eta', 0)
                        
                        # تحديث كل 5%
                        if int(percentage) % 5 == 0:
                            progress_bar = self.create_progress_bar(percentage)
                            text = (
                                f"⬇️ *جاري التحميل...*\n\n"
                                f"📊 {progress_bar} {percentage:.1f}%\n"
                                f"⚡ السرعة: {speed_str}\n"
                                f"⏱ الوقت المتبقي: {self.format_time(eta)}\n"
                                f"📦 تم: {self.format_size(downloaded)} / {self.format_size(total)}"
                            )
                            asyncio.create_task(progress_msg.edit_text(text, parse_mode='Markdown'))
            
            # تحميل الفيديو
            result = await self.video_processor.download_video(
                url=url,
                quality=quality,
                format=format,
                progress_callback=progress_hook
            )
            
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
                
                # تسجيل في الإحصائيات
                await self.stats_manager.log_download(
                    user_id=user_id,
                    video_info=video_info,
                    quality=quality,
                    format=format,
                    size=size
                )
                
                # إرسال الفيديو
                caption = (
                    f"✅ *تم التحميل بنجاح!*\n\n"
                    f"🎬 {html.escape(video_info.get('title', '')[:100])}\n"
                    f"⚡ الجودة: {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}\n"
                    f"📁 الصيغة: {DOWNLOAD_FORMATS[format]['emoji']} {DOWNLOAD_FORMATS[format]['name']}\n"
                    f"📦 الحجم: {self.format_size(size)}\n"
                    f"⏱ المدة: {self.format_time(video_info.get('duration', 0))}\n\n"
                    f"شكراً لاستخدامك البوت ❤️"
                )
                
                with open(file, 'rb') as f:
                    if format == 'mp3':
                        await context.bot.send_audio(
                            chat_id=user_id,
                            audio=f,
                            caption=caption,
                            parse_mode='Markdown',
                            title=video_info.get('title', '')[:100],
                            performer=video_info.get('uploader', ''),
                            duration=video_info.get('duration', 0)
                        )
                    else:
                        await context.bot.send_video(
                            chat_id=user_id,
                            video=f,
                            caption=caption,
                            parse_mode='Markdown',
                            supports_streaming=True,
                            duration=video_info.get('duration', 0),
                            width=video_info.get('width', 0),
                            height=video_info.get('height', 0)
                        )
                
                # حذف الملف
                os.remove(file)
                await progress_msg.delete()
                
            else:
                await progress_msg.edit_text(f"❌ فشل التحميل: {result.get('error', 'خطأ غير معروف')}")
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            await progress_msg.edit_text(f"❌ خطأ في التحميل: {str(e)[:200]}")
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المفضلة"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        favorites = user_data.get('favorites', [])
        
        if not favorites:
            await query.edit_message_text(
                "⭐ *المفضلة*\n\nلا توجد فيديوهات في المفضلة بعد.\n\nأضف فيديوهات للمفضلة بالضغط على زر ⭐ أثناء مشاهدة أي فيديو.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        text = "⭐ *المفضلة*\n\n"
        keyboard = []
        
        for i, fav in enumerate(reversed(favorites[-10:]), 1):
            title = fav.get('title', '')[:50]
            duration = self.format_time(fav.get('duration', 0))
            platform = fav.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {title} - {duration}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"fav_{fav['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_watch_later(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة المشاهدة لاحقاً"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        watch_later = user_data.get('watch_later', [])
        
        if not watch_later:
            await query.edit_message_text(
                "⏰ *للمشاهدة لاحقاً*\n\nلا توجد فيديوهات في القائمة.\n\nأضف فيديوهات للقائمة بالضغط على زر ⏰ أثناء مشاهدة أي فيديو.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        text = "⏰ *للمشاهدة لاحقاً*\n\n"
        keyboard = []
        
        for i, item in enumerate(reversed(watch_later[-10:]), 1):
            title = item.get('title', '')[:50]
            duration = self.format_time(item.get('duration', 0))
            platform = item.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {title} - {duration}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"wl_{item['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض سجل النشاط"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        history = user_data.get('history', [])[-20:]
        
        if not history:
            await query.edit_message_text(
                "📜 *سجل النشاط*\n\nلا يوجد سجل بعد.\n\nشاهد أو حمل بعض الفيديوهات لتظهر هنا.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        text = "📜 *آخر 20 نشاط*\n\n"
        keyboard = []
        
        for i, item in enumerate(reversed(history), 1):
            date = item.get('date', '')[:10]
            title = item.get('title', '')[:40]
            platform = item.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {title}\n   📅 {date}\n\n"
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإحصائيات الشخصية"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        
        # حساب الإحصائيات
        joined = datetime.fromisoformat(user_data.get('joined_date', datetime.now().isoformat()))
        days_active = (datetime.now() - joined).days
        
        downloads = user_data.get('download_count', 0)
        total_size = user_data.get('total_size', 0)
        favorites = len(user_data.get('favorites', []))
        watch_later = len(user_data.get('watch_later', []))
        history = len(user_data.get('history', []))
        
        stats_text = f"""
📊 *إحصائياتك الشخصية*

👤 *المستخدم:* {user_data.get('first_name', 'Unknown')}
📅 *عضو منذ:* {days_active} يوم
⭐ *الحالة:* {'مميز ⭐' if user_data.get('is_premium') else 'عادي'}

📥 *التحميلات:*
• عدد التحميلات: {downloads:,}
• حجم التحميلات: {self.format_size(total_size)}
• متوسط الحجم: {self.format_size(total_size // (downloads or 1))}

🎬 *المحتوى:*
• في المفضلة: {favorites}
• للمشاهدة لاحقاً: {watch_later}
• في السجل: {history}

⚙️ *الإعدادات:*
• الجودة الافتراضية: {VIDEO_QUALITIES.get(user_data.get('settings', {}).get('default_quality', 'best'), {}).get('name', 'أفضل جودة')}
• الصيغة الافتراضية: {DOWNLOAD_FORMATS.get(user_data.get('settings', {}).get('default_format', 'mp4'), {}).get('name', 'MP4')}
• الحذف التلقائي: {'✅' if user_data.get('settings', {}).get('auto_delete', True) else '❌'}

🏆 *الإنجازات:*
• {len(user_data.get('achievements', []))} إنجاز
• {len(user_data.get('badges', []))} شارة
        """
        
        keyboard = [
            [InlineKeyboardButton("📥 سجل التحميلات", callback_data="download_history")],
            [InlineKeyboardButton("🏆 الإنجازات", callback_data="achievements")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإعدادات"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        settings = user_data.get('settings', {})
        
        settings_text = f"""
⚙️ *الإعدادات الشخصية*

🔰 *الإعدادات الحالية:*

🎬 *الجودة الافتراضية:* {VIDEO_QUALITIES.get(settings.get('default_quality', 'best'), {}).get('name', 'أفضل جودة')}
📁 *الصيغة الافتراضية:* {DOWNLOAD_FORMATS.get(settings.get('default_format', 'mp4'), {}).get('name', 'MP4')}
🗑 *الحذف التلقائي:* {'✅' if settings.get('auto_delete', True) else '❌'}
🔔 *الإشعارات:* {'✅' if settings.get('notifications', True) else '❌'}
🌙 *الوضع الليلي:* {'✅' if settings.get('dark_mode', True) else '❌'}
📝 *حفظ السجل:* {'✅' if settings.get('save_history', True) else '❌'}
🎯 *الحد الأقصى للجودة:* {settings.get('max_quality', '1080p')}
🎥 *الكوديك المفضل:* {settings.get('preferred_codec', 'h264')}

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
            parse_mode='Markdown'
        )
    
    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الملف الشخصي"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        
        # حساب المستوى
        downloads = user_data.get('download_count', 0)
        level = downloads // 10 + 1
        next_level = (level * 10) - downloads
        
        profile_text = f"""
👤 *الملف الشخصي*

🆔 *المعرف:* {user_id}
📛 *الاسم:* {user_data.get('first_name', 'Unknown')}
🔰 *اسم المستخدم:* @{user_data.get('username', 'لا يوجد')}

⭐ *المستوى:* {level}
📊 *نقاط الخبرة:* {downloads}/100
📈 *التقدم:* {self.create_progress_bar((downloads % 10) * 10)} {downloads % 10 * 10}%

🏅 *الشارات:*
{self.format_badges(user_data.get('badges', []))}

📊 *الإحصائيات:*
• التحميلات: {downloads}
• المفضلة: {len(user_data.get('favorites', []))}
• المشاهدة لاحقاً: {len(user_data.get('watch_later', []))}
• الأيام النشطة: {(datetime.now() - datetime.fromisoformat(user_data.get('joined_date', datetime.now().isoformat()))).days}

🔗 *كود الإحالة:* `{user_data.get('referral_code', '')}`
👥 *عدد المحالين:* {len(user_data.get('referrals', []))}
        """
        
        keyboard = [
            [InlineKeyboardButton("🏆 الإنجازات", callback_data="achievements")],
            [InlineKeyboardButton("📊 إحصائيات متقدمة", callback_data="advanced_stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            profile_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    def format_badges(self, badges: List[str]) -> str:
        """تنسيق عرض الشارات"""
        badge_emojis = {
            'new': '🆕',
            'veteran': '⚔️',
            'expert': '🏆',
            'legend': '👑',
            'downloader': '📥',
            'favorite': '⭐',
            'social': '👥',
            'premium': '💎'
        }
        
        if not badges:
            return "لا توجد شارات بعد"
        
        return ' '.join([badge_emojis.get(b, '🎖️') for b in badges])
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المساعدة"""
        query = update.callback_query
        await query.answer()
        
        help_text = f"""
❓ *مساعدة البوت*

📥 *تحميل الفيديوهات:*
• أرسل رابط الفيديو مباشرة
• اختر الجودة المناسبة
• اختر الصيغة المطلوبة
• انتظر التحميل واستلم الفيديو

🔍 *البحث عن فيديوهات:*
• اكتب أي كلمة للبحث
• تصفح النتائج مع الصور
• اختر الفيديو المناسب
• حمله أو شاهده مباشرة

🔥 *تصفح الفيديوهات:*
• استخدم قائمة التصفح
• اختر الفئة المناسبة
• تصفح الفيديوهات مع الصور
• شاهد أو حمل ما تريد

⭐ *المفضلة:*
• أضف فيديوهات للمفضلة
• رجع لها في أي وقت
• نظم قائمتك المفضلة

⏰ *للمشاهدة لاحقاً:*
• احفظ فيديوهات لمشاهدتها لاحقاً
• لا تفوت فيديوهات مهمة
• نظم وقت مشاهدتك

⚙️ *الإعدادات:*
• خصص البوت حسب رغبتك
• اختر الجودة الافتراضية
• ضبط الإشعارات والمظهر

📊 *الإحصائيات:*
• تتبع نشاطك في البوت
• اعرف عدد تحميلاتك
• شاهد تقدمك ومستواك

👤 *الملف الشخصي:*
• اعرض معلوماتك
• اجمع الشارات والإنجازات
• ادع أصدقاءك بكود إحالة

🌐 *المنصات المدعومة:*
{', '.join([f"{p['emoji']} {p['name']}" for p in SUPPORTED_PLATFORMS.values()][:10])}
والمزيد...

📌 *للدعم والاستفسارات:* @YourSupport
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض معلومات البوت"""
        query = update.callback_query
        await query.answer()
        
        # إحصائيات عامة
        stats = await self.stats_manager.get_detailed_stats()
        
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        about_text = f"""
ℹ️ *عن البوت*

🤖 *الاسم:* بوت تحميل الفيديوهات المتطور
📊 *الإصدار:* {BOT_VERSION}
📅 *تاريخ الإصدار:* {BOT_RELEASE_DATE}
👨‍💻 *المطور:* @YourUsername
📦 *المنصة:* Python + Telegram Bot API

✨ *المميزات:*
• تحميل من {len(SUPPORTED_PLATFORMS)}+ منصة
• {len(VIDEO_QUALITIES)} جودة مختلفة (حتى 8K)
• {len(DOWNLOAD_FORMATS)} صيغة مختلفة
• {len(VIDEO_CATEGORIES)} فئة للتصفح
• نظام إنجازات وشارات
• نظام إحالة ومكافآت
• إحصائيات متقدمة

📊 *الإحصائيات العامة:*
👥 المستخدمين: {stats['total_users']:,}
📥 التحميلات: {stats['total_downloads']:,}
📦 حجم التحميلات: {self.format_size(stats['total_size'])}
⭐ المستخدمين المميزين: {stats['premium_users']}
🔥 النشطون اليوم: {stats['active_today']}

⏰ *مدة التشغيل:* {days} يوم {hours:02d}:{minutes:02d}

❤️ *شكراً لاستخدامك البوت!*
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        await query.edit_message_text(
            about_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج جميع الأزرار"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
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
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data == "download":
            await query.edit_message_text(
                "📥 *تحميل*\n\nأرسل رابط الفيديو الآن:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data == "favorites":
            await self.show_favorites(update, context)
        
        elif data == "watchlater":
            await self.show_watch_later(update, context)
        
        elif data == "stats":
            await self.show_stats(update, context)
        
        elif data == "settings":
            await self.show_settings(update, context)
        
        elif data == "profile":
            await self.show_profile(update, context)
        
        elif data == "help":
            await self.show_help(update, context)
        
        elif data == "about":
            await self.show_about(update, context)
        
        # أزرار التصفح
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            await self.browse_category(update, context, category)
        
        elif data == "nav_prev":
            session = self.user_sessions.get(user_id, {}).get('browse', {})
            videos = session.get('videos', [])
            page = session.get('page', 0)
            if page > 0:
                session['page'] = page - 1
                await self.show_video(update, context, videos[page - 1], page - 1)
        
        elif data == "nav_next":
            session = self.user_sessions.get(user_id, {}).get('browse', {})
            videos = session.get('videos', [])
            page = session.get('page', 0)
            if page < len(videos) - 1:
                session['page'] = page + 1
                await self.show_video(update, context, videos[page + 1], page + 1)
        
        # أزرار البحث
        elif data == "search_prev":
            session = self.user_sessions.get(user_id, {})
            videos = session.get('search_results', [])
            page = session.get('search_page', 0)
            if page > 0:
                session['search_page'] = page - 1
                await self.show_search_result(update, context, videos[page - 1], page - 1)
        
        elif data == "search_next":
            session = self.user_sessions.get(user_id, {})
            videos = session.get('search_results', [])
            page = session.get('search_page', 0)
            if page < len(videos) - 1:
                session['search_page'] = page + 1
                await self.show_search_result(update, context, videos[page + 1], page + 1)
        
        # أزرار التحميل
        elif data == "download_menu":
            await self.download_menu(update, context)
        
        elif data == "back_to_video":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                await self.show_video_info(update, context, video_info)
            else:
                await self.browse(update, context)
        
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            await self.select_quality(update, context, quality)
        
        elif data.startswith("format_"):
            parts = data.replace("format_", "").split("_")
            quality = parts[0]
            format = parts[1]
            await self.start_download(update, context, quality, format)
        
        # أزرار المفضلة والمشاهدة لاحقاً
        elif data.startswith("fav_"):
            url = data.replace("fav_", "").split("_")[0]
            video_info = {'webpage_url': url}
            await self.user_manager.add_to_favorites(user_id, video_info)
            await query.answer("✅ تمت الإضافة للمفضلة")
        
        elif data.startswith("wl_"):
            url = data.replace("wl_", "").split("_")[0]
            video_info = {'webpage_url': url}
            await self.user_manager.add_to_watch_later(user_id, video_info)
            await query.answer("✅ تمت الإضافة للمشاهدة لاحقاً")
        
        elif data == "add_favorite":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                await self.user_manager.add_to_favorites(user_id, video_info)
                await query.answer("✅ تمت الإضافة للمفضلة")
        
        elif data == "add_watchlater":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                await self.user_manager.add_to_watch_later(user_id, video_info)
                await query.answer("✅ تمت الإضافة للمشاهدة لاحقاً")
        
        # أزرار الإعدادات
        elif data == "set_default_quality":
            keyboard = []
            row = []
            for i, (q_id, q_info) in enumerate(VIDEO_QUALITIES.items(), 1):
                row.append(InlineKeyboardButton(
                    f"{q_info['emoji']} {q_info['name']}",
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
                parse_mode='Markdown'
            )
        
        elif data.startswith("save_quality_"):
            quality = data.replace("save_quality_", "")
            await self.user_manager.update_user(user_id, {
                'settings': {
                    **(await self.user_manager.get_user(user_id)).get('settings', {}),
                    'default_quality': quality
                }
            })
            await query.answer(f"✅ تم حفظ الجودة الافتراضية: {VIDEO_QUALITIES[quality]['name']}")
            await self.show_settings(update, context)
        
        elif data == "set_default_format":
            keyboard = []
            row = []
            for i, (f_id, f_info) in enumerate(DOWNLOAD_FORMATS.items(), 1):
                row.append(InlineKeyboardButton(
                    f"{f_info['emoji']} {f_info['name']}",
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
                parse_mode='Markdown'
            )
        
        elif data.startswith("save_format_"):
            format = data.replace("save_format_", "")
            await self.user_manager.update_user(user_id, {
                'settings': {
                    **(await self.user_manager.get_user(user_id)).get('settings', {}),
                    'default_format': format
                }
            })
            await query.answer(f"✅ تم حفظ الصيغة الافتراضية: {DOWNLOAD_FORMATS[format]['name']}")
            await self.show_settings(update, context)
        
        elif data == "toggle_auto_delete":
            user_data = await self.user_manager.get_user(user_id)
            current = user_data.get('settings', {}).get('auto_delete', True)
            await self.user_manager.update_user(user_id, {
                'settings': {
                    **user_data.get('settings', {}),
                    'auto_delete': not current
                }
            })
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} الحذف التلقائي")
            await self.show_settings(update, context)
        
        elif data == "toggle_notifications":
            user_data = await self.user_manager.get_user(user_id)
            current = user_data.get('settings', {}).get('notifications', True)
            await self.user_manager.update_user(user_id, {
                'settings': {
                    **user_data.get('settings', {}),
                    'notifications': not current
                }
            })
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} الإشعارات")
            await self.show_settings(update, context)
        
        elif data == "toggle_dark_mode":
            user_data = await self.user_manager.get_user(user_id)
            current = user_data.get('settings', {}).get('dark_mode', True)
            await self.user_manager.update_user(user_id, {
                'settings': {
                    **user_data.get('settings', {}),
                    'dark_mode': not current
                }
            })
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} الوضع الليلي")
            await self.show_settings(update, context)
        
        elif data == "toggle_save_history":
            user_data = await self.user_manager.get_user(user_id)
            current = user_data.get('settings', {}).get('save_history', True)
            await self.user_manager.update_user(user_id, {
                'settings': {
                    **user_data.get('settings', {}),
                    'save_history': not current
                }
            })
            await query.answer(f"✅ تم {'تفعيل' if not current else 'تعطيل'} حفظ السجل")
            await self.show_settings(update, context)
        
        # أزرار المعلومات
        elif data == "more_info":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                text = f"""
ℹ️ *معلومات إضافية*

📹 *العنوان الكامل:* {html.escape(video_info.get('title', ''))}
👤 *الرافع:* {html.escape(video_info.get('uploader', ''))}
🆔 *معرف الرافع:* {video_info.get('uploader_id', '')}
📅 *تاريخ الرفع:* {video_info.get('upload_date', 'غير معروف')}
🔗 *رابط القناة:* {video_info.get('uploader_url', 'غير متوفر')}
🎵 *الصوت متوفر:* {'✅' if video_info.get('acodec') != 'none' else '❌'}
🖼 *الدقة:* {video_info.get('resolution', 'غير معروف')}
⚡ *معدل الإطارات:* {video_info.get('fps', 'غير معروف')} fps
🔊 *معدل الصوت:* {video_info.get('abr', 'غير معروف')} kbps
🎥 *كوديك الفيديو:* {video_info.get('vcodec', 'غير معروف')}
🎧 *كوديك الصوت:* {video_info.get('acodec', 'غير معروف')}
📦 *الحجم التقريبي:* {self.format_size(video_info.get('filesize', 0))}
🌐 *المنصة:* {video_info.get('extractor', 'غير معروفة')}
🔞 *الحد العمري:* {video_info.get('age_limit', 0)}+

📊 *إحصائيات متقدمة:*
👍 الإعجابات: {self.format_number(video_info.get('like_count', 0))}
👎 عدم الإعجاب: {self.format_number(video_info.get('dislike_count', 0))}
👁 المشاهدات: {self.format_number(video_info.get('view_count', 0))}
💬 التعليقات: {self.format_number(video_info.get('comment_count', 0))}
⭐ التقييم: {video_info.get('average_rating', 0):.1f}/5

🏷 *التصنيفات:* {', '.join(video_info.get('categories', ['لا يوجد']))[:100]}
🔖 *الوسوم:* {', '.join(video_info.get('tags', ['لا يوجد']))[:100]}
                """
                
                await query.edit_message_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_video")
                    ]])
                )
        
        elif data == "available_qualities":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            formats = video_info.get('formats', [])
            
            if formats:
                text = "🔄 *الجودات المتاحة:*\n\n"
                qualities = set()
                for f in formats:
                    if f.get('height'):
                        qualities.add(f"{f['height']}p")
                
                for q in sorted(qualities, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0):
                    text += f"• {q}\n"
                
                await query.answer(f"الجودات المتاحة: {', '.join(sorted(qualities, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0))[:50]}")
            else:
                await query.answer("لا توجد معلومات عن الجودات المتاحة")
        
        elif data == "page_info":
            await query.answer("استخدم أزرار التنقل للتصفح بين الفيديوهات")
        
        elif data == "download_history":
            await query.answer("قريباً... جاري تطوير هذه الميزة")
        
        elif data == "achievements":
            await query.answer("قريباً... جاري تطوير هذه الميزة")
        
        elif data == "advanced_stats":
            await query.answer("قريباً... جاري تطوير هذه الميزة")
        
        else:
            await query.answer("إجراء غير معروف")
    
    async def show_video_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video_info: Dict):
        """عرض معلومات الفيديو"""
        query = update.callback_query
        
        platform = self.get_platform_info(video_info.get('webpage_url', ''))
        
        text = f"""
{platform['emoji']} *معلومات الفيديو*

📹 *العنوان:* {html.escape(video_info.get('title', '')[:200])}
⏱ *المدة:* {self.format_time(video_info.get('duration', 0))}
📊 *المنصة:* {platform['emoji']} {platform['name']}
👤 *الرافع:* {html.escape(video_info.get('uploader', ''))}
👁 *المشاهدات:* {self.format_number(video_info.get('view_count', 0))}
👍 *الإعجابات:* {self.format_number(video_info.get('like_count', 0))}

🔗 *رابط المشاهدة:*
[اضغط هنا للمشاهدة]({video_info.get('webpage_url', '')})

📥 *لتحميل الفيديو:* استخدم الأزرار أدناه
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video_info.get('webpage_url', '')),
                InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data="add_favorite"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="add_watchlater")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        
        try:
            await query.edit_message_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
    
    # ========== تشغيل البوت ==========
    def run(self):
        """تشغيل البوت"""
        try:
            # إنشاء التطبيق
            app = Application.builder().token(BOT_TOKEN).build()
            
            # إضافة معالجات الأوامر
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("help", self.show_help))
            app.add_handler(CommandHandler("browse", self.browse))
            app.add_handler(CommandHandler("favorites", self.show_favorites))
            app.add_handler(CommandHandler("watchlater", self.show_watch_later))
            app.add_handler(CommandHandler("history", self.show_history))
            app.add_handler(CommandHandler("stats", self.show_stats))
            app.add_handler(CommandHandler("settings", self.show_settings))
            app.add_handler(CommandHandler("profile", self.show_profile))
            app.add_handler(CommandHandler("about", self.show_about))
            
            # معالج الرسائل النصية
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # معالج الأزرار
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # معالج الأخطاء
            app.add_error_handler(self.error_handler)
            
            # تشغيل البوت
            print("=" * 70)
            print("🚀 بوت تحميل الفيديوهات المتطور - الإصدار 4.0")
            print("=" * 70)
            print(f"✅ البوت يعمل بنجاح!")
            print(f"👥 المستخدمين: {len(self.db.get(USERS_FILE, {}))}")
            print(f"📁 المجلدات: {DOWNLOAD_FOLDER}, {THUMBNAIL_FOLDER}, {LOGS_FOLDER}")
            print(f"⚡ وقت التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 70)
            print("📌 المميزات المضافة:")
            print("   • تحميل من 20+ منصة")
            print("   • 9 جودات مختلفة (حتى 8K)")
            print("   • 12 صيغة مختلفة")
            print("   • 20 فئة للتصفح")
            print("   • نظام إنجازات وشارات")
            print("   • نظام إحالة ومكافآت")
            print("   • إحصائيات متقدمة")
            print("   • ملف شخصي لكل مستخدم")
            print("   • سجل نشاط كامل")
            print("   • إعدادات مخصصة")
            print("=" * 70)
            
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ خطأ في تشغيل البوت: {e}")
            logger.error(f"Bot startup error: {e}")
            traceback.print_exc()
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأخطاء العام"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى لاحقاً.\n\n"
                    "إذا استمرت المشكلة، تواصل مع الدعم الفني @YourSupport"
                )
        except:
            pass

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    # إنشاء وتشغيل البوت
    bot = VideoDownloaderBot()
    bot.run()
