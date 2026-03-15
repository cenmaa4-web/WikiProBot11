import os
import logging
import re
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List
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
import yt_dlp
import subprocess
import sys
import urllib.parse

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
DOWNLOAD_FOLDER = "downloads"
THUMBNAIL_FOLDER = "thumbnails"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_DURATION = 600  # 10 دقائق
USERS_FILE = "users.json"
COOKIES_FILE = "cookies.txt"

# حالات المحادثة
QUALITY_SELECTION, DOWNLOAD_CONFIRM, SETTINGS_MENU, BROWSING_VIDEOS = range(4)

# إنشاء المجلدات
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# جودات الفيديو
QUALITIES = {
    '144': '144p (منخفضة)',
    '240': '240p (منخفضة)',
    '360': '360p (متوسطة)',
    '480': '480p (جيدة)',
    '720': '720p (عالية)',
    '1080': '1080p (فائقة)',
    '2k': '2K (عالية جداً)',
    '4k': '4K (فائقة الدقة)',
    'best': 'أفضل جودة متاحة'
}

# صيغ الفيديو
FORMATS = {
    'mp4': 'MP4',
    'webm': 'WEBM',
    'mkv': 'MKV',
    'mp3': 'MP3 (صوت فقط)'
}

# فئات الفيديو للتصفح
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

# ==================== إدارة المستخدمين ====================
class UserManager:
    def __init__(self):
        self.users = self.load_users()
    
    def load_users(self) -> Dict:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_users(self):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'username': username,
                'first_name': first_name,
                'joined_date': datetime.now().isoformat(),
                'downloads_count': 0,
                'total_downloads': 0,
                'watch_later': [],
                'favorites': [],
                'settings': {
                    'default_quality': 'best',
                    'auto_delete': True,
                    'notifications': True,
                    'theme': 'dark',
                    'language': 'ar'
                },
                'download_history': [],
                'watch_history': []
            }
            self.save_users()
    
    def update_stats(self, user_id: int, video_info: Dict):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]['downloads_count'] += 1
            self.users[user_id]['total_downloads'] += 1
            self.users[user_id]['download_history'].append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'platform': video_info.get('extractor', 'Unknown'),
                'quality': video_info.get('quality', 'Unknown'),
                'size': video_info.get('filesize', 0),
                'url': video_info.get('url', ''),
                'thumbnail': video_info.get('thumbnail', '')
            })
            # Keep last 50 downloads
            if len(self.users[user_id]['download_history']) > 50:
                self.users[user_id]['download_history'] = self.users[user_id]['download_history'][-50:]
            self.save_users()
    
    def add_to_watch_later(self, user_id: int, video_info: Dict):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]['watch_later'].append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': video_info.get('webpage_url', ''),
                'thumbnail': video_info.get('thumbnail', ''),
                'duration': video_info.get('duration', 0)
            })
            # Keep last 20 videos
            if len(self.users[user_id]['watch_later']) > 20:
                self.users[user_id]['watch_later'] = self.users[user_id]['watch_later'][-20:]
            self.save_users()
    
    def add_to_favorites(self, user_id: int, video_info: Dict):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]['favorites'].append({
                'date': datetime.now().isoformat(),
                'title': video_info.get('title', 'Unknown'),
                'url': video_info.get('webpage_url', ''),
                'thumbnail': video_info.get('thumbnail', ''),
                'duration': video_info.get('duration', 0)
            })
            # Keep last 20 favorites
            if len(self.users[user_id]['favorites']) > 20:
                self.users[user_id]['favorites'] = self.users[user_id]['favorites'][-20:]
            self.save_users()

# ==================== البوت الرئيسي ====================
class AdvancedVideoBot:
    def __init__(self):
        self.user_manager = UserManager()
        self.active_downloads = {}
        self.check_ffmpeg()
        self.browse_sessions = {}
    
    def check_ffmpeg(self):
        """التحقق من تثبيت ffmpeg"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            logger.info("FFmpeg مثبت بشكل صحيح")
        except FileNotFoundError:
            logger.warning("FFmpeg غير مثبت. بعض الميزات قد لا تعمل.")
    
    # ========== دوال المساعدة ==========
    def format_time(self, seconds: int) -> str:
        """تنسيق الوقت"""
        if not seconds:
            return "00:00"
        try:
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"
        except:
            return "00:00"
    
    def format_size(self, size_bytes: int) -> str:
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
            return "Unknown"
    
    def get_platform_emoji(self, platform: str) -> str:
        """إيموجي المنصة"""
        platforms = {
            'youtube': '📺',
            'instagram': '📷',
            'facebook': '📘',
            'twitter': '🐦',
            'tiktok': '🎵',
            'reddit': '👽',
            'pinterest': '📌',
            'vimeo': '🎥',
            'twitch': '🎮',
            'soundcloud': '🎵'
        }
        platform_lower = platform.lower()
        for key, emoji in platforms.items():
            if key in platform_lower:
                return emoji
        return '🎬'
    
    def clean_text_for_telegram(self, text: str) -> str:
        """تنظيف النص من الأحرف الخاصة"""
        if not text:
            return ""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def download_thumbnail(self, url: str, video_id: str) -> str:
        """تحميل الصورة المصغرة"""
        try:
            import aiohttp
            thumbnail_path = f"{THUMBNAIL_FOLDER}/{video_id}.jpg"
            
            if not os.path.exists(thumbnail_path):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            with open(thumbnail_path, 'wb') as f:
                                f.write(await resp.read())
            return thumbnail_path
        except:
            return None
    
    # ========== أوامر البوت ==========
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر البدء"""
        user = update.effective_user
        self.user_manager.add_user(user.id, user.username, user.first_name)
        
        welcome_text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل ومشاهدة الفيديوهات المتطور 🚀

