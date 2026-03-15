#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي والمضمون
Version: 2.0.0
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
import html
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

import yt_dlp
import requests

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

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
BOT_VERSION = "2.0.0"

# إنشاء مجلد التحميلات
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== جودات الفيديو ====================
VIDEO_QUALITIES = {
    '144': {'name': '144p', 'emoji': '📱'},
    '240': {'name': '240p', 'emoji': '📱'},
    '360': {'name': '360p', 'emoji': '📺'},
    '480': {'name': '480p', 'emoji': '📺'},
    '720': {'name': '720p HD', 'emoji': '🎬'},
    '1080': {'name': '1080p FHD', 'emoji': '🎥'},
    'best': {'name': 'أفضل جودة', 'emoji': '🏆'}
}

# ==================== صيغ التحميل ====================
DOWNLOAD_FORMATS = {
    'mp4': {'name': 'MP4 فيديو', 'emoji': '🎬'},
    'mp3': {'name': 'MP3 صوت', 'emoji': '🎵'}
}

# ==================== فئات التصفح ====================
VIDEO_CATEGORIES = {
    'trending': {'name': '🔥 الأكثر مشاهدة', 'query': 'trending'},
    'music': {'name': '🎵 موسيقى', 'query': 'music'},
    'gaming': {'name': '🎮 ألعاب', 'query': 'gaming'},
    'news': {'name': '📰 أخبار', 'query': 'news'},
    'sports': {'name': '⚽ رياضة', 'query': 'sports'},
    'education': {'name': '📚 تعليم', 'query': 'educational'}
}

# ==================== المنصات المدعومة ====================
SUPPORTED_PLATFORMS = {
    'youtube': {'name': 'يوتيوب', 'emoji': '📺'},
    'youtu.be': {'name': 'يوتيوب', 'emoji': '📺'},
    'instagram': {'name': 'انستغرام', 'emoji': '📷'},
    'facebook': {'name': 'فيسبوك', 'emoji': '📘'},
    'twitter': {'name': 'تويتر', 'emoji': '🐦'},
    'x.com': {'name': 'تويتر', 'emoji': '🐦'},
    'tiktok': {'name': 'تيك توك', 'emoji': '🎵'}
}

# ==================== دوال المساعدة ====================
def format_time(seconds: int) -> str:
    """تنسيق الوقت"""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_size(size: int) -> str:
    """تنسيق الحجم"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def format_number(num: int) -> str:
    """تنسيق الأرقام"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def get_platform_emoji(url: str) -> str:
    """الحصول على إيموجي المنصة"""
    url_lower = url.lower()
    for platform, info in SUPPORTED_PLATFORMS.items():
        if platform in url_lower:
            return info['emoji']
    return '🌐'

def get_platform_name(url: str) -> str:
    """الحصول على اسم المنصة"""
    url_lower = url.lower()
    for platform, info in SUPPORTED_PLATFORMS.items():
        if platform in url_lower:
            return info['name']
    return 'أخرى'

# ==================== معالج الفيديو ====================
class VideoProcessor:
    """معالج الفيديو - يعمل مع yt-dlp"""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """الحصول على معلومات الفيديو"""
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
                )
                
                if not info:
                    return None
                
                return {
                    'title': info.get('title', 'بدون عنوان'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'غير معروف'),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'webpage_url': info.get('webpage_url', url),
                    'extractor': info.get('extractor', 'unknown')
                }
        except Exception as e:
            logger.error(f"خطأ في الحصول على معلومات الفيديو: {e}")
            return None
    
    async def search_videos(self, query: str, limit: int = 5) -> List[Dict]:
        """البحث عن فيديوهات"""
        try:
            loop = asyncio.get_event_loop()
            search_opts = {**self.ydl_opts, 'extract_flat': True}
            
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                results = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                )
                
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry and entry.get('id'):
                            video_id = entry.get('id', '')
                            videos.append({
                                'id': video_id,
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={video_id}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                'channel': entry.get('uploader', 'غير معروف')
                            })
                return videos
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []
    
    async def download_video(self, url: str, quality: str = 'best', format: str = 'mp4') -> Optional[Dict]:
        """تحميل الفيديو"""
        try:
            # إعدادات التحميل حسب الجودة
            if quality == 'best':
                if format == 'mp3':
                    format_spec = 'bestaudio/best'
                else:
                    format_spec = 'best[ext=mp4]/best'
            elif quality.isdigit():
                if format == 'mp3':
                    format_spec = 'bestaudio/best'
                else:
                    format_spec = f'best[height<={quality}][ext=mp4]/best'
            else:
                format_spec = 'best[ext=mp4]/best'
            
            # اسم الملف
            timestamp = int(time.time())
            random_id = random.randint(1000, 9999)
            filename = DOWNLOAD_DIR / f"video_{timestamp}_{random_id}.%(ext)s"
            
            ydl_opts = {
                **self.ydl_opts,
                'format': format_spec,
                'outtmpl': str(filename),
            }
            
            # إضافة معالج الصوت لـ MP3
            if format == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            # التحميل
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=True)
                )
                
                # الحصول على اسم الملف الفعلي
                file = ydl.prepare_filename(info)
                
                if format == 'mp3':
                    # تغيير الامتداد لـ MP3
                    file = str(file).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                else:
                    # البحث عن الملف بامتدادات مختلفة
                    for ext in ['.mp4', '.webm', '.mkv']:
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
                        'title': info.get('title', 'فيديو'),
                        'duration': info.get('duration', 0)
                    }
                
                return {'success': False, 'error': 'الملف غير موجود'}
                
        except Exception as e:
            logger.error(f"خطأ في التحميل: {e}")
            return {'success': False, 'error': str(e)}

