#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Video Downloader Bot - الإصدار النهائي المضمون
Version: 1.0.0
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
BOT_TOKEN = "7536390168:AAHZNO7XjIRBpwhMf3O5RojM9f2RrPYzUZ4"  # ضع التوكن هنا
BOT_VERSION = "1.0.0"

# إنشاء المجلدات
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
    'mp4': {'name': 'MP4', 'emoji': '🎬'},
    'mp3': {'name': 'MP3 (صوت)', 'emoji': '🎵'}
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
    'instagram': {'name': 'انستغرام', 'emoji': '📷'},
    'facebook': {'name': 'فيسبوك', 'emoji': '📘'},
    'twitter': {'name': 'تويتر', 'emoji': '🐦'},
    'tiktok': {'name': 'تيك توك', 'emoji': '🎵'}
}

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
            logger.error(f"خطأ في الحصول على معلومات الفيديو: {e}")
            return None
    
    async def search_videos(self, query: str, limit: int = 5) -> List[Dict]:
        """البحث عن فيديوهات"""
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL({**self.ydl_opts, 'extract_flat': True}) as ydl:
                results = await loop.run_in_executor(
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
                                'thumbnail': f"https://img.youtube.com/vi/{entry.get('id', '')}/hqdefault.jpg",
                                'channel': entry.get('uploader', '')
                            })
                return videos
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []
    
    async def download_video(self, url: str, quality: str = 'best', format: str = 'mp4') -> Optional[Dict]:
        """تحميل الفيديو"""
        try:
            # إعدادات التحميل
            if quality == 'best':
                format_spec = 'best[ext=mp4]/best'
            elif quality.isdigit():
                format_spec = f'best[height<={quality}][ext=mp4]/best'
            else:
                format_spec = 'best[ext=mp4]/best'
            
            if format == 'mp3':
                format_spec = 'bestaudio/best'
            
            # اسم الملف
            filename = DOWNLOAD_DIR / f"video_{int(time.time())}_{random.randint(1000,9999)}.%(ext)s"
            
            ydl_opts = {
                **self.ydl_opts,
                'format': format_spec,
                'outtmpl': str(filename),
            }
            
            # إضافة معالج الصوت
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
                        'title': info.get('title', ''),
                        'duration': info.get('duration', 0)
                    }
                
                return {'success': False, 'error': 'الملف غير موجود'}
                
        except Exception as e:
            logger.error(f"خطأ في التحميل: {e}")
            return {'success': False, 'error': str(e)}

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

# ==================== بوت التليجرام ====================
class VideoBot:
    """البوت الرئيسي"""
    
    def __init__(self):
        self.processor = VideoProcessor()
        self.user_sessions = {}
        self.start_time = datetime.now()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر البدء"""
        user = update.effective_user
        
        text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات. أرسل لي رابط فيديو أو كلمة للبحث!

📥 *للتحميل:* أرسل رابط الفيديو
🔍 *للبحث:* اكتب أي كلمة
🔥 *للتصفح:* استخدم الأزرار أدناه

الأوامر:
/start - القائمة الرئيسية
/browse - تصفح الفيديوهات
/help - المساعدة

👥 عدد المستخدمين: {len(self.user_sessions)}
⚡ الإصدار: {BOT_VERSION}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح", callback_data="browse")],
            [InlineKeyboardButton("❓ مساعدة", callback_data="help")]
        ]
        
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
        for cat_id, cat_info in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(
                cat_info['name'],
                callback_data=f"cat_{cat_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🔥 *اختر الفئة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """تصفح فئة محددة"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text(f"🔍 جاري البحث في {VIDEO_CATEGORIES[category]['name']}...")
        
        videos = await self.processor.search_videos(
            VIDEO_CATEGORIES[category]['query'],
            limit=5
        )
        
        if not videos:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات",
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
        
        text = f"""
🎬 *{video['title'][:100]}*

📺 القناة: {video.get('channel', 'غير معروف')}
⏱ المدة: {format_time(video.get('duration', 0))}

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
        except:
            # إذا فشل إرسال الصورة
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
        text = update.message.text
        
        # التحقق من الرابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة رابط فيديو"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        platform_emoji = get_platform_emoji(url)
        info = await self.processor.get_video_info(url)
        
        if not info:
            await msg.edit_text(
                f"{platform_emoji} ❌ تعذر الحصول على معلومات الفيديو",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {'current_video': info}
        
        text = f"""
{platform_emoji} *معلومات الفيديو*

