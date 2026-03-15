#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي المبسط
Version: 3.0.0
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
import hashlib
import html
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import yt_dlp
import requests
from dotenv import load_dotenv
import psutil

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes
)
from telegram.constants import ParseMode

# ==================== LOAD ENVIRONMENT ====================
load_dotenv()

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.getenv("BOT_TOKEN", "7536390168:AAHZNO7XjIRBpwhMf3O5RojM9f2RrPYzUZ4")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
BOT_VERSION = "3.0.0"

# Directory Structure
BASE_DIR = Path(__file__).parent.absolute()
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_DIR = BASE_DIR / "database"

# Create directories
for directory in [DOWNLOAD_DIR, LOGS_DIR, DATABASE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Files
USERS_DB = DATABASE_DIR / "users.json"
STATS_DB = DATABASE_DIR / "stats.json"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOGS_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Limits
MAX_DURATION = 43200  # 12 hours
MAX_SEARCH_RESULTS = 10
MAX_HISTORY_ITEMS = 100

# ==================== VIDEO QUALITIES ====================

VIDEO_QUALITIES = {
    '144': {'name': '144p', 'name_ar': '١٤٤ بكسل', 'emoji': '📱'},
    '240': {'name': '240p', 'name_ar': '٢٤٠ بكسل', 'emoji': '📱'},
    '360': {'name': '360p', 'name_ar': '٣٦٠ بكسل', 'emoji': '📺'},
    '480': {'name': '480p', 'name_ar': '٤٨٠ بكسل', 'emoji': '📺'},
    '720': {'name': '720p HD', 'name_ar': '٧٢٠ بكسل', 'emoji': '🎬'},
    '1080': {'name': '1080p FHD', 'name_ar': '١٠٨٠ بكسل', 'emoji': '🎥'},
    'best': {'name': 'Best', 'name_ar': 'أفضل جودة', 'emoji': '🏆'}
}

# ==================== DOWNLOAD FORMATS ====================

DOWNLOAD_FORMATS = {
    'mp4': {'name': 'MP4', 'name_ar': 'فيديو MP4', 'emoji': '🎬'},
    'mp3': {'name': 'MP3', 'name_ar': 'صوت MP3', 'emoji': '🎵'}
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
        self.load_all()
    
    def load_all(self):
        for file_path in [USERS_DB, STATS_DB]:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.data[str(file_path)] = json.load(f)
                except:
                    self.data[str(file_path)] = {}
            else:
                self.data[str(file_path)] = {}
    
    def save(self, file_path: Path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data.get(str(file_path), {}), f, ensure_ascii=False, indent=2, default=str)
    
    def get(self, file_path: Path, key: str = None, default: Any = None) -> Any:
        data = self.data.get(str(file_path), {})
        if key is None:
            return data
        return data.get(key, default)
    
    def set(self, file_path: Path, key: str, value: Any):
        if str(file_path) not in self.data:
            self.data[str(file_path)] = {}
        self.data[str(file_path)][key] = value
        self.save(file_path)
    
    def update(self, file_path: Path, key: str, updates: Dict):
        current = self.get(file_path, key, {})
        if isinstance(current, dict):
            current.update(updates)
            self.set(file_path, key, current)

# ==================== USER MANAGER ====================

class UserManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def get_user(self, user_id: int) -> Dict:
        user_id = str(user_id)
        user_data = self.db.get(USERS_DB, user_id, {})
        
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
                    'auto_delete': True
                }
            }
            self.db.set(USERS_DB, user_id, user_data)
        
        return user_data
    
    def update_user(self, user_id: int, updates: Dict):
        user_id = str(user_id)
        self.db.update(USERS_DB, user_id, updates)
    
    def add_to_history(self, user_id: int, video_info: Dict):
        user_id = str(user_id)
        user_data = self.get_user(user_id)
        
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
        
        self.update_user(user_id, {'history': history})
    
    def add_to_favorites(self, user_id: int, video_info: Dict) -> bool:
        user_id = str(user_id)
        user_data = self.get_user(user_id)
        
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
            self.update_user(user_id, {'favorites': favorites})
            return True
        return False
    
    def add_to_watch_later(self, user_id: int, video_info: Dict) -> bool:
        user_id = str(user_id)
        user_data = self.get_user(user_id)
        
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
            self.update_user(user_id, {'watch_later': watch_later})
            return True
        return False

# ==================== VIDEO PROCESSOR ====================

class VideoProcessor:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'socket_timeout': 30,
            'retries': 3
        }
    
    def get_video_info(self, url: str) -> Optional[Dict]:
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'webpage_url': info.get('webpage_url', url),
                    'extractor': info.get('extractor', 'unknown')
                }
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    
    def search_videos(self, query: str, limit: int = 5) -> List[Dict]:
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
                                'channel': entry.get('uploader', 'Unknown')
                            })
                return videos
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def download_video(self, url: str, quality: str = 'best', format: str = 'mp4') -> Optional[Dict]:
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
            }
            
            if format == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
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

class VideoBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.user_manager = UserManager(self.db)
        self.video_processor = VideoProcessor()
        self.user_sessions = {}
        self.start_time = datetime.now()
        self.check_ffmpeg()
        
        print("=" * 50)
        print("🚀 بوت تحميل الفيديوهات")
        print("=" * 50)
    
    def check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            print("✅ FFmpeg found")
        except:
            print("⚠️ FFmpeg not found - MP3 conversion may not work")
    
    def format_time(self, seconds: int) -> str:
        if not seconds:
            return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    
    def format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.user_manager.get_user(user.id)
        
        text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات 🚀

📥 *أرسل رابط فيديو للتحميل*
🔍 *أو اكتب كلمة للبحث*

✨ *المميزات:*
• تحميل من يوتيوب، انستغرام، فيسبوك
• اختيار الجودة (144p - 1080p)
• تحميل فيديو أو صوت
• بحث مع صور مصغرة
• مفضلة ومشاهدة لاحقاً

⚡ *الأوامر:*
/start - الرئيسية
/browse - تصفح
/help - المساعدة
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح", callback_data="browse")],
            [InlineKeyboardButton("🔍 بحث", callback_data="search"),
             InlineKeyboardButton("❓ مساعدة", callback_data="help")]
        ]
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = """
❓ *المساعدة*

📥 *للتحميل:* أرسل رابط الفيديو
🔍 *للبحث:* اكتب أي كلمة
🔥 *للتصفح:* استخدم /browse

🌐 *المنصات المدعومة:*
• يوتيوب 📺
• انستغرام 📷
• فيسبوك 📘
• تويتر 🐦
• تيك توك 🎵
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for cat_id, cat_info in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_info['name_ar'], callback_data=f"cat_{cat_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])
        
        await query.edit_message_text("🔥 *اختر الفئة:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("🔍 جاري البحث...")
        
        videos = self.video_processor.search_videos(VIDEO_CATEGORIES[category]['query'], limit=5)
        
        if not videos:
            await query.edit_message_text("❌ لا توجد فيديوهات", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="browse")]]))
            return
        
        self.user_sessions[user_id] = {'browse': {'videos': videos, 'page': 0}}
        await self.show_video(update, context, videos[0], 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video: Dict, index: int):
        query = update.callback_query
        user_id = update.effective_user.id
        
        text = f"""
🎬 *{video['title'][:100]}*