# ==================== بوت التليجرام ====================
class VideoBot:
    """البوت الرئيسي"""
    
    def __init__(self):
        self.processor = VideoProcessor()
        self.user_sessions = {}
        self.start_time = datetime.now()
        self.users_count = 0
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر البدء"""
        user = update.effective_user
        self.users_count += 1
        
        welcome_text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات من جميع المنصات 🚀

📥 *أرسل لي رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات:*
• تحميل من يوتيوب، انستغرام، فيسبوك، تيك توك، تويتر
• اختيار الجودة (144p - 1080p)
• تحميل فيديو أو صوت MP3
• بحث سريع عن الفيديوهات
• تصفح الفئات المختلفة
• واجهة عربية سهلة

👥 *المستخدمين:* {self.users_count}
⚡ *الإصدار:* {BOT_VERSION}

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
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تصفح الفئات"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for cat_id, cat_info in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(
                cat_info['name'],
                callback_data=f"cat_{cat_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🔥 *اختر الفئة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """تصفح فئة محددة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text(
            f"⏳ جاري البحث في {VIDEO_CATEGORIES[category]['name']}...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        videos = await self.processor.search_videos(
            VIDEO_CATEGORIES[category]['query'],
            limit=5
        )
        
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
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        self.user_sessions[user_id]['browse'] = {
            'category': category,
            'videos': videos,
            'page': 0
        }
        
        await self.show_video(update, context, videos[0], 0)
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video: Dict, index: int):
        """عرض الفيديو مع الصورة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        duration = format_time(video.get('duration', 0))
        
        text = f"""
🎬 *{video['title'][:100]}*

📺 *القناة:* {video.get('channel', 'غير معروف')}
⏱ *المدة:* {duration}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ]
        ]
        
        # أزرار التنقل
        videos = self.user_sessions.get(user_id, {}).get('browse', {}).get('videos', [])
        nav_buttons = []
        
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="nav_prev"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data="nav_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton(
                f"📄 الصفحة {index + 1}/{len(videos)}", 
                callback_data="page_info"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="browse")])
        
        # إرسال الصورة
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
        except Exception as e:
            logger.error(f"خطأ في إرسال الصورة: {e}")
            # إذا فشل إرسال الصورة، أرسل نص فقط
            if query:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل"""
        text = update.message.text.strip()
        
        # التحقق من الرابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة رابط فيديو"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        platform_emoji = get_platform_emoji(url)
        platform_name = get_platform_name(url)
        
        info = await self.processor.get_video_info(url)
        
        if not info:
            await msg.edit_text(
                f"{platform_emoji} ❌ تعذر الحصول على معلومات الفيديو من {platform_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {'current_video': info}
        
        duration = format_time(info['duration'])
        views = format_number(info['view_count'])
        likes = format_number(info['like_count'])
        
        text = f"""
{platform_emoji} *معلومات الفيديو من {platform_name}*

🎬 *العنوان:* {info['title'][:100]}
👤 *الرافع:* {info['uploader']}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}
👍 *الإعجابات:* {likes}

