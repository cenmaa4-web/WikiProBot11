#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - Professional Edition
Version: 5.0.0
Author: Professional Developer
Description: Advanced Telegram bot for downloading videos from all social media platforms
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
import subprocess
import re
import time
import random
import string
import hashlib
import html
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import defaultdict, deque
from urllib.parse import urlparse, quote, unquote
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from contextlib import asynccontextmanager

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ParseMode, ChatMember
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes,
    ConversationHandler,
    PreCheckoutQueryHandler,
    ShippingQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler
)
from telegram.constants import ParseMode, ChatAction, ChatType
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError
import aiofiles
from PIL import Image
import io

# ==================== CONFIGURATION ====================

# Bot Configuration
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # Replace with your token
BOT_USERNAME = "@YourBotUsername"
BOT_VERSION = "5.0.0"
BOT_RELEASE_DATE = "2024-03-15"
OWNER_ID = 123456789  # Replace with your Telegram ID
OWNER_USERNAME = "@YourUsername"

# Directory Structure
BASE_DIR = Path(__file__).parent.absolute()
DOWNLOAD_DIR = BASE_DIR / "downloads"
THUMBNAIL_DIR = BASE_DIR / "thumbnails"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_DIR = BASE_DIR / "database"
TEMP_DIR = BASE_DIR / "temp"
COOKIES_DIR = BASE_DIR / "cookies"
CACHE_DIR = BASE_DIR / "cache"