📥 *المميزات الكاملة:*
• تحميل من جميع المنصات
• مشاهدة مباشرة للفيديوهات
• تصفح أحدث الفيديوهات
• إضافة للمفضلة والمشاهدة لاحقاً
• اختيار الجودة والصيغة
• بحث متقدم
• إحصائيات شخصية
• إعدادات مخصصة

👥 *عدد المستخدمين:* {len(self.user_manager.users)}

🔰 *الأوامر المتاحة:*
/start - بدء البوت
/browse - تصفح الفيديوهات
/search - بحث متقدم
/watch - مشاهدة فيديو
/download - تحميل فيديو
/favorites - المفضلة
/watchlater - المشاهدة لاحقاً
/history - سجل المشاهدة
/settings - الإعدادات
/stats - إحصائياتك
/help - المساعدة
/about - عن البوت

👇 *اختر ما تريد فعله:*
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح الفيديوهات", callback_data="browse_menu"),
             InlineKeyboardButton("🔍 بحث متقدم", callback_data="search_menu")],
            [InlineKeyboardButton("📥 تحميل", callback_data="download_menu"),
             InlineKeyboardButton("🎬 مشاهدة", callback_data="watch_menu")],
            [InlineKeyboardButton("⭐ المفضلة", callback_data="show_favorites"),
             InlineKeyboardButton("⏰ للمشاهدة لاحقاً", callback_data="show_watchlater")],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
             InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
            [InlineKeyboardButton("❓ المساعدة", callback_data="help"),
             InlineKeyboardButton("ℹ️ عن البوت", callback_data="about")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تصفح الفيديوهات"""
        keyboard = [
            [InlineKeyboardButton("🔥 الأكثر مشاهدة", callback_data="browse_trending")],
            [InlineKeyboardButton("🎵 موسيقى", callback_data="browse_music")],
            [InlineKeyboardButton("🎮 ألعاب", callback_data="browse_gaming")],
            [InlineKeyboardButton("📰 أخبار", callback_data="browse_news")],
            [InlineKeyboardButton("⚽ رياضة", callback_data="browse_sports")],
            [InlineKeyboardButton("📚 تعليم", callback_data="browse_education")],
            [InlineKeyboardButton("💻 تكنولوجيا", callback_data="browse_technology")],
            [InlineKeyboardButton("🎭 ترفيه", callback_data="browse_entertainment")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
        ]
        
        await update.message.reply_text(
            "🔥 *تصفح الفيديوهات*\n\nاختر الفئة التي تريد تصفحها:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """تصفح فئة معينة"""
        query = update.callback_query
        await query.answer()
        
        loading_msg = await query.edit_message_text(
            f"⏳ جاري تحميل فيديوهات {VIDEO_CATEGORIES.get(category, category)}...",
            parse_mode='Markdown'
        )
        
        try:
            # البحث عن فيديوهات في الفئة
            search_queries = {
                'trending': 'trending',
                'music': 'music video',
                'gaming': 'gaming',
                'news': 'news today',
                'sports': 'sports highlights',
                'education': 'educational',
                'technology': 'tech reviews',
                'entertainment': 'entertainment'
            }
            
            search_query = search_queries.get(category, category)
            
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch10:{search_query}", download=False)
                
                if results and 'entries' in results:
                    videos = []
                    for video in results['entries']:
                        if video and video.get('title'):
                            videos.append({
                                'title': video.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={video.get('id', '')}",
                                'duration': video.get('duration', 0),
                                'thumbnail': video.get('thumbnail', ''),
                                'channel': video.get('uploader', 'غير معروف'),
                                'views': video.get('view_count', 0)
                            })
                    
                    # حفظ قائمة الفيديوهات في جلسة المستخدم
                    user_id = update.effective_user.id
                    if user_id not in self.browse_sessions:
                        self.browse_sessions[user_id] = {}
                    self.browse_sessions[user_id][category] = videos
                    self.browse_sessions[user_id]['current_page'] = 0
                    
                    await self.show_video_page(update, context, category, 0)
                    
                else:
                    await loading_msg.edit_text("❌ لا توجد فيديوهات في هذه الفئة")
                    
        except Exception as e:
            await loading_msg.edit_text(f"❌ خطأ في التحميل: {str(e)[:100]}")
    
    async def show_video_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, page: int):
        """عرض صفحة فيديوهات"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        videos = self.browse_sessions.get(user_id, {}).get(category, [])
        if not videos:
            await query.edit_message_text("❌ لا توجد فيديوهات")
            return
        
        start_idx = page * 5
        end_idx = min(start_idx + 5, len(videos))
        page_videos = videos[start_idx:end_idx]
        
        text = f"🔥 *{VIDEO_CATEGORIES.get(category, category)}* (الصفحة {page + 1}/{(len(videos)-1)//5 + 1})\n\n"
        
        keyboard = []
        for i, video in enumerate(page_videos, start_idx + 1):
            title = video['title'][:50]
            duration = self.format_time(video['duration'])
            channel = video['channel'][:15]
            
            text += f"{i}. *{title}*\n   📺 {channel} | ⏱ {duration}\n\n"
            
            # زر لكل فيديو
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title[:30]}", 
                callback_data=f"view_video_{category}_{i-1}"
            )])
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"browse_page_{category}_{page-1}"))
        if end_idx < len(videos):
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"browse_page_{category}_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع للفئات", callback_data="browse_menu"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_start")
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def view_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, video_idx: int):
        """عرض فيديو مع خيارات المشاهدة والتحميل"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        video = self.browse_sessions.get(user_id, {}).get(category, [])[video_idx]
        
        # الحصول على معلومات تفصيلية
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video['url'], download=False)
                
                text = f"""
