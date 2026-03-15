#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي المضمون
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
import aiofiles
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
import signal
import gc
import psutil

import yt_dlp
import requests
from cryptography.fernet import Fernet
from dotenv import load_dotenv

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

# ==================== LOAD ENVIRONMENT VARIABLES ====================
load_dotenv()

# ==================== CONFIGURATION ====================

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "7536390168:AAHZNO7XjIRBpwhMf3O5RojM9f2RrPYzUZ4")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
BOT_VERSION = "5.0.0"

# Directory Structure
BASE_DIR = Path(__file__).parent.absolute()
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_DIR = BASE_DIR / "database"
TEMP_DIR = BASE_DIR / "temp"

# Create all directories
for directory in [DOWNLOAD_DIR, LOGS_DIR, DATABASE_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Files
USERS_DB = DATABASE_DIR / "users.json"
STATS_DB = DATABASE_DIR / "stats.json"
DOWNLOADS_DB = DATABASE_DIR / "downloads.json"

# Logging Configuration
LOG_FILE = LOGS_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Limits
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2 GB
MAX_DURATION = 43200  # 12 hours
MAX_SEARCH_RESULTS = 10
MAX_HISTORY_ITEMS = 100
CONCURRENT_DOWNLOADS = 3

# Conversation States
MAIN_MENU, BROWSE_MENU, SEARCH_MENU, DOWNLOAD_MENU, QUALITY_SELECTION, FORMAT_SELECTION = range(6)

# ==================== VIDEO QUALITIES ====================

VIDEO_QUALITIES = {
    '144': {'name': '144p', 'name_ar': '١٤٤ بكسل', 'emoji': '📱'},
    '240': {'name': '240p', 'name_ar': '٢٤٠ بكسل', 'emoji': '📱'},
    '360': {'name': '360p', 'name_ar': '٣٦٠ بكسل', 'emoji': '📺'},
    '480': {'name': '480p', 'name_ar': '٤٨٠ بكسل', 'emoji': '📺'},
    '720': {'name': '720p HD', 'name_ar': '٧٢٠ بكسل', 'emoji': '🎬'},
    '1080': {'name': '1080p FHD', 'name_ar': '١٠٨٠ بكسل', 'emoji': '🎥'},
    'best': {'name': 'Best Quality', 'name_ar': 'أفضل جودة', 'emoji': '🏆'}
}

# ==================== DOWNLOAD FORMATS ====================

DOWNLOAD_FORMATS = {
    'mp4': {'name': 'MP4', 'name_ar': 'إم بي ٤', 'emoji': '🎬'},
    'mp3': {'name': 'MP3 Audio', 'name_ar': 'إم بي ٣', 'emoji': '🎵'}
}

# ==================== VIDEO CATEGORIES ====================

VIDEO_CATEGORIES = {
    'trending': {'name': '🔥 Trending', 'name_ar': 'الأكثر مشاهدة', 'query': 'trending'},
    'music': {'name': '🎵 Music', 'name_ar': 'موسيقى', 'query': 'music'},
    'gaming': {'name': '🎮 Gaming', 'name_ar': 'ألعاب', 'query': 'gaming'},
    'news': {'name': '📰 News', 'name_ar': 'أخبار', 'query': 'news'},
    'sports': {'name': '⚽ Sports', 'name_ar': 'رياضة', 'query': 'sports'},
    'education': {'name': '📚 Education', 'name_ar': 'تعليم', 'query': 'educational'}
}

# ==================== DATABASE MANAGER ====================

class DatabaseManager:
    def __init__(self):
        self.data = {}
        self.locks = defaultdict(asyncio.Lock)
        self.load_all()
    
    def load_all(self):
        for file_path in [USERS_DB, STATS_DB, DOWNLOADS_DB]:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.data[str(file_path)] = json.load(f)
                except:
                    self.data[str(file_path)] = {}
            else:
                self.data[str(file_path)] = {}
    
    async def save(self, file_path: Path):
        async with self.locks[str(file_path)]:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data.get(str(file_path), {}), f, ensure_ascii=False, indent=2, default=str)
    
    async def get(self, file_path: Path, key: str = None, default: Any = None) -> Any:
        data = self.data.get(str(file_path), {})
        if key is None:
            return data
        return data.get(key, default)
    
    async def set(self, file_path: Path, key: str, value: Any):
        if str(file_path) not in self.data:
            self.data[str(file_path)] = {}
        self.data[str(file_path)][key] = value
        await self.save(file_path)
    
    async def update(self, file_path: Path, key: str, updates: Dict):
        current = await self.get(file_path, key, {})
        if isinstance(current, dict):
            current.update(updates)
            await self.set(file_path, key, current)

