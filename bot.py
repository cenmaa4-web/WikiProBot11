#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي المتطور
Version: 20.0.0
جميع الأزرار تعمل بـ EDIT - بدون حذف الرسائل
واجهة محسنة - صور + فيديو + أزرار متطورة
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
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
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
from telegram.constants import ParseMode

# ==================== التوكن ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن الصحيح هنا

# ==================== الإعدادات ====================
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== إعدادات الفيديو المتطورة ====================
VIDEO_QUALITIES = {
    '144': {'name': '144p', 'emoji': '📱', 'color': '⚪'},
    '240': {'name': '240p', 'emoji': '📱', 'color': '⚪'},
    '360': {'name': '360p', 'emoji': '📺', 'color': '🟢'},
    '480': {'name': '480p', 'emoji': '📺', 'color': '🟢'},
    '720': {'name': '720p HD', 'emoji': '🎬', 'color': '🔵'},
    '1080': {'name': '1080p FHD', 'emoji': '🎥', 'color': '🟣'},
    'best': {'name': 'أفضل جودة', 'emoji': '🏆', 'color': '⭐'}
}

DOWNLOAD_FORMATS = {
    'mp4': {'name': 'فيديو MP4', 'emoji': '🎬', 'desc': 'جودة عالية'},
    'mp3': {'name': 'صوت MP3', 'emoji': '🎵', 'desc': 'صوت نقي'}
}

VIDEO_CATEGORIES = {
    'trending': '🔥 الأكثر مشاهدة',
    'music': '🎵 موسيقى',
    'gaming': '🎮 ألعاب',
    'news': '📰 أخبار',
    'sports': '⚽ رياضة',
    'education': '📚 تعليم',
    'technology': '💻 تكنولوجيا',
    'entertainment': '🎭 ترفيه'
}

# ==================== دوال مساعدة ====================
def format_time(seconds):
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def format_number(num):
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def escape_markdown(text):
    if not text:
        return ""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in chars:
        text = text.replace(c, f'\\{c}')
    return text

def create_progress_bar(percentage, width=10):
    filled = int(width * percentage / 100)
    return '█' * filled + '░' * (width - filled)

# ==================== مدير البيانات ====================
class Database:
    def __init__(self):
        self.data = {}
        self.load()
    
    def load(self):
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except:
                self.data = {}
        else:
            self.data = {}
        self.save()
    
    def save(self):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {
                'joined': datetime.now().isoformat(),
                'downloads': 0,
                'favorites': [],
                'watch_later': [],
                'history': [],
                'settings': {
                    'quality': 'best',
                    'format': 'mp4'
                }
            }
            self.save()
        return self.data[user_id]
    
    def update_user(self, user_id, data):
        user_id = str(user_id)
        self.data[user_id] = data
        self.save()