🎬 *{self.clean_text_for_telegram(info.get('title', 'فيديو'))}*

📊 *معلومات الفيديو:*
👤 القناة: {self.clean_text_for_telegram(info.get('uploader', 'غير معروف'))}
⏱ المدة: {self.format_time(info.get('duration', 0))}
👁 المشاهدات: {info.get('view_count', 0):,}
👍 الإعجابات: {info.get('like_count', 0):,}
📅 تاريخ الرفع: {info.get('upload_date', 'غير معروف')}

📝 *الوصف:*
{self.clean_text_for_telegram(info.get('description', 'لا يوجد وصف')[:200])}...
                """
                
                keyboard = [
                    [InlineKeyboardButton("🎬 مشاهدة مباشرة", callback_data=f"watch_now_{video['url']}")],
                    [InlineKeyboardButton("📥 تحميل", callback_data=f"download_now_{video['url']}")],
                    [InlineKeyboardButton("⭐ إضافة للمفضلة", callback_data=f"add_favorite_{video['url']}")],
                    [InlineKeyboardButton("⏰ مشاهدة لاحقاً", callback_data=f"add_watchlater_{video['url']}")],
                    [InlineKeyboardButton("🔗 مشاركة الرابط", callback_data=f"share_{video['url']}")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"browse_page_{category}_{self.browse_sessions[user_id]['current_page']}")]
                ]
                
                # محاولة إرسال الصورة المصغرة
                try:
                    thumbnail = info.get('thumbnail')
                    if thumbnail:
                        await context.bot.send_photo(
                            chat_id=user_id,
                            photo=thumbnail,
                            caption=text,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                        await query.message.delete()
                    else:
                        await query.edit_message_text(
                            text,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                except:
                    await query.edit_message_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
    
    async def watch_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """مشاهدة الفيديو مباشرة"""
        query = update.callback_query
        
        try:
            # الحصول على روابط المشاهدة
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best[height<=720]',  # جودة مناسبة للمشاهدة
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # الحصول على أفضل رابط للمشاهدة
                video_url = None
                for format in info.get('formats', []):
                    if format.get('height') and format['height'] <= 720 and format.get('url'):
                        video_url = format['url']
                        break
                
                if not video_url:
                    video_url = info.get('url', info.get('webpage_url', ''))
                
                text = f"""
🎬 *مشاهدة الفيديو*

📹 *العنوان:* {self.clean_text_for_telegram(info.get('title', 'فيديو')[:100])}
⏱ *المدة:* {self.format_time(info.get('duration', 0))}

🔗 *رابط المشاهدة المباشرة:*
{video_url}

📌 *يمكنك فتح الرابط مباشرة في المتصفح*
                """
                
                keyboard = [
                    [InlineKeyboardButton("📥 تحميل الفيديو", callback_data=f"download_now_{url}")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
                ]
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ في المشاهدة: {str(e)[:100]}")
    
    async def download_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """بدء التحميل مباشرة"""
        query = update.callback_query
        
        try:
            # الحصول على معلومات الفيديو
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                context.user_data['url'] = url
                context.user_data['info'] = info
                
                # عرض خيارات الجودة
                info_text = f"""
{self.get_platform_emoji(info.get('extractor', ''))} *معلومات الفيديو*

📹 *العنوان:* {self.clean_text_for_telegram(info.get('title', 'غير معروف')[:100])}
⏱ *المدة:* {self.format_time(info.get('duration', 0))}
📊 *المنصة:* {info.get('extractor', 'غير معروفة')}