📺 {video.get('channel', 'غير معروف')} | ⏱ {self.format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        keyboard = [[InlineKeyboardButton("▶️ مشاهدة", url=video['url']), InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")]]
        
        videos = self.user_sessions.get(user_id, {}).get('browse', {}).get('videos', [])
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton("◀️", callback_data="nav_prev"))
        if index < len(videos) - 1:
            nav.append(InlineKeyboardButton("▶️", callback_data="nav_next"))
        if nav:
            keyboard.append(nav)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="browse")])
        
        try:
            await query.message.delete()
            await context.bot.send_photo(chat_id=user_id, photo=video['thumbnail'], caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        except:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("⏳ جاري المعالجة...")
        user_id = update.effective_user.id
        
        info = self.video_processor.get_video_info(url)
        
        if not info:
            await msg.edit_text("❌ تعذر الحصول على معلومات الفيديو")
            return
        
        self.user_sessions[user_id] = {'current_video': info}
        self.user_manager.add_to_history(user_id, info)
        
        text = f"""
📹 *معلومات الفيديو*

🎬 {info['title'][:100]}
👤 {info['uploader']} | ⏱ {self.format_time(info['duration'])}
👁 {info['view_count']}

🔗 [شاهد على يوتيوب]({info['webpage_url']})
        """
        
        keyboard = [
            [InlineKeyboardButton("▶️ مشاهدة", url=info['webpage_url']), InlineKeyboardButton("📥 تحميل", callback_data="download_menu")],
            [InlineKeyboardButton("⭐ مفضلة", callback_data="add_favorite"), InlineKeyboardButton("⏰ للمشاهدة", callback_data="add_watchlater")],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        try:
            await msg.delete()
            await update.message.reply_photo(photo=info['thumbnail'], caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        except:
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        msg = await update.message.reply_text(f"🔍 جاري البحث...")
        user_id = update.effective_user.id
        
        videos = self.video_processor.search_videos(query, limit=5)
        
        if not videos:
            await msg.edit_text("❌ لا توجد نتائج", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]]))
            return
        
        self.user_sessions[user_id] = {'search_results': videos, 'search_page': 0}
        await self.show_search_result(update, context, videos[0], 0)
        await msg.delete()
    
    async def show_search_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video: Dict, index: int):
        query = update.callback_query
        user_id = update.effective_user.id
        
        text = f"""
🔍 *نتيجة {index + 1}*

🎬 {video['title'][:100]}
📺 {video.get('channel', 'غير معروف')} | ⏱ {self.format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        videos = self.user_sessions.get(user_id, {}).get('search_results', [])
        keyboard = []
        
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton("◀️", callback_data="search_prev"))
        if index < len(videos) - 1:
            nav.append(InlineKeyboardButton("▶️", callback_data="search_next"))
        if nav:
            keyboard.append(nav)
        
        keyboard.append([InlineKeyboardButton("▶️ مشاهدة", url=video['url']), InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")])
        
        try:
            if query:
                await query.message.delete()
                await context.bot.send_photo(chat_id=user_id, photo=video['thumbnail'], caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_photo(photo=video['thumbnail'], caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        except:
            if query:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        video = self.user_sessions.get(update.effective_user.id, {}).get('current_video', {})
        
        if not video:
            await query.edit_message_text("❌ لا توجد معلومات", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]]))
            return
        
        keyboard = []
        for q_id, q_info in VIDEO_QUALITIES.items():
            keyboard.append([InlineKeyboardButton(f"{q_info['emoji']} {q_info['name_ar']}", callback_data=f"quality_{q_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text("📥 *اختر الجودة:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for f_id, f_info in DOWNLOAD_FORMATS.items():
            keyboard.append([InlineKeyboardButton(f"{f_info['emoji']} {f_info['name_ar']}", callback_data=f"format_{quality}_{f_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="download_menu")])
        
        await query.edit_message_text(f"📥 *اختر الصيغة:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, format: str):
        query = update.callback_query
        user_id = update.effective_user.id
        
        video = self.user_sessions.get(user_id, {}).get('current_video', {})
        url = video.get('webpage_url', '')
        title = video.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text("❌ لا يوجد رابط")
            return
        
        await query.edit_message_text(f"⬇️ *جاري التحميل...*\n\n{title[:50]}", parse_mode=ParseMode.MARKDOWN)
        
        result = self.video_processor.download_video(url, quality, format)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(chat_id=user_id, audio=f, caption=f"✅ تم التحميل!\n📦 {self.format_size(result['size'])}", title=title[:100], duration=result['duration'])
                else:
                    await context.bot.send_video(chat_id=user_id, video=f, caption=f"✅ تم التحميل!\n📦 {self.format_size(result['size'])}", supports_streaming=True)
            
            Path(result['file']).unlink()
            user = self.user_manager.get_user(user_id)
            self.user_manager.update_user(user_id, {'download_count': user.get('download_count', 0) + 1, 'total_size': user.get('total_size', 0) + result['size']})
            
            await query.delete()
        else:
            await query.edit_message_text("❌ فشل التحميل")
    
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
            await query.edit_message_text("🔍 *بحث*\n\nأرسل كلمة البحث:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)
        elif data == "help":
            await self.help(update, context)
        elif data.startswith("cat_"):
            await self.browse_category(update, context, data.replace("cat_", ""))
        elif data == "nav_prev":
            s = self.user_sessions.get(user_id, {}).get('browse', {})
            v = s.get('videos', [])
            p = s.get('page', 0)
            if p > 0:
                s['page'] = p - 1
                await self.show_video(update, context, v[p - 1], p - 1)
        elif data == "nav_next":
            s = self.user_sessions.get(user_id, {}).get('browse', {})
            v = s.get('videos', [])
            p = s.get('page', 0)
            if p < len(v) - 1:
                s['page'] = p + 1
                await self.show_video(update, context, v[p + 1], p + 1)
        elif data == "search_prev":
            s = self.user_sessions.get(user_id, {})
            v = s.get('search_results', [])
            p = s.get('search_page', 0)
            if p > 0:
                s['search_page'] = p - 1
                await self.show_search_result(update, context, v[p - 1], p - 1)
        elif data == "search_next":
            s = self.user_sessions.get(user_id, {})
            v = s.get('search_results', [])
            p = s.get('search_page', 0)
            if p < len(v) - 1:
                s['search_page'] = p + 1
                await self.show_search_result(update, context, v[p + 1], p + 1)
        elif data == "download_menu":
            await self.download_menu(update, context)
        elif data.startswith("quality_"):
            await self.select_quality(update, context, data.replace("quality_", ""))
        elif data.startswith("format_"):
            parts = data.replace("format_", "").split("_")
            await self.start_download(update, context, parts[0], parts[1])
        elif data.startswith("dl_"):
            await self.handle_url(update, context, data.replace("dl_", ""))
        elif data == "add_favorite":
            v = self.user_sessions.get(user_id, {}).get('current_video', {})
            if v:
                added = self.user_manager.add_to_favorites(user_id, v)
                await query.answer("✅ أضيف" if added else "❌ موجود")
        elif data == "add_watchlater":
            v = self.user_sessions.get(user_id, {}).get('current_video', {})
            if v:
                added = self.user_manager.add_to_watch_later(user_id, v)
                await query.answer("✅ أضيف" if added else "❌ موجود")
    
    def run(self):
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("browse", self.browse))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
        print("✅ البوت شغال!")
        print("📌 أرسل /start في تليجرام")
        print("=" * 50)
        
        app.run_polling()

# ==================== MAIN ====================

if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