# Create all directories
for directory in [DOWNLOAD_DIR, THUMBNAIL_DIR, LOGS_DIR, DATABASE_DIR, TEMP_DIR, COOKIES_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Files
USERS_DB = DATABASE_DIR / "users.json"
STATS_DB = DATABASE_DIR / "stats.json"
DOWNLOADS_DB = DATABASE_DIR / "downloads.json"
BANNED_DB = DATABASE_DIR / "banned.json"
CHANNELS_DB = DATABASE_DIR / "channels.json"
CONFIG_DB = DATABASE_DIR / "config.json"
CACHE_DB = DATABASE_DIR / "cache.json"

# Logging Configuration
LOG_FILE = LOGS_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
ERROR_LOG_FILE = LOGS_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Error Logging
error_logger = logging.getLogger('error')
error_logger.addHandler(logging.FileHandler(ERROR_LOG_FILE, encoding='utf-8'))

# Limits and Constraints
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2 GB (Telegram Premium limit)
MAX_DURATION = 43200  # 12 hours
MAX_SEARCH_RESULTS = 50
MAX_HISTORY_ITEMS = 200
MAX_FAVORITES = 100
MAX_WATCH_LATER = 100
MAX_PLAYLISTS = 50
MAX_PLAYLIST_ITEMS = 200
MAX_CACHE_SIZE = 1000
CACHE_TTL = 3600  # 1 hour
RATE_LIMIT = 10  # requests per second
RATE_LIMIT_WINDOW = 60  # seconds

# Conversation States
(
    MAIN_MENU,
    BROWSE_MENU,
    SEARCH_MENU,
    DOWNLOAD_MENU,
    QUALITY_SELECTION,
    FORMAT_SELECTION,
    PLAYLIST_SELECTION,
    PLAYLIST_CREATION,
    PLAYLIST_EDITING,
    SETTINGS_MENU,
    FAVORITES_MENU,
    HISTORY_MENU,
    CHANNEL_MENU,
    ADMIN_MENU,
    BROADCAST_MENU,
    STATS_MENU,
    LANGUAGE_MENU,
    THEME_MENU,
    NOTIFICATION_MENU,
    ADVANCED_SETTINGS,
    PROFILE_MENU,
    ACHIEVEMENTS_MENU,
    REFERRAL_MENU,
    PREMIUM_MENU,
    SUPPORT_MENU,
    FEEDBACK_MENU,
    REPORT_MENU,
    HELP_MENU,
    ABOUT_MENU,
    UPDATE_MENU,
    BACKUP_MENU,
    RESTORE_MENU,
    MAINTENANCE_MENU,
    DEBUG_MENU,
    TEST_MENU
) = range(35)

# ==================== VIDEO QUALITIES ====================

VIDEO_QUALITIES = {
    '144': {
        'name': '144p',
        'description': 'Very Low Quality',
        'emoji': '📱',
        'height': 144,
        'width': 256,
        'bitrate': '100k',
        'fps': 15,
        'filesize_factor': 0.05,
        'suitable_for': ['Mobile', 'Slow Internet'],
        'icon': '📱'
    },
    '240': {
        'name': '240p',
        'description': 'Low Quality',
        'emoji': '📱',
        'height': 240,
        'width': 426,
        'bitrate': '200k',
        'fps': 20,
        'filesize_factor': 0.1,
        'suitable_for': ['Mobile', 'Limited Data'],
        'icon': '📱'
    },
    '360': {
        'name': '360p',
        'description': 'Medium Quality',
        'emoji': '📺',
        'height': 360,
        'width': 640,
        'bitrate': '500k',
        'fps': 25,
        'filesize_factor': 0.2,
        'suitable_for': ['Mobile', 'Tablet'],
        'icon': '📱'
    },
    '480': {
        'name': '480p',
        'description': 'Good Quality',
        'emoji': '📺',
        'height': 480,
        'width': 854,
        'bitrate': '1000k',
        'fps': 30,
        'filesize_factor': 0.3,
        'suitable_for': ['Tablet', 'Small Screen'],
        'icon': '📺'
    },
    '720': {
        'name': '720p HD',
        'description': 'High Quality',
        'emoji': '🎬',
        'height': 720,
        'width': 1280,
        'bitrate': '2500k',
        'fps': 30,
        'filesize_factor': 0.5,
        'suitable_for': ['HD TV', 'Computer'],
        'icon': '💻'
    },
    '1080': {
        'name': '1080p Full HD',
        'description': 'Very High Quality',
        'emoji': '🎥',
        'height': 1080,
        'width': 1920,
        'bitrate': '5000k',
        'fps': 30,
        'filesize_factor': 1.0,
        'suitable_for': ['Full HD TV', 'Monitor'],
        'icon': '🖥️'
    },
    '1440': {
        'name': '2K Quad HD',
        'description': 'Ultra High Quality',
        'emoji': '🎥',
        'height': 1440,
        'width': 2560,
        'bitrate': '10000k',
        'fps': 30,
        'filesize_factor': 1.8,
        'suitable_for': ['2K Monitor', 'Gaming'],
        'icon': '🖥️'
    },
    '2160': {
        'name': '4K Ultra HD',
        'description': 'Ultra High Quality',
        'emoji': '🎥',
        'height': 2160,
        'width': 3840,
        'bitrate': '20000k',
        'fps': 30,
        'filesize_factor': 3.0,
        'suitable_for': ['4K TV', 'Home Theater'],
        'icon': '📺'
    },
    '4320': {
        'name': '8K Ultra HD',
        'description': 'Professional Quality',
        'emoji': '🎥',
        'height': 4320,
        'width': 7680,
        'bitrate': '40000k',
        'fps': 30,
        'filesize_factor': 6.0,
        'suitable_for': ['8K TV', 'Professional'],
        'icon': '🎬'
    },
    'best': {
        'name': 'Best Quality',
        'description': 'Automatic Best Quality',
        'emoji': '🏆',
        'height': 9999,
        'width': 9999,
        'bitrate': 'best',
        'fps': 60,
        'filesize_factor': 2.0,
        'suitable_for': ['Best Available'],
        'icon': '⭐'
    }
}

# ==================== DOWNLOAD FORMATS ====================

DOWNLOAD_FORMATS = {
    'mp4': {
        'name': 'MP4',
        'description': 'Universal Format',
        'emoji': '🎬',
        'extension': 'mp4',
        'mime_type': 'video/mp4',
        'video_codec': 'h264',
        'audio_codec': 'aac',
        'container': 'MPEG-4',
        'quality': 'Lossy',
        'compression': 'Good',
        'compatibility': 'All Devices',
        'icon': '📹'
    },
    'webm': {
        'name': 'WEBM',
        'description': 'Web Optimized',
        'emoji': '🌐',
        'extension': 'webm',
        'mime_type': 'video/webm',
        'video_codec': 'vp9',
        'audio_codec': 'opus',
        'container': 'Matroska',
        'quality': 'Good',
        'compression': 'Excellent',
        'compatibility': 'Modern Browsers',
        'icon': '🌍'
    },
    'mkv': {
        'name': 'MKV',
        'description': 'Matroska Container',
        'emoji': '📦',
        'extension': 'mkv',
        'mime_type': 'video/x-matroska',
        'video_codec': 'h264/h265',
        'audio_codec': 'aac/mp3',
        'container': 'Matroska',
        'quality': 'Excellent',
        'compression': 'Variable',
        'compatibility': 'VLC, Players',
        'icon': '🗃️'
    },
    'avi': {
        'name': 'AVI',
        'description': 'Legacy Format',
        'emoji': '💾',
        'extension': 'avi',
        'mime_type': 'video/x-msvideo',
        'video_codec': 'mpeg4',
        'audio_codec': 'mp3',
        'container': 'AVI',
        'quality': 'Good',
        'compression': 'Low',
        'compatibility': 'Windows, Old Devices',
        'icon': '📼'
    },
    'mov': {
        'name': 'MOV',
        'description': 'Apple Format',
        'emoji': '🍎',
        'extension': 'mov',
        'mime_type': 'video/quicktime',
        'video_codec': 'h264',
        'audio_codec': 'aac',
        'container': 'QuickTime',
        'quality': 'Excellent',
        'compression': 'Good',
        'compatibility': 'Apple Devices',
        'icon': '📱'
    },
    'wmv': {
        'name': 'WMV',
        'description': 'Windows Format',
        'emoji': '🪟',
        'extension': 'wmv',
        'mime_type': 'video/x-ms-wmv',
        'video_codec': 'wmv',
        'audio_codec': 'wma',
        'container': 'ASF',
        'quality': 'Good',
        'compression': 'Good',
        'compatibility': 'Windows',
        'icon': '💻'
    },
    'flv': {
        'name': 'FLV',
        'description': 'Flash Video',
        'emoji': '⚡',
        'extension': 'flv',
        'mime_type': 'video/x-flv',
        'video_codec': 'h263',
        'audio_codec': 'mp3',
        'container': 'FLV',
        'quality': 'Low',
        'compression': 'Good',
        'compatibility': 'Flash Player',
        'icon': '🎞️'
    },
    '3gp': {
        'name': '3GP',
        'description': 'Mobile Format',
        'emoji': '📱',
        'extension': '3gp',
        'mime_type': 'video/3gpp',
        'video_codec': 'h263',
        'audio_codec': 'amr',
        'container': '3GPP',
        'quality': 'Low',
        'compression': 'High',
        'compatibility': 'Mobile Phones',
        'icon': '📱'
    },
    'mp3': {
        'name': 'MP3',
        'description': 'Audio Only',
        'emoji': '🎵',
        'extension': 'mp3',
        'mime_type': 'audio/mpeg',
        'audio_codec': 'mp3',
        'bitrate': '320k',
        'sample_rate': '44100',
        'channels': 'Stereo',
        'quality': 'Excellent',
        'compression': 'Good',
        'compatibility': 'All Devices',
        'icon': '🎧'
    },
    'm4a': {
        'name': 'M4A',
        'description': 'AAC Audio',
        'emoji': '🎧',
        'extension': 'm4a',
        'mime_type': 'audio/mp4',
        'audio_codec': 'aac',
        'bitrate': '256k',
        'sample_rate': '48000',
        'channels': 'Stereo',
        'quality': 'Excellent',
        'compression': 'Good',
        'compatibility': 'Apple Devices',
        'icon': '🍎'
    },
    'wav': {
        'name': 'WAV',
        'description': 'Uncompressed Audio',
        'emoji': '🎼',
        'extension': 'wav',
        'mime_type': 'audio/wav',
        'audio_codec': 'pcm',
        'bitrate': '1411k',
        'sample_rate': '44100',
        'channels': 'Stereo',
        'quality': 'Lossless',
        'compression': 'None',
        'compatibility': 'Professional',
        'icon': '💿'
    },
    'flac': {
        'name': 'FLAC',
        'description': 'Lossless Audio',
        'emoji': '💿',
        'extension': 'flac',
        'mime_type': 'audio/flac',
        'audio_codec': 'flac',
        'bitrate': '1000k',
        'sample_rate': '96000',
        'channels': 'Stereo',
        'quality': 'Lossless',
        'compression': 'Good',
        'compatibility': 'Audiophile',
        'icon': '🎵'
    },
    'ogg': {
        'name': 'OGG',
        'description': 'Open Audio',
        'emoji': '🔊',
        'extension': 'ogg',
        'mime_type': 'audio/ogg',
        'audio_codec': 'vorbis',
        'bitrate': '192k',
        'sample_rate': '48000',
        'channels': 'Stereo',
        'quality': 'Good',
        'compression': 'Good',
        'compatibility': 'Open Source',
        'icon': '🐧'
    },
    'aac': {
        'name': 'AAC',
        'description': 'Advanced Audio',
        'emoji': '🎵',
        'extension': 'aac',
        'mime_type': 'audio/aac',
        'audio_codec': 'aac',
        'bitrate': '256k',
        'sample_rate': '48000',
        'channels': 'Stereo',
        'quality': 'Excellent',
        'compression': 'Good',
        'compatibility': 'Modern Devices',
        'icon': '📱'
    }
}

# ==================== VIDEO CATEGORIES ====================

VIDEO_CATEGORIES = {
    'trending': {
        'name': '🔥 Trending',
        'name_ar': 'الأكثر مشاهدة',
        'emoji': '🔥',
        'color': 'red',
        'query': 'trending',
        'icon': '📈',
        'description': 'Most popular videos right now',
        'description_ar': 'الفيديوهات الأكثر مشاهدة حالياً'
    },
    'music': {
        'name': '🎵 Music',
        'name_ar': 'موسيقى',
        'emoji': '🎵',
        'color': 'purple',
        'query': 'music video',
        'icon': '🎤',
        'description': 'Music videos and songs',
        'description_ar': 'فيديوهات موسيقية وأغاني'
    },
    'gaming': {
        'name': '🎮 Gaming',
        'name_ar': 'ألعاب',
        'emoji': '🎮',
        'color': 'blue',
        'query': 'gaming',
        'icon': '🕹️',
        'description': 'Gameplay and reviews',
        'description_ar': 'لعب وألعاب فيديو'
    },
    'news': {
        'name': '📰 News',
        'name_ar': 'أخبار',
        'emoji': '📰',
        'color': 'yellow',
        'query': 'news today',
        'icon': '📺',
        'description': 'Latest news and updates',
        'description_ar': 'آخر الأخبار والتحديثات'
    },
    'sports': {
        'name': '⚽ Sports',
        'name_ar': 'رياضة',
        'emoji': '⚽',
        'color': 'green',
        'query': 'sports highlights',
        'icon': '🏆',
        'description': 'Sports highlights and matches',
        'description_ar': 'أبرز الأحداث الرياضية'
    },
    'education': {
        'name': '📚 Education',
        'name_ar': 'تعليم',
        'emoji': '📚',
        'color': 'brown',
        'query': 'educational',
        'icon': '🎓',
        'description': 'Educational content',
        'description_ar': 'محتوى تعليمي'
    },
    'technology': {
        'name': '💻 Technology',
        'name_ar': 'تكنولوجيا',
        'emoji': '💻',
        'color': 'cyan',
        'query': 'tech reviews',
        'icon': '⚙️',
        'description': 'Tech reviews and gadgets',
        'description_ar': 'مراجعات التكنولوجيا'
    },
    'entertainment': {
        'name': '🎭 Entertainment',
        'name_ar': 'ترفيه',
        'emoji': '🎭',
        'color': 'pink',
        'query': 'entertainment',
        'icon': '🎪',
        'description': 'Fun and entertainment',
        'description_ar': 'تسلية وترفيه'
    },
    'comedy': {
        'name': '😄 Comedy',
        'name_ar': 'كوميديا',
        'emoji': '😄',
        'color': 'orange',
        'query': 'comedy',
        'icon': '🎭',
        'description': 'Funny videos and sketches',
        'description_ar': 'فيديوهات مضحكة'
    },
    'movies': {
        'name': '🎬 Movies',
        'name_ar': 'أفلام',
        'emoji': '🎬',
        'color': 'red',
        'query': 'movie trailers',
        'icon': '🍿',
        'description': 'Movie trailers and clips',
        'description_ar': 'إعلانات أفلام ومقاطع'
    },
    'animation': {
        'name': '🖌️ Animation',
        'name_ar': 'أنميشن',
        'emoji': '🖌️',
        'color': 'rainbow',
        'query': 'animation',
        'icon': '🎨',
        'description': 'Animated videos and cartoons',
        'description_ar': 'رسوم متحركة'
    },
    'documentary': {
        'name': '📽️ Documentary',
        'name_ar': 'وثائقيات',
        'emoji': '📽️',
        'color': 'brown',
        'query': 'documentary',
        'icon': '🌍',
        'description': 'Documentaries and educational',
        'description_ar': 'أفلام وثائقية'
    },
    'cooking': {
        'name': '🍳 Cooking',
        'name_ar': 'طبخ',
        'emoji': '🍳',
        'color': 'orange',
        'query': 'cooking recipes',
        'icon': '🥘',
        'description': 'Recipes and cooking shows',
        'description_ar': 'وصفات وطبخ'
    },
    'travel': {
        'name': '✈️ Travel',
        'name_ar': 'سفر',
        'emoji': '✈️',
        'color': 'blue',
        'query': 'travel vlog',
        'icon': '🌍',
        'description': 'Travel vlogs and guides',
        'description_ar': 'مدونات سفر'
    },
    'fashion': {
        'name': '👗 Fashion',
        'name_ar': 'موضة',
        'emoji': '👗',
        'color': 'pink',
        'query': 'fashion',
        'icon': '💄',
        'description': 'Fashion and style',
        'description_ar': 'أزياء وموضة'
    },
    'beauty': {
        'name': '💄 Beauty',
        'name_ar': 'تجميل',
        'emoji': '💄',
        'color': 'pink',
        'query': 'beauty tips',
        'icon': '✨',
        'description': 'Makeup and beauty tips',
        'description_ar': 'مكياج ونصائح تجميل'
    },
    'fitness': {
        'name': '💪 Fitness',
        'name_ar': 'لياقة',
        'emoji': '💪',
        'color': 'green',
        'query': 'fitness workout',
        'icon': '🏋️',
        'description': 'Workout and exercise',
        'description_ar': 'تمارين ولياقة'
    },
    'science': {
        'name': '🔬 Science',
        'name_ar': 'علوم',
        'emoji': '🔬',
        'color': 'cyan',
        'query': 'science experiments',
        'icon': '🧪',
        'description': 'Science and experiments',
        'description_ar': 'علوم وتجارب'
    },
    'history': {
        'name': '📜 History',
        'name_ar': 'تاريخ',
        'emoji': '📜',
        'color': 'brown',
        'query': 'history documentary',
        'icon': '🏛️',
        'description': 'Historical content',
        'description_ar': 'محتوى تاريخي'
    },
    'art': {
        'name': '🎨 Art',
        'name_ar': 'فن',
        'emoji': '🎨',
        'color': 'rainbow',
        'query': 'art tutorial',
        'icon': '🖼️',
        'description': 'Art and creativity',
        'description_ar': 'فن وإبداع'
    }
}

# ==================== SUPPORTED PLATFORMS ====================

SUPPORTED_PLATFORMS = {
    'youtube': {
        'name': 'YouTube',
        'name_ar': 'يوتيوب',
        'emoji': '📺',
        'color': 'red',
        'url_pattern': r'(youtube\.com|youtu\.be)',
        'max_quality': '8K',
        'speed': 'Fast',
        'login_required': False,
        'rate_limit': False,
        'icon': '🎬',
        'description': 'World\'s largest video platform',
        'description_ar': 'أكبر منصة فيديو في العالم'
    },
    'instagram': {
        'name': 'Instagram',
        'name_ar': 'انستغرام',
        'emoji': '📷',
        'color': 'purple',
        'url_pattern': r'(instagram\.com)',
        'max_quality': '1080p',
        'speed': 'Medium',
        'login_required': True,
        'rate_limit': True,
        'icon': '📱',
        'description': 'Photo and video sharing',
        'description_ar': 'مشاركة الصور والفيديو'
    },
    'facebook': {
        'name': 'Facebook',
        'name_ar': 'فيسبوك',
        'emoji': '📘',
        'color': 'blue',
        'url_pattern': r'(facebook\.com|fb\.watch)',
        'max_quality': '720p',
        'speed': 'Medium',
        'login_required': False,
        'rate_limit': True,
        'icon': '👤',
        'description': 'Social networking',
        'description_ar': 'تواصل اجتماعي'
    },
    'twitter': {
        'name': 'Twitter',
        'name_ar': 'تويتر',
        'emoji': '🐦',
        'color': 'cyan',
        'url_pattern': r'(twitter\.com|x\.com)',
        'max_quality': '720p',
        'speed': 'Fast',
        'login_required': False,
        'rate_limit': True,
        'icon': '🐦',
        'description': 'Microblogging platform',
        'description_ar': 'منصة تدوين مصغر'
    },
    'tiktok': {
        'name': 'TikTok',
        'name_ar': 'تيك توك',
        'emoji': '🎵',
        'color': 'black',
        'url_pattern': r'(tiktok\.com)',
        'max_quality': '1080p',
        'speed': 'Fast',
        'login_required': False,
        'rate_limit': True,
        'icon': '🎵',
        'description': 'Short video platform',
        'description_ar': 'منصة فيديوهات قصيرة'
    },
    'reddit': {
        'name': 'Reddit',
        'name_ar': 'ريديت',
        'emoji': '👽',
        'color': 'orange',
        'url_pattern': r'(reddit\.com)',
        'max_quality': '720p',
        'speed': 'Medium',
        'login_required': False,
        'rate_limit': False,
        'icon': '👽',
        'description': 'Social news aggregation',
        'description_ar': 'تجميع الأخبار الاجتماعية'
    },
    'pinterest': {
        'name': 'Pinterest',
        'name_ar': 'بنترست',
        'emoji': '📌',
        'color': 'red',
        'url_pattern': r'(pinterest\.com)',
        'max_quality': '720p',
        'speed': 'Medium',
        'login_required': False,
        'rate_limit': True,
        'icon': '📌',
        'description': 'Visual discovery engine',
        'description_ar': 'محرك اكتشاف بصري'
    },
    'vimeo': {
        'name': 'Vimeo',
        'name_ar': 'فيميو',
        'emoji': '🎥',
        'color': 'cyan',
        'url_pattern': r'(vimeo\.com)',
        'max_quality': '4K',
        'speed': 'Fast',
        'login_required': False,
        'rate_limit': False,
        'icon': '🎬',
        'description': 'High-quality video platform',
        'description_ar': 'منصة فيديو عالية الجودة'
    },
    'twitch': {
        'name': 'Twitch',
        'name_ar': 'تويش',
        'emoji': '🎮',
        'color': 'purple',
        'url_pattern': r'(twitch\.tv)',
        'max_quality': '1080p',
        'speed': 'Fast',
        'login_required': True,
        'rate_limit': True,
        'icon': '🎮',
        'description': 'Live streaming platform',
        'description_ar': 'منصة بث مباشر'
    },
    'dailymotion': {
        'name': 'Dailymotion',
        'name_ar': 'ديلي موشن',
        'emoji': '📺',
        'color': 'blue',
        'url_pattern': r'(dailymotion\.com)',
        'max_quality': '1080p',
        'speed': 'Medium',
        'login_required': False,
        'rate_limit': False,
        'icon': '🎬',
        'description': 'Video sharing platform',
        'description_ar': 'منصة مشاركة فيديو'
    },
    'soundcloud': {
        'name': 'SoundCloud',
        'name_ar': 'ساوند كلاود',
        'emoji': '🎵',
        'color': 'orange',
        'url_pattern': r'(soundcloud\.com)',
        'max_quality': 'Audio',
        'speed': 'Fast',
        'login_required': False,
        'rate_limit': True,
        'icon': '🎧',
        'description': 'Audio distribution platform',
        'description_ar': 'منصة توزيع صوتي'
    },
    'spotify': {
        'name': 'Spotify',
        'name_ar': 'سبوتيفاي',
        'emoji': '🎧',
        'color': 'green',
        'url_pattern': r'(spotify\.com)',
        'max_quality': 'Audio',
        'speed': 'Fast',
        'login_required': True,
        'rate_limit': True,
        'icon': '🎵',
        'description': 'Music streaming service',
        'description_ar': 'خدمة بث موسيقى'
    },
    'linkedin': {
        'name': 'LinkedIn',
        'name_ar': 'لينكد إن',
        'emoji': '💼',
        'color': 'blue',
        'url_pattern': r'(linkedin\.com)',
        'max_quality': '720p',
        'speed': 'Medium',
        'login_required': True,
        'rate_limit': True,
        'icon': '👔',
        'description': 'Professional network',
        'description_ar': 'شبكة مهنية'
    },
    'telegram': {
        'name': 'Telegram',
        'name_ar': 'تليجرام',
        'emoji': '✈️',
        'color': 'blue',
        'url_pattern': r'(t\.me|telegram\.org)',
        'max_quality': '1080p',
        'speed': 'Fast',
        'login_required': False,
        'rate_limit': False,
        'icon': '📱',
        'description': 'Messaging app',
        'description_ar': 'تطبيق مراسلة'
    }
}

# ==================== DATABASE MANAGER ====================

class DatabaseManager:
    """Advanced database manager with caching and atomic operations"""
    
    def __init__(self):
        self.data = {}
        self.cache = {}
        self.locks = defaultdict(asyncio.Lock)
        self.backup_dir = BASE_DIR / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.load_all()
    
    def load_all(self):
        """Load all database files"""
        for file_path in [USERS_DB, STATS_DB, DOWNLOADS_DB, BANNED_DB, CHANNELS_DB, CONFIG_DB, CACHE_DB]:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.data[str(file_path)] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Error loading {file_path}: {e}")
                    self.data[str(file_path)] = {}
            else:
                self.data[str(file_path)] = {}
    
    async def save(self, file_path: Path, data: Dict = None):
        """Save data to file with atomic operation"""
        async with self.locks[str(file_path)]:
            temp_file = file_path.with_suffix('.tmp')
            try:
                if data is not None:
                    self.data[str(file_path)] = data
                
                # Write to temp file first
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(self.data[str(file_path)], ensure_ascii=False, indent=2, default=str))
                
                # Atomic rename
                temp_file.replace(file_path)
                
                # Create backup
                if file_path.exists() and file_path.stat().st_size > 0:
                    backup_file = self.backup_dir / f"{file_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    import shutil
                    shutil.copy2(file_path, backup_file)
                    
                    # Clean old backups (keep last 10)
                    backups = sorted(self.backup_dir.glob(f"{file_path.stem}_*.json"))
                    for old_backup in backups[:-10]:
                        old_backup.unlink()
                
            except Exception as e:
                logger.error(f"Error saving {file_path}: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                raise
    
    async def get(self, file_path: Path, key: str = None, default: Any = None) -> Any:
        """Get value from database"""
        data = self.data.get(str(file_path), {})
        if key is None:
            return data
        return data.get(key, default)
    
    async def set(self, file_path: Path, key: str, value: Any):
        """Set value in database"""
        if str(file_path) not in self.data:
            self.data[str(file_path)] = {}
        self.data[str(file_path)][key] = value
        await self.save(file_path)
    
    async def update(self, file_path: Path, key: str, updates: Dict):
        """Update value in database"""
        current = await self.get(file_path, key, {})
        if isinstance(current, dict):
            current.update(updates)
            await self.set(file_path, key, current)
    
    async def delete(self, file_path: Path, key: str):
        """Delete value from database"""
        if str(file_path) in self.data and key in self.data[str(file_path)]:
            del self.data[str(file_path)][key]
            await self.save(file_path)
    
    async def increment(self, file_path: Path, key: str, field: str, amount: int = 1):
        """Increment a numeric field"""
        data = await self.get(file_path, key, {})
        if isinstance(data, dict):
            data[field] = data.get(field, 0) + amount
            await self.set(file_path, key, data)
    
    async def get_all(self, file_path: Path) -> Dict:
        """Get all data from file"""
        return self.data.get(str(file_path), {})
    
    async def query(self, file_path: Path, condition: callable) -> List[Tuple[str, Any]]:
        """Query database with condition"""
        data = self.data.get(str(file_path), {})
        return [(k, v) for k, v in data.items() if condition(k, v)]
    
    async def backup_all(self):
        """Backup all databases"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.backup_dir / f"full_backup_{timestamp}"
        backup_dir.mkdir(exist_ok=True)
        
        for file_path in [USERS_DB, STATS_DB, DOWNLOADS_DB, BANNED_DB, CHANNELS_DB, CONFIG_DB]:
            if file_path.exists():
                import shutil
                shutil.copy2(file_path, backup_dir / file_path.name)
        
        logger.info(f"Full backup created at {backup_dir}")
        return backup_dir
    
    async def restore(self, backup_path: Path):
        """Restore from backup"""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        if backup_path.is_dir():
            # Restore directory backup
            for file_path in backup_path.glob("*.json"):
                dest = DATABASE_DIR / file_path.name
                import shutil
                shutil.copy2(file_path, dest)
                await self.load_file(dest)
        else:
            # Restore single file
            dest = DATABASE_DIR / backup_path.name
            import shutil
            shutil.copy2(backup_path, dest)
            await self.load_file(dest)
        
        logger.info(f"Restored from {backup_path}")
    
    async def load_file(self, file_path: Path):
        """Load a specific file"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                self.data[str(file_path)] = json.load(f)

# ==================== USER MANAGER ====================

class UserManager:
    """Advanced user manager with caching and analytics"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.active_users = defaultdict(int)
        self.daily_stats = defaultdict(lambda: defaultdict(int))
    
    async def get_user(self, user_id: int) -> Dict:
        """Get user data with caching"""
        user_id = str(user_id)
        
        # Check cache
        if user_id in self.cache:
            cache_time, data = self.cache[user_id]
            if time.time() - cache_time < self.cache_ttl:
                return data
        
        # Get from database
        user_data = await self.db.get(USERS_DB, user_id, {})
        
        # Create new user if not exists
        if not user_data:
            user_data = await self.create_user(user_id)
        
        # Update cache
        self.cache[user_id] = (time.time(), user_data)
        self.active_users[user_id] = time.time()
        
        return user_data
    
    async def create_user(self, user_id: str, username: str = None, first_name: str = None) -> Dict:
        """Create new user with default settings"""
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'joined_date': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'language': 'ar',
            'theme': 'dark',
            'is_banned': False,
            'is_admin': False,
            'is_premium': False,
            'premium_until': None,
            'premium_type': None,
            'download_count': 0,
            'total_downloads': 0,
            'total_size': 0,
            'total_watch_time': 0,
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
                'thumbnail_enabled': True,
                'metadata_enabled': True,
                'compression_enabled': False,
                'subtitle_enabled': True,
                'subtitle_language': 'ar',
                'download_speed': 'normal',
                'concurrent_downloads': 1,
                'bandwidth_limit': 0,
                'proxy_enabled': False,
                'proxy_url': None
            },
            'stats': {
                'videos_downloaded': 0,
                'audio_downloaded': 0,
                'playlists_downloaded': 0,
                'favorites_added': 0,
                'searches_performed': 0,
                'watch_later_added': 0,
                'playlists_created': 0,
                'referrals_count': 0,
                'achievements_unlocked': 0,
                'badges_earned': 0,
                'streak_days': 0,
                'last_streak_date': None
            },
            'daily_limits': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'downloads': 0,
                'size': 0,
                'searches': 0
            },
            'referrals': [],
            'referral_code': self.generate_referral_code(),
            'referred_by': None,
            'referral_earnings': 0,
            'badges': ['new'],
            'achievements': [],
            'points': 0,
            'level': 1,
            'xp': 0,
            'next_level_xp': 100,
            'preferences': {},
            'devices': [],
            'sessions': [],
            'notifications': [],
            'feedback': [],
            'reports': [],
            'notes': []
        }
        
        await self.db.set(USERS_DB, user_id, user_data)
        await self.update_global_stats('new_users')
        
        return user_data
    
    def generate_referral_code(self) -> str:
        """Generate unique referral code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    async def update_user(self, user_id: int, updates: Dict):
        """Update user data"""
        user_id = str(user_id)
        await self.db.update(USERS_DB, user_id, updates)
        
        # Update cache
        if user_id in self.cache:
            cache_time, data = self.cache[user_id]
            data.update(updates)
            self.cache[user_id] = (time.time(), data)
    
    async def update_global_stats(self, stat_name: str, value: int = 1):
        """Update global statistics"""
        stats = await self.db.get(STATS_DB, 'global', {})
        stats[stat_name] = stats.get(stat_name, 0) + value
        stats['last_updated'] = datetime.now().isoformat()
        await self.db.set(STATS_DB, 'global', stats)
    
    async def add_to_history(self, user_id: int, video_info: Dict):
        """Add video to user history"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        if not user_data.get('settings', {}).get('save_history', True):
            return
        
        history = user_data.get('history', [])
        history.append({
            'id': hashlib.md5(f"{video_info.get('webpage_url', '')}_{time.time()}".encode()).hexdigest()[:8],
            'date': datetime.now().isoformat(),
            'title': video_info.get('title', 'Unknown'),
            'url': video_info.get('webpage_url', ''),
            'platform': video_info.get('extractor', 'Unknown'),
            'duration': video_info.get('duration', 0),
            'thumbnail': video_info.get('thumbnail', ''),
            'views': video_info.get('view_count', 0),
            'uploader': video_info.get('uploader', 'Unknown'),
            'watch_time': 0,
            'completed': False
        })
        
        # Keep only last MAX_HISTORY_ITEMS
        if len(history) > MAX_HISTORY_ITEMS:
            history = history[-MAX_HISTORY_ITEMS:]
        
        await self.update_user(user_id, {'history': history})
    
    async def add_to_favorites(self, user_id: int, video_info: Dict) -> bool:
        """Add video to favorites"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        favorites = user_data.get('favorites', [])
        
        # Check for duplicates
        url = video_info.get('webpage_url', '')
        if not any(f.get('url') == url for f in favorites):
            if len(favorites) >= MAX_FAVORITES:
                return False
            
            favorites.append({
                'id': hashlib.md5(f"{url}_{time.time()}".encode()).hexdigest()[:8],
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'thumbnail': video_info.get('thumbnail', ''),
                'uploader': video_info.get('uploader', 'Unknown'),
                'notes': '',
                'tags': []
            })
            
            # Update stats
            stats = user_data.get('stats', {})
            stats['favorites_added'] = stats.get('favorites_added', 0) + 1
            
            await self.update_user(user_id, {
                'favorites': favorites,
                'stats': stats
            })
            
            await self.update_global_stats('total_favorites')
            return True
        return False
    
    async def remove_from_favorites(self, user_id: int, url: str):
        """Remove video from favorites"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        favorites = user_data.get('favorites', [])
        favorites = [f for f in favorites if f.get('url') != url]
        
        await self.update_user(user_id, {'favorites': favorites})
    
    async def add_to_watch_later(self, user_id: int, video_info: Dict) -> bool:
        """Add video to watch later"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        watch_later = user_data.get('watch_later', [])
        
        # Check for duplicates
        url = video_info.get('webpage_url', '')
        if not any(w.get('url') == url for w in watch_later):
            if len(watch_later) >= MAX_WATCH_LATER:
                return False
            
            watch_later.append({
                'id': hashlib.md5(f"{url}_{time.time()}".encode()).hexdigest()[:8],
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
            
            # Update stats
            stats = user_data.get('stats', {})
            stats['watch_later_added'] = stats.get('watch_later_added', 0) + 1
            
            await self.update_user(user_id, {
                'watch_later': watch_later,
                'stats': stats
            })
            
            await self.update_global_stats('total_watch_later')
            return True
        return False
    
    async def check_daily_limits(self, user_id: int, file_size: int) -> Tuple[bool, str]:
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
                'size': 0,
                'searches': 0
            }
        
        # Regular user limits
        MAX_DAILY_DOWNLOADS = 50
        MAX_DAILY_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
        MAX_DAILY_SEARCHES = 100
        
        # Premium user limits
        if user_data.get('is_premium'):
            MAX_DAILY_DOWNLOADS = 200
            MAX_DAILY_SIZE = 20 * 1024 * 1024 * 1024  # 20 GB
            MAX_DAILY_SEARCHES = 500
        
        if limits['downloads'] >= MAX_DAILY_DOWNLOADS:
            return False, "You have exceeded the daily download limit"
        
        if limits['size'] + file_size > MAX_DAILY_SIZE:
            return False, "You have exceeded the daily size limit"
        
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
                'size': file_size,
                'searches': 0
            }
        else:
            limits['downloads'] += 1
            limits['size'] += file_size
        
        await self.update_user(user_id, {'daily_limits': limits})
    
    async def add_xp(self, user_id: int, xp: int):
        """Add XP to user and check level up"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        current_xp = user_data.get('xp', 0)
        current_level = user_data.get('level', 1)
        next_level_xp = user_data.get('next_level_xp', 100)
        
        new_xp = current_xp + xp
        new_level = current_level
        
        # Check for level up
        while new_xp >= next_level_xp:
            new_level += 1
            new_xp -= next_level_xp
            next_level_xp = int(next_level_xp * 1.5)
            
            # Award level up badge
            if 'level_up' not in user_data.get('badges', []):
                badges = user_data.get('badges', [])
                badges.append('level_up')
                await self.update_user(user_id, {'badges': badges})
        
        await self.update_user(user_id, {
            'xp': new_xp,
            'level': new_level,
            'next_level_xp': next_level_xp
        })
    
    async def check_achievements(self, user_id: int):
        """Check and award achievements"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        achievements = []
        stats = user_data.get('stats', {})
        
        # Download achievements
        if stats.get('videos_downloaded', 0) >= 10:
            achievements.append('downloader_10')
        if stats.get('videos_downloaded', 0) >= 100:
            achievements.append('downloader_100')
        if stats.get('videos_downloaded', 0) >= 1000:
            achievements.append('downloader_1000')
        
        # Favorite achievements
        if stats.get('favorites_added', 0) >= 10:
            achievements.append('favorite_10')
        if stats.get('favorites_added', 0) >= 50:
            achievements.append('favorite_50')
        
        # Streak achievements
        if stats.get('streak_days', 0) >= 7:
            achievements.append('streak_7')
        if stats.get('streak_days', 0) >= 30:
            achievements.append('streak_30')
        
        # Update achievements
        current_achievements = user_data.get('achievements', [])
        new_achievements = [a for a in achievements if a not in current_achievements]
        
        if new_achievements:
            current_achievements.extend(new_achievements)
            await self.update_user(user_id, {
                'achievements': current_achievements,
                'stats': {**stats, 'achievements_unlocked': len(current_achievements)}
            })
            
            # Award XP for achievements
            await self.add_xp(user_id, len(new_achievements) * 10)
    
    async def update_streak(self, user_id: int):
        """Update user streak"""
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        stats = user_data.get('stats', {})
        last_streak = stats.get('last_streak_date')
        today = datetime.now().date()
        
        if last_streak:
            last_date = datetime.fromisoformat(last_streak).date()
            if (today - last_date).days == 1:
                # Consecutive day
                stats['streak_days'] = stats.get('streak_days', 0) + 1
            elif (today - last_date).days > 1:
                # Streak broken
                stats['streak_days'] = 1
        else:
            # First day
            stats['streak_days'] = 1
        
        stats['last_streak_date'] = today.isoformat()
        
        await self.update_user(user_id, {'stats': stats})
        
        # Award XP for streak
        if stats['streak_days'] % 7 == 0:
            await self.add_xp(user_id, 50)

# ==================== STATS MANAGER ====================

class StatsManager:
    """Advanced statistics manager with analytics"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.daily_stats = defaultdict(lambda: defaultdict(int))
        self.hourly_stats = defaultdict(lambda: defaultdict(int))
        self.platform_stats = defaultdict(int)
        self.quality_stats = defaultdict(int)
        self.format_stats = defaultdict(int)
    
    async def get_global_stats(self) -> Dict:
        """Get global statistics"""
        return await self.db.get(STATS_DB, 'global', {})
    
    async def get_detailed_stats(self) -> Dict:
        """Get detailed statistics"""
        users = await self.db.get_all(USERS_DB)
        downloads = await self.db.get_all(DOWNLOADS_DB)
        
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        week_ago = (now - timedelta(days=7)).isoformat()
        month_ago = (now - timedelta(days=30)).isoformat()
        
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
            'peak_day': '',
            'platform_stats': {},
            'quality_stats': {},
            'format_stats': {},
            'hourly_stats': {i: 0 for i in range(24)},
            'daily_stats': {},
            'monthly_stats': {},
            'user_growth': [],
            'download_growth': [],
            'top_platforms': [],
            'top_qualities': [],
            'top_formats': [],
            'top_users': [],
            'system_stats': {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'uptime': 0,
                'requests_per_minute': 0,
                'error_rate': 0
            }
        }
        
        # Process users
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
        
        # Process downloads
        total_downloads = 0
        total_size = 0
        
        for dl_id, dl in downloads.items():
            stats['total_downloads'] += 1
            stats['total_size'] += dl.get('size', 0)
            total_downloads += 1
            total_size += dl.get('size', 0)
            
            dl_date = dl.get('date', '')[:10]
            if dl_date == today:
                stats['today_downloads'] += 1
                stats['today_size'] += dl.get('size', 0)
            if dl_date >= week_ago[:10]:
                stats['week_downloads'] += 1
                stats['week_size'] += dl.get('size', 0)
            if dl_date >= month_ago[:10]:
                stats['month_downloads'] += 1
                stats['month_size'] += dl.get('size', 0)
            
            # Platform statistics
            platform = dl.get('platform', 'unknown')
            stats['platform_stats'][platform] = stats['platform_stats'].get(platform, 0) + 1
            
            # Quality statistics
            quality = dl.get('quality', 'unknown')
            stats['quality_stats'][quality] = stats['quality_stats'].get(quality, 0) + 1
            
            # Format statistics
            fmt = dl.get('format', 'unknown')
            stats['format_stats'][fmt] = stats['format_stats'].get(fmt, 0) + 1
            
            # Hourly statistics
            try:
                hour = int(dl.get('date', '12:00').split('T')[1].split(':')[0])
                stats['hourly_stats'][hour] += 1
                if stats['hourly_stats'][hour] > stats['hourly_stats'].get(stats['peak_hour'], 0):
                    stats['peak_hour'] = hour
            except:
                pass
            
            # Daily statistics
            stats['daily_stats'][dl_date] = stats['daily_stats'].get(dl_date, 0) + 1
            
            # Monthly statistics
            month = dl_date[:7]
            stats['monthly_stats'][month] = stats['monthly_stats'].get(month, 0) + 1
        
        # Calculate averages
        if stats['total_downloads'] > 0:
            stats['avg_download_size'] = stats['total_size'] / stats['total_downloads']
        
        # Get top platforms
        stats['top_platforms'] = sorted(
            stats['platform_stats'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Get top qualities
        stats['top_qualities'] = sorted(
            stats['quality_stats'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Get top formats
        stats['top_formats'] = sorted(
            stats['format_stats'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Get top users
        user_downloads = defaultdict(int)
        for dl_id, dl in downloads.items():
            user_downloads[dl.get('user_id', 'unknown')] += 1
        
        stats['top_users'] = sorted(
            user_downloads.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return stats
    
    async def log_download(self, user_id: int, video_info: Dict, quality: str, format: str, size: int):
        """Log download for statistics"""
        download_id = f"{user_id}_{int(time.time())}_{random.randint(1000, 9999)}"
        
        download_data = {
            'id': download_id,
            'user_id': user_id,
            'date': datetime.now().isoformat(),
            'title': video_info.get('title', 'Unknown'),
            'url': video_info.get('webpage_url', ''),
            'platform': video_info.get('extractor', 'Unknown'),
            'quality': quality,
            'format': format,
            'size': size,
            'duration': video_info.get('duration', 0),
            'success': True,
            'error': None
        }
        
        await self.db.set(DOWNLOADS_DB, download_id, download_data)
        
        # Update daily stats
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_stats[today]['downloads'] += 1
        self.daily_stats[today]['size'] += size
        
        # Update hourly stats
        hour = datetime.now().hour
        self.hourly_stats[today][hour] += 1
        
        # Update platform stats
        platform = video_info.get('extractor', 'unknown')
        self.platform_stats[platform] += 1
        
        # Update quality stats
        self.quality_stats[quality] += 1
        
        # Update format stats
        self.format_stats[format] += 1
        
        # Update global stats
        await self.db.increment(STATS_DB, 'global', 'total_downloads')
        await self.db.increment(STATS_DB, 'global', 'total_size', size)
    
    async def log_error(self, error_type: str, error_msg: str, user_id: int = None):
        """Log error for statistics"""
        error_id = f"error_{int(time.time())}_{random.randint(1000, 9999)}"
        
        error_data = {
            'id': error_id,
            'date': datetime.now().isoformat(),
            'type': error_type,
            'message': error_msg,
            'user_id': user_id,
            'resolved': False
        }
        
        error_logger.error(f"Error: {error_type} - {error_msg} - User: {user_id}")
        
        # Store in database
        error_file = DATABASE_DIR / "errors.json"
        errors = await self.db.get(error_file, 'errors', [])
        errors.append(error_data)
        
        # Keep last 1000 errors
        if len(errors) > 1000:
            errors = errors[-1000:]
        
        await self.db.set(error_file, 'errors', errors)

# ==================== VIDEO PROCESSOR ====================

class VideoProcessor:
    """Advanced video processor with yt-dlp"""
    
    def __init__(self, stats_manager: StatsManager):
        self.stats_manager = stats_manager
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.download_semaphore = asyncio.Semaphore(3)
        self.active_downloads = {}
        self.download_queue = asyncio.Queue()
        self.cache = {}
        self.rate_limiter = defaultdict(lambda: deque(maxlen=RATE_LIMIT))
        
        # Base yt-dlp options
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
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash'],
                }
            }
        }
        
        # Cookies file if exists
        cookies_file = COOKIES_DIR / 'cookies.txt'
        if cookies_file.exists():
            self.ydl_opts_base['cookiefile'] = str(cookies_file)
    
    def check_rate_limit(self, ip: str) -> bool:
        """Check rate limit for IP"""
        now = time.time()
        self.rate_limiter[ip].append(now)
        
        # Remove old entries
        while self.rate_limiter[ip] and self.rate_limiter[ip][0] < now - RATE_LIMIT_WINDOW:
            self.rate_limiter[ip].popleft()
        
        return len(self.rate_limiter[ip]) <= RATE_LIMIT
    
    async def get_video_info(self, url: str, user_id: int = None) -> Optional[Dict]:
        """Get video information"""
        # Check cache
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < CACHE_TTL:
                return data
        
        try:
            # Run in executor
            loop = asyncio.get_event_loop()
            
            with yt_dlp.YoutubeDL(self.ydl_opts_base) as ydl:
                info = await loop.run_in_executor(
                    self.executor,
                    lambda: ydl.extract_info(url, download=False)
                )
                
                if not info:
                    return None
                
                processed_info = self.process_video_info(info)
                
                # Cache the result
                self.cache[cache_key] = (time.time(), processed_info)
                
                # Clean old cache entries
                if len(self.cache) > MAX_CACHE_SIZE:
                    oldest = min(self.cache.keys(), key=lambda k: self.cache[k][0])
                    del self.cache[oldest]
                
                return processed_info
                
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            if user_id:
                await self.stats_manager.log_error('info_error', str(e), user_id)
            return None
    
    def process_video_info(self, info: Dict) -> Dict:
        """Process and structure video information"""
        # Basic information
        video_info = {
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
            'subtitles': info.get('subtitles', {}),
            'automatic_captions': info.get('automatic_captions', {}),
            'heatmap': info.get('heatmap', []),
            'chapters': info.get('chapters', []),
        }
        
        # Available formats
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
                        'quality': f.get('quality', None),
                        'tbr': f.get('tbr', 0),
                        'asr': f.get('asr', 0),
                        'container': f.get('container', ''),
                    }
                    video_info['formats'].append(format_info)
        
        return video_info
    
    async def search_videos(self, query: str, limit: int = 10, user_id: int = None) -> List[Dict]:
        """Search for videos"""
        try:
            ydl_opts = {
                **self.ydl_opts_base,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            loop = asyncio.get_event_loop()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = await loop.run_in_executor(
                    self.executor,
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
                                'thumbnail': entry.get('thumbnail', f"https://img.youtube.com/vi/{entry.get('id', '')}/maxresdefault.jpg"),
                                'channel': entry.get('uploader', ''),
                                'views': entry.get('view_count', 0),
                                'upload_date': entry.get('upload_date', ''),
                                'description': entry.get('description', '')[:200]
                            })
                return videos
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            if user_id:
                await self.stats_manager.log_error('search_error', str(e), user_id)
            return []
    
    async def get_trending(self, category: str = 'trending', limit: int = 10, user_id: int = None) -> List[Dict]:
        """Get trending videos by category"""
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
                'education': 'educational',
                'technology': 'tech',
                'entertainment': 'entertainment',
                'comedy': 'comedy',
                'movies': 'movie trailers',
                'animation': 'animation',
                'documentary': 'documentary',
                'cooking': 'cooking',
                'travel': 'travel',
                'fashion': 'fashion',
                'beauty': 'beauty',
                'fitness': 'fitness',
                'science': 'science',
                'history': 'history',
                'art': 'art'
            }
            
            query = search_queries.get(category, 'trending')
            
            loop = asyncio.get_event_loop()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = await loop.run_in_executor(
                    self.executor,
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
                                'thumbnail': entry.get('thumbnail', f"https://img.youtube.com/vi/{entry.get('id', '')}/maxresdefault.jpg"),
                                'channel': entry.get('uploader', ''),
                                'views': entry.get('view_count', 0),
                                'category': category
                            })
                return videos
                
        except Exception as e:
            logger.error(f"Trending error: {e}")
            if user_id:
                await self.stats_manager.log_error('trending_error', str(e), user_id)
            return []
    
    async def download_video(self, url: str, quality: str = 'best', format: str = 'mp4', 
                            user_id: int = None, progress_callback=None) -> Optional[Dict]:
        """Download video with options"""
        async with self.download_semaphore:
            try:
                # Configure format
                if quality == 'best':
                    if format == 'mp3':
                        format_spec = 'bestaudio/best'
                    else:
                        format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    height = VIDEO_QUALITIES.get(quality, {}).get('height', 720)
                    if format == 'mp3':
                        format_spec = 'bestaudio/best'
                    else:
                        format_spec = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'
                
                # Generate filename
                timestamp = int(time.time())
                random_id = random.randint(1000, 9999)
                filename = DOWNLOAD_DIR / f"video_{timestamp}_{random_id}.%(ext)s"
                
                # Configure yt-dlp options
                ydl_opts = {
                    **self.ydl_opts_base,
                    'format': format_spec,
                    'outtmpl': str(filename),
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
                    'postprocessors': []
                }
                
                # Add audio postprocessor for MP3
                if format == 'mp3':
                    ydl_opts['postprocessors'].append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    })
                
                # Add thumbnail embedder
                ydl_opts['postprocessors'].append({
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False
                })
                
                # Add metadata embedder
                ydl_opts['postprocessors'].append({
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                })
                
                # Track download
                download_id = f"{user_id}_{timestamp}" if user_id else f"anon_{timestamp}"
                self.active_downloads[download_id] = {
                    'url': url,
                    'quality': quality,
                    'format': format,
                    'start_time': time.time(),
                    'status': 'downloading',
                    'progress': 0
                }
                
                # Download
                loop = asyncio.get_event_loop()
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await loop.run_in_executor(
                        self.executor,
                        lambda: ydl.extract_info(url, download=True)
                    )
                    
                    # Get filename
                    file = ydl.prepare_filename(info)
                    
                    # Adjust extension
                    if format == 'mp3':
                        file = str(file).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                    else:
                        for ext in ['.mp4', '.webm', '.mkv']:
                            test_file = str(file).replace('%(ext)s', ext)
                            if Path(test_file).exists():
                                file = test_file
                                break
                    
                    file_path = Path(file)
                    
                    if file_path.exists():
                        size = file_path.stat().st_size
                        
                        # Update download status
                        self.active_downloads[download_id]['status'] = 'completed'
                        self.active_downloads[download_id]['file'] = str(file_path)
                        self.active_downloads[download_id]['size'] = size
                        self.active_downloads[download_id]['end_time'] = time.time()
                        
                        # Process info
                        processed_info = self.process_video_info(info)
                        
                        return {
                            'success': True,
                            'file': str(file_path),
                            'size': size,
                            'info': processed_info,
                            'title': info.get('title', ''),
                            'duration': info.get('duration', 0),
                            'download_id': download_id
                        }
                    
                    return {'success': False, 'error': 'File not found'}
                    
            except Exception as e:
                logger.error(f"Download error: {e}")
                if user_id:
                    await self.stats_manager.log_error('download_error', str(e), user_id)
                
                if 'download_id' in locals():
                    self.active_downloads[download_id]['status'] = 'error'
                    self.active_downloads[download_id]['error'] = str(e)
                
                return {'success': False, 'error': str(e)}
    
    async def get_download_status(self, download_id: str) -> Optional[Dict]:
        """Get download status"""
        return self.active_downloads.get(download_id)
    
    async def cancel_download(self, download_id: str) -> bool:
        """Cancel ongoing download"""
        if download_id in self.active_downloads:
            self.active_downloads[download_id]['status'] = 'cancelled'
            # TODO: Implement actual cancellation
            return True
        return False
    
    async def get_playlist_info(self, url: str, user_id: int = None) -> Optional[Dict]:
        """Get playlist information"""
        try:
            ydl_opts = {
                **self.ydl_opts_base,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            loop = asyncio.get_event_loop()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    self.executor,
                    lambda: ydl.extract_info(url, download=False)
                )
                
                if info and 'entries' in info:
                    playlist_info = {
                        'id': info.get('id', ''),
                        'title': info.get('title', 'Playlist'),
                        'description': info.get('description', ''),
                        'uploader': info.get('uploader', ''),
                        'view_count': info.get('view_count', 0),
                        'entries': []
                    }
                    
                    for entry in info['entries']:
                        if entry:
                            playlist_info['entries'].append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', ''),
                                'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': entry.get('thumbnail', f"https://img.youtube.com/vi/{entry.get('id', '')}/maxresdefault.jpg"),
                                'channel': entry.get('uploader', ''),
                                'views': entry.get('view_count', 0)
                            })
                    
                    return playlist_info
                
                return None
                
        except Exception as e:
            logger.error(f"Playlist info error: {e}")
            if user_id:
                await self.stats_manager.log_error('playlist_error', str(e), user_id)
            return None

# ==================== BOT CLASS ====================

class VideoDownloaderBot:
    """Main bot class"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.stats_manager = StatsManager(self.db)
        self.user_manager = UserManager(self.db)
        self.video_processor = VideoProcessor(self.stats_manager)
        self.user_sessions = {}
        self.start_time = datetime.now()
        self.is_running = True
        
        # Check FFmpeg
        self.check_ffmpeg()
        
        logger.info("=" * 60)
        logger.info(f"Bot initialized - Version {BOT_VERSION}")
        logger.info(f"Start time: {self.start_time}")
        logger.info("=" * 60)
    
    def check_ffmpeg(self):
        """Check FFmpeg installation"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                logger.info(f"FFmpeg: {version[:100]}")
            else:
                logger.warning("FFmpeg not installed properly")
        except FileNotFoundError:
            logger.warning("FFmpeg not found - some features may not work")
    
    # ========== Helper Functions ==========
    
    def format_time(self, seconds: int) -> str:
        """Format time duration"""
        if not seconds:
            return "00:00"
        
        try:
            seconds = int(seconds)
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            
            if days > 0:
                return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
            elif hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes:02d}:{secs:02d}"
        except:
            return "00:00"
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size"""
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
        """Format number with K/M/B suffixes"""
        if number >= 1_000_000_000:
            return f"{number/1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        return str(number)
    
    def get_platform_info(self, url: str) -> Dict:
        """Get platform info from URL"""
        for platform_id, info in SUPPORTED_PLATFORMS.items():
            if re.search(info['url_pattern'], url, re.I):
                return {
                    'id': platform_id,
                    **info
                }
        return {
            'id': 'unknown',
            'name': 'Unknown',
            'name_ar': 'غير معروفة',
            'emoji': '🌐',
            'color': 'gray',
            'max_quality': 'Unknown',
            'speed': 'Unknown',
            'login_required': False,
            'icon': '🌐'
        }
    
    def create_progress_bar(self, percentage: float, width: int = 10) -> str:
        """Create progress bar"""
        filled = int(width * percentage / 100)
        empty = width - filled
        return '█' * filled + '░' * empty
    
    def escape_markdown(self, text: str) -> str:
        """Escape Markdown special characters"""
        if not text:
            return ""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    # ========== Command Handlers ==========
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_data = await self.user_manager.get_user(user.id)
        
        # Update user info
        await self.user_manager.update_user(user.id, {
            'username': user.username,
            'first_name': user.first_name,
            'last_active': datetime.now().isoformat()
        })
        
        # Update streak
        await self.user_manager.update_streak(user.id)
        
        # Get stats
        uptime = datetime.now() - self.start_time
        users_count = len(await self.db.get_all(USERS_DB))
        stats = await self.stats_manager.get_global_stats()
        downloads_count = stats.get('total_downloads', 0)
        
        welcome_text = f"""
🎬 *Welcome {self.escape_markdown(user.first_name)}!*

I'm a professional video downloader bot version {BOT_VERSION} 🚀

📥 *Send me a video link and I'll download it for you*
🔍 *Or type any keyword to search for videos*

✨ *Features:*
• Download from {len(SUPPORTED_PLATFORMS)}+ platforms
• Multiple qualities (144p - 8K)
• Multiple formats (MP4, MP3, MKV, etc.)
• Direct watch links
• Browse videos by category
• Favorites and watch later
• Personal statistics
• Custom settings
• Achievements and badges
• Referral system
• Daily limits and streaks

📊 *Bot Statistics:*
👥 Users: {users_count:,}
📥 Downloads: {downloads_count:,}
⏰ Uptime: {self.format_time(int(uptime.total_seconds()))}

🔰 *Available Commands:*
/start - Main menu
/browse - Browse videos
/search - Advanced search
/favorites - My favorites
/watchlater - Watch later
/history - My history
/stats - My statistics
/settings - Settings
/profile - My profile
/referrals - Referral system
/help - Help
/about - About

👇 *Choose an option:*
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🔥 Browse", callback_data="browse"),
                InlineKeyboardButton("🔍 Search", callback_data="search"),
                InlineKeyboardButton("📥 Download", callback_data="download")
            ],
            [
                InlineKeyboardButton("⭐ Favorites", callback_data="favorites"),
                InlineKeyboardButton("⏰ Watch Later", callback_data="watchlater"),
                InlineKeyboardButton("📊 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("👤 Profile", callback_data="profile"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle browse command"""
        query = update.callback_query
        await query.answer()
        
        # Create category buttons
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
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🔥 *Browse Videos*\n\nChoose a category:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """Handle category browsing"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text(
            f"⏳ Loading {VIDEO_CATEGORIES[category]['name_ar']}...",
            parse_mode='Markdown'
        )
        
        # Get videos
        videos = await self.video_processor.get_trending(category, limit=10, user_id=user_id)
        
        if not videos:
            await query.edit_message_text(
                "❌ No videos found in this category",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="browse")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        # Save in session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        self.user_sessions[user_id]['browse'] = {
            'category': category,
            'videos': videos,
            'page': 0
        }
        
        # Show first video
        await self.show_video(update, context, videos[0], 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                        video: Dict, index: int):
        """Show video with thumbnail and info"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        duration = self.format_time(video.get('duration', 0))
        views = self.format_number(video.get('views', 0))
        
        text = f"""
🎬 *{self.escape_markdown(video['title'][:200])}*

📺 *Channel:* {self.escape_markdown(video.get('channel', 'Unknown'))}
⏱ *Duration:* {duration}
👁 *Views:* {views}

🔗 *Watch on YouTube:*
[Click here to watch]({video['url']})

📝 *To download:* Use the buttons below
        """
        
        # Video buttons
        keyboard = [
            [
                InlineKeyboardButton("▶️ Watch", url=video['url']),
                InlineKeyboardButton("📥 Download", callback_data=f"dl_{video['url']}")
            ],
            [
                InlineKeyboardButton("⭐ Favorite", callback_data=f"fav_{video['url']}"),
                InlineKeyboardButton("⏰ Watch Later", callback_data=f"wl_{video['url']}")
            ]
        ]
        
        # Navigation buttons
        session = self.user_sessions.get(user_id, {}).get('browse', {})
        videos = session.get('videos', [])
        
        if videos:
            nav_buttons = []
            if index > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data="nav_prev"))
            if index < len(videos) - 1:
                nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="nav_next"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
                keyboard.append([InlineKeyboardButton(
                    f"📄 Page {index + 1}/{len(videos)}", 
                    callback_data="page_info"
                )])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="browse")])
        
        # Send photo
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
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text
        user = update.effective_user
        
        # Update last active
        await self.user_manager.update_user(user.id, {
            'last_active': datetime.now().isoformat()
        })
        
        # Update streak
        await self.user_manager.update_streak(user.id)
        
        # Check if URL
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """Handle video URL"""
        msg = await update.message.reply_text("⏳ Processing link...")
        
        # Get platform info
        platform = self.get_platform_info(url)
        user_id = update.effective_user.id
        
        try:
            # Get video info
            info = await self.video_processor.get_video_info(url, user_id)
            
            if not info:
                await msg.edit_text(
                    f"❌ Could not get video info\n\n"
                    f"Platform: {platform['emoji']} {platform['name']}\n"
                    f"Link: {url[:50]}..."
                )
                return
            
            # Check duration
            if info['duration'] > MAX_DURATION:
                await msg.edit_text(
                    f"❌ Video duration ({self.format_time(info['duration'])}) exceeds limit ({self.format_time(MAX_DURATION)})"
                )
                return
            
            # Save in session
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id]['current_video'] = info
            
            # Video info text
            text = f"""
{platform['emoji']} *Video Information*

📹 *Title:* {self.escape_markdown(info['title'][:200])}
⏱ *Duration:* {self.format_time(info['duration'])}
📊 *Platform:* {platform['emoji']} {platform['name']}
👤 *Uploader:* {self.escape_markdown(info['uploader'])}
👁 *Views:* {self.format_number(info['view_count'])}
👍 *Likes:* {self.format_number(info['like_count'])}
📅 *Upload Date:* {info['upload_date'] or 'Unknown'}

🔗 *Watch Link:*
[Click here to watch]({info['webpage_url']})

📥 *To download:* Use the buttons below
            """
            
            # Video buttons
            keyboard = [
                [
                    InlineKeyboardButton("▶️ Watch", url=info['webpage_url']),
                    InlineKeyboardButton("📥 Download", callback_data="download_menu")
                ],
                [
                    InlineKeyboardButton("⭐ Favorite", callback_data="add_favorite"),
                    InlineKeyboardButton("⏰ Watch Later", callback_data="add_watchlater")
                ],
                [
                    InlineKeyboardButton("ℹ️ More Info", callback_data="more_info"),
                    InlineKeyboardButton("🔄 Qualities", callback_data="available_qualities")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            # Send thumbnail
            try:
                await msg.delete()
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                await msg.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            
            # Add to history
            await self.user_manager.add_to_history(user_id, info)
            
            # Add XP
            await self.user_manager.add_xp(user_id, 5)
            
        except Exception as e:
            logger.error(f"URL handling error: {e}")
            await self.stats_manager.log_error('url_error', str(e), user_id)
            await msg.edit_text(
                f"❌ Error processing link: {str(e)[:200]}\n\n"
                f"Platform: {platform['emoji']} {platform['name']}\n"
                f"Link: {url[:50]}..."
            )
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """Handle search query"""
        msg = await update.message.reply_text(f"🔍 Searching for: '{query}'...")
        user_id = update.effective_user.id
        
        try:
            # Search videos
            videos = await self.video_processor.search_videos(query, limit=10, user_id=user_id)
            
            if not videos:
                await msg.edit_text(
                    f"❌ No results found for: '{query}'",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                    ]])
                )
                return
            
            # Save results
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id]['search_results'] = videos
            self.user_sessions[user_id]['search_page'] = 0
            
            # Show first result
            await self.show_search_result(update, context, videos[0], 0)
            await msg.delete()
            
            # Update search stats
            user_data = await self.user_manager.get_user(user_id)
            stats = user_data.get('stats', {})
            stats['searches_performed'] = stats.get('searches_performed', 0) + 1
            await self.user_manager.update_user(user_id, {'stats': stats})
            
            # Add XP
            await self.user_manager.add_xp(user_id, 2)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await self.stats_manager.log_error('search_error', str(e), user_id)
            await msg.edit_text(f"❌ Search error: {str(e)[:200]}")
    
    async def show_search_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                video: Dict, index: int):
        """Show search result"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        duration = self.format_time(video.get('duration', 0))
        views = self.format_number(video.get('views', 0))
        
        text = f"""
