#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي المصحح
Version: 8.0.0
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
STATS_FILE = DATA_DIR / "stats.json"

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== إعدادات الفيديو ====================
VIDEO_QUALITIES = {
    '360': {'name': '360p', 'emoji': '📺'},
    '480': {'name': '480p', 'emoji': '📺'},
    '720': {'name': '720p HD', 'emoji': '🎬'},
    '1080': {'name': '1080p FHD', 'emoji': '🎥'},
    'best': {'name': 'أفضل جودة', 'emoji': '🏆'}
}

DOWNLOAD_FORMATS = {
    'mp4': {'name': 'فيديو MP4', 'emoji': '🎬'},
    'mp3': {'name': 'صوت MP3', 'emoji': '🎵'}
}

VIDEO_CATEGORIES = {
    'trending': '🔥 الأكثر مشاهدة',
    'music': '🎵 موسيقى',
    'gaming': '🎮 ألعاب',
    'news': '📰 أخبار',
    'sports': '⚽ رياضة',
    'education': '📚 تعليم'
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

def escape_markdown(text):
    if not text:
        return ""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in chars:
        text = text.replace(c, f'\\{c}')
    return text

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

# ==================== معالج التحميل ====================
class Downloader:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
    
    def get_info(self, url):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return {
                        'title': info.get('title', 'بدون عنوان'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'غير معروف'),
                        'views': info.get('view_count', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'url': info.get('webpage_url', url),
                    }
            return None
        except Exception as e:
            logger.error(f"خطأ: {e}")
            return None
    
    def search(self, query, limit=5):
        try:
            with yt_dlp.YoutubeDL({**self.ydl_opts, 'extract_flat': True}) as ydl:
                results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry and entry.get('id'):
                            videos.append({
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{entry.get('id')}/hqdefault.jpg",
                                'channel': entry.get('uploader', 'غير معروف')
                            })
                return videos
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []
    
    def download(self, url, quality='best', format='mp4'):
        try:
            if quality == 'best':
                format_spec = 'best[ext=mp4]/best' if format != 'mp3' else 'bestaudio/best'
            else:
                height = int(quality)
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

# ==================== البوت الرئيسي ====================
class VideoBot:
    def __init__(self):
        self.db = Database()
        self.downloader = Downloader()
        self.user_data = {}
        print("=" * 50)
        print("🚀 بوت تحميل الفيديوهات - الإصدار النهائي")
        print("=" * 50)
    
    # ==================== الأوامر الرئيسية ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.db.get_user(user.id)
        
        text = f"""
🎬 *مرحباً {escape_markdown(user.first_name)}!*

أنا بوت تحميل الفيديوهات من يوتيوب 🚀

📥 *أرسل رابط فيديو للتحميل*
🔍 *أو اكتب كلمة للبحث*

✨ *المميزات:*
• تحميل فيديوهات يوتيوب
• اختيار الجودة (360p - 1080p)
• تحميل فيديو MP4 أو صوت MP3
• بحث سريع مع صور مصغرة
• تصفح بالفئات المختلفة
• مفضلة ومشاهدة لاحقاً
• سجل النشاط
• إحصائيات شخصية

⚡ *الأوامر:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/favorites - المفضلة
/watchlater - المشاهدة لاحقاً
/history - سجل النشاط
/stats - إحصائياتي
/settings - الإعدادات
/help - المساعدة

👇 *اختر ما تريد:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح", callback_data="browse")],
            [
                InlineKeyboardButton("⭐ مفضلة", callback_data="favorites"),
                InlineKeyboardButton("⏰ للمشاهدة", callback_data="watchlater")
            ],
            [
                InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
                InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")
            ],
            [InlineKeyboardButton("❓ مساعدة", callback_data="help")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = """
❓ *المساعدة*

📥 *للتحميل:* أرسل رابط يوتيوب مباشرة
🔍 *للبحث:* اكتب أي كلمة
🔥 *للتصفح:* استخدم قائمة التصفح

🌐 *المنصات المدعومة:*
• يوتيوب 📺
• يوتيوب شورتس
• قوائم التشغيل

⚡ *الأوامر:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/favorites - المفضلة
/watchlater - المشاهدة لاحقاً
/history - سجل النشاط
/stats - إحصائياتي
/settings - الإعدادات
/help - المساعدة
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
        
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
    
    # ==================== التصفح ====================
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for cat_id, cat_name in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="start")])
        
        await query.edit_message_text(
            "🔥 *اختر الفئة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("🔍 جاري البحث...")
        
        videos = self.downloader.search(category, limit=5)
        
        if not videos:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="browse")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.user_data[user_id] = {
            'browse': {
                'videos': videos,
                'page': 0
            }
        }
        
        await self.show_video(update, context, videos[0], 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video, index):
        query = update.callback_query
        user_id = update.effective_user.id
        
        text = f"""
🎬 *{escape_markdown(video['title'][:100])}*

📺 {video.get('channel', 'غير معروف')} | ⏱ {format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ]
        ]
        
        videos = self.user_data.get(user_id, {}).get('browse', {}).get('videos', [])
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
    
    # ==================== معالجة الرسائل ====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url):
        msg = await update.message.reply_text("⏳ جاري المعالجة...")
        user_id = update.effective_user.id
        
        info = self.downloader.get_info(url)
        
        if not info:
            await msg.edit_text("❌ تعذر الحصول على معلومات الفيديو")
            return
        
        self.user_data[user_id] = {
            'url': url,
            'info': info
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
        
        text = f"""