# ==================== USER MANAGER ====================

class UserManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.cache = {}
        self.cache_ttl = 300
    
    async def get_user(self, user_id: int) -> Dict:
        user_id = str(user_id)
        
        if user_id in self.cache:
            cache_time, data = self.cache[user_id]
            if time.time() - cache_time < self.cache_ttl:
                return data
        
        user_data = await self.db.get(USERS_DB, user_id, {})
        
        if not user_data:
            user_data = {
                'user_id': user_id,
                'joined_date': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'download_count': 0,
                'total_size': 0,
                'favorites': [],
                'watch_later': [],
                'history': [],
                'settings': {
                    'default_quality': 'best',
                    'default_format': 'mp4',
                    'auto_delete': True,
                    'save_history': True
                }
            }
            await self.db.set(USERS_DB, user_id, user_data)
        
        self.cache[user_id] = (time.time(), user_data)
        return user_data
    
    async def update_user(self, user_id: int, updates: Dict):
        user_id = str(user_id)
        await self.db.update(USERS_DB, user_id, updates)
        
        if user_id in self.cache:
            cache_time, data = self.cache[user_id]
            data.update(updates)
            self.cache[user_id] = (time.time(), data)
    
    async def add_to_history(self, user_id: int, video_info: Dict):
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
            'duration': video_info.get('duration', 0)
        })
        
        if len(history) > MAX_HISTORY_ITEMS:
            history = history[-MAX_HISTORY_ITEMS:]
        
        await self.update_user(user_id, {'history': history})
    
    async def add_to_favorites(self, user_id: int, video_info: Dict) -> bool:
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        favorites = user_data.get('favorites', [])
        url = video_info.get('webpage_url', '')
        
        if not any(f.get('url') == url for f in favorites):
            favorites.append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0)
            })
            await self.update_user(user_id, {'favorites': favorites})
            return True
        return False
    
    async def add_to_watch_later(self, user_id: int, video_info: Dict) -> bool:
        user_id = str(user_id)
        user_data = await self.get_user(user_id)
        
        watch_later = user_data.get('watch_later', [])
        url = video_info.get('webpage_url', '')
        
        if not any(w.get('url') == url for w in watch_later):
            watch_later.append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': url,
                'platform': video_info.get('extractor', 'Unknown'),
                'duration': video_info.get('duration', 0)
            })
            await self.update_user(user_id, {'watch_later': watch_later})
            return True
        return False

# ==================== STATS MANAGER ====================

class StatsManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def log_download(self, user_id: int, video_info: Dict, quality: str, format: str, size: int):
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
            'duration': video_info.get('duration', 0)
        }
        
        await self.db.set(DOWNLOADS_DB, download_id, download_data)
        
        stats = await self.db.get(STATS_DB, 'global', {})
        stats['total_downloads'] = stats.get('total_downloads', 0) + 1
        stats['total_size'] = stats.get('total_size', 0) + size
        stats['last_updated'] = datetime.now().isoformat()
        await self.db.set(STATS_DB, 'global', stats)

# ==================== VIDEO PROCESSOR ====================