👇 *اختر جودة التحميل:*
                """
                
                keyboard = []
                
                # أزرار الجودة
                quality_row1 = []
                for q_id, q_name in list(QUALITIES.items())[:3]:
                    quality_row1.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row1)
                
                quality_row2 = []
                for q_id, q_name in list(QUALITIES.items())[3:6]:
                    quality_row2.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row2)
                
                quality_row3 = []
                for q_id, q_name in list(QUALITIES.items())[6:]:
                    quality_row3.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row3)
                
                keyboard.append([
                    InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
                ])
                
                await query.edit_message_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المفضلة"""
        user_id = str(update.effective_user.id)
        favorites = self.user_manager.users.get(user_id, {}).get('favorites', [])
        
        if not favorites:
            text = "⭐ *المفضلة*\n\nلا توجد فيديوهات في المفضلة بعد"
        else:
            text = "⭐ *المفضلة*\n\n"
            keyboard = []
            
            for i, video in enumerate(reversed(favorites[-10:]), 1):
                title = video['title'][:50]
                duration = self.format_time(video.get('duration', 0))
                text += f"{i}. {title} - {duration}\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {title[:30]}",
                    callback_data=f"fav_video_{video['url']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")])
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
    
    async def show_watchlater(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة المشاهدة لاحقاً"""
        user_id = str(update.effective_user.id)
        watch_later = self.user_manager.users.get(user_id, {}).get('watch_later', [])
        
        if not watch_later:
            text = "⏰ *للمشاهدة لاحقاً*\n\nلا توجد فيديوهات في القائمة"
        else:
            text = "⏰ *للمشاهدة لاحقاً*\n\n"
            keyboard = []
            
            for i, video in enumerate(reversed(watch_later[-10:]), 1):
                title = video['title'][:50]
                duration = self.format_time(video.get('duration', 0))
                text += f"{i}. {title} - {duration}\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {title[:30]}",
                    callback_data=f"watch_video_{video['url']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")])
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر المساعدة"""
        help_text = """
❓ *دليل استخدام البوت*

📥 *تحميل فيديو:*
• أرسل رابط الفيديو مباشرة
• أو استخدم /download ثم الرابط

🎬 *مشاهدة فيديو:*
• /watch + رابط الفيديو
• أو اختر من قائمة التصفح

🔥 *تصفح الفيديوهات:*
• /browse لاستعراض الفئات
• اختر الفئة التي تريد

⭐ *المفضلة:*
• /favorites لعرض المفضلة
• أضف فيديوهات للمفضلة

⏰ *للمشاهدة لاحقاً:*
• /watchlater لعرض القائمة
• أضف فيديوهات للمشاهدة لاحقاً

🔍 *بحث متقدم:*
• /search + كلمة البحث
• أو اكتب أي كلمة للبحث

⚙️ *الإعدادات:*
• /settings لتخصيص البوت
• اختر الجودة الافتراضية
• ضبط الإشعارات

📊 *الإحصائيات:*
• /stats لعرض إحصائياتك
• /history لعرض سجل المشاهدة

⚠️ *القيود:*
• الحد الأقصى: 50 ميجابايت
• المدة القصوى: 10 دقائق

📌 *للدعم:* @YourSupport
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر الإعدادات"""
        user_id = str(update.effective_user.id)
        user_settings = self.user_manager.users.get(user_id, {}).get('settings', {})
        
        settings_text = f"""
⚙️ *الإعدادات الشخصية*

🔰 *الإعدادات الحالية:*
• الجودة الافتراضية: {QUALITIES.get(user_settings.get('default_quality', 'best'), 'أفضل جودة')}
• الحذف التلقائي: {'✅' if user_settings.get('auto_delete', True) else '❌'}
• الإشعارات: {'✅' if user_settings.get('notifications', True) else '❌'}
• الثيم: {'🌙 داكن' if user_settings.get('theme', 'dark') == 'dark' else '☀️ فاتح'}
• اللغة: العربية

📝 *يمكنك تعديل الإعدادات من الأزرار أدناه*
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 الجودة الافتراضية", callback_data="set_default_quality")],
            [InlineKeyboardButton("🗑 الحذف التلقائي", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton("🔔 الإشعارات", callback_data="toggle_notifications")],
            [InlineKeyboardButton("🎨 تغيير الثيم", callback_data="toggle_theme")],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                settings_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                settings_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        return SETTINGS_MENU
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإحصائيات"""
        user_id = str(update.effective_user.id)
        user_data = self.user_manager.users.get(user_id, {})
        
        # حساب الإحصائيات
        total_size = sum(d.get('size', 0) for d in user_data.get('download_history', []))
        watch_count = len(user_data.get('watch_history', []))
        favorites_count = len(user_data.get('favorites', []))
        watch_later_count = len(user_data.get('watch_later', []))
        
        stats_text = f"""
📊 *إحصائياتك الشخصية*

👤 *المستخدم:* {user_data.get('first_name', 'Unknown')}
📅 *تاريخ الانضمام:* {user_data.get('joined_date', 'Unknown')[:10]}

📥 *التحميلات:*
• عدد التحميلات: {user_data.get('downloads_count', 0)}
• إجمالي التحميلات: {user_data.get('total_downloads', 0)}
• حجم التحميلات: {self.format_size(total_size)}

🎬 *المشاهدة:*
• عدد المشاهدات: {watch_count}
• في المفضلة: {favorites_count}
• للمشاهدة لاحقاً: {watch_later_count}

⚙️ *إعداداتك:*
• الجودة الافتراضية: {QUALITIES.get(user_data.get('settings', {}).get('default_quality', 'best'), 'أفضل جودة')}
• الحذف التلقائي: {'✅' if user_data.get('settings', {}).get('auto_delete', True) else '❌'}

📌 *آخر 5 تحميلات:*
        """
        
        # آخر 5 تحميلات
        history = user_data.get('download_history', [])[-5:]
        if history:
            for i, item in enumerate(reversed(history), 1):
                stats_text += f"\n{i}. {item.get('title', 'Unknown')[:30]}..."
        else:
            stats_text += "\nلا توجد تحميلات سابقة"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_settings")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عن البوت"""
        about_text = f"""
ℹ️ *عن البوت*

🤖 *الاسم:* بوت الفيديوهات المتطور
📊 *الإصدار:* 3.0
👨‍💻 *المطور:* @YourUsername
📅 *تاريخ التحديث:* 2024

✨ *المميزات الكاملة:*
• تحميل من 20+ منصة
• مشاهدة مباشرة للفيديوهات
• تصفح الفيديوهات بفئات
• إضافة للمفضلة
• قائمة المشاهدة لاحقاً
• بحث متقدم
• إحصائيات شخصية
• إعدادات مخصصة
• جودات متعددة حتى 4K
• صيغ متعددة (MP4, MP3, MKV)
• واجهة عربية سهلة

⚡ *الإحصائيات العامة:*
• عدد المستخدمين: {len(self.user_manager.users)}
• إجمالي التحميلات: {sum(u.get('total_downloads', 0) for u in self.user_manager.users.values())}

📊 *حالة البوت:* 🟢 نشط

شكراً لاستخدامك البوت! ❤️
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                about_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                about_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل"""
        text = update.message.text
        
        # تحديث معلومات المستخدم
        user = update.effective_user
        self.user_manager.add_user(user.id, user.username, user.first_name)
        
        # التحقق إذا كان رابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        elif text.startswith('/watch '):
            url = text.replace('/watch ', '').strip()
            await self.handle_url(update, context, url)
        elif text.startswith('/download '):
            url = text.replace('/download ', '').strip()
            await self.handle_url(update, context, url)
        elif text.startswith('/search '):
            query = text.replace('/search ', '').strip()
            await self.handle_search(update, context, query)
        else:
            # بحث عادي
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة الروابط"""
        msg = await update.message.reply_text("⏳ *جاري معالجة الرابط...*", parse_mode='Markdown')
        
        try:
            # إعدادات yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'ignoreerrors': True,
                'no_color': True,
                'geo_bypass': True,
            }
            
            if os.path.exists(COOKIES_FILE):
                ydl_opts['cookiefile'] = COOKIES_FILE
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                context.user_data['url'] = url
                context.user_data['info'] = info
                
                title = info.get('title', 'غير معروف')
                duration = info.get('duration', 0)
                platform = info.get('extractor', 'غير معروفة')
                views = info.get('view_count', 0)
                uploader = info.get('uploader', 'غير معروف')
                
                if duration > MAX_DURATION:
                    await msg.edit_text(
                        f"❌ عذراً، مدة الفيديو ({self.format_time(duration)}) تتجاوز الحد المسموح"
                    )
                    return
                
                info_text = f"""
{self.get_platform_emoji(platform)} *معلومات الفيديو*

📹 *العنوان:* {self.clean_text_for_telegram(title[:100])}
⏱ *المدة:* {self.format_time(duration)}
📊 *المنصة:* {platform}
👤 *الرافع:* {self.clean_text_for_telegram(uploader)}
👁 *المشاهدات:* {views:,}

👇 *اختر ما تريد فعله:*
                """
                
                keyboard = [
                    [InlineKeyboardButton("🎬 مشاهدة مباشرة", callback_data=f"watch_now_{url}")],
                    [InlineKeyboardButton("📥 تحميل", callback_data=f"download_menu_{url}")],
                    [InlineKeyboardButton("⭐ إضافة للمفضلة", callback_data=f"add_favorite_{url}")],
                    [InlineKeyboardButton("⏰ مشاهدة لاحقاً", callback_data=f"add_watchlater_{url}")],
                    [InlineKeyboardButton("ℹ️ معلومات إضافية", callback_data="more_info")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
                ]
                
                await msg.edit_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"URL processing error: {error_message}")
            
            if "unsupported url" in error_message.lower():
                await msg.edit_text("❌ هذا الرابط غير مدعوم")
            elif "video unavailable" in error_message.lower():
                await msg.edit_text("❌ الفيديو غير متاح")
            elif "private" in error_message.lower():
                await msg.edit_text("❌ هذا الفيديو خاص")
            else:
                await msg.edit_text(f"❌ خطأ: {error_message[:100]}")
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 *جاري البحث عن:* '{query}'...", parse_mode='Markdown')
        
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
                'ignoreerrors': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch10:{query}", download=False)
                
                if results and 'entries' in results:
                    keyboard = []
                    videos = []
                    
                    for i, video in enumerate(results['entries'][:10], 1):
                        if video and video.get('title'):
                            title = video.get('title', 'بدون عنوان')[:50]
                            duration = self.format_time(video.get('duration', 0))
                            channel = video.get('uploader', 'غير معروف')[:15]
                            
                            btn_text = f"{i}. {title} - {channel} ({duration})"
                            url = f"https://youtube.com/watch?v={video.get('id', '')}"
                            
                            videos.append({
                                'title': title,
                                'url': url,
                                'duration': duration,
                                'channel': channel
                            })
                            
                            keyboard.append([InlineKeyboardButton(
                                btn_text, callback_data=f"search_result_{i-1}"
                            )])
                    
                    if keyboard:
                        # حفظ نتائج البحث
                        user_id = update.effective_user.id
                        if user_id not in self.browse_sessions:
                            self.browse_sessions[user_id] = {}
                        self.browse_sessions[user_id]['search_results'] = videos
                        
                        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                        
                        await msg.edit_text(
                            f"🔍 *نتائج البحث عن:* '{query}'\n\nاختر الفيديو:",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                    else:
                        await msg.edit_text("❌ لم يتم العثور على نتائج")
                else:
                    await msg.edit_text("❌ لم يتم العثور على نتائج")
                    
        except Exception as e:
            await msg.edit_text(f"❌ خطأ في البحث: {str(e)[:100]}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # ========== التنقل الرئيسي ==========
        if data == "back_to_start":
            await query.message.delete()
            await self.start(update, context)
            return
        
        elif data == "back_to_settings":
            await query.message.delete()
            await self.settings_command(update, context)
            return
        
        # ========== قوائم التصفح ==========
        elif data == "browse_menu":
            keyboard = [
                [InlineKeyboardButton("🔥 الأكثر مشاهدة", callback_data="browse_trending")],
                [InlineKeyboardButton("🎵 موسيقى", callback_data="browse_music")],
                [InlineKeyboardButton("🎮 ألعاب", callback_data="browse_gaming")],
                [InlineKeyboardButton("📰 أخبار", callback_data="browse_news")],
                [InlineKeyboardButton("⚽ رياضة", callback_data="browse_sports")],
                [InlineKeyboardButton("📚 تعليم", callback_data="browse_education")],
                [InlineKeyboardButton("💻 تكنولوجيا", callback_data="browse_technology")],
                [InlineKeyboardButton("🎭 ترفيه", callback_data="browse_entertainment")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
            ]
            
            await query.edit_message_text(
                "🔥 *تصفح الفيديوهات*\n\nاختر الفئة:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("browse_"):
            category = data.replace("browse_", "")
            await self.browse_category(update, context, category)
        
        elif data.startswith("browse_page_"):
            parts = data.replace("browse_page_", "").split("_")
            category = parts[0]
            page = int(parts[1])
            self.browse_sessions[user_id]['current_page'] = page
            await self.show_video_page(update, context, category, page)
        
        elif data.startswith("view_video_"):
            parts = data.replace("view_video_", "").split("_")
            category = parts[0]
            idx = int(parts[1])
            await self.view_video(update, context, category, idx)
        
        # ========== نتائج البحث ==========
        elif data.startswith("search_result_"):
            idx = int(data.replace("search_result_", ""))
            video = self.browse_sessions.get(user_id, {}).get('search_results', [])[idx]
            if video:
                await self.view_video(update, context, "search_results", idx)
        
        # ========== المشاهدة والتحميل ==========
        elif data.startswith("watch_now_"):
            url = data.replace("watch_now_", "")
            await self.watch_now(update, context, url)
        
        elif data.startswith("download_now_"):
            url = data.replace("download_now_", "")
            await self.download_now(update, context, url)
        
        elif data.startswith("add_favorite_"):
            url = data.replace("add_favorite_", "")
            try:
                ydl_opts = {'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    self.user_manager.add_to_favorites(user_id, info)
                await query.edit_message_text("✅ *تمت الإضافة للمفضلة*", parse_mode='Markdown')
            except:
                await query.edit_message_text("❌ خطأ في الإضافة", parse_mode='Markdown')
        
        elif data.startswith("add_watchlater_"):
            url = data.replace("add_watchlater_", "")
            try:
                ydl_opts = {'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    self.user_manager.add_to_watch_later(user_id, info)
                await query.edit_message_text("✅ *تمت الإضافة للمشاهدة لاحقاً*", parse_mode='Markdown')
            except:
                await query.edit_message_text("❌ خطأ في الإضافة", parse_mode='Markdown')
        
        elif data.startswith("fav_video_"):
            url = data.replace("fav_video_", "")
            await self.view_video(update, context, "favorites", 0)
        
        elif data.startswith("watch_video_"):
            url = data.replace("watch_video_", "")
            await self.view_video(update, context, "watchlater", 0)
        
        # ========== قوائم المستخدم ==========
        elif data == "show_favorites":
            await self.show_favorites(update, context)
        
        elif data == "show_watchlater":
            await self.show_watchlater(update, context)
        
        # ========== الإعدادات ==========
        elif data == "settings":
            await self.settings_command(update, context)
        
        elif data == "set_default_quality":
            keyboard = []
            for q_id, q_name in QUALITIES.items():
                keyboard.append([InlineKeyboardButton(
                    f"🎬 {q_name}", callback_data=f"save_quality_{q_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_settings")])
            
            await query.edit_message_text(
                "🎬 *اختر الجودة الافتراضية:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("save_quality_"):
            quality = data.replace("save_quality_", "")
            if str(user_id) in self.user_manager.users:
                self.user_manager.users[str(user_id)]['settings']['default_quality'] = quality
                self.user_manager.save_users()
            
            await query.edit_message_text(
                f"✅ *تم حفظ الجودة الافتراضية:* {QUALITIES.get(quality, quality)}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                ]])
            )
        
        elif data == "toggle_auto_delete":
            if str(user_id) in self.user_manager.users:
                current = self.user_manager.users[str(user_id)]['settings'].get('auto_delete', True)
                self.user_manager.users[str(user_id)]['settings']['auto_delete'] = not current
                self.user_manager.save_users()
                
                status = "✅ مفعل" if not current else "❌ معطل"
                await query.edit_message_text(
                    f"✅ *تم تغيير إعداد الحذف التلقائي:* {status}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                    ]])
                )
        
        elif data == "toggle_notifications":
            if str(user_id) in self.user_manager.users:
                current = self.user_manager.users[str(user_id)]['settings'].get('notifications', True)
                self.user_manager.users[str(user_id)]['settings']['notifications'] = not current
                self.user_manager.save_users()
                
                status = "✅ مفعل" if not current else "❌ معطل"
                await query.edit_message_text(
                    f"✅ *تم تغيير إعداد الإشعارات:* {status}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                    ]])
                )
        
        elif data == "toggle_theme":
            if str(user_id) in self.user_manager.users:
                current = self.user_manager.users[str(user_id)]['settings'].get('theme', 'dark')
                new_theme = 'light' if current == 'dark' else 'dark'
                self.user_manager.users[str(user_id)]['settings']['theme'] = new_theme
                self.user_manager.save_users()
                
                theme_name = "فاتح ☀️" if new_theme == 'light' else "داكن 🌙"
                await query.edit_message_text(
                    f"✅ *تم تغيير الثيم إلى:* {theme_name}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                    ]])
                )
        
        # ========== الأوامر الأساسية ==========
        elif data == "help":
            await self.help_command(update, context)
        
        elif data == "stats":
            await self.stats_command(update, context)
        
        elif data == "about":
            await self.about_command(update, context)
        
        elif data == "platforms":
            text = """
📱 *المنصات المدعومة بالكامل:*

✅ يوتيوب - YouTube
✅ تيك توك - TikTok
✅ فيسبوك - Facebook
✅ تويتر - Twitter/X
✅ انستغرام - Instagram
✅ ريديت - Reddit
✅ تويش - Twitch
✅ ساوند كلاود - SoundCloud
✅ فيميو - Vimeo
✅ ديلي موشن - Dailymotion

✨ *جميع المنصات تعمل مع إمكانية المشاهدة والتحميل*
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
        
        elif data == "download_menu":
            await query.edit_message_text(
                "📥 *لتحميل فيديو*\n\nأرسل رابط الفيديو مباشرة",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
        
        elif data == "watch_menu":
            await query.edit_message_text(
                "🎬 *لمشاهدة فيديو*\n\nأرسل رابط الفيديو أو اختر من التصفح",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
        
        elif data == "search_menu":
            await query.edit_message_text(
                "🔍 *بحث متقدم*\n\nأرسل كلمة البحث",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
        
        elif data == "more_info":
            info = context.user_data.get('info', {})
            if info:
                more_text = f"""
ℹ️ *معلومات إضافية*

📹 *العنوان:* {self.clean_text_for_telegram(info.get('fulltitle', info.get('title', 'غير معروف')))}
👤 *الرافع:* {self.clean_text_for_telegram(info.get('uploader', 'غير معروف'))}
📅 *تاريخ الرفع:* {info.get('upload_date', 'غير معروف')}
🔗 *رابط القناة:* {info.get('uploader_url', 'غير متوفر')}
🎵 *الصوت:* {'✅' if info.get('acodec') != 'none' else '❌'}
🖼 *الدقة:* {info.get('resolution', 'غير معروف')}
⚡ *معدل الإطارات:* {info.get('fps', 'غير معروف')} fps

📊 *إحصائيات:*
• 👍 الإعجابات: {info.get('like_count', 0):,}
• 👁 المشاهدات: {info.get('view_count', 0):,}
                """
                
                await query.edit_message_text(
                    more_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_qualities")
                    ]])
                )
        
        elif data == "back_to_qualities":
            info = context.user_data.get('info', {})
            if info:
                info_text = f"""
{self.get_platform_emoji(info.get('extractor', ''))} *معلومات الفيديو*

📹 *العنوان:* {self.clean_text_for_telegram(info.get('title', 'غير معروف')[:100])}
⏱ *المدة:* {self.format_time(info.get('duration', 0))}
📊 *المنصة:* {info.get('extractor', 'غير معروفة')}

👇 *اختر ما تريد:*
                """
                
                keyboard = [
                    [InlineKeyboardButton("🎬 مشاهدة", callback_data=f"watch_now_{context.user_data.get('url')}")],
                    [InlineKeyboardButton("📥 تحميل", callback_data=f"download_menu_{context.user_data.get('url')}")],
                    [InlineKeyboardButton("ℹ️ معلومات إضافية", callback_data="more_info")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
                ]
                
                await query.edit_message_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        
        elif data == "cancel":
            await query.edit_message_text("✅ *تم الإلغاء*", parse_mode='Markdown')
        
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            context.user_data['selected_quality'] = quality
            
            keyboard = []
            for fmt_id, fmt_name in FORMATS.items():
                keyboard.append([InlineKeyboardButton(
                    f"📁 {fmt_name}", callback_data=f"download_{quality}_{fmt_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_qualities")])
            
            await query.edit_message_text(
                f"⚡ *الجودة:* {QUALITIES.get(quality, quality)}\n\n📁 *اختر الصيغة:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("download_"):
            parts = data.replace("download_", "").split("_")
            quality = parts[0]
            fmt = parts[1] if len(parts) > 1 else 'mp4'
            
            await self.download_video(update, context, quality, fmt)
    
    async def download_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, fmt: str = 'mp4'):
        """تحميل الفيديو"""
        query = update.callback_query
        url = context.user_data.get('url')
        info = context.user_data.get('info', {})
        title = info.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text("❌ الرابط غير صالح")
            return
        
        progress_msg = await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n"
            f"📹 *العنوان:* {title[:50]}\n"
            f"⚡ *الجودة:* {QUALITIES.get(quality, quality)}\n"
            f"📁 *الصيغة:* {FORMATS.get(fmt, fmt).upper()}\n\n"
            f"⏳ يرجى الانتظار...",
            parse_mode='Markdown'
        )
        
        try:
            if quality == 'best':
                if fmt == 'mp3':
                    format_spec = 'bestaudio/best'
                else:
                    format_spec = 'best[ext=mp4]/best'
            elif fmt == 'mp3':
                format_spec = 'bestaudio/best'
            else:
                format_spec = f'best[height<={quality}][ext={fmt}]/best[height<={quality}]/best'
            
            filename = f"{DOWNLOAD_FOLDER}/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.%(ext)s"
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': filename,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'geo_bypass': True,
            }
            
            if fmt == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            if os.path.exists(COOKIES_FILE):
                ydl_opts['cookiefile'] = COOKIES_FILE
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                downloaded_info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(downloaded_info)
                
                if fmt == 'mp3':
                    file = file.replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                else:
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test_file = file.replace('%(ext)s', ext).replace('.*', ext)
                        if os.path.exists(test_file):
                            file = test_file
                            break
                
                if os.path.exists(file):
                    size = os.path.getsize(file)
                    
                    # تحديث الإحصائيات
                    user_id = update.effective_user.id
                    video_info = {
                        'title': downloaded_info.get('title', 'فيديو'),
                        'extractor': downloaded_info.get('extractor', 'Unknown'),
                        'quality': quality,
                        'filesize': size,
                        'url': url,
                        'thumbnail': downloaded_info.get('thumbnail', '')
                    }
                    self.user_manager.update_stats(user_id, video_info)
                    
                    # إرسال الملف
                    with open(file, 'rb') as video_file:
                        clean_title = self.clean_text_for_telegram(downloaded_info.get('title', 'فيديو')[:100])
                        
                        caption = f"""
✅ *تم التحميل بنجاح!*

📹 *العنوان:* {clean_title}
⚡ *الجودة:* {QUALITIES.get(quality, quality)}
📁 *الصيغة:* {FORMATS.get(fmt, fmt).upper()}
📦 *الحجم:* {self.format_size(size)}
⏱ *المدة:* {self.format_time(downloaded_info.get('duration', 0))}

شكراً لاستخدامك البوت ❤️
                        """
                        
                        if fmt == 'mp3':
                            await context.bot.send_audio(
                                chat_id=update.effective_user.id,
                                audio=video_file,
                                caption=caption,
                                parse_mode='Markdown',
                                title=downloaded_info.get('title', 'صوت')[:50],
                                performer=downloaded_info.get('uploader', 'غير معروف')[:50],
                                duration=downloaded_info.get('duration', 0)
                            )
                        else:
                            await context.bot.send_video(
                                chat_id=update.effective_user.id,
                                video=video_file,
                                caption=caption,
                                parse_mode='Markdown',
                                supports_streaming=True,
                                duration=downloaded_info.get('duration', 0),
                                width=downloaded_info.get('width', 0),
                                height=downloaded_info.get('height', 0)
                            )
                    
                    os.remove(file)
                    await progress_msg.delete()
                    
                else:
                    await progress_msg.edit_text("❌ فشل في العثور على الملف المحمل")
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Download error: {error_msg}")
            
            if "requested format not available" in error_msg.lower():
                await progress_msg.edit_text("❌ الجودة المطلوبة غير متوفرة")
            else:
                await progress_msg.edit_text(f"❌ خطأ في التحميل: {error_msg[:100]}")
    
    # ========== تشغيل البوت ==========
    def run(self):
        """تشغيل البوت"""
        try:
            app = Application.builder().token(BOT_TOKEN).build()
            
            # أوامر البوت
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("help", self.help_command))
            app.add_handler(CommandHandler("settings", self.settings_command))
            app.add_handler(CommandHandler("stats", self.stats_command))
            app.add_handler(CommandHandler("history", self.history_command))
            app.add_handler(CommandHandler("about", self.about_command))
            app.add_handler(CommandHandler("browse", self.browse_command))
            app.add_handler(CommandHandler("favorites", self.show_favorites))
            app.add_handler(CommandHandler("watchlater", self.show_watchlater))
            
            # معالج الرسائل
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # معالج الأزرار
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # معالج الأخطاء
            app.add_error_handler(self.error_handler)
            
            # تشغيل البوت
            print("=" * 60)
            print("🚀 بوت الفيديوهات المتطور - الإصدار 3.0")
            print("=" * 60)
            print(f"✅ البوت يعمل بنجاح!")
            print(f"👥 المستخدمين: {len(self.user_manager.users)}")
            print(f"📁 المجلدات: {DOWNLOAD_FOLDER}, {THUMBNAIL_FOLDER}")
            print("=" * 60)
            print("📌 المميزات المضافة:")
            print("   • تصفح الفيديوهات بفئات")
            print("   • مشاهدة مباشرة")
            print("   • إضافة للمفضلة")
            print("   • قائمة المشاهدة لاحقاً")
            print("   • بحث متقدم")
            print("   • إحصائيات شخصية")
            print("   • إعدادات مخصصة")
            print("=" * 60)
            
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ خطأ في التشغيل: {e}")
            logger.error(f"Bot startup error: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأخطاء"""
        logger.error(f"خطأ: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى."
                )
        except:
            pass

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    bot = AdvancedVideoBot()
    bot.run()