🔗 [شاهد على يوتيوب]({info['webpage_url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=info['webpage_url']),
                InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        # إرسال الصورة المصغرة
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
        
        videos = await self.processor.search_videos(query, limit=5)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج للبحث عن: '{query}'",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {'search_results': videos, 'search_page': 0}
        
        await self.show_search_result(update, context, videos[0], 0)
        await msg.delete()
    
    async def show_search_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video: Dict, index: int):
        """عرض نتيجة البحث"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        duration = format_time(video.get('duration', 0))
        
        text = f"""
🔍 *نتيجة البحث {index + 1}*

🎬 *{video['title'][:100]}*

📺 *القناة:* {video.get('channel', 'غير معروف')}
⏱ *المدة:* {duration}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        videos = self.user_sessions.get(user_id, {}).get('search_results', [])
        keyboard = []
        
        # أزرار التنقل
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
        
        keyboard.append([InlineKeyboardButton("🔙 بحث جديد", callback_data="search")])
        
        # إرسال الصورة
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
        except Exception as e:
            logger.error(f"خطأ في إرسال الصورة: {e}")
            if query:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة التحميل"""
        query = update.callback_query
        await query.answer()
        
        video = self.user_sessions.get(update.effective_user.id, {}).get('current_video', {})
        
        if not video:
            await query.edit_message_text(
                "❌ لا توجد معلومات فيديو. أرسل رابط فيديو أولاً.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
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
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            "📥 *اختر جودة التحميل:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        """اختيار الجودة"""
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
            f"📥 *اختر الصيغة:*\n\nالجودة: {VIDEO_QUALITIES[quality]['emoji']} {VIDEO_QUALITIES[quality]['name']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, format: str):
        """بدء التحميل"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        video = self.user_sessions.get(user_id, {}).get('current_video', {})
        url = video.get('webpage_url', '')
        title = video.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text(
                "❌ لا يوجد رابط فيديو",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n"
            f"🎬 {title[:50]}\n"
            f"⚡ {VIDEO_QUALITIES[quality]['name']} | {DOWNLOAD_FORMATS[format]['name']}\n\n"
            f"⏳ الرجاء الانتظار...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        result = await self.processor.download_video(url, quality, format)
        
        if result['success']:
            file = result['file']
            size = result['size']
            
            with open(file, 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=f"✅ تم التحميل بنجاح!\n📦 الحجم: {format_size(size)}",
                        title=title[:100],
                        duration=result['duration'],
                        performer=video.get('uploader', '')
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=f"✅ تم التحميل بنجاح!\n📦 الحجم: {format_size(size)}",
                        supports_streaming=True,
                        duration=result['duration']
                    )
            
            # حذف الملف بعد الإرسال
            Path(file).unlink()
            await query.delete()
        else:
            await query.edit_message_text(
                f"❌ فشل التحميل: {result.get('error', 'خطأ غير معروف')}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
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
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "help":
            help_text = """
❓ *المساعدة*

📥 *لتحميل فيديو:*
• أرسل رابط الفيديو مباشرة
• اختر الجودة المناسبة
• اختر الصيغة (فيديو أو صوت)
• انتظر التحميل

🔍 *للبحث عن فيديوهات:*
• اكتب أي كلمة للبحث
• تصفح النتائج مع الصور
• اختر الفيديو المطلوب

🔥 *للتصفح:*
• استخدم قائمة التصفح
• اختر الفئة المناسبة
• تصفح الفيديوهات

🌐 *المنصات المدعومة:*
• يوتيوب 📺
• انستغرام 📷
• فيسبوك 📘
• تويتر 🐦
• تيك توك 🎵
• والمزيد...

⚡ *الأوامر المتاحة:*
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/help - هذه المساعدة
            """
            await query.edit_message_text(
                help_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")
                ]])
            )
        
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
            # محاكاة إرسال رابط
            await self.handle_url(update, context, url)
        
        elif data == "page_info":
            await query.answer("استخدم الأزرار للتنقل بين الفيديوهات")
        
        else:
            await query.answer("إجراء غير معروف")
    
    def run(self):
        """تشغيل البوت"""
        try:
            print("=" * 60)
            print("🚀 بوت تحميل الفيديوهات - الإصدار النهائي")
            print("=" * 60)
            print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
            print(f"✅ Python: {sys.version}")
            print("✅ المكتبات: python-telegram-bot, yt-dlp")
            print("=" * 60)
            print("📌 أرسل /start في تليجرام للبدء")
            print("=" * 60)
            
            # إنشاء التطبيق
            app = Application.builder().token(BOT_TOKEN).build()
            
            # إضافة المعالجات
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("browse", self.browse))
            app.add_handler(CommandHandler("help", self.help))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # تشغيل البوت
            app.run_polling()
            
        except Exception as e:
            print(f"❌ خطأ في تشغيل البوت: {e}")
            traceback.print_exc()

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