🔍 *Search Result ({index + 1})*

🎬 *{self.escape_markdown(video['title'][:200])}*

📺 *Channel:* {self.escape_markdown(video.get('channel', 'Unknown'))}
⏱ *Duration:* {duration}
👁 *Views:* {views}

🔗 *Watch on YouTube:*
[Click here to watch]({video['url']})
        """
        
        # Navigation buttons
        keyboard = []
        videos = self.user_sessions.get(user_id, {}).get('search_results', [])
        
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data="search_prev"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="search_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.extend([
            [
                InlineKeyboardButton("▶️ Watch", url=video['url']),
                InlineKeyboardButton("📥 Download", callback_data=f"dl_{video['url']}")
            ],
            [InlineKeyboardButton("🔙 New Search", callback_data="search")]
        ])
        
        # Send photo
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
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
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
        """Show download menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
        
        if not video_info:
            await query.edit_message_text(
                "❌ No video info. Send a video link first.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]])
            )
            return
        
        text = f"""
📥 *Choose Download Options*

🎬 *Video:* {self.escape_markdown(video_info.get('title', '')[:100])}
⏱ *Duration:* {self.format_time(video_info.get('duration', 0))}

👇 *Select quality:*
        """
        
        # Quality buttons
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
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_video")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        """Select video quality"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
        
        text = f"""
📥 *Choose Format*

🎬 *Quality:* {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}
⏱ *Duration:* {self.format_time(video_info.get('duration', 0))}

👇 *Select format:*
        """
        
        # Format buttons
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
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="download_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                            quality: str, format: str):
        """Start video download"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
        url = video_info.get('webpage_url', '')
        
        if not url:
            await query.edit_message_text("❌ No video URL")
            return
        
        # Check daily limits
        can_download, message = await self.user_manager.check_daily_limits(user_id, 0)
        if not can_download:
            await query.edit_message_text(message)
            return
        
        # Progress message
        progress_msg = await query.edit_message_text(
            f"⬇️ *Downloading...*\n\n"
            f"🎬 {self.escape_markdown(video_info.get('title', '')[:100])}\n"
            f"⚡ Quality: {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}\n"
            f"📁 Format: {DOWNLOAD_FORMATS[format]['emoji']} {DOWNLOAD_FORMATS[format]['name']}\n\n"
            f"⏳ Please wait...",
            parse_mode='Markdown'
        )
        
        # Progress callback
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percentage = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    speed_str = self.format_size(speed) + '/s' if speed else '?'
                    eta = d.get('eta', 0)
                    
                    # Update every 5%
                    if int(percentage) % 5 == 0:
                        progress_bar = self.create_progress_bar(percentage)
                        text = (
                            f"⬇️ *Downloading...*\n\n"
                            f"📊 {progress_bar} {percentage:.1f}%\n"
                            f"⚡ Speed: {speed_str}\n"
                            f"⏱ ETA: {self.format_time(eta)}\n"
                            f"📦 Downloaded: {self.format_size(downloaded)} / {self.format_size(total)}"
                        )
                        asyncio.create_task(progress_msg.edit_text(text, parse_mode='Markdown'))
        
        try:
            # Download video
            result = await self.video_processor.download_video(
                url=url,
                quality=quality,
                format=format,
                user_id=user_id,
                progress_callback=progress_hook
            )
            
            if result['success']:
                file = result['file']
                size = result['size']
                
                # Update daily limits
                await self.user_manager.increment_daily_usage(user_id, size)
                
                # Update user stats
                user_data = await self.user_manager.get_user(user_id)
                stats = user_data.get('stats', {})
                if format == 'mp3':
                    stats['audio_downloaded'] = stats.get('audio_downloaded', 0) + 1
                else:
                    stats['videos_downloaded'] = stats.get('videos_downloaded', 0) + 1
                
                await self.user_manager.update_user(user_id, {
                    'download_count': user_data.get('download_count', 0) + 1,
                    'total_downloads': user_data.get('total_downloads', 0) + 1,
                    'total_size': user_data.get('total_size', 0) + size,
                    'stats': stats
                })
                
                # Log download
                await self.stats_manager.log_download(
                    user_id=user_id,
                    video_info=video_info,
                    quality=quality,
                    format=format,
                    size=size
                )
                
                # Add XP
                xp = size // (1024 * 1024)  # 1 XP per MB
                await self.user_manager.add_xp(user_id, max(1, xp))
                
                # Check achievements
                await self.user_manager.check_achievements(user_id)
                
                # Send file
                caption = (
                    f"✅ *Download Complete!*\n\n"
                    f"🎬 {self.escape_markdown(video_info.get('title', '')[:100])}\n"
                    f"⚡ Quality: {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}\n"
                    f"📁 Format: {DOWNLOAD_FORMATS[format]['emoji']} {DOWNLOAD_FORMATS[format]['name']}\n"
                    f"📦 Size: {self.format_size(size)}\n"
                    f"⏱ Duration: {self.format_time(video_info.get('duration', 0))}\n\n"
                    f"Thanks for using the bot! ❤️"
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
                
                # Delete file
                Path(file).unlink()
                await progress_msg.delete()
                
            else:
                await progress_msg.edit_text(f"❌ Download failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            await self.stats_manager.log_error('download_error', str(e), user_id)
            await progress_msg.edit_text(f"❌ Download error: {str(e)[:200]}")
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show favorites"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        favorites = user_data.get('favorites', [])
        
        if not favorites:
            await query.edit_message_text(
                "⭐ *Favorites*\n\nNo videos in favorites yet.\n\nAdd videos to favorites by clicking the ⭐ button while watching any video.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        text = "⭐ *Favorites*\n\n"
        keyboard = []
        
        for i, fav in enumerate(reversed(favorites[-10:]), 1):
            title = fav.get('title', '')[:50]
            duration = self.format_time(fav.get('duration', 0))
            platform = fav.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {self.escape_markdown(title)} - {duration}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"fav_{fav['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_watch_later(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show watch later"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        watch_later = user_data.get('watch_later', [])
        
        if not watch_later:
            await query.edit_message_text(
                "⏰ *Watch Later*\n\nNo videos in watch later.\n\nAdd videos by clicking the ⏰ button while watching any video.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        text = "⏰ *Watch Later*\n\n"
        keyboard = []
        
        for i, item in enumerate(reversed(watch_later[-10:]), 1):
            title = item.get('title', '')[:50]
            duration = self.format_time(item.get('duration', 0))
            platform = item.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {self.escape_markdown(title)} - {duration}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"wl_{item['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show history"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        history = user_data.get('history', [])[-20:]
        
        if not history:
            await query.edit_message_text(
                "📜 *History*\n\nNo history yet.\n\nWatch or download videos to see them here.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        text = "📜 *Last 20 Activities*\n\n"
        keyboard = []
        
        for i, item in enumerate(reversed(history), 1):
            date = item.get('date', '')[:10]
            title = item.get('title', '')[:40]
            platform = item.get('platform', 'youtube')
            emoji = SUPPORTED_PLATFORMS.get(platform, {}).get('emoji', '🎬')
            
            text += f"{i}. {emoji} {self.escape_markdown(title)}\n   📅 {date}\n\n"
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        
        # Calculate stats
        joined = datetime.fromisoformat(user_data.get('joined_date', datetime.now().isoformat()))
        days_active = (datetime.now() - joined).days
        
        downloads = user_data.get('download_count', 0)
        total_size = user_data.get('total_size', 0)
        favorites = len(user_data.get('favorites', []))
        watch_later = len(user_data.get('watch_later', []))
        history = len(user_data.get('history', []))
        
        stats = user_data.get('stats', {})
        videos_downloaded = stats.get('videos_downloaded', 0)
        audio_downloaded = stats.get('audio_downloaded', 0)
        searches = stats.get('searches_performed', 0)
        streak = stats.get('streak_days', 0)
        
        level = user_data.get('level', 1)
        xp = user_data.get('xp', 0)
        next_xp = user_data.get('next_level_xp', 100)
        xp_progress = (xp / next_xp) * 100 if next_xp > 0 else 0
        progress_bar = self.create_progress_bar(xp_progress)
        
        stats_text = f"""