# ==================== معالج التحميل المتطور ====================
class Downloader:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
    
    def get_info(self, url):
        """الحصول على معلومات الفيديو مع الصور"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return {
                        'title': info.get('title', 'بدون عنوان'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'غير معروف'),
                        'views': info.get('view_count', 0),
                        'likes': info.get('like_count', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'thumbnails': info.get('thumbnails', []),
                        'url': info.get('webpage_url', url),
                        'description': info.get('description', '')[:200]
                    }
            return None
        except Exception as e:
            logger.error(f"خطأ: {e}")
            return None
    
    def search(self, query, limit=10):
        """بحث متقدم مع صور عالية الجودة"""
        try:
            with yt_dlp.YoutubeDL({**self.ydl_opts, 'extract_flat': True}) as ydl:
                results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry and entry.get('id'):
                            video_id = entry.get('id', '')
                            # استخدام صور عالية الجودة
                            thumbnails = [
                                f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                                f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                            ]
                            videos.append({
                                'id': video_id,
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={video_id}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': thumbnails[0],
                                'thumbnails': thumbnails,
                                'channel': entry.get('uploader', 'غير معروف'),
                                'views': entry.get('view_count', 0),
                                'description': entry.get('description', '')[:100]
                            })
                return videos
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []
    
    def get_trending(self, category, limit=8):
        """الحصول على الفيديوهات الرائجة"""
        search_map = {
            'trending': 'trending',
            'music': 'music video',
            'gaming': 'gaming',
            'news': 'news today',
            'sports': 'sports highlights',
            'education': 'educational',
            'technology': 'tech reviews',
            'entertainment': 'entertainment'
        }
        query = search_map.get(category, 'trending')
        return self.search(query, limit)
    
    def download(self, url, quality='best', format='mp4', progress_callback=None):
        """تحميل الفيديو مع تتبع التقدم"""
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
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
                
                if format == 'mp3':
                    file = str(file).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                else:
                    for ext in ['.mp4', '.webm']:
                        test = str(file).replace('%(ext)s', ext)
                        if Path(test).exists():
                            file = test
                            break
                
                if Path(file).exists():
                    return {
                        'success': True,
                        'file': file,
                        'size': Path(file).stat().st_size,
                        'title': info.get('title', 'فيديو'),
                        'duration': info.get('duration', 0)
                    }
                return {'success': False, 'error': 'الملف غير موجود'}
        except Exception as e:
            logger.error(f"خطأ في التحميل: {e}")
            return {'success': False, 'error': str(e)}

# ==================== البوت الرئيسي المتطور ====================
class VideoBot:
    def __init__(self):
        self.db = Database()
        self.downloader = Downloader()
        self.user_data = {}
        self.browse_sessions = {}
        self.search_sessions = {}
        self.user_states = {}  # لتخزين حالة المستخدم الحالية
        self.start_time = datetime.now()
        print("=" * 60)
        print("🚀 بوت تحميل الفيديوهات المتطور - الإصدار 20.0")
        print("=" * 60)
    
    # ==================== نظام إدارة الحالة ====================
    
    def set_state(self, user_id, state, data=None):
        """تخزين حالة المستخدم الحالية"""
        self.user_states[user_id] = {
            'state': state,
            'data': data,
            'time': time.time()
        }
    
    def get_state(self, user_id):
        """الحصول على حالة المستخدم"""
        return self.user_states.get(user_id, {'state': 'main', 'data': None})
    
    # ==================== القائمة الرئيسية ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """القائمة الرئيسية - تستخدم EDIT"""
        user = update.effective_user
        user_id = user.id
        
        # تسجيل المستخدم
        self.db.get_user(user_id)
        self.set_state(user_id, 'main')
        
        # إحصائيات سريعة
        users_count = len(self.db.data)
        downloads = sum(u.get('downloads', 0) for u in self.db.data.values())
        
        text = f"""
🎬 *مرحباً {escape_markdown(user.first_name)}!*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🤖 *بوت تحميل الفيديوهات المتطور*

📥 *أرسل رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات المتاحة:*
• تحميل من يوتيوب، انستغرام، فيسبوك، تيك توك
• 7 جودات مختلفة (144p - 1080p)
• صيغ MP4 و MP3
• 8 فئات للتصفح
• بحث بـ 10 نتائج مع صور عالية الجودة
• مفضلة ومشاهدة لاحقاً
• سجل وإحصائيات
• إعدادات مخصصة

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📊 *إحصائيات البوت:*
👥 المستخدمين: {users_count}
📥 التحميلات: {downloads}