🎬 *{escape_markdown(info['title'][:100])}*

👤 {info['uploader']} | ⏱ {format_time(info['duration'])} | 👁 {info['views']}

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
            [InlineKeyboardButton("🔙 رجوع", callback_data="start")]
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
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        user_id = update.effective_user.id
        
        videos = self.downloader.search(query, limit=5)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.user_data[user_id] = {
            'search': videos,
            'page': 0
        }
        
        await self.show_search(update, context, videos[0], 0)
        await msg.delete()
    
    async def show_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video, index):
        query = update.callback_query
        user_id = update.effective_user.id
        
        text = f"""
🔍 *نتيجة {index + 1}*

🎬 *{escape_markdown(video['title'][:100])}*

📺 {video.get('channel', 'غير معروف')} | ⏱ {format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        videos = self.user_data.get(user_id, {}).get('search', [])
        keyboard = []
        
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton("◀️", callback_data="search_prev"))
        if index < len(videos) - 1:
            nav.append(InlineKeyboardButton("▶️", callback_data="search_next"))
        if nav:
            keyboard.append(nav)
        
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
    
    # ==================== التحميل ====================
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        video = self.user_data.get(update.effective_user.id, {}).get('info', {})
        
        if not video:
            await query.edit_message_text(
                "❌ لا توجد معلومات فيديو",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        keyboard = []
        for q_id, q_info in VIDEO_QUALITIES.items():
            keyboard.append([InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name']}",
                callback_data=f"quality_{q_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="start")])
        
        await query.edit_message_text(
            "📥 *اختر الجودة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for f_id, f_info in DOWNLOAD_FORMATS.items():
            keyboard.append([InlineKeyboardButton(
                f"{f_info['emoji']} {f_info['name']}",
                callback_data=f"format_{quality}_{f_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="download_menu")])
        
        await query.edit_message_text(
            f"📥 *اختر الصيغة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality, format):
        query = update.callback_query
        user_id = update.effective_user.id
        
        video = self.user_data.get(user_id, {}).get('info', {})
        url = video.get('url', '')
        title = video.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text(
                "❌ لا يوجد رابط",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n{title[:50]}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        result = self.downloader.download(url, quality, format)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=f"✅ تم التحميل!\n📦 {format_size(result['size'])}",
                        title=title[:100],
                        duration=result['duration']
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=f"✅ تم التحميل!\n📦 {format_size(result['size'])}",
                        supports_streaming=True
                    )
            
            Path(result['file']).unlink()
            
            user = self.db.get_user(user_id)
            user['downloads'] += 1
            self.db.update_user(user_id, user)
            
            await query.delete()
        else:
            await query.edit_message_text(
                "❌ فشل التحميل",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
    
    # ==================== المفضلة ====================
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        favorites = user.get('favorites', [])
        
        if not favorites:
            await query.edit_message_text(
                "⭐ *المفضلة*\n\nلا توجد فيديوهات في المفضلة.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "⭐ *المفضلة*\n\n"
        keyboard = []
        
        for i, fav in enumerate(favorites[-10:], 1):
            text += f"{i}. {fav['title'][:50]}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {fav['title'][:30]}",
                callback_data=f"fav_{fav['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="start")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_watch_later(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        watch_later = user.get('watch_later', [])
        
        if not watch_later:
            await query.edit_message_text(
                "⏰ *للمشاهدة لاحقاً*\n\nلا توجد فيديوهات في القائمة.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "⏰ *للمشاهدة لاحقاً*\n\n"
        keyboard = []
        
        for i, item in enumerate(watch_later[-10:], 1):
            text += f"{i}. {item['title'][:50]}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {item['title'][:30]}",
                callback_data=f"wl_{item['url']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="start")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        history = user.get('history', [])[:10]
        
        if not history:
            await query.edit_message_text(
                "📜 *السجل*\n\nلا يوجد سجل بعد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="start")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = "📜 *آخر المشاهدات*\n\n"
        
        for item in history:
            date = item.get('date', '')[:10]
            text += f"• {item['title'][:50]}\n  📅 {date}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== الإحصائيات ====================
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        text = f"""
📊 *إحصائياتك*

