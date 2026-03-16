#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
███████╗██████╗ ███████╗███████╗██████╗ ███████╗ ██████╗ ████████╗
██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝██╔═══██╗╚══██╔══╝
█████╗  ██████╔╝█████╗  █████╗  ██████╔╝█████╗  ██║   ██║   ██║   
██╔══╝  ██╔══██╗██╔══╝  ██╔══╝  ██╔══██╗██╔══╝  ██║   ██║   ██║   
██║     ██║  ██║███████╗███████╗██║  ██║███████╗╚██████╔╝   ██║   
╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝    ╚═╝   
"""

import os
import re
import io
import sys
import time
import json
import asyncio
import logging
import shutil
import hashlib
import inspect
import platform
import tempfile
import subprocess
import importlib
from math import floor
from pathlib import Path
from queue import Queue
from threading import Thread
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List, Union, Callable
from urllib.parse import urlparse, unquote
from functools import wraps, lru_cache
from dataclasses import dataclass, field
from enum import Enum
import traceback

# ================== المكتبات الخارجية ==================
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError, ExtractorError
except ImportError:
    print("❌ يرجى تثبيت yt-dlp: pip install yt-dlp")
    sys.exit(1)

try:
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
    from telegram.error import TelegramError, RetryAfter, TimedOut
except ImportError:
    print("❌ يرجى تثبيت python-telegram-bot: pip install python-telegram-bot==20.3")
    sys.exit(1)

try:
    import aiohttp
    import aiofiles
except ImportError:
    print("⚠️ aiohttp غير مثبت، سيتم استخدام الطرق البديلة")

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("⚠️ cryptography غير مثبت، تشفير الكوكيز غير متاح")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️ Pillow غير مثبت، معالجة الصور محدودة")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# ================== إعدادات الألوان ==================
if HAS_COLORAMA:
    RED = Fore.RED
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    MAGENTA = Fore.MAGENTA
    CYAN = Fore.CYAN
    WHITE = Fore.WHITE
    RESET = Style.RESET_ALL
else:
    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""

# ================== إعدادات البوت الأساسية ==================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع توكن البوت هنا
ADMIN_IDS = [123456789]  # ضع معرفات المشرفين هنا

# إعدادات التحميل
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت
MAX_DURATION = 7200  # أقصى مدة فيديو بالثواني (ساعتين)
MAX_CONCURRENT_DOWNLOADS = 5  # أقصى تحميل متزامن
CHUNK_SIZE = 1024 * 1024  # حجم القطعة للتحميل (1 ميجابايت)

# إعدادات المجلدات
BASE_DIR = Path(__file__).parent.absolute()
DOWNLOAD_DIR = BASE_DIR / "downloads"
COOKIES_DIR = BASE_DIR / "cookies"
CACHE_DIR = BASE_DIR / "cache"
LOGS_DIR = BASE_DIR / "logs"
THUMBNAIL_DIR = BASE_DIR / "thumbnails"
USER_DATA_DIR = BASE_DIR / "user_data"

# إنشاء المجلدات
for dir_path in [DOWNLOAD_DIR, COOKIES_DIR, CACHE_DIR, LOGS_DIR, THUMBNAIL_DIR, USER_DATA_DIR]:
    dir_path.mkdir(exist_ok=True)

# ================== إعدادات التسجيل ==================
log_file = LOGS_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================== أنماط التحميل ==================
class DownloadType(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    PLAYLIST = "playlist"
    CHANNEL = "channel"
    STORY = "story"
    POST = "post"
    IMAGE = "image"
    GIF = "gif"
    LIVE = "live"

class Quality(Enum):
    BEST = "best"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    AUDIO_ONLY = "audio"

# ================== قاعدة بيانات المنصات ==================
@dataclass
class PlatformInfo:
    name: str
    icon: str
    types: List[str]
    quality_levels: List[str]
    needs_auth: bool
    rate_limit: int
    priority: int
    extractor: str
    notes: str = ""

SUPPORTED_PLATFORMS: Dict[str, PlatformInfo] = {
    # منصات فيديو رئيسية
    'youtube': PlatformInfo(
        name='YouTube', icon='📺', 
        types=['video', 'audio', 'playlist', 'channel', 'live'],
        quality_levels=['best', 'high', 'medium', 'low', 'audio'],
        needs_auth=False, rate_limit=10, priority=1, extractor='youtube'
    ),
    'youtu.be': PlatformInfo(
        name='YouTube', icon='📺',
        types=['video', 'audio', 'live'],
        quality_levels=['best', 'high', 'medium', 'low', 'audio'],
        needs_auth=False, rate_limit=10, priority=1, extractor='youtube'
    ),
    'youtube.com/shorts': PlatformInfo(
        name='YouTube Shorts', icon='📱',
        types=['video', 'audio'],
        quality_levels=['best', 'high', 'medium', 'low', 'audio'],
        needs_auth=False, rate_limit=10, priority=1, extractor='youtube'
    ),
    
    # منصات التواصل الاجتماعي
    'instagram.com': PlatformInfo(
        name='Instagram', icon='📸',
        types=['video', 'image', 'story', 'reel', 'post', 'carousel'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=5, priority=2, extractor='instagram'
    ),
    'instagram.com/p/': PlatformInfo(
        name='Instagram Post', icon='📷',
        types=['image', 'video', 'carousel'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=5, priority=2, extractor='instagram'
    ),
    'instagram.com/reel/': PlatformInfo(
        name='Instagram Reel', icon='📱',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=5, priority=2, extractor='instagram'
    ),
    'instagram.com/stories/': PlatformInfo(
        name='Instagram Story', icon='📖',
        types=['video', 'image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=5, priority=2, extractor='instagram'
    ),
    
    'tiktok.com': PlatformInfo(
        name='TikTok', icon='🎵',
        types=['video', 'audio', 'slideshow'],
        quality_levels=['best', 'high', 'medium', 'low', 'audio'],
        needs_auth=False, rate_limit=8, priority=2, extractor='tiktok'
    ),
    'tiktok.com/@': PlatformInfo(
        name='TikTok', icon='🎵',
        types=['video', 'audio'],
        quality_levels=['best', 'high', 'medium', 'low', 'audio'],
        needs_auth=False, rate_limit=8, priority=2, extractor='tiktok'
    ),
    
    'twitter.com': PlatformInfo(
        name='Twitter', icon='🐦',
        types=['video', 'image', 'gif', 'poll'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=15, priority=3, extractor='twitter'
    ),
    'x.com': PlatformInfo(
        name='Twitter', icon='🐦',
        types=['video', 'image', 'gif'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=15, priority=3, extractor='twitter'
    ),
    
    'facebook.com': PlatformInfo(
        name='Facebook', icon='📘',
        types=['video', 'image', 'reel', 'live', 'story'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=5, priority=3, extractor='facebook'
    ),
    'fb.watch': PlatformInfo(
        name='Facebook', icon='📘',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=5, priority=3, extractor='facebook'
    ),
    'facebook.com/watch': PlatformInfo(
        name='Facebook Watch', icon='📺',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=5, priority=3, extractor='facebook'
    ),
    
    # منصات مشاركة الصور والفيديو
    'pinterest.com': PlatformInfo(
        name='Pinterest', icon='📌',
        types=['image', 'video', 'gif'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=4, extractor='pinterest',
        notes='قد يحتاج إلى محاولات متعددة'
    ),
    'pin.it': PlatformInfo(
        name='Pinterest', icon='📌',
        types=['image', 'video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=4, extractor='pinterest'
    ),
    
    'reddit.com': PlatformInfo(
        name='Reddit', icon='👽',
        types=['video', 'image', 'gif', 'gallery'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=20, priority=4, extractor='reddit'
    ),
    'redd.it': PlatformInfo(
        name='Reddit', icon='👽',
        types=['video', 'image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=20, priority=4, extractor='reddit'
    ),
    
    'tumblr.com': PlatformInfo(
        name='Tumblr', icon='📱',
        types=['video', 'image', 'gif'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=5, extractor='tumblr'
    ),
    
    'linkedin.com': PlatformInfo(
        name='LinkedIn', icon='💼',
        types=['video', 'image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=5, extractor='linkedin'
    ),
    
    # منصات فيديو بديلة
    'dailymotion.com': PlatformInfo(
        name='Dailymotion', icon='🎬',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=15, priority=6, extractor='dailymotion'
    ),
    
    'vimeo.com': PlatformInfo(
        name='Vimeo', icon='🎥',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=15, priority=6, extractor='vimeo'
    ),
    
    'twitch.tv': PlatformInfo(
        name='Twitch', icon='🎮',
        types=['video', 'clip', 'live'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=6, extractor='twitch'
    ),
    'twitch.tv/clips': PlatformInfo(
        name='Twitch Clip', icon='✂️',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=6, extractor='twitch'
    ),
    
    'rumble.com': PlatformInfo(
        name='Rumble', icon='📹',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=7, extractor='rumble'
    ),
    
    'odysee.com': PlatformInfo(
        name='Odysee', icon='🔗',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=7, extractor='odysee'
    ),
    'lbry.tv': PlatformInfo(
        name='LBRY', icon='🔗',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=7, extractor='lbry'
    ),
    
    'bitchute.com': PlatformInfo(
        name='BitChute', icon='🎦',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=5, priority=8, extractor='bitchute'
    ),
    
    # منصات مشاركة الملفات
    'streamable.com': PlatformInfo(
        name='Streamable', icon='🎥',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=15, priority=9, extractor='streamable'
    ),
    
    'gfycat.com': PlatformInfo(
        name='Gfycat', icon='🎞️',
        types=['video', 'gif'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=15, priority=9, extractor='gfycat'
    ),
    
    'imgur.com': PlatformInfo(
        name='Imgur', icon='🖼️',
        types=['image', 'video', 'gif', 'album'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=15, priority=9, extractor='imgur'
    ),
    
    'flickr.com': PlatformInfo(
        name='Flickr', icon='📷',
        types=['image', 'video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=10, extractor='flickr'
    ),
    
    '500px.com': PlatformInfo(
        name='500px', icon='📷',
        types=['image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=10, extractor='500px'
    ),
    
    'unsplash.com': PlatformInfo(
        name='Unsplash', icon='📷',
        types=['image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=20, priority=10, extractor='unsplash'
    ),
    
    'pexels.com': PlatformInfo(
        name='Pexels', icon='📷',
        types=['image', 'video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=20, priority=10, extractor='pexels'
    ),
    
    'pixabay.com': PlatformInfo(
        name='Pixabay', icon='📷',
        types=['image', 'video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=20, priority=10, extractor='pixabay'
    ),
    
    # منصات صوتية
    'soundcloud.com': PlatformInfo(
        name='SoundCloud', icon='🎵',
        types=['audio', 'playlist', 'track'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=11, extractor='soundcloud'
    ),
    
    'spotify.com': PlatformInfo(
        name='Spotify', icon='🎵',
        types=['audio', 'playlist', 'album', 'track'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=10, priority=11, extractor='spotify',
        notes='قد يحتاج إلى كوكيز'
    ),
    
    'deezer.com': PlatformInfo(
        name='Deezer', icon='🎵',
        types=['audio', 'playlist', 'album'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=11, extractor='deezer'
    ),
    
    'tidal.com': PlatformInfo(
        name='Tidal', icon='🎵',
        types=['audio', 'playlist'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=11, extractor='tidal'
    ),
    
    'bandcamp.com': PlatformInfo(
        name='Bandcamp', icon='🎵',
        types=['audio', 'album', 'track'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=11, extractor='bandcamp'
    ),
    
    'audiomack.com': PlatformInfo(
        name='Audiomack', icon='🎵',
        types=['audio', 'playlist'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=11, extractor='audiomack'
    ),
    
    'mixcloud.com': PlatformInfo(
        name='Mixcloud', icon='🎵',
        types=['audio', 'show'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=10, priority=11, extractor='mixcloud'
    ),
    
    # منصات إخبارية
    'bbc.co.uk': PlatformInfo(
        name='BBC', icon='📻',
        types=['audio', 'video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=20, priority=12, extractor='bbc'
    ),
    
    'npr.org': PlatformInfo(
        name='NPR', icon='📻',
        types=['audio'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=20, priority=12, extractor='npr'
    ),
    
    'ted.com': PlatformInfo(
        name='TED', icon='🎤',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=15, priority=13, extractor='ted'
    ),
    
    'coursera.org': PlatformInfo(
        name='Coursera', icon='📚',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=True, rate_limit=5, priority=14, extractor='coursera'
    ),
    
    'udemy.com': PlatformInfo(
        name='Udemy', icon='📚',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=True, rate_limit=5, priority=14, extractor='udemy'
    ),
    
    # منصات آسيوية
    'bilibili.com': PlatformInfo(
        name='Bilibili', icon='🇨🇳',
        types=['video'],
        quality_levels=['best', 'high', 'medium', 'low'],
        needs_auth=False, rate_limit=8, priority=15, extractor='bilibili'
    ),
    
    'nicovideo.jp': PlatformInfo(
        name='NicoNico', icon='🇯🇵',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='nicovideo'
    ),
    
    'weibo.com': PlatformInfo(
        name='Weibo', icon='🇨🇳',
        types=['video', 'image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='weibo'
    ),
    
    'tieba.com': PlatformInfo(
        name='Baidu Tieba', icon='🇨🇳',
        types=['video', 'image'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='tieba'
    ),
    
    'naver.com': PlatformInfo(
        name='Naver', icon='🇰🇷',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='naver'
    ),
    
    'daum.net': PlatformInfo(
        name='Daum', icon='🇰🇷',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='daum'
    ),
    
    'kakao.com': PlatformInfo(
        name='Kakao', icon='🇰🇷',
        types=['video'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='kakao'
    ),
    
    'vlive.tv': PlatformInfo(
        name='V Live', icon='🇰🇷',
        types=['video', 'live'],
        quality_levels=['best', 'high'],
        needs_auth=False, rate_limit=8, priority=15, extractor='vlive'
    ),
    
    # منصات مراسلة
    'telegram.org': PlatformInfo(
        name='Telegram', icon='✈️',
        types=['video', 'image', 'audio', 'document'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=16, extractor='telegram'
    ),
    't.me': PlatformInfo(
        name='Telegram', icon='✈️',
        types=['video', 'image', 'audio'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=16, extractor='telegram'
    ),
    
    'whatsapp.com': PlatformInfo(
        name='WhatsApp', icon='💬',
        types=['video', 'image'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=20, priority=16, extractor='whatsapp'
    ),
    
    'snapchat.com': PlatformInfo(
        name='Snapchat', icon='👻',
        types=['video', 'image'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=10, priority=16, extractor='snapchat'
    ),
    
    # منصات مباشرة للملفات
    'drive.google.com': PlatformInfo(
        name='Google Drive', icon='📁',
        types=['video', 'audio', 'document'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=10, priority=17, extractor='googledrive'
    ),
    
    'dropbox.com': PlatformInfo(
        name='Dropbox', icon='📁',
        types=['video', 'audio', 'document'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=15, priority=17, extractor='dropbox'
    ),
    
    'mega.nz': PlatformInfo(
        name='MEGA', icon='📁',
        types=['video', 'audio', 'document'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=5, priority=17, extractor='mega'
    ),
    
    'mediafire.com': PlatformInfo(
        name='MediaFire', icon='📁',
        types=['video', 'audio', 'document'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=10, priority=17, extractor='mediafire'
    ),
    
    'archive.org': PlatformInfo(
        name='Internet Archive', icon='🏛️',
        types=['video', 'audio', 'text'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=20, priority=18, extractor='archive'
    ),
    
    # روابط مباشرة
    '.mp4': PlatformInfo(
        name='MP4 Video', icon='🎬',
        types=['video'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.mkv': PlatformInfo(
        name='MKV Video', icon='🎬',
        types=['video'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.webm': PlatformInfo(
        name='WebM Video', icon='🎬',
        types=['video'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.mp3': PlatformInfo(
        name='MP3 Audio', icon='🎵',
        types=['audio'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.wav': PlatformInfo(
        name='WAV Audio', icon='🎵',
        types=['audio'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.jpg': PlatformInfo(
        name='JPEG Image', icon='🖼️',
        types=['image'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.jpeg': PlatformInfo(
        name='JPEG Image', icon='🖼️',
        types=['image'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.png': PlatformInfo(
        name='PNG Image', icon='🖼️',
        types=['image'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
    '.gif': PlatformInfo(
        name='GIF Image', icon='🎞️',
        types=['image', 'gif'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=100, extractor='generic'
    ),
}

# ================== نظام التخزين المؤقت ==================
class CacheSystem:
    def __init__(self, cache_dir: Path, max_size: int = 1000, ttl: int = 3600):
        self.cache_dir = cache_dir
        self.max_size = max_size
        self.ttl = ttl
        self.memory_cache = {}
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """الحصول على مسار ملف الكاش"""
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed}.json"
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """تخزين قيمة في الكاش"""
        try:
            data = {
                'value': value,
                'expires': time.time() + (ttl or self.ttl)
            }
            
            # تخزين في الذاكرة
            self.memory_cache[key] = data
            
            # تخزين على القرص
            cache_file = self._get_cache_path(key)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """استرجاع قيمة من الكاش"""
        try:
            # البحث في الذاكرة أولاً
            if key in self.memory_cache:
                data = self.memory_cache[key]
                if data['expires'] > time.time():
                    return data['value']
                else:
                    del self.memory_cache[key]
            
            # البحث على القرص
            cache_file = self._get_cache_path(key)
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data['expires'] > time.time():
                    self.memory_cache[key] = data
                    return data['value']
                else:
                    cache_file.unlink()
            
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """حذف قيمة من الكاش"""
        try:
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            cache_file = self._get_cache_path(key)
            if cache_file.exists():
                cache_file.unlink()
            
            return True
        except Exception:
            return False
    
    def clear_expired(self):
        """تنظيف الكاش منتهي الصلاحية"""
        try:
            now = time.time()
            
            # تنظيف الذاكرة
            expired = [k for k, v in self.memory_cache.items() if v['expires'] <= now]
            for k in expired:
                del self.memory_cache[k]
            
            # تنظيف القرص
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data['expires'] <= now:
                        cache_file.unlink()
                except:
                    cache_file.unlink()
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
    
    def get_stats(self) -> dict:
        """إحصائيات الكاش"""
        return {
            'memory_items': len(self.memory_cache),
            'disk_items': len(list(self.cache_dir.glob("*.json"))),
            'cache_dir': str(self.cache_dir),
            'max_size': self.max_size,
            'ttl': self.ttl
        }

# ================== نظام إدارة المستخدمين ==================
class UserManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.users = {}
        self.load_all_users()
    
    def _get_user_file(self, user_id: int) -> Path:
        """الحصول على ملف المستخدم"""
        return self.data_dir / f"{user_id}.json"
    
    def load_user(self, user_id: int) -> dict:
        """تحميل بيانات مستخدم"""
        try:
            user_file = self._get_user_file(user_id)
            if user_file.exists():
                with open(user_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                'id': user_id,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'downloads': 0,
                'total_size': 0,
                'favorites': [],
                'settings': {
                    'default_quality': 'best',
                    'auto_audio': False,
                    'save_history': True
                }
            }
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {e}")
            return {}
    
    def save_user(self, user_id: int, data: dict) -> bool:
        """حفظ بيانات مستخدم"""
        try:
            user_file = self._get_user_file(user_id)
            data['last_seen'] = datetime.now().isoformat()
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.users[user_id] = data
            return True
        except Exception as e:
            logger.error(f"Error saving user {user_id}: {e}")
            return False
    
    def load_all_users(self):
        """تحميل كل المستخدمين"""
        try:
            for user_file in self.data_dir.glob("*.json"):
                try:
                    with open(user_file, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                        self.users[user_data['id']] = user_data
                except:
                    continue
        except Exception as e:
            logger.error(f"Error loading all users: {e}")
    
    def update_user_stats(self, user_id: int, download_size: int):
        """تحديث إحصائيات المستخدم"""
        user_data = self.load_user(user_id)
        user_data['downloads'] = user_data.get('downloads', 0) + 1
        user_data['total_size'] = user_data.get('total_size', 0) + download_size
        self.save_user(user_id, user_data)
    
    def get_user_stats(self, user_id: int) -> dict:
        """الحصول على إحصائيات المستخدم"""
        return self.load_user(user_id)
    
    def get_all_users_count(self) -> int:
        """عدد المستخدمين الكلي"""
        return len(list(self.data_dir.glob("*.json")))
    
    def get_active_users_today(self) -> int:
        """المستخدمين النشطين اليوم"""
        today = datetime.now().date().isoformat()
        count = 0
        for user_file in self.data_dir.glob("*.json"):
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('last_seen', '').startswith(today):
                    count += 1
            except:
                continue
        return count
    
    def get_total_downloads(self) -> int:
        """إجمالي التحميلات"""
        total = 0
        for user_file in self.data_dir.glob("*.json"):
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                total += data.get('downloads', 0)
            except:
                continue
        return total

# ================== نظام إدارة التحميل ==================
class DownloadManager:
    def __init__(self, max_concurrent: int = MAX_CONCURRENT_DOWNLOADS):
        self.max_concurrent = max_concurrent
        self.active_downloads = {}
        self.download_queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.stats = {
            'total_downloads': 0,
            'total_size': 0,
            'failed_downloads': 0,
            'active_downloads': 0
        }
    
    async def download(self, url: str, options: dict, callback: Callable = None) -> Tuple[Optional[str], Optional[str]]:
        """تحميل ملف مع إمكانية التتبع"""
        download_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:8]
        
        self.active_downloads[download_id] = {
            'url': url,
            'status': 'downloading',
            'progress': 0,
            'start_time': time.time()
        }
        
        self.stats['active_downloads'] += 1
        
        try:
            # تنفيذ التحميل في ThreadPoolExecutor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._sync_download,
                url,
                options,
                download_id,
                callback
            )
            
            if result[0]:
                self.stats['total_downloads'] += 1
                if os.path.exists(result[0]):
                    self.stats['total_size'] += os.path.getsize(result[0])
            else:
                self.stats['failed_downloads'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.stats['failed_downloads'] += 1
            return None, str(e)
        finally:
            if download_id in self.active_downloads:
                del self.active_downloads[download_id]
            self.stats['active_downloads'] -= 1
    
    def _sync_download(self, url: str, options: dict, download_id: str, callback: Callable = None) -> Tuple[Optional[str], Optional[str]]:
        """تحميل متزامن (يعمل في Thread)"""
        try:
            # إعدادات yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True,
                'noplaylist': True,
                'geo_bypass': True,
                'socket_timeout': 30,
                'retries': 5,
                'fragment_retries': 5,
            }
            
            # دمج الخيارات المخصصة
            ydl_opts.update(options)
            
            # إضافة callback للتقدم
            if callback:
                ydl_opts['progress_hooks'] = [lambda d: self._progress_hook(d, download_id, callback)]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # تحديد اسم الملف
                if options.get('postprocessors') and any(p.get('key') == 'FFmpegExtractAudio' for p in options.get('postprocessors', [])):
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = ydl.prepare_filename(info)
                    if not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'
                
                # البحث عن الملف
                if os.path.exists(filename):
                    return filename, None
                
                # البحث بامتدادات مختلفة
                base = filename.rsplit('.', 1)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.jpg', '.png', '.gif']:
                    test = base + ext
                    if os.path.exists(test):
                        return test, None
                
                return None, "لم يتم العثور على الملف"
                
        except Exception as e:
            return None, str(e)
    
    def _progress_hook(self, d: dict, download_id: str, callback: Callable):
        """تتبع تقدم التحميل"""
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                progress = d['downloaded_bytes'] / d['total_bytes'] * 100
            elif 'total_bytes_estimate' in d:
                progress = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
            else:
                progress = 0
            
            self.active_downloads[download_id]['progress'] = progress
            
            if callback:
                asyncio.run(callback(progress))
        
        elif d['status'] == 'finished':
            self.active_downloads[download_id]['status'] = 'finished'
            self.active_downloads[download_id]['progress'] = 100
    
    def cancel_download(self, download_id: str) -> bool:
        """إلغاء تحميل"""
        if download_id in self.active_downloads:
            self.active_downloads[download_id]['status'] = 'cancelled'
            return True
        return False
    
    def get_stats(self) -> dict:
        """إحصائيات التحميل"""
        return self.stats.copy()
    
    def get_active_downloads(self) -> list:
        """التحميلات النشطة"""
        return list(self.active_downloads.values())

# ================== نظام معالجة الصور ==================
class ImageProcessor:
    @staticmethod
    async def get_thumbnail(info: dict) -> Optional[bytes]:
        """الحصول على الصورة المصغرة"""
        if not info.get('thumbnail'):
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(info['thumbnail']) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except:
            pass
        
        return None
    
    @staticmethod
    def resize_image(image_data: bytes, max_size: Tuple[int, int] = (320, 320)) -> Optional[bytes]:
        """تغيير حجم الصورة"""
        if not HAS_PIL:
            return image_data
        
        try:
            img = Image.open(io.BytesIO(image_data))
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            return output.getvalue()
        except:
            return image_data
    
    @staticmethod
    def get_image_info(image_path: str) -> dict:
        """معلومات الصورة"""
        if not HAS_PIL:
            return {}
        
        try:
            img = Image.open(image_path)
            return {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size': os.path.getsize(image_path)
            }
        except:
            return {}

# ================== نظام معالجة الفيديو ==================
class VideoProcessor:
    @staticmethod
    def get_video_info(file_path: str) -> dict:
        """معلومات الفيديو"""
        info = {}
        
        try:
            # استخدام ffprope
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # البحث عن stream الفيديو
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        info.update({
                            'width': int(stream.get('width', 0)),
                            'height': int(stream.get('height', 0)),
                            'codec': stream.get('codec_name', ''),
                            'fps': eval(stream.get('r_frame_rate', '0/1')) if '/' in stream.get('r_frame_rate', '') else 0,
                        })
                        break
                
                # معلومات عامة
                format_info = data.get('format', {})
                info.update({
                    'duration': float(format_info.get('duration', 0)),
                    'size': int(format_info.get('size', 0)),
                    'bitrate': int(format_info.get('bit_rate', 0)),
                    'format': format_info.get('format_name', ''),
                })
        except:
            pass
        
        return info
    
    @staticmethod
    def compress_video(input_path: str, output_path: str, target_size: int) -> bool:
        """ضغط الفيديو"""
        try:
            # حساب bitrate المناسب
            duration = VideoProcessor.get_video_info(input_path).get('duration', 0)
            if duration <= 0:
                return False
            
            target_bitrate = int((target_size * 8) / duration)
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264',
                '-b:v', f'{target_bitrate}',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0 and os.path.exists(output_path)
        except:
            return False

# ================== نظام معالجة الصوت ==================
class AudioProcessor:
    @staticmethod
    def get_audio_info(file_path: str) -> dict:
        """معلومات الصوت"""
        info = {}
        
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        info.update({
                            'codec': stream.get('codec_name', ''),
                            'sample_rate': int(stream.get('sample_rate', 0)),
                            'channels': int(stream.get('channels', 0)),
                            'bitrate': int(stream.get('bit_rate', 0)),
                            'duration': float(stream.get('duration', 0)),
                        })
                        break
        except:
            pass
        
        return info

# ================== نظام إدارة المهام ==================
class TaskScheduler:
    def __init__(self):
        self.tasks = []
        self.running = True
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def add_task(self, func: Callable, interval: int, *args, **kwargs):
        """إضافة مهمة دورية"""
        self.tasks.append({
            'func': func,
            'interval': interval,
            'last_run': 0,
            'args': args,
            'kwargs': kwargs
        })
    
    def _run(self):
        """تشغيل المهام"""
        while self.running:
            now = time.time()
            for task in self.tasks:
                if now - task['last_run'] >= task['interval']:
                    try:
                        task['func'](*task['args'], **task['kwargs'])
                        task['last_run'] = now
                    except Exception as e:
                        logger.error(f"Task error: {e}")
            time.sleep(1)
    
    def stop(self):
        """إيقاف المهام"""
        self.running = False
        self.thread.join(timeout=5)

# ================== نظام إدارة الكوكيز ==================
class CookieManager:
    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir
        self.cookies_dir.mkdir(exist_ok=True)
        self.key = None
        
        if HAS_CRYPTO:
            key_file = cookies_dir / 'key.key'
            if key_file.exists():
                with open(key_file, 'rb') as f:
                    self.key = f.read()
            else:
                self.key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(self.key)
            self.cipher = Fernet(self.key)
    
    def save_cookies(self, domain: str, cookies: str) -> bool:
        """حفظ كوكيز للمنصة"""
        try:
            cookie_file = self.cookies_dir / f"{domain}.txt"
            
            if self.cipher:
                cookies = self.cipher.encrypt(cookies.encode()).decode()
            
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookies)
            
            return True
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False
    
    def load_cookies(self, domain: str) -> Optional[str]:
        """تحميل كوكيز المنصة"""
        try:
            cookie_file = self.cookies_dir / f"{domain}.txt"
            
            if not cookie_file.exists():
                return None
            
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = f.read()
            
            if self.cipher:
                cookies = self.cipher.decrypt(cookies.encode()).decode()
            
            return cookies
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return None
    
    def delete_cookies(self, domain: str) -> bool:
        """حذف كوكيز المنصة"""
        try:
            cookie_file = self.cookies_dir / f"{domain}.txt"
            if cookie_file.exists():
                cookie_file.unlink()
            return True
        except Exception:
            return False

# ================== نظام الإحصائيات ==================
class StatisticsCollector:
    def __init__(self):
        self.stats = {
            'start_time': time.time(),
            'total_requests': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_size': 0,
            'users': set(),
            'platforms': defaultdict(int),
            'errors': defaultdict(int),
            'daily_stats': defaultdict(lambda: {'downloads': 0, 'size': 0})
        }
    
    def add_request(self, user_id: int, platform: str, success: bool, size: int = 0):
        """إضافة إحصائية"""
        self.stats['total_requests'] += 1
        self.stats['users'].add(user_id)
        
        if success:
            self.stats['successful_downloads'] += 1
            self.stats['total_size'] += size
            self.stats['platforms'][platform] += 1
            
            # إحصائيات يومية
            day = datetime.now().strftime('%Y-%m-%d')
            self.stats['daily_stats'][day]['downloads'] += 1
            self.stats['daily_stats'][day]['size'] += size
        else:
            self.stats['failed_downloads'] += 1
    
    def add_error(self, error_type: str):
        """إضافة خطأ"""
        self.stats['errors'][error_type] += 1
    
    def get_stats(self) -> dict:
        """الحصول على الإحصائيات"""
        uptime = time.time() - self.stats['start_time']
        
        return {
            'uptime': str(timedelta(seconds=int(uptime))),
            'total_requests': self.stats['total_requests'],
            'successful_downloads': self.stats['successful_downloads'],
            'failed_downloads': self.stats['failed_downloads'],
            'success_rate': (self.stats['successful_downloads'] / max(self.stats['total_requests'], 1)) * 100,
            'total_size': self.stats['total_size'],
            'total_users': len(self.stats['users']),
            'platforms': dict(self.stats['platforms']),
            'errors': dict(self.stats['errors']),
            'daily_stats': dict(self.stats['daily_stats']),
            'today_downloads': self.stats['daily_stats'].get(datetime.now().strftime('%Y-%m-%d'), {}).get('downloads', 0),
        }

# ================== دوال المساعدة العامة ==================
def format_size(size: int) -> str:
    """تنسيق الحجم"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    elif size < 1024 ** 4:
        return f"{size / 1024 ** 3:.1f} GB"
    else:
        return f"{size / 1024 ** 4:.1f} TB"