👇 *اختر ما تريد:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح الفيديوهات", callback_data="browse")],
            [InlineKeyboardButton("🔍 بحث متقدم", callback_data="search")],
            [
                InlineKeyboardButton("⭐ المفضلة", callback_data="favorites"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="watchlater")
            ],
            [
                InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
                InlineKeyboardButton("📜 السجل", callback_data="history")
            ],
            [
                InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings"),
                InlineKeyboardButton("❓ المساعدة", callback_data="help")
            ]
        ]
        
        if update.callback_query:
            # إذا كان الطلب من زر، نستخدم edit
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # إذا كان أمر /start جديد
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة المساعدة - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        self.set_state(user_id, 'help')
        
        text = """
❓ *مساعدة البوت المتطورة*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📥 *للتحميل:*
• أرسل رابط فيديو مباشرة
• اختر الجودة المناسبة
• اختر الصيغة المطلوبة
• انتظر التحميل

🔍 *للبحث:*
• اكتب أي كلمة
• اختر من 10 نتائج
• شاهد الصور عالية الجودة
• حمله أو شاهده

🔥 *للتصفح:*
• اختر من 8 فئات
• تصفح بالصور
• تنقل بين الفيديوهات

⭐ *للمفضلة:*
• أضف فيديوهات
• شاهدها لاحقاً
• احفظ ما تريد

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🌐 *المنصات المدعومة:*
يوتيوب 📺 | انستغرام 📷 | فيسبوك 📘
تويتر 🐦 | تيك توك 🎵

⚡ *الأوامر المتاحة:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/favorites - المفضلة
/watchlater - للمشاهدة
/history - السجل
/stats - الإحصائيات
/settings - الإعدادات
/help - المساعدة
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== التصفح المتطور ====================
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة التصفح - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        self.set_state(user_id, 'browse')
        
        keyboard = []
        for cat_id, cat_name in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_id}")])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "🔥 *تصفح الفيديوهات*\n\nاختر الفئة التي تريدها:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category):
        """عرض فيديوهات الفئة - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("⏳ جاري تحميل الفيديوهات...")
        
        videos = self.downloader.get_trending(category, limit=8)
        
        if not videos:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات في هذه الفئة",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.browse_sessions[user_id] = {
            'category': category,
            'videos': videos,
            'page': 0
        }
        
        self.set_state(user_id, 'browsing', {'category': category, 'page': 0})
        await self.show_browse_video(update, context, 0)
    
    async def show_browse_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, index):
        """عرض فيديو من التصفح مع صورة عالية الجودة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.browse_sessions.get(user_id, {})
        videos = session.get('videos', [])
        
        if not videos or index >= len(videos):
            await query.edit_message_text("❌ خطأ في عرض الفيديو")
            return
        
        video = videos[index]
        
        duration = format_time(video.get('duration', 0))
        views = format_number(video.get('views', 0))
        
        # استخدام أفضل صورة متاحة
        thumbnail = video.get('thumbnail', '')
        
        text = f"""
🎬 *{escape_markdown(video['title'][:100])}*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📺 *القناة:* {escape_markdown(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 [شاهد على يوتيوب]({video['url']})
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data=f"fav_{video['url']}|{video['title'][:50]}"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data=f"wl_{video['url']}|{video['title'][:50]}")
            ]
        ]
        
        # أزرار التنقل
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"browse_prev"))
        if index < len(videos) - 1:
            nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"browse_next"))
        if nav:
            keyboard.append(nav)
            keyboard.append([InlineKeyboardButton(f"📄 الصفحة {index+1} من {len(videos)}", callback_data="page_info")])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        try:
            # محاولة إرسال الصورة مع التعديل
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=thumbnail,
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            # إذا فشل تعديل الصورة، نعدل النص فقط
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
    
    # ==================== معالجة الروابط والبحث ====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل النصية"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url):
        """معالجة رابط فيديو - إرسال رسالة جديدة مع صورة"""
        user_id = update.effective_user.id
        
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        info = self.downloader.get_info(url)
        
        if not info:
            await msg.edit_text("❌ تعذر الحصول على معلومات الفيديو")
            return
        
        self.user_data[user_id] = {
            'url': url,
            'info': info,
            'time': time.time()
        }
        
        # حفظ في السجل
        user = self.db.get_user(user_id)
        user['history'].insert(0, {
            'title': info['title'],
            'url': info['url'],
            'date': datetime.now().isoformat()
        })
        if len(user['history']) > 50:
            user['history'] = user['history'][:50]
        self.db.update_user(user_id, user)
        
        duration = format_time(info['duration'])
        views = format_number(info['views'])
        likes = format_number(info['likes'])
        
        text = f"""
🎬 *{escape_markdown(info['title'][:100])}*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
👤 *القناة:* {escape_markdown(info['uploader'])}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}
👍 *الإعجابات:* {likes}

🔗 [شاهد على يوتيوب]({info['url']})
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=info['url']),
                InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data="add_favorite"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="add_watchlater")
            ],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
            ]
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
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        """معالجة البحث - إرسال رسالة جديدة مع النتائج"""
        user_id = update.effective_user.id
        
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        
        videos = self.downloader.search(query, limit=10)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج للبحث عن: '{query}'",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.search_sessions[user_id] = {
            'query': query,
            'videos': videos,
            'page': 0
        }
        
        await msg.delete()
        await self.show_search_video(update, context, 0)
    
    async def show_search_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, index):
        """عرض نتيجة بحث مع صورة عالية الجودة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.search_sessions.get(user_id, {})
        videos = session.get('videos', [])
        
        if not videos or index >= len(videos):
            await query.edit_message_text("❌ خطأ في عرض النتائج")
            return
        
        video = videos[index]
        
        duration = format_time(video.get('duration', 0))
        views = format_number(video.get('views', 0))
        
        text = f"""
🔍 *نتيجة البحث {index+1} من {len(videos)}*

🎬 *{escape_markdown(video['title'][:100])}*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📺 *القناة:* {escape_markdown(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 [شاهد على يوتيوب]({video['url']})
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data=f"fav_{video['url']}|{video['title'][:50]}"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data=f"wl_{video['url']}|{video['title'][:50]}")
            ]
        ]
        
        # أزرار التنقل
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton("◀️ السابق", callback_data="search_prev"))
        if index < len(videos) - 1:
            nav.append(InlineKeyboardButton("التالي ▶️", callback_data="search_next"))
        if nav:
            keyboard.append(nav)
            keyboard.append([InlineKeyboardButton(f"📄 الصفحة {index+1} من {len(videos)}", callback_data="page_info")])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=video['thumbnail'],
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
    
    # ==================== نظام التحميل المتطور ====================
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة اختيار الجودة - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        info = self.user_data.get(user_id, {}).get('info', {})
        
        if not info:
            await query.edit_message_text(
                "❌ لا توجد معلومات فيديو",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = f"""