class VideoProcessor:
    def __init__(self, stats_manager: StatsManager):
        self.stats_manager = stats_manager
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.download_semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'socket_timeout': 30,
            'retries': 3
        }
    
    async def get_video_info(self, url: str, user_id: int = None) -> Optional[Dict]:
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    self.executor,
                    lambda: ydl.extract_info(url, download=False)
                )
                
                if not info:
                    return None
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'webpage_url': info.get('webpage_url', url),
                    'extractor': info.get('extractor', 'unknown')
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    async def search_videos(self, query: str, limit: int = 5) -> List[Dict]:
        try:
            loop = asyncio.get_event_loop()
            search_opts = {**self.ydl_opts, 'extract_flat': True}
            
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                results = await loop.run_in_executor(
                    self.executor,
                    lambda: ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                )
                
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
                                'channel': entry.get('uploader', 'Unknown')
                            })
                return videos
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def download_video(self, url: str, quality: str = 'best', format: str = 'mp4', 
                            user_id: int = None, progress_callback=None) -> Optional[Dict]:
        async with self.download_semaphore:
            try:
                if quality == 'best':
                    format_spec = 'best[ext=mp4]/best' if format != 'mp3' else 'bestaudio/best'
                else:
                    height = int(quality) if quality.isdigit() else 720
                    format_spec = f'best[height<={height}][ext=mp4]/best' if format != 'mp3' else 'bestaudio/best'
                
                filename = DOWNLOAD_DIR / f"video_{int(time.time())}_{random.randint(1000,9999)}.%(ext)s"
                
                ydl_opts = {
                    **self.ydl_opts,
                    'format': format_spec,
                    'outtmpl': str(filename),
                    'progress_hooks': [progress_callback] if progress_callback else []
                }
                
                if format == 'mp3':
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                
                loop = asyncio.get_event_loop()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await loop.run_in_executor(
                        self.executor,
                        lambda: ydl.extract_info(url, download=True)
                    )
                    
                    file = ydl.prepare_filename(info)
                    
                    if format == 'mp3':
                        file = str(file).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                    else:
                        for ext in ['.mp4', '.webm']:
                            test_file = str(file).replace('%(ext)s', ext)
                            if Path(test_file).exists():
                                file = test_file
                                break
                    
                    if Path(file).exists():
                        size = Path(file).stat().st_size
                        return {
                            'success': True,
                            'file': file,
                            'size': size,
                            'title': info.get('title', 'Video'),
                            'duration': info.get('duration', 0)
                        }
                    
                    return {'success': False, 'error': 'File not found'}
                    
            except Exception as e:
                logger.error(f"Download error: {e}")
                return {'success': False, 'error': str(e)}

# ==================== BOT CLASS ====================

class VideoDownloaderBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.stats_manager = StatsManager(self.db)
        self.user_manager = UserManager(self.db)
        self.video_processor = VideoProcessor(self.stats_manager)
        self.user_sessions = {}
        self.start_time = datetime.now()
        self.check_ffmpeg()
        
        logger.info("=" * 60)
        logger.info(f"Bot initialized - Version {BOT_VERSION}")
        logger.info("=" * 60)
    
    def check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            logger.info("FFmpeg is installed")
        except:
            logger.warning("FFmpeg not found - MP3 conversion may not work")
    
    def format_time(self, seconds: int) -> str:
        if not seconds:
            return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    
    def format_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def format_number(self, number: int) -> str:
        if number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        if number >= 1_000:
            return f"{number/1_000:.1f}K"
        return str(number)
    
    def create_progress_bar(self, percentage: float, width: int = 10) -> str:
        filled = int(width * percentage / 100)
        return '█' * filled + '░' * (width - filled)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.user_manager.get_user(user.id)
        
        welcome_text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات الاحترافي 🤖

📥 *أرسل لي رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات:*
• تحميل من يوتيوب، انستغرام، فيسبوك، تيك توك، تويتر
• اختيار الجودة (144p - 1080p)
• تحميل فيديو أو صوت MP3
• بحث سريع مع صور مصغرة
• تصفح الفئات المختلفة
• مفضلة ومشاهدة لاحقاً
• إحصائيات شخصية

⚡ *الأوامر:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/help - المساعدة