def format_duration(seconds: int) -> str:
    """تنسيق المدة"""
    if not seconds:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def format_number(num: int) -> str:
    """تنسيق الأرقام الكبيرة"""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def clean_filename(filename: str) -> str:
    """تنظيف اسم الملف"""
    # إزالة الرموز غير المسموحة
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    # تقصير الاسم الطويل
    if len(filename) > 100:
        filename = filename[:97] + '...'
    
    return filename

def extract_urls(text: str) -> List[str]:
    """استخراج الروابط من النص"""
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    return re.findall(url_pattern, text)

def detect_platform(url: str) -> Tuple[str, PlatformInfo]:
    """كشف المنصة من الرابط"""
    url_lower = url.lower()
    
    for domain, info in SUPPORTED_PLATFORMS.items():
        if domain in url_lower:
            return info.name, info
    
    # التحقق من امتدادات الملفات
    for ext, info in SUPPORTED_PLATFORMS.items():
        if ext.startswith('.') and url_lower.endswith(ext):
            return info.name, info
    
    return 'رابط عادي', PlatformInfo(
        name='رابط عادي', icon='🌐',
        types=['unknown'],
        quality_levels=['best'],
        needs_auth=False, rate_limit=30, priority=999,
        extractor='generic'
    )

def check_ffmpeg() -> Tuple[bool, str]:
    """التحقق من تثبيت FFmpeg"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            return True, version[:50]
        return False, "غير مثبت"
    except:
        return False, "غير مثبت"

def get_system_info() -> dict:
    """معلومات النظام"""
    info = {
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'cpu_count': os.cpu_count(),
        'pid': os.getpid(),
        'cwd': str(Path.cwd()),
    }
    
    if HAS_PSUTIL:
        process = psutil.Process()
        info.update({
            'memory_used': format_size(process.memory_info().rss),
            'cpu_percent': process.cpu_percent(),
            'threads': process.num_threads(),
            'open_files': len(process.open_files()),
            'connections': len(process.connections()),
        })
    
    return info

def colored_print(text: str, color: str = WHITE):
    """طباعة ملونة"""
    if HAS_COLORAMA:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def log_error(error: Exception, context: str = ""):
    """تسجيل خطأ مع التفاصيل"""
    error_type = type(error).__name__
    error_msg = str(error)
    tb = traceback.format_exc()
    
    logger.error(f"Error in {context}: {error_type} - {error_msg}")
    logger.debug(f"Traceback: {tb}")

# ================== إعدادات yt-dlp المتقدمة ==================
def get_ydl_options(
    media_type: str = 'video',
    quality: str = 'best',
    platform: str = '',
    cookies: str = None,
    extractor_args: dict = None
) -> dict:
    """الحصول على إعدادات yt-dlp المخصصة"""
    
    options = {
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
    
    # إعدادات التنسيق حسب الجودة والنوع
    if media_type == 'audio':
        options.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif media_type == 'image':
        options['format'] = 'best'
    else:  # video
        if quality == 'best':
            options['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == 'high':
            options['format'] = 'best[height<=1080][ext=mp4]/best[height<=1080]'
        elif quality == 'medium':
            options['format'] = 'best[height<=720][ext=mp4]/best[height<=720]'
        elif quality == 'low':
            options['format'] = 'worst[ext=mp4]/worst'
        else:
            options['format'] = 'best[ext=mp4]/best'
    
    # إضافة كوكيز
    if cookies:
        options['cookiefile'] = cookies
    
    # إعدادات خاصة للمستخرج
    if extractor_args:
        options['extractor_args'] = extractor_args
    
    # إعدادات خاصة بالمنصات
    if 'instagram' in platform.lower():
        options['extractor_args'] = {'instagram': {'webpage': ['1']}}
        options['headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
        }
    
    elif 'tiktok' in platform.lower():
        options['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        options['extractor_args'] = {'tiktok': {'webpage': ['1']}}
    
    elif 'pinterest' in platform.lower():
        options['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        options['extractor_args'] = {'pinterest': {'webpage': ['1']}}
    
    elif 'twitter' in platform.lower() or 'x.com' in platform.lower():
        options['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    
    elif 'facebook' in platform.lower():
        options['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    
    return options

# ================== دوال استخراج المعلومات ==================
async def extract_info_advanced(url: str, retries: int = 3) -> Tuple[Optional[dict], Optional[str]]:
    """استخراج معلومات متقدم مع محاولات متعددة"""
    
    attempts = [
        {'headers': None},
        {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}},
        {'headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'}},
        {'cookies': True},
    ]
    
    platform_name, platform_info = detect_platform(url)
    
    for attempt_num in range(retries):
        for attempt in attempts:
            try:
                opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                    'socket_timeout': 15,
                }
                
                if 'headers' in attempt and attempt['headers']:
                    opts['headers'] = attempt['headers']
                
                if platform_info.needs_auth:
                    opts['cookiefile'] = str(COOKIES_DIR / f"{platform_info.extractor}.txt")
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if info:
                        # استخراج الصورة المصغرة
                        thumbnail = info.get('thumbnail', '')
                        if not thumbnail and 'thumbnails' in info and info['thumbnails']:
                            thumbnail = info['thumbnails'][-1].get('url', '')
                        
                        # تقدير الحجم
                        filesize = info.get('filesize') or info.get('filesize_approx') or 0
                        
                        return {
                            'id': info.get('id', ''),
                            'title': info.get('title', 'محتوى')[:200],
                            'description': info.get('description', '')[:500],
                            'duration': info.get('duration', 0),
                            'uploader': info.get('uploader', info.get('channel', 'غير معروف')),
                            'uploader_id': info.get('uploader_id', ''),
                            'upload_date': info.get('upload_date', ''),
                            'view_count': info.get('view_count', 0),
                            'like_count': info.get('like_count', 0),
                            'comment_count': info.get('comment_count', 0),
                            'repost_count': info.get('repost_count', 0),
                            'thumbnail': thumbnail,
                            'thumbnails': info.get('thumbnails', []),
                            'tags': info.get('tags', []),
                            'categories': info.get('categories', []),
                            'format': info.get('format', ''),
                            'width': info.get('width', 0),
                            'height': info.get('height', 0),
                            'fps': info.get('fps', 0),
                            'filesize': filesize,
                            'filesize_approx': info.get('filesize_approx', 0),
                            'extractor': info.get('extractor', ''),
                            'extractor_key': info.get('extractor_key', ''),
                            'webpage_url': info.get('webpage_url', url),
                            'platform': platform_name,
                            'platform_icon': platform_info.icon,
                            'platform_info': platform_info,
                        }, None
                        
            except Exception as e:
                continue
        
        await asyncio.sleep(1)
    
    return None, "فشل استخراج المعلومات بعد عدة محاولات"

# ================== دوال التحميل المتقدمة ==================
async def download_media_advanced(
    url: str,
    media_type: str = 'video',
    quality: str = 'best',
    progress_callback: Callable = None
) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    """تحميل متقدم مع محاولات متعددة"""
    
    platform_name, platform_info = detect_platform(url)
    
    # محاولات متعددة
    for attempt in range(3):
        try:
            # الحصول على الإعدادات
            cookies = str(COOKIES_DIR / f"{platform_info.extractor}.txt") if platform_info.needs_auth else None
            options = get_ydl_options(media_type, quality, platform_name, cookies)
            
            # إضافة callback للتقدم
            if progress_callback:
                options['progress_hooks'] = [lambda d: asyncio.run(progress_callback(d))]
            
            # تنفيذ التحميل
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # تحديد اسم الملف
                if media_type == 'audio':
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = ydl.prepare_filename(info)
                    if not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'
                
                # التحقق من وجود الملف
                if os.path.exists(filename):
                    return filename, None, info
                
                # البحث بامتدادات مختلفة
                base = filename.rsplit('.', 1)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.jpg', '.png', '.gif']:
                    test = base + ext
                    if os.path.exists(test):
                        return test, None, info
                
                return None, "لم يتم العثور على الملف", info
                
        except Exception as e:
            if attempt == 2:
                return None, str(e), None
            await asyncio.sleep(1)
    
    return None, "فشل التحميل بعد عدة محاولات", None

# ================== دوال الرفع إلى تليجرام ==================
async def upload_to_telegram(
    update: Update,
    file_path: str,
    info: dict,
    media_type: str = 'video'
) -> bool:
    """رفع الملف إلى تليجرام مع محاولات متعددة"""
    
    file_size = os.path.getsize(file_path)
    caption = f"{info.get('platform_icon', '')} {info.get('title', '')[:100]}\n📊 {format_size(file_size)}"
    
    for attempt in range(3):
        try:
            await update.effective_chat.send_action(
                action=ChatAction.UPLOAD_VIDEO if media_type == 'video' else ChatAction.UPLOAD_AUDIO
            )
            
            with open(file_path, 'rb') as f:
                if media_type == 'audio':
                    await update.effective_message.reply_audio(
                        audio=f,
                        title=info.get('title', 'صوت'),
                        performer=info.get('uploader', 'غير معروف'),
                        duration=info.get('duration', 0),
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'image':
                    await update.effective_message.reply_photo(
                        photo=f,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:  # video
                    try:
                        await update.effective_message.reply_video(
                            video=f,
                            caption=caption,
                            supports_streaming=True,
                            duration=info.get('duration', 0),
                            width=info.get('width'),
                            height=info.get('height'),
                            parse_mode=ParseMode.HTML
                        )
                    except Exception:
                        # إذا فشل إرسال كفيديو، أرسل كمستند
                        f.seek(0)
                        await update.effective_message.reply_document(
                            document=f,
                            filename=os.path.basename(file_path),
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
            
            return True
            
        except RetryAfter as e:
            wait_time = e.retry_after
            await asyncio.sleep(wait_time)
        except TimedOut:
            await asyncio.sleep(2)
        except Exception as e:
            log_error(e, "upload_to_telegram")
            if attempt == 2:
                return False
            await asyncio.sleep(1)
    
    return False

# ================== معالجات البوت ==================
# الحالات للمحادثة
(MAIN_MENU, WAITING_URL, SELECTING_QUALITY, DOWNLOADING, SETTINGS) = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية البوت"""
    user = update.effective_user
    
    # تسجيل المستخدم
    context.user_data['user_id'] = user.id
    context.user_data['username'] = user.username
    context.user_data['first_name'] = user.first_name
    
    # إحصائيات
    stats_collector.add_request(user.id, 'start', True)
    
    # رسالة الترحيب
    text = f"""
🎬 <b>مرحباً بك {user.first_name} في أقوى بوت تحميل!</b>

✨ <b>المميزات الحصرية:</b>
• تحميل من <b>{len(SUPPORTED_PLATFORMS)}+</b> منصة مختلفة
• دعم الفيديو، الصوت، الصور، القصص، البث المباشر
• اختيار الجودة (HD، 1080p، 720p، 480p، MP3)
• تحميل سريع مع تتبع التقدم
• معالجة ذكية للأخطاء

📥 <b>فقط أرسل الرابط وسأقوم بالباقي!</b>

<b>المنصات الرئيسية:</b>
📺 YouTube - 📸 Instagram - 🎵 TikTok - 🐦 Twitter
📘 Facebook - 📌 Pinterest - 👽 Reddit - 🎮 Twitch
🎵 SoundCloud - 🎥 Vimeo - 📁 Google Drive

<b>حالة البوت:</b>
⚡ <b>نشط وفعال</b>
📊 حجم حتى 50 ميجابايت
⏱️ مدة حتى ساعتين
    """
    
    keyboard = [
        [
            InlineKeyboardButton("📥 تحميل", callback_data="main_menu"),
            InlineKeyboardButton("❓ مساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton("📊 إحصائيات", callback_data="stats"),
            InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")
        ],
        [
            InlineKeyboardButton("👨‍💻 المطور", url="https://t.me/your_username"),
            InlineKeyboardButton("📢 القناة", url="https://t.me/your_channel")
        ]
    ]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return MAIN_MENU

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    query = update.callback_query
    await query.answer()
    
    text = """
📚 <b>دليل استخدام البوت:</b>

<b>🔹 طريقة الاستخدام:</b>
1️⃣ أرسل رابط الفيديو/الصورة/الصوت
2️⃣ اختر الجودة المناسبة
3️⃣ انتظر التحميل
4️⃣ استلم الملف مباشرة

<b>🔸 خيارات التحميل:</b>
🎬 <b>فيديو:</b> HD, 1080p, 720p, 480p
🎵 <b>صوت:</b> MP3 320kbps, 192kbps, 128kbps
📷 <b>صور:</b> أصلية، مصغرة
📱 <b>قصص:</b> فيديو وصور
🎮 <b>بث مباشر:</b> تحميل بعد البث

<b>🔹 المنصات المدعومة بالكامل:</b>
• <b>يوتيوب:</b> فيديوهات، شورتس، بث مباشر
• <b>انستغرام:</b> منشورات، ريلز، قصص
• <b>تيك توك:</b> فيديوهات بدون علامة مائية
• <b>تويتر:</b> فيديوهات، صور، GIF
• <b>فيسبوك:</b> فيديوهات عامة، ريلز
• <b>بنترست:</b> صور، فيديوهات
• <b>ريديت:</b> فيديوهات، صور
• <b>ساوند كلاود:</b> أغاني، بودكاست

<b>⚠️ ملاحظات مهمة:</b>
• الحد الأقصى للحجم: 50 ميجابايت
• الحد الأقصى للمدة: ساعتين
• المحتوى الخاص غير مدعوم
• قد تستغرق الفيديوهات الطويلة وقتاً
    """
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات"""
    query = update.callback_query
    await query.answer()
    
    stats = stats_collector.get_stats()
    system_info = get_system_info()
    user_manager = context.bot_data.get('user_manager')
    
    ffmpeg_available, ffmpeg_version = check_ffmpeg()
    
    text = f"""
📊 <b>إحصائيات البوت:</b>

<b>⏱️ وقت التشغيل:</b> {stats['uptime']}
<b>👥 المستخدمين:</b> {stats['total_users']}
<b>📥 التحميلات:</b> {stats['successful_downloads']:,}
<b>✅ نسبة النجاح:</b> {stats['success_rate']:.1f}%
<b>📦 الحجم الكلي:</b> {format_size(stats['total_size'])}

<b>🌐 أشهر المنصات:</b>
{chr(10).join([f'• {platform}: {count}' for platform, count in sorted(stats['platforms'].items(), key=lambda x: x[1], reverse=True)[:5]])}

<b>⚙️ معلومات النظام:</b>
• <b>Python:</b> {system_info.get('python', '')}
• <b>FFmpeg:</b> {'✅' if ffmpeg_available else '❌'}
• <b>الذاكرة:</b> {system_info.get('memory_used', 'غير معروف')}
• <b>المعالج:</b> {system_info.get('cpu_percent', 0)}%

<b>📊 اليوم:</b>
• التحميلات: {stats['today_downloads']}
• المستخدمين النشطين: {user_manager.get_active_users_today() if user_manager else 0}
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعدادات المستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_manager = context.bot_data.get('user_manager')
    user_settings = user_manager.load_user(user_id).get('settings', {})
    
    text = f"""
⚙️ <b>إعدادات المستخدم:</b>

<b>🎬 الجودة الافتراضية:</b> {user_settings.get('default_quality', 'best')}
<b>🎵 تحميل الصوت تلقائياً:</b> {'✅' if user_settings.get('auto_audio', False) else '❌'}
<b>📝 حفظ السجل:</b> {'✅' if user_settings.get('save_history', True) else '❌'}

<b>🔹 اختر الإعداد لتغييره:</b>
    """
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 الجودة", callback_data="set_quality"),
            InlineKeyboardButton("🎵 الصوت", callback_data="toggle_audio")
        ],
        [
            InlineKeyboardButton("📝 السجل", callback_data="toggle_history"),
            InlineKeyboardButton("🗑️ مسح", callback_data="clear_data")
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_url_advanced(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط بشكل متقدم"""
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # استخراج الروابط من النص
    urls = extract_urls(url)
    if not urls:
        await update.message.reply_text("❌ لم أجد رابط صحيح في الرسالة")
        return
    
    url = urls[0]
    
    # تنظيف الملفات القديمة
    cleanup_temp_files()
    
    # إرسال رسالة المعالجة
    status_msg = await update.message.reply_text("🔍 <b>جاري تحليل الرابط...</b>", parse_mode=ParseMode.HTML)
    
    try:
        # استخراج المعلومات
        info, error = await extract_info_advanced(url)
        
        if error or not info:
            await status_msg.edit_text(
                f"❌ <b>فشل تحليل الرابط</b>\n\n{error or 'الرابط غير صالح'}",
                parse_mode=ParseMode.HTML
            )
            stats_collector.add_request(user_id, 'unknown', False)
            return
        
        # حفظ المعلومات
        context.user_data['video_info'] = info
        context.user_data['video_url'] = url
        
        # تحضير الرسالة
        platform_icon = info.get('platform_icon', '🌐')
        duration = format_duration(info.get('duration', 0))
        views = format_number(info.get('view_count', 0))
        likes = format_number(info.get('like_count', 0))
        filesize = format_size(info.get('filesize', info.get('filesize_approx', 0)))
        
        text = f"""
{platform_icon} <b>{info['platform']}</b>

📹 <b>{info['title']}</b>
👤 <b>الناشر:</b> {info['uploader']}
⏱️ <b>المدة:</b> {duration}
👁️ <b>المشاهدات:</b> {views}
❤️ <b>الإعجابات:</b> {likes}
📊 <b>الحجم:</b> {filesize}

📥 <b>اختر نوع التحميل:</b>
        """
        
        # إنشاء الأزرار حسب نوع المحتوى
        keyboard = []
        
        # أزرار الفيديو
        video_row = []
        if 'video' in info['platform_info'].types:
            video_row.append(InlineKeyboardButton("🎬 HD", callback_data="dl_video_best"))
            video_row.append(InlineKeyboardButton("🎬 720p", callback_data="dl_video_720"))
            video_row.append(InlineKeyboardButton("🎬 480p", callback_data="dl_video_480"))
        if video_row:
            keyboard.append(video_row)
        
        # أزرار الصوت
        audio_row = []
        if 'audio' in info['platform_info'].types:
            audio_row.append(InlineKeyboardButton("🎵 MP3 320", callback_data="dl_audio_320"))
            audio_row.append(InlineKeyboardButton("🎵 MP3 192", callback_data="dl_audio_192"))
            audio_row.append(InlineKeyboardButton("🎵 MP3 128", callback_data="dl_audio_128"))
        if audio_row:
            keyboard.append(audio_row)
        
        # أزرار الصور
        image_row = []
        if 'image' in info['platform_info'].types:
            image_row.append(InlineKeyboardButton("🖼️ صور", callback_data="dl_image"))
        if 'gif' in info['platform_info'].types:
            image_row.append(InlineKeyboardButton("🎞️ GIF", callback_data="dl_gif"))
        if image_row:
            keyboard.append(image_row)
        
        # أزرار إضافية
        extra_row = []
        if 'playlist' in info['platform_info'].types:
            extra_row.append(InlineKeyboardButton("📋 قائمة", callback_data="dl_playlist"))
        if 'story' in info['platform_info'].types:
            extra_row.append(InlineKeyboardButton("📖 قصة", callback_data="dl_story"))
        if extra_row:
            keyboard.append(extra_row)
        
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        
        await status_msg.delete()
        
        # إرسال مع الصورة المصغرة
        if info.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        stats_collector.add_request(user_id, info['platform'], True)
        
    except Exception as e:
        log_error(e, "handle_url_advanced")
        await status_msg.edit_text(
            f"❌ <b>حدث خطأ غير متوقع</b>\n\n{str(e)[:200]}",
            parse_mode=ParseMode.HTML
        )
        stats_collector.add_request(user_id, 'unknown', False)

async def download_callback_advanced(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التحميل المتقدم"""
    query = update.callback_query
    await query.answer()
    
    # معالجة الأزرار العامة
    if query.data == "cancel":
        await query.edit_message_text("✅ <b>تم الإلغاء</b>", parse_mode=ParseMode.HTML)
        return
    
    if query.data == "main_menu":
        await start(update, context)
        return
    
    if query.data == "help":
        await help_handler(update, context)
        return
    
    if query.data == "stats":
        await stats_handler(update, context)
        return
    
    if query.data == "settings":
        await settings_handler(update, context)
        return
    
    if query.data == "refresh_stats":
        await stats_handler(update, context)
        return
    
    if query.data == "back_to_main":
        await start(update, context)
        return
    
    # معالجة أزرار التحميل
    if query.data.startswith("dl_"):
        # استخراج معلومات التحميل
        parts = query.data.split('_')
        media_type = parts[1]  # video, audio, image, gif
        quality = parts[2] if len(parts) > 2 else 'best'
        
        info = context.user_data.get('video_info', {})
        url = context.user_data.get('video_url')
        
        if not url:
            await query.edit_message_text("❌ <b>انتهت الجلسة</b>\n\nأرسل الرابط مجدداً", parse_mode=ParseMode.HTML)
            return
        
        # تحديد نوع التحميل والجودة
        download_type = 'video'
        if media_type == 'audio':
            download_type = 'audio'
            quality_map = {'320': '320', '192': '192', '128': '128'}
            quality = quality_map.get(quality, '192')
        elif media_type == 'image':
            download_type = 'image'
        elif media_type == 'gif':
            download_type = 'gif'
        
        # رسالة التحميل
        type_names = {
            'video_best': '🎬 فيديو HD',
            'video_720': '🎬 فيديو 720p',
            'video_480': '🎬 فيديو 480p',
            'audio_320': '🎵 MP3 320kbps',
            'audio_192': '🎵 MP3 192kbps',
            'audio_128': '🎵 MP3 128kbps',
            'image': '🖼️ صور',
            'gif': '🎞️ GIF',
        }
        
        status_text = f"⏳ <b>جاري التحميل...</b>\n\n{type_names.get(query.data, '')}\n{info.get('title', '')[:50]}..."
        await query.edit_message_text(status_text, parse_mode=ParseMode.HTML)
        
        try:
            # تحميل الملف
            file_path, error, file_info = await download_media_advanced(
                url,
                download_type,
                quality,
                lambda p: asyncio.run(update_progress(query, p))
            )
            
            if error or not file_path:
                await query.edit_message_text(f"❌ <b>فشل التحميل</b>\n\n{error}", parse_mode=ParseMode.HTML)
                stats_collector.add_error(error)
                return
            
            if not os.path.exists(file_path):
                await query.edit_message_text("❌ <b>الملف غير موجود</b>", parse_mode=ParseMode.HTML)
                return
            
            # التحقق من الحجم
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                os.remove(file_path)
                await query.edit_message_text(f"❌ <b>الملف كبير جداً</b>\n\n📊 {format_size(file_size)}", parse_mode=ParseMode.HTML)
                return
            
            # رفع الملف
            await query.edit_message_text("📤 <b>جاري الرفع إلى تليجرام...</b>", parse_mode=ParseMode.HTML)
            
            success = await upload_to_telegram(update, file_path, info, download_type)
            
            if success:
                # تحديث إحصائيات المستخدم
                user_manager = context.bot_data.get('user_manager')
                if user_manager:
                    user_manager.update_user_stats(update.effective_user.id, file_size)
                
                # حذف الملف
                try:
                    os.remove(file_path)
                except:
                    pass
                
                # حذف رسالة الحالة
                await query.delete_message()
            else:
                await query.edit_message_text("❌ <b>فشل الرفع إلى تليجرام</b>", parse_mode=ParseMode.HTML)
                
        except Exception as e:
            log_error(e, "download_callback_advanced")
            await query.edit_message_text(f"❌ <b>خطأ في التحميل</b>\n\n{str(e)[:200]}", parse_mode=ParseMode.HTML)

async def update_progress(query, progress: float):
    """تحديث تقدم التحميل"""
    try:
        if progress % 10 < 0.1:  # تحديث كل 10%
            bars = '█' * int(progress / 10) + '░' * (10 - int(progress / 10))
            await query.edit_message_text(f"⏳ <b>جاري التحميل...</b>\n\n[{bars}] {progress:.1f}%", parse_mode=ParseMode.HTML)
    except:
        pass

def cleanup_temp_files():
    """تنظيف الملفات المؤقتة"""
    try:
        now = time.time()
        for file_path in DOWNLOAD_DIR.glob('*'):
            if file_path.is_file() and now - file_path.stat().st_mtime > 3600:
                file_path.unlink()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    error = context.error
    log_error(error, "error_handler")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ <b>عذراً، حدث خطأ غير متوقع</b>\n\nالرجاء المحاولة مرة أخرى",
                parse_mode=ParseMode.HTML
            )
    except:
        pass

# ================== تهيئة البوت ==================
def setup_bot() -> Application:
    """تهيئة البوت وإعداداته"""
    
    print(f"{CYAN}{'='*60}{RESET}")
    print(f"{GREEN}🤖 بوت التحميل الفائق - الإصدار 3.0{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    
    # التحقق من FFmpeg
    ffmpeg_available, ffmpeg_version = check_ffmpeg()
    if ffmpeg_available:
        print(f"{GREEN}✅ FFmpeg: {ffmpeg_version}{RESET}")
    else:
        print(f"{YELLOW}⚠️ FFmpeg غير مثبت، تحميل الصوت قد لا يعمل{RESET}")
    
    # معلومات النظام
    system_info = get_system_info()
    print(f"{BLUE}📊 Python: {system_info.get('python', '')}{RESET}")
    print(f"{BLUE}💻 النظام: {system_info.get('platform', '')[:50]}{RESET}")
    print(f"{BLUE}🧠 المعالجات: {system_info.get('cpu_count', 0)}{RESET}")
    
    # المجلدات
    print(f"{MAGENTA}📁 مجلد التحميل: {DOWNLOAD_DIR}{RESET}")
    print(f"{MAGENTA}📁 مجلد الكاش: {CACHE_DIR}{RESET}")
    print(f"{MAGENTA}📁 مجلد السجلات: {LOGS_DIR}{RESET}")
    
    print(f"{CYAN}{'='*60}{RESET}")
    print(f"{GREEN}✅ البوت جاهز للتشغيل!{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة الأنظمة
    application.bot_data['cache'] = CacheSystem(CACHE_DIR)
    application.bot_data['user_manager'] = UserManager(USER_DATA_DIR)
    application.bot_data['download_manager'] = DownloadManager()
    application.bot_data['cookie_manager'] = CookieManager(COOKIES_DIR)
    application.bot_data['stats_collector'] = stats_collector
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("settings", settings_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_advanced))
    application.add_handler(CallbackQueryHandler(download_callback_advanced))
    
    application.add_error_handler(error_handler)
    
    return application

# ================== تشغيل البوت ==================
if __name__ == '__main__':
    try:
        # تهيئة الإحصائيات
        stats_collector = StatisticsCollector()
        
        # تهيئة البوت
        app = setup_bot()
        
        # تشغيل البوت
        print(f"{GREEN}🚀 بدء تشغيل البوت...{RESET}")
        app.run_polling()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}👋 تم إيقاف البوت{RESET}")
    except Exception as e:
        print(f"{RED}❌ خطأ فادح: {e}{RESET}")
        log_error(e, "main")