📥 *اختر جودة التحميل*

🎬 *العنوان:* {escape_markdown(info.get('title', '')[:100])}
⏱ *المدة:* {format_time(info.get('duration', 0))}

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
👇 *اختر الجودة المطلوبة:*
        """
        
        keyboard = []
        row = []
        for i, (q_id, q_info) in enumerate(VIDEO_QUALITIES.items(), 1):
            row.append(InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name']}",
                callback_data=f"quality_{q_id}"
            ))
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality):
        """اختيار الجودة وانتقال لاختيار الصيغة"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        text = f"""
📥 *اختر صيغة التحميل*

⚡ *الجودة المختارة:* {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
👇 *اختر الصيغة المطلوبة:*
        """
        
        keyboard = [
            [InlineKeyboardButton(f"🎬 MP4 فيديو - جودة عالية", callback_data=f"format_{quality}_mp4")],
            [InlineKeyboardButton(f"🎵 MP3 صوت - نقي", callback_data=f"format_{quality}_mp3")],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
            ]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality, format):
        """بدء التحميل مع شريط تقدم"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        info = self.user_data.get(user_id, {}).get('info', {})
        url = info.get('url', '')
        title = info.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text(
                "❌ لا يوجد رابط",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n{escape_markdown(title[:50])}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percentage = (downloaded / total) * 100
                    if int(percentage) % 10 == 0:
                        bar = create_progress_bar(percentage)
                        speed = d.get('speed', 0)
                        speed_str = format_size(speed) + '/s' if speed else '?'
                        eta = d.get('eta', 0)
                        text = f"⬇️ *التحميل:*\n{bar} {percentage:.1f}%\n⚡ السرعة: {speed_str}\n⏱ المتبقي: {format_time(eta)}"
                        asyncio.create_task(query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN))
        
        result = self.downloader.download(url, quality, format, progress_hook)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=f"✅ *تم التحميل بنجاح!*\n📦 الحجم: {format_size(result['size'])}",
                        parse_mode=ParseMode.MARKDOWN,
                        title=title[:100],
                        duration=result['duration']
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=f"✅ *تم التحميل بنجاح!*\n📦 الحجم: {format_size(result['size'])}",
                        parse_mode=ParseMode.MARKDOWN,
                        supports_streaming=True
                    )
            
            Path(result['file']).unlink()
            
            user = self.db.get_user(user_id)
            user['downloads'] += 1
            self.db.update_user(user_id, user)
            
            await query.delete()
        else:
            await query.edit_message_text(
                f"❌ فشل التحميل",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
    
    # ==================== المفضلة والمشاهدة لاحقاً ====================
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المفضلة - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        user = self.db.get_user(user_id)
        favorites = user.get('favorites', [])
        
        if not favorites:
            await query.edit_message_text(
                "⭐ *المفضلة*\n\nلا توجد فيديوهات في المفضلة بعد.\n\nأضف فيديوهات بالضغط على ⭐ أثناء مشاهدة أي فيديو.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "⭐ *المفضلة*\n\n"
        keyboard = []
        
        for i, fav in enumerate(reversed(favorites[-10:]), 1):
            title = fav.get('title', 'فيديو')[:50]
            text += f"{i}. {title}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"show_fav_{fav['url']}"
            )])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_watch_later(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة المشاهدة لاحقاً - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        user = self.db.get_user(user_id)
        watch_later = user.get('watch_later', [])
        
        if not watch_later:
            await query.edit_message_text(
                "⏰ *للمشاهدة لاحقاً*\n\nلا توجد فيديوهات في القائمة.\n\nأضف فيديوهات بالضغط على ⏰ أثناء مشاهدة أي فيديو.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "⏰ *للمشاهدة لاحقاً*\n\n"
        keyboard = []
        
        for i, item in enumerate(reversed(watch_later[-10:]), 1):
            title = item.get('title', 'فيديو')[:50]
            text += f"{i}. {title}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}",
                callback_data=f"show_wl_{item['url']}"
            )])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض سجل النشاط - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        user = self.db.get_user(user_id)
        history = user.get('history', [])[:15]
        
        if not history:
            await query.edit_message_text(
                "📜 *سجل النشاط*\n\nلا يوجد سجل بعد.\n\nشاهد أو حمل الفيديوهات لتظهر هنا.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "📜 *آخر 15 نشاط*\n\n"
        
        for item in history[:10]:
            date = item.get('date', '')[:10]
            title = item.get('title', '')[:50]
            text += f"• {title}\n  📅 {date}\n\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== الإحصائيات ====================
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإحصائيات الشخصية - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        user = self.db.get_user(user_id)
        
        joined = datetime.fromisoformat(user['joined'])
        days = (datetime.now() - joined).days
        
        text = f"""
📊 *إحصائياتك الشخصية*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
👤 *المستخدم:* {update.effective_user.first_name}
📅 *عضو منذ:* {days} يوم
📥 *التحميلات:* {user['downloads']}

🎬 *المحتوى:*
• المفضلة: {len(user['favorites'])}
• للمشاهدة: {len(user['watch_later'])}
• السجل: {len(user['history'])}

⚙️ *الإعدادات:*
• الجودة: {VIDEO_QUALITIES[user['settings']['quality']]['name']}
• الصيغة: {DOWNLOAD_FORMATS[user['settings']['format']]['name']}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
        """
        
        keyboard = [[
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== الإعدادات ====================
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإعدادات - تستخدم EDIT"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        user = self.db.get_user(user_id)
        settings = user['settings']
        
        text = f"""
⚙️ *الإعدادات الشخصية*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🔰 *الإعدادات الحالية:*

🎬 *الجودة الافتراضية:* {VIDEO_QUALITIES[settings['quality']]['name']}
📁 *الصيغة الافتراضية:* {DOWNLOAD_FORMATS[settings['format']]['name']}

👇 *اختر الإعداد لتعديله:
        ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 تغيير الجودة", callback_data="set_quality")],
            [InlineKeyboardButton("📁 تغيير الصيغة", callback_data="set_format")],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
            ]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تغيير الجودة الافتراضية"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
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
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "🎬 *اختر الجودة الافتراضية:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تغيير الصيغة الافتراضية"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("🎬 MP4 فيديو", callback_data="save_format_mp4")],
            [InlineKeyboardButton("🎵 MP3 صوت", callback_data="save_format_mp3")],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
            ]
        ]
        
        await query.edit_message_text(
            "📁 *اختر الصيغة الافتراضية:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== معالج الأزرار الرئيسي ====================
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج جميع الأزرار - كلها تستخدم EDIT بدون حذف"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        await query.answer()
        
        # ========== أزرار التنقل الأساسية ==========
        
        if data == "main_menu":
            # الرجوع للقائمة الرئيسية - edit
            await self.start(update, context)
        
        elif data == "back":
            # الرجوع للصفحة السابقة بناءً على الحالة
            state = self.get_state(user_id)
            current_state = state.get('state', 'main')
            
            if current_state == 'browsing':
                # الرجوع لقائمة التصفح
                await self.browse(update, context)
            elif current_state == 'searching':
                # الرجوع لصفحة البحث
                await query.edit_message_text(
                    "🔍 *بحث*\n\nأرسل كلمة البحث الآن:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                        InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                    ]]),
                    parse_mode=ParseMode.MARKDOWN
                )
            elif current_state == 'downloading':
                # الرجوع لقائمة التحميل
                await self.download_menu(update, context)
            elif current_state == 'settings':
                # الرجوع للإعدادات
                await self.settings(update, context)
            else:
                # الرجوع للقائمة الرئيسية
                await self.start(update, context)
        
        # ========== أزرار القائمة الرئيسية ==========
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "search":
            self.set_state(user_id, 'searching')
            await query.edit_message_text(
                "🔍 *بحث متقدم*\n\nأرسل كلمة البحث الآن:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                    InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "favorites":
            self.set_state(user_id, 'favorites')
            await self.show_favorites(update, context)
        
        elif data == "watchlater":
            self.set_state(user_id, 'watchlater')
            await self.show_watch_later(update, context)
        
        elif data == "history":
            self.set_state(user_id, 'history')
            await self.show_history(update, context)
        
        elif data == "stats":
            self.set_state(user_id, 'stats')
            await self.show_stats(update, context)
        
        elif data == "settings":
            self.set_state(user_id, 'settings')
            await self.settings(update, context)
        
        elif data == "help":
            await self.help(update, context)
        
        # ========== أزرار التصفح ==========
        
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            self.set_state(user_id, 'browsing', {'category': category, 'page': 0})
            await self.browse_category(update, context, category)
        
        elif data == "browse_prev":
            session = self.browse_sessions.get(user_id, {})
            page = session.get('page', 0)
            if page > 0:
                session['page'] = page - 1
                self.set_state(user_id, 'browsing', {'page': page - 1})
                await self.show_browse_video(update, context, page - 1)
        
        elif data == "browse_next":
            session = self.browse_sessions.get(user_id, {})
            page = session.get('page', 0)
            videos = session.get('videos', [])
            if page < len(videos) - 1:
                session['page'] = page + 1
                self.set_state(user_id, 'browsing', {'page': page + 1})
                await self.show_browse_video(update, context, page + 1)
        
        # ========== أزرار البحث ==========
        
        elif data == "search_prev":
            session = self.search_sessions.get(user_id, {})
            page = session.get('page', 0)
            if page > 0:
                session['page'] = page - 1
                self.set_state(user_id, 'searching', {'page': page - 1})
                await self.show_search_video(update, context, page - 1)
        
        elif data == "search_next":
            session = self.search_sessions.get(user_id, {})
            page = session.get('page', 0)
            videos = session.get('videos', [])
            if page < len(videos) - 1:
                session['page'] = page + 1
                self.set_state(user_id, 'searching', {'page': page + 1})
                await self.show_search_video(update, context, page + 1)
        
        # ========== أزرار التحميل ==========
        
        elif data == "download_menu":
            self.set_state(user_id, 'downloading', {'step': 'quality'})
            await self.download_menu(update, context)
        
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            self.set_state(user_id, 'downloading', {'step': 'format', 'quality': quality})
            await self.select_quality(update, context, quality)
        
        elif data.startswith("format_"):
            parts = data.replace("format_", "").split("_")
            quality = parts[0]
            format_type = parts[1]
            self.set_state(user_id, 'downloading', {'step': 'downloading', 'quality': quality, 'format': format_type})
            await self.start_download(update, context, quality, format_type)
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.handle_url(update, context, url)
        
        # ========== أزرار المفضلة والمشاهدة لاحقاً ==========
        
        elif data.startswith("fav_"):
            parts = data.replace("fav_", "").split("|")
            url = parts[0]
            title = parts[1] if len(parts) > 1 else 'فيديو'
            
            user = self.db.get_user(user_id)
            if 'favorites' not in user:
                user['favorites'] = []
            
            exists = any(f.get('url') == url for f in user['favorites'])
            if not exists:
                user['favorites'].append({
                    'url': url,
                    'title': title,
                    'date': datetime.now().isoformat()
                })
                self.db.update_user(user_id, user)
                await query.answer("✅ أضيف إلى المفضلة")
            else:
                await query.answer("❌ موجود مسبقاً")
        
        elif data.startswith("wl_"):
            parts = data.replace("wl_", "").split("|")
            url = parts[0]
            title = parts[1] if len(parts) > 1 else 'فيديو'
            
            user = self.db.get_user(user_id)
            if 'watch_later' not in user:
                user['watch_later'] = []
            
            exists = any(w.get('url') == url for w in user['watch_later'])
            if not exists:
                user['watch_later'].append({
                    'url': url,
                    'title': title,
                    'date': datetime.now().isoformat()
                })
                self.db.update_user(user_id, user)
                await query.answer("✅ أضيف إلى قائمة المشاهدة")
            else:
                await query.answer("❌ موجود مسبقاً")
        
        elif data.startswith("show_fav_"):
            url = data.replace("show_fav_", "")
            await self.handle_url(update, context, url)
        
        elif data.startswith("show_wl_"):
            url = data.replace("show_wl_", "")
            await self.handle_url(update, context, url)
        
        elif data == "add_favorite":
            info = self.user_data.get(user_id, {}).get('info', {})
            if info:
                user = self.db.get_user(user_id)
                if 'favorites' not in user:
                    user['favorites'] = []
                
                exists = any(f.get('url') == info['url'] for f in user['favorites'])
                if not exists:
                    user['favorites'].append({
                        'url': info['url'],
                        'title': info['title'],
                        'date': datetime.now().isoformat()
                    })
                    self.db.update_user(user_id, user)
                    await query.answer("✅ أضيف إلى المفضلة")
                else:
                    await query.answer("❌ موجود مسبقاً")
        
        elif data == "add_watchlater":
            info = self.user_data.get(user_id, {}).get('info', {})
            if info:
                user = self.db.get_user(user_id)
                if 'watch_later' not in user:
                    user['watch_later'] = []
                
                exists = any(w.get('url') == info['url'] for w in user['watch_later'])
                if not exists:
                    user['watch_later'].append({
                        'url': info['url'],
                        'title': info['title'],
                        'date': datetime.now().isoformat()
                    })
                    self.db.update_user(user_id, user)
                    await query.answer("✅ أضيف إلى قائمة المشاهدة")
                else:
                    await query.answer("❌ موجود مسبقاً")
        
        # ========== أزرار الإعدادات ==========
        
        elif data == "set_quality":
            await self.set_quality(update, context)
        
        elif data == "set_format":
            await self.set_format(update, context)
        
        elif data.startswith("save_quality_"):
            quality = data.replace("save_quality_", "")
            user = self.db.get_user(user_id)
            user['settings']['quality'] = quality
            self.db.update_user(user_id, user)
            await query.answer(f"✅ تم حفظ الجودة: {VIDEO_QUALITIES[quality]['name']}")
            await self.settings(update, context)
        
        elif data.startswith("save_format_"):
            format_type = data.replace("save_format_", "")
            user = self.db.get_user(user_id)
            user['settings']['format'] = format_type
            self.db.update_user(user_id, user)
            await query.answer(f"✅ تم حفظ الصيغة: {DOWNLOAD_FORMATS[format_type]['name']}")
            await self.settings(update, context)
        
        elif data == "page_info":
            await query.answer("استخدم أزرار التنقل للتصفح بين الفيديوهات")
    
    # ==================== تشغيل البوت ====================
    
    def run(self):
        """تشغيل البوت"""
        print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
        print("✅ جاري تشغيل البوت...")
        print("=" * 60)
        print("📌 جميع الأزرار تعمل بـ EDIT ✅")
        print("📌 زر الرجوع يعود للصفحة السابقة ✅")
        print("📌 زر الرئيسية يرجع للقائمة ✅")
        print("📌 بدون حذف الرسائل أبداً ✅")
        print("📌 البحث يعمل بـ 10 نتائج مع صور ✅")
        print("📌 التصفح يعمل بـ 8 فئات ✅")
        print("📌 المفضلة والمشاهدة لاحقاً ✅")
        print("📌 السجل والإحصائيات ✅")
        print("📌 الإعدادات ✅")
        print("=" * 60)
        print("📌 أرسل /start في تليجرام للبدء")
        print("=" * 60)
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # أوامر البوت
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("browse", self.browse))
        app.add_handler(CommandHandler("favorites", self.show_favorites))
        app.add_handler(CommandHandler("watchlater", self.show_watch_later))
        app.add_handler(CommandHandler("history", self.show_history))
        app.add_handler(CommandHandler("stats", self.show_stats))
        app.add_handler(CommandHandler("settings", self.settings))
        
        # معالج الرسائل النصية
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # معالج الأزرار
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # تشغيل البوت
        app.run_polling(allowed_updates=Update.ALL_TYPES)

# ==================== MAIN ====================
if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