👤 *المستخدم:* {update.effective_user.first_name}
📅 *عضو منذ:* {user['joined'][:10]}
📥 *التحميلات:* {user['downloads']}
⭐ *المفضلة:* {len(user.get('favorites', []))}
⏰ *للمشاهدة:* {len(user.get('watch_later', []))}
📜 *السجل:* {len(user.get('history', []))}

⚙️ *الإعدادات:*
🎬 الجودة: {VIDEO_QUALITIES[user['settings']['quality']]['name']}
📁 الصيغة: {DOWNLOAD_FORMATS[user['settings']['format']]['name']}
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== الإعدادات ====================
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        settings = user['settings']
        
        text = f"""
⚙️ *الإعدادات*

🎬 *الجودة الافتراضية:* {VIDEO_QUALITIES[settings['quality']]['name']}
📁 *الصيغة الافتراضية:* {DOWNLOAD_FORMATS[settings['format']]['name']}

👇 *اختر الإعداد لتعديله:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 تغيير الجودة", callback_data="set_quality")],
            [InlineKeyboardButton("📁 تغيير الصيغة", callback_data="set_format")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="start")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for q_id, q_info in VIDEO_QUALITIES.items():
            keyboard.append([InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name']}",
                callback_data=f"save_quality_{q_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="settings")])
        
        await query.edit_message_text(
            "🎬 *اختر الجودة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for f_id, f_info in DOWNLOAD_FORMATS.items():
            keyboard.append([InlineKeyboardButton(
                f"{f_info['emoji']} {f_info['name']}",
                callback_data=f"save_format_{f_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="settings")])
        
        await query.edit_message_text(
            "📁 *اختر الصيغة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== معالج الأزرار ====================
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        await query.answer()
        
        # أزرار القائمة الرئيسية
        if data == "start":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "browse":
            await self.browse(update, context)
        
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
        
        elif data == "set_quality":
            await self.set_quality(update, context)
        
        elif data == "set_format":
            await self.set_format(update, context)
        
        # أزرار التصفح
        elif data.startswith("cat_"):
            cat = data.replace("cat_", "")
            await self.browse_category(update, context, cat)
        
        elif data == "nav_prev":
            session = self.user_data.get(user_id, {}).get('browse', {})
            videos = session.get('videos', [])
            page = session.get('page', 0)
            if page > 0:
                session['page'] = page - 1
                await self.show_video(update, context, videos[page - 1], page - 1)
        
        elif data == "nav_next":
            session = self.user_data.get(user_id, {}).get('browse', {})
            videos = session.get('videos', [])
            page = session.get('page', 0)
            if page < len(videos) - 1:
                session['page'] = page + 1
                await self.show_video(update, context, videos[page + 1], page + 1)
        
        elif data == "search_prev":
            session = self.user_data.get(user_id, {})
            videos = session.get('search', [])
            page = session.get('page', 0)
            if page > 0:
                session['page'] = page - 1
                await self.show_search(update, context, videos[page - 1], page - 1)
        
        elif data == "search_next":
            session = self.user_data.get(user_id, {})
            videos = session.get('search', [])
            page = session.get('page', 0)
            if page < len(videos) - 1:
                session['page'] = page + 1
                await self.show_search(update, context, videos[page + 1], page + 1)
        
        # أزرار التحميل
        elif data == "download_menu":
            await self.download_menu(update, context)
        
        elif data.startswith("quality_"):
            q = data.replace("quality_", "")
            await self.select_quality(update, context, q)
        
        elif data.startswith("format_"):
            parts = data.replace("format_", "").split("_")
            await self.start_download(update, context, parts[0], parts[1])
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.handle_url(update, context, url)
        
        # أزرار المفضلة والمشاهدة لاحقاً
        elif data.startswith("fav_"):
            url = data.replace("fav_", "")
            info = {'url': url, 'title': 'فيديو'}
            user = self.db.get_user(user_id)
            if 'favorites' not in user:
                user['favorites'] = []
            user['favorites'].append(info)
            self.db.update_user(user_id, user)
            await query.answer("✅ أضيف للمفضلة")
        
        elif data.startswith("wl_"):
            url = data.replace("wl_", "")
            info = {'url': url, 'title': 'فيديو'}
            user = self.db.get_user(user_id)
            if 'watch_later' not in user:
                user['watch_later'] = []
            user['watch_later'].append(info)
            self.db.update_user(user_id, user)
            await query.answer("✅ أضيف للمشاهدة لاحقاً")
        
        elif data == "add_favorite":
            video = self.user_data.get(user_id, {}).get('info', {})
            if video:
                user = self.db.get_user(user_id)
                if 'favorites' not in user:
                    user['favorites'] = []
                user['favorites'].append(video)
                self.db.update_user(user_id, user)
                await query.answer("✅ أضيف للمفضلة")
        
        elif data == "add_watchlater":
            video = self.user_data.get(user_id, {}).get('info', {})
            if video:
                user = self.db.get_user(user_id)
                if 'watch_later' not in user:
                    user['watch_later'] = []
                user['watch_later'].append(video)
                self.db.update_user(user_id, user)
                await query.answer("✅ أضيف للمشاهدة لاحقاً")
        
        # أزرار الإعدادات
        elif data.startswith("save_quality_"):
            q = data.replace("save_quality_", "")
            user = self.db.get_user(user_id)
            user['settings']['quality'] = q
            self.db.update_user(user_id, user)
            await query.answer(f"✅ تم الحفظ")
            await self.settings(update, context)
        
        elif data.startswith("save_format_"):
            f = data.replace("save_format_", "")
            user = self.db.get_user(user_id)
            user['settings']['format'] = f
            self.db.update_user(user_id, user)
            await query.answer(f"✅ تم الحفظ")
            await self.settings(update, context)
    
    # ==================== تشغيل البوت ====================
    
    def run(self):
        print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
        print("✅ البوت يعمل...")
        print("📌 أرسل /start في تليجرام")
        print("=" * 50)
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("browse", self.browse))
        app.add_handler(CommandHandler("favorites", self.show_favorites))
        app.add_handler(CommandHandler("watchlater", self.show_watch_later))
        app.add_handler(CommandHandler("history", self.show_history))
        app.add_handler(CommandHandler("stats", self.show_stats))
        app.add_handler(CommandHandler("settings", self.settings))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        app.run_polling()

# ==================== التشغيل ====================
if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