🎬 *العنوان:* {info['title'][:100]}
👤 الرافع: {info['uploader']}
⏱ المدة: {format_time(info['duration'])}
👁 المشاهدات: {format_number(info['view_count'])}
👍 الإعجابات: {format_number(info['like_count'])}

🔗 [شاهد على يوتيوب]({info['webpage_url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=info['webpage_url']),
                InlineKeyboardButton("📥 تحميل", callback_data="download_menu")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
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
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        
        videos = await self.processor.search_videos(query, limit=5)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج للبحث: '{query}'",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
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
        
        text = f"""
🔍 *نتيجة {index + 1}*

🎬 *{video['title'][:100]}*

📺 القناة: {video.get('channel', 'غير معروف')}
⏱ المدة: {format_time(video.get('duration', 0))}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        # أزرار التنقل
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
        except:
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
            await query.edit_message_text("❌ لا توجد معلومات فيديو")
            return
        
        keyboard = []
        for q_id, q_info in VIDEO_QUALITIES.items():
            keyboard.append([InlineKeyboardButton(
                f"{q_info['emoji']} {q_info['name']}",
                callback_data=f"quality_{q_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            "📥 *اختر الجودة:*",
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
            f"📥 *اختر الصيغة:*\n\nالجودة: {VIDEO_QUALITIES[quality]['name']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, format: str):
        """بدء التحميل"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        video = self.user_sessions.get(user_id, {}).get('current_video', {})
        url = video.get('webpage_url', '')
        
        if not url:
            await query.edit_message_text("❌ لا يوجد رابط فيديو")
            return
        
        await query.edit_message_text("⬇️ جاري التحميل... الرجاء الانتظار")
        
        result = await self.processor.download_video(url, quality, format)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                if format == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption="✅ تم التحميل بنجاح!",
                        title=result['title'][:100],
                        duration=result['duration']
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption="✅ تم التحميل بنجاح!",
                        supports_streaming=True
                    )
            
            # حذف الملف
            Path(result['file']).unlink()
            await query.delete()
        else:
            await query.edit_message_text(f"❌ فشل التحميل: {result.get('error', 'خطأ غير معروف')}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        if data == "main_menu":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "help":
            text = """
❓ *المساعدة*

📥 *للتحميل:* أرسل رابط الفيديو
🔍 *للبحث:* اكتب أي كلمة
🔥 *للتصفح:* استخدم قائمة التصفح

المنصات المدعومة:
• يوتيوب
• انستغرام
• فيسبوك
• تيك توك
• تويتر
• والمزيد...

⚠️ *ملاحظة:* بعض المنصات قد لا تعمل بسبب التحديثات
            """
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]])
            )
        
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
            format = parts[1]
            await self.start_download(update, context, quality, format)
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.handle_url(update, context, url)
    
    def run(self):
        """تشغيل البوت"""
        try:
            app = Application.builder().token(BOT_TOKEN).build()
            
            # إضافة المعالجات
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("browse", self.browse))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # رسالة البدء
            print("=" * 50)
            print("🚀 بوت تحميل الفيديوهات - شغال!")
            print("=" * 50)
            print(f"✅ التوكن: {BOT_TOKEN[:10]}...")
            print(f"✅ البوت يعمل على Python {sys.version}")
            print("=" * 50)
            print("📌 أرسل /start في تليجرام للبدء")
            print("=" * 50)
            
            app.run_polling()
            
        except Exception as e:
            print(f"❌ خطأ: {e}")
            traceback.print_exc()

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