📊 *Your Statistics*

👤 *User:* {self.escape_markdown(user_data.get('first_name', 'Unknown'))}
📅 *Member for:* {days_active} days
⭐ *Level:* {level} {progress_bar} {xp}/{next_xp} XP

📥 *Downloads:*
• Total: {downloads:,}
• Videos: {videos_downloaded:,}
• Audio: {audio_downloaded:,}
• Size: {self.format_size(total_size)}

🎬 *Content:*
• Favorites: {favorites}
• Watch Later: {watch_later}
• History: {history}
• Searches: {searches}

🔥 *Streak:* {streak} days
🏆 *Achievements:* {len(user_data.get('achievements', []))}
🎖️ *Badges:* {len(user_data.get('badges', []))}

⚙️ *Settings:*
• Quality: {VIDEO_QUALITIES.get(user_data.get('settings', {}).get('default_quality', 'best'), {}).get('name', 'Best')}
• Format: {DOWNLOAD_FORMATS.get(user_data.get('settings', {}).get('default_format', 'mp4'), {}).get('name', 'MP4')}
• Auto Delete: {'✅' if user_data.get('settings', {}).get('auto_delete', True) else '❌'}
        """
        
        keyboard = [
            [InlineKeyboardButton("📥 Download History", callback_data="history")],
            [InlineKeyboardButton("🏆 Achievements", callback_data="achievements")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        settings = user_data.get('settings', {})
        
        settings_text = f"""