👇 *اختر ما تريد:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح", callback_data="browse")],
            [InlineKeyboardButton("🔍 بحث", callback_data="search"),
             InlineKeyboardButton("❓ مساعدة", callback_data="help")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
❓ *المساعدة*

📥 *لتحميل فيديو:*
• أرسل الرابط مباشرة
• اختر الجودة
• اختر الصيغة
• انتظر التحميل

🔍 *للبحث:*
• اكتب أي كلمة
• اختر من النتائج
• حمله أو شاهده

🔥 *للتصفح:*
• استخدم /browse
• اختر الفئة
• تصفح الفيديوهات

🌐 *المنصات المدعومة:*
• يوتيوب 📺
• انستغرام 📷
• فيسبوك 📘
• تويتر 🐦
• تيك توك 🎵

⚡ *الأوامر:*
/start - الرئيسية
/browse - تصفح
/help - المساعدة
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for cat_id, cat_info in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(
                cat_info['name_ar'],
                callback_data=f"cat_{cat_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🔥 *اختر الفئة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("🔍 جاري البحث...")
        
        videos = await self.video_processor.search_videos(VIDEO_CATEGORIES[category]['query'], limit=5)
        
        if not videos:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="browse")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        self.user_sessions[user_id]['browse'] = {
            'videos': videos,
            'page': 0
        }
        
        await self.show_video(update, context, videos[0], 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video: Dict, index: int):
        query = update.callback_query
        user_id = update.effective_user.id
        
        text = f"""
🎬 *{video['title'][:100]}*

📺 *القناة:* {video.get('channel', 'غير معروف')}
⏱ *المدة:* {self.format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ]
        ]
        
        videos = self.user_sessions.get(user_id, {}).get('browse', {}).get('videos', [])
        nav_buttons = []
        
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="nav_prev"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data="nav_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="browse")])
        
        try:
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=user_id,
                photo=video['thumbnail'],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("⏳ جاري المعالجة...")
        user_id = update.effective_user.id
        
        info = await self.video_processor.get_video_info(url, user_id)
        
        if not info:
            await msg.edit_text("❌ تعذر الحصول على معلومات الفيديو")
            return
        
        self.user_sessions[user_id] = {'current_video': info}
        await self.user_manager.add_to_history(user_id, info)
        
        text = f"""
📹 *معلومات الفيديو*

🎬 *العنوان:* {info['title'][:100]}
👤 *الرافع:* {info['uploader']}
⏱ *المدة:* {self.format_time(info['duration'])}
👁 *المشاهدات:* {self.format_number(info['view_count'])}

🔗 [شاهد على يوتيوب]({info['webpage_url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=info['webpage_url']),
                InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
            ],
            [
                InlineKeyboardButton("⭐ مفضلة", callback_data="add_favorite"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="add_watchlater")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        try:
            await msg.delete()
            await update.message.reply_photo(
                photo=info['thumbnail'],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            await msg.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        user_id = update.effective_user.id
        
        videos = await self.video_processor.search_videos(query, limit=5)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.user_sessions[user_id] = {'search_results': videos, 'search_page': 0}
        await self.show_search_result(update, context, videos[0], 0)
        await msg.delete()
    
    async def show_search_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video: Dict, index: int):
        query = update.callback_query
        user_id = update.effective_user.id
        
        text = f"""
🔍 *نتيجة {index + 1}*

🎬 *{video['title'][:100]}*

📺 *القناة:* {video.get('channel', 'غير معروف')}
⏱ *المدة:* {self.format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        videos = self.user_sessions.get(user_id, {}).get('search_results', [])
        keyboard = []
        
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="search_prev"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data="search_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
            InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
        ])
        
        try:
            if query:
                await query.message.delete()
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=video['thumbnail'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_photo(
                    photo=video['thumbnail'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
        except:
            if query:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        video = self.user_sessions.get(update.effective_user.id, {}).get('current_video', {})
        
        if not video:
            await query.edit_message_text(
                "❌ لا توجد معلومات فيديو",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        keyboard = []
        for q_id, q_info in VIDEO_QUALITIES.items():
            keyboard.append([InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name_ar']}",
                callback_data=f"quality_{q_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            "📥 *اختر الجودة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for f_id, f_info in DOWNLOAD_FORMATS.items():
            keyboard.append([InlineKeyboardButton(
                f"{f_info['emoji']} {f_info['name_ar']}",
                callback_data=f"format_{quality}_{f_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="download_menu")])
        
        await query.edit_message_text(
            f"📥 *اختر الصيغة:*\n\nالجودة: {VIDEO_QUALITIES[quality]['name_ar']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, format: str):
        query = update.callback_query
        user_id = update.effective_user.id
        
        video = self.user_sessions.get(user_id, {}).get('current_video', {})
        url = video.get('webpage_url', '')
        title = video.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text("❌ لا يوجد رابط")
            return
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n{title[:50]}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percentage = (downloaded / total) * 100
                    if int(percentage) % 25 == 0:
                        progress_bar = self.create_progress_bar(percentage)
                        text = f"⬇️ *التحميل:* {progress_bar} {percentage:.1f}%"
                        asyncio.create_task(query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN))
        
        result = await self.video_processor.download_video(url, quality, format, user_id, progress_hook)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=f"✅ تم التحميل بنجاح!\n📦 الحجم: {self.format_size(result['size'])}",
                        title=title[:100],
                        duration=result['duration']
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=f"✅ تم التحميل بنجاح!\n📦 الحجم: {self.format_size(result['size'])}",
                        supports_streaming=True
                    )
            
            Path(result['file']).unlink()
            
            # Update stats
            await self.user_manager.update_user(user_id, {
                'download_count': (await self.user_manager.get_user(user_id)).get('download_count', 0) + 1,
                'total_size': (await self.user_manager.get_user(user_id)).get('total_size', 0) + result['size']
            })
            await self.stats_manager.log_download(user_id, video, quality, format, result['size'])
            
            await query.delete()
        else:
            await query.edit_message_text(f"❌ فشل التحميل")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        if data == "main_menu":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "search":
            await query.edit_message_text(
                "🔍 *بحث*\n\nأرسل كلمة البحث:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "help":
            await self.help_command(update, context)
        
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
        
        elif data == "download_menu":
            await self.download_menu(update, context)
        
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            await self.select_quality(update, context, quality)
        
        elif data.startswith("format_"):
            parts = data.replace("format_", "").split("_")
            quality = parts[0]
            fmt = parts[1]
            await self.start_download(update, context, quality, fmt)
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.handle_url(update, context, url)
        
        elif data == "add_favorite":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                added = await self.user_manager.add_to_favorites(user_id, video_info)
                await query.answer("✅ أضيف للمفضلة" if added else "❌ موجود مسبقاً")
        
        elif data == "add_watchlater":
            video_info = self.user_sessions.get(user_id, {}).get('current_video', {})
            if video_info:
                added = await self.user_manager.add_to_watch_later(user_id, video_info)
                await query.answer("✅ أضيف للمشاهدة لاحقاً" if added else "❌ موجود مسبقاً")
        
        else:
            await query.answer("إجراء غير معروف")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى."
                )
        except:
            pass
    
    def run(self):
        try:
            app = Application.builder().token(BOT_TOKEN).build()
            
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("browse", self.browse))
            app.add_handler(CommandHandler("help", self.help_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            app.add_error_handler(self.error_handler)
            
            print("=" * 50)
            print("🚀 بوت تحميل الفيديوهات - شغال!")
            print("=" * 50)
            print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
            print(f"✅ البوت يعمل على Python {sys.version}")
            print("=" * 50)
            print("📌 أرسل /start في تليجرام للبدء")
            print("=" * 50)
            
            app.run_polling()
            
        except Exception as e:
            print(f"❌ خطأ: {e}")
            traceback.print_exc()

# ==================== MAIN ====================

if __name__ == "__main__":
    bot = VideoDownloaderBot()
    bot.run()