⚙️ *Settings*

🔰 *Current Settings:*

🎬 *Default Quality:* {VIDEO_QUALITIES.get(settings.get('default_quality', 'best'), {}).get('name', 'Best')}
📁 *Default Format:* {DOWNLOAD_FORMATS.get(settings.get('default_format', 'mp4'), {}).get('name', 'MP4')}
🗑 *Auto Delete:* {'✅' if settings.get('auto_delete', True) else '❌'}
🔔 *Notifications:* {'✅' if settings.get('notifications', True) else '❌'}
🌙 *Dark Mode:* {'✅' if settings.get('dark_mode', True) else '❌'}
📝 *Save History:* {'✅' if settings.get('save_history', True) else '❌'}
🎯 *Max Quality:* {settings.get('max_quality', '1080p')}
🎥 *Preferred Codec:* {settings.get('preferred_codec', 'h264')}

👇 *Choose setting to modify:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 Default Quality", callback_data="set_default_quality")],
            [InlineKeyboardButton("📁 Default Format", callback_data="set_default_format")],
            [InlineKeyboardButton("🗑 Auto Delete", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton("🔔 Notifications", callback_data="toggle_notifications")],
            [InlineKeyboardButton("🌙 Dark Mode", callback_data="toggle_dark_mode")],
            [InlineKeyboardButton("📝 Save History", callback_data="toggle_save_history")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user profile"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        user_data = await self.user_manager.get_user(user_id)
        
        # Calculate level progress
        level = user_data.get('level', 1)
        xp = user_data.get('xp', 0)
        next_xp = user_data.get('next_level_xp', 100)
        xp_progress = (xp / next_xp) * 100 if next_xp > 0 else 0
        progress_bar = self.create_progress_bar(xp_progress)
        
        # Format badges
        badges = user_data.get('badges', [])
        badge_emojis = {
            'new': '🆕',
            'veteran': '⚔️',
            'expert': '🏆',
            'legend': '👑',
            'downloader': '📥',
            'favorite': '⭐',
            'social': '👥',
            'premium': '💎',
            'level_up': '📈',
            'streak': '🔥'
        }
        badges_text = ' '.join([badge_emojis.get(b, '🎖️') for b in badges]) if badges else 'No badges yet'
        
        profile_text = f"""
👤 *Profile*

🆔 *ID:* `{user_id}`
📛 *Name:* {self.escape_markdown(user_data.get('first_name', 'Unknown'))}
🔰 *Username:* @{user_data.get('username', 'None')}

⭐ *Level:* {level}
📊 *XP:* {xp}/{next_xp}
📈 *Progress:* {progress_bar} {xp_progress:.1f}%

🏅 *Badges:* {badges_text}

📊 *Stats:*
• Downloads: {user_data.get('download_count', 0)}
• Favorites: {len(user_data.get('favorites', []))}
• Watch Later: {len(user_data.get('watch_later', []))}
• Streak: {user_data.get('stats', {}).get('streak_days', 0)} days

🔗 *Referral Code:* `{user_data.get('referral_code', '')}`
👥 *Referrals:* {len(user_data.get('referrals', []))}

📅 *Joined:* {user_data.get('joined_date', '')[:10]}
        """
        
        keyboard = [
            [InlineKeyboardButton("🏆 Achievements", callback_data="achievements")],
            [InlineKeyboardButton("📊 Advanced Stats", callback_data="advanced_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            profile_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu"""
        query = update.callback_query
        await query.answer()
        
        help_text = f"""
❓ *Help*

📥 *Download Videos:*
• Send a video link directly
• Choose quality and format
• Wait for download
• Get your video

🔍 *Search Videos:*
• Type any keyword
• Browse results with thumbnails
• Choose video to watch/download

🔥 *Browse Videos:*
• Use browse menu
• Choose category
• Browse videos with navigation
• Watch or download

⭐ *Favorites:*
• Add videos to favorites
• Access them anytime
• Organize your collection

⏰ *Watch Later:*
• Save videos to watch later
• Never miss important videos
• Manage your watchlist

📊 *Statistics:*
• Track your activity
• See download counts
• Monitor your progress

⚙️ *Settings:*
• Customize bot behavior
• Set default quality
• Configure notifications

👤 *Profile:*
• View your information
• Check achievements
• See your badges

🌐 *Supported Platforms:*
{', '.join([f"{p['emoji']} {p['name']}" for p in list(SUPPORTED_PLATFORMS.values())[:10]])}
And many more...

📌 *Support:* @YourSupport
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show about info"""
        query = update.callback_query
        await query.answer()
        
        # Get global stats
        stats = await self.stats_manager.get_detailed_stats()
        
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        about_text = f"""
ℹ️ *About*

🤖 *Name:* Professional Video Downloader Bot
📊 *Version:* {BOT_VERSION}
📅 *Release:* {BOT_RELEASE_DATE}
👨‍💻 *Developer:* @YourUsername
📦 *Platform:* Python + Telegram Bot API

✨ *Features:*
• {len(SUPPORTED_PLATFORMS)}+ platforms supported
• {len(VIDEO_QUALITIES)} quality options (up to 8K)
• {len(DOWNLOAD_FORMATS)} format options
• {len(VIDEO_CATEGORIES)} browse categories
• Achievements & badges system
• Referral & rewards system
• Advanced statistics
• Personal profiles
• Daily streaks
• XP & leveling system

📊 *Global Statistics:*
👥 Users: {stats['total_users']:,}
📥 Downloads: {stats['total_downloads']:,}
📦 Total Size: {self.format_size(stats['total_size'])}
⭐ Premium Users: {stats['premium_users']}
🔥 Active Today: {stats['active_today']}

⏰ *Uptime:* {days}d {hours:02d}:{minutes:02d}

❤️ *Thank you for using the bot!*
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        
        await query.edit_message_text(
            about_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ========== Callback Handler ==========
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callbacks"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        # Main menu
        if data == "main_menu":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "search":
            await query.edit_message_text(
                "🔍 *Search*\n\nSend your search query now:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data == "download":
            await query.edit_message_text(
                "📥 *Download*\n\nSend a video link now:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
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
            await self.show_settings(update, context)
        
        elif data == "profile":
            await self.show_profile(update, context)
        
        elif data == "help":
            await self.show_help(update, context)
        
        elif data == "about":
            await self.show_about(update, context)
        
        # Browse categories
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
        
        # Search navigation
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
        
        # Download menu
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
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            # Save URL in session
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id]['temp_url'] = url
            # Get video info first
            await self.handle_url(update, context, url)
        
        # Favorites and watch later
        elif data.startswith("fav_"):
            url = data.replace("fav_", "")
            video_info = {'webpage_url': url, 'title': 'Video', 'extractor': 'youtube'}
            added = await self.user_manager.add_to_favorites(user_id, video_info)
            if added:
                await query.answer("✅ Added to favorites!")
            else:
                await query.answer("❌ Already in favorites or limit reached")
        
        elif data.startswith("wl_"):
            url = data.replace("wl_", "")
            video_info = {'webpage_url': url, 'title': 'Video', 'extractor': 'youtube'}
            added = await self.user_manager.add_to_watch_later(user_id, video_info)
            if added:
                await query.answer("✅ Added to watch later!")
            else:
                await query.answer("❌ Already in watch later or limit reached")
        
        elif data == "add_favorite":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                added = await self.user_manager.add_to_favorites(user_id, video_info)
                if added:
                    await query.answer("✅ Added to favorites!")
                    await self.user_manager.add_xp(user_id, 5)
                else:
                    await query.answer("❌ Already in favorites")
        
        elif data == "add_watchlater":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                added = await self.user_manager.add_to_watch_later(user_id, video_info)
                if added:
                    await query.answer("✅ Added to watch later!")
                    await self.user_manager.add_xp(user_id, 3)
                else:
                    await query.answer("❌ Already in watch later")
        
        # Settings
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
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings")])
            
            await query.edit_message_text(
                "🎬 *Choose Default Quality:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("save_quality_"):
            quality = data.replace("save_quality_", "")
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            settings['default_quality'] = quality
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ Default quality set to {VIDEO_QUALITIES[quality]['name']}")
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
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings")])
            
            await query.edit_message_text(
                "📁 *Choose Default Format:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("save_format_"):
            format = data.replace("save_format_", "")
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            settings['default_format'] = format
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ Default format set to {DOWNLOAD_FORMATS[format]['name']}")
            await self.show_settings(update, context)
        
        elif data == "toggle_auto_delete":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('auto_delete', True)
            settings['auto_delete'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ Auto delete {'enabled' if not current else 'disabled'}")
            await self.show_settings(update, context)
        
        elif data == "toggle_notifications":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('notifications', True)
            settings['notifications'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ Notifications {'enabled' if not current else 'disabled'}")
            await self.show_settings(update, context)
        
        elif data == "toggle_dark_mode":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('dark_mode', True)
            settings['dark_mode'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ Dark mode {'enabled' if not current else 'disabled'}")
            await self.show_settings(update, context)
        
        elif data == "toggle_save_history":
            user_data = await self.user_manager.get_user(user_id)
            settings = user_data.get('settings', {})
            current = settings.get('save_history', True)
            settings['save_history'] = not current
            await self.user_manager.update_user(user_id, {'settings': settings})
            await query.answer(f"✅ Save history {'enabled' if not current else 'disabled'}")
            await self.show_settings(update, context)
        
        # Info buttons
        elif data == "more_info":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                text = f"""
ℹ️ *Additional Information*

📹 *Full Title:* {self.escape_markdown(video_info.get('title', ''))}
👤 *Uploader:* {self.escape_markdown(video_info.get('uploader', ''))}
🆔 *Uploader ID:* {video_info.get('uploader_id', '')}
📅 *Upload Date:* {video_info.get('upload_date', 'Unknown')}
🔗 *Channel URL:* {video_info.get('uploader_url', 'N/A')}
🎵 *Audio:* {'✅' if video_info.get('acodec') != 'none' else '❌'}
🖼 *Resolution:* {video_info.get('resolution', 'Unknown')}
⚡ *FPS:* {video_info.get('fps', 'Unknown')}
🔊 *Audio Bitrate:* {video_info.get('abr', 'Unknown')} kbps
🎥 *Video Codec:* {video_info.get('vcodec', 'Unknown')}
🎧 *Audio Codec:* {video_info.get('acodec', 'Unknown')}
📦 *Approx Size:* {self.format_size(video_info.get('filesize', 0))}
🌐 *Platform:* {video_info.get('extractor', 'Unknown')}
🔞 *Age Limit:* {video_info.get('age_limit', 0)}+

📊 *Advanced Stats:*
👍 Likes: {self.format_number(video_info.get('like_count', 0))}
👎 Dislikes: {self.format_number(video_info.get('dislike_count', 0))}
👁 Views: {self.format_number(video_info.get('view_count', 0))}
💬 Comments: {self.format_number(video_info.get('comment_count', 0))}
⭐ Rating: {video_info.get('average_rating', 0):.1f}/5

🏷 *Categories:* {', '.join(video_info.get('categories', ['None']))[:100]}
🔖 *Tags:* {', '.join(video_info.get('tags', ['None']))[:100]}
                """
                
                await query.edit_message_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="back_to_video")
                    ]])
                )
        
        elif data == "available_qualities":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            formats = video_info.get('formats', [])
            
            if formats:
                qualities = set()
                for f in formats:
                    if f.get('height'):
                        qualities.add(f"{f['height']}p")
                
                text = "🔄 *Available Qualities:*\n\n"
                for q in sorted(qualities, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0):
                    text += f"• {q}\n"
                
                await query.answer(f"Qualities: {', '.join(sorted(qualities, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0))[:50]}")
            else:
                await query.answer("No quality information available")
        
        elif data == "page_info":
            await query.answer("Use navigation buttons to browse videos")
        
        elif data == "achievements":
            user_data = await self.user_manager.get_user(user_id)
            achievements = user_data.get('achievements', [])
            
            if not achievements:
                text = "🏆 *Achievements*\n\nNo achievements yet. Keep using the bot to unlock them!"
            else:
                text = "🏆 *Achievements*\n\n"
                for i, ach in enumerate(achievements, 1):
                    text += f"{i}. {ach}\n"
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="profile")
                ]])
            )
        
        elif data == "advanced_stats":
            # Get detailed stats
            stats = await self.stats_manager.get_detailed_stats()
            
            text = f"""
📊 *Advanced Statistics*

📈 *Platform Usage:*
{chr(10).join([f"• {p}: {c}" for p, c in stats['top_platforms'][:5]])}

🎬 *Quality Preferences:*
{chr(10).join([f"• {q}: {c}" for q, c in stats['top_qualities'][:5]])}

📁 *Format Preferences:*
{chr(10).join([f"• {f}: {c}" for f, c in stats['top_formats'][:5]])}

⏰ *Peak Hour:* {stats['peak_hour']}:00
📊 *Today's Downloads:* {stats['today_downloads']}
📦 *Today's Size:* {self.format_size(stats['today_size'])}
            """
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="profile")
                ]])
            )
        
        else:
            await query.answer("Unknown action")
    
    async def show_video_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video_info: Dict):
        """Show video info"""
        query = update.callback_query
        
        platform = self.get_platform_info(video_info.get('webpage_url', ''))
        
        text = f"""
{platform['emoji']} *Video Information*

📹 *Title:* {self.escape_markdown(video_info.get('title', '')[:200])}
⏱ *Duration:* {self.format_time(video_info.get('duration', 0))}
📊 *Platform:* {platform['emoji']} {platform['name']}
👤 *Uploader:* {self.escape_markdown(video_info.get('uploader', ''))}
👁 *Views:* {self.format_number(video_info.get('view_count', 0))}
👍 *Likes:* {self.format_number(video_info.get('like_count', 0))}

🔗 *Watch Link:*
[Click here to watch]({video_info.get('webpage_url', '')})

📥 *To download:* Use the buttons below
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ Watch", url=video_info.get('webpage_url', '')),
                InlineKeyboardButton("📥 Download", callback_data="download_menu")
            ],
            [
                InlineKeyboardButton("⭐ Favorite", callback_data="add_favorite"),
                InlineKeyboardButton("⏰ Watch Later", callback_data="add_watchlater")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
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
    
    # ========== Error Handler ==========
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        error = context.error
        logger.error(f"Error: {error}")
        
        # Log to error file
        error_logger.error(f"Update: {update}\nError: {error}\n{traceback.format_exc()}")
        
        # Store in stats
        if update and update.effective_user:
            await self.stats_manager.log_error(
                'bot_error',
                str(error)[:200],
                update.effective_user.id
            )
        
        # Notify user
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An unexpected error occurred. Please try again later.\n\n"
                    "If the problem persists, contact support @YourSupport"
                )
        except:
            pass
    
    # ========== Run Bot ==========
    
    def run(self):
        """Run the bot"""
        try:
            # Create application
            app = Application.builder().token(BOT_TOKEN).build()
            
            # Add command handlers
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
            
            # Message handler
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Callback handler
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # Error handler
            app.add_error_handler(self.error_handler)
            
            # Print startup message
            print("=" * 70)
            print(f"🚀 Video Downloader Bot v{BOT_VERSION}")
            print("=" * 70)
            print(f"✅ Bot started successfully!")
            print(f"👥 Users: {len(self.db.data.get(str(USERS_DB), {}))}")
            print(f"📁 Directories: DOWNLOAD, THUMBNAIL, LOGS, DATABASE")
            print(f"⚡ Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 70)
            print("📌 Features:")
            print("   • 20+ platforms supported")
            print("   • 9 quality options (up to 8K)")
            print("   • 14 format options")
            print("   • 20 browse categories")
            print("   • Achievements & badges")
            print("   • Referral system")
            print("   • XP & leveling")
            print("   • Daily streaks")
            print("=" * 70)
            
            # Run bot
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            logger.error(f"Startup error: {e}")
            traceback.print_exc()

# ==================== MAIN ====================

if __name__ == "__main__":
    # Create and run bot
    bot = VideoDownloaderBot()
    bot.run()
