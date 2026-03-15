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

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "7536390168:AAHZNO7XjIRBpwhMf3O5RojM9f2RrPYzUZ4"  # ضع التوكن هنا
DOWNLOAD_FOLDER = "downloads"
THUMBNAIL_FOLDER = "thumbnails"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_DURATION = 600  # 10 دقائق
USERS_FILE = "users.json"
COOKIES_FILE = "cookies.txt"

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
    '144': '144p',
    '240': '240p',
    '360': '360p',
    '480': '480p',
    '720': '720p',
    '1080': '1080p',
    'best': 'أفضل جودة'
}

# صيغ الفيديو
FORMATS = {
    'mp4': 'MP4',
    'webm': 'WEBM',
    'mp3': 'MP3 (صوت)'
}

# فئات الفيديو للتصفح
VIDEO_CATEGORIES = {
    'trending': '🔥 الأكثر مشاهدة',
    'music': '🎵 موسيقى',
    'gaming': '🎮 ألعاب',
    'news': '📰 أخبار',
    'sports': '⚽ رياضة',
    'education': '📚 تعليم'
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
                'favorites': [],
                'settings': {
                    'default_quality': 'best',
                },
                'history': []
            }
            self.save_users()

# ==================== البوت الرئيسي ====================
class VideoBot:
    def __init__(self):
        self.user_manager = UserManager()
        self.browse_sessions = {}
    
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
    
    def get_platform_emoji(self, platform: str) -> str:
        """إيموجي المنصة"""
        platforms = {
            'youtube': '📺',
            'instagram': '📷',
            'facebook': '📘',
            'twitter': '🐦',
            'tiktok': '🎵',
        }
        platform_lower = platform.lower()
        for key, emoji in platforms.items():
            if key in platform_lower:
                return emoji
        return '🎬'
    
    # ========== أوامر البوت ==========
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر البدء"""
        user = update.effective_user
        self.user_manager.add_user(user.id, user.username, user.first_name)
        
        welcome_text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت الفيديوهات المتطور 🤖

📥 *لتحميل فيديو:* أرسل الرابط
🔍 *للبحث:* اكتب أي كلمة
🔥 *للتصفح:* استخدم الأزرار

👥 المستخدمين: {len(self.user_manager.users)}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔥 تصفح", callback_data="browse"),
             InlineKeyboardButton("🔍 بحث", callback_data="search")],
            [InlineKeyboardButton("⭐ المفضلة", callback_data="favorites"),
             InlineKeyboardButton("❓ مساعدة", callback_data="help")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تصفح الفيديوهات"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("🔥 الأكثر مشاهدة", callback_data="cat_trending")],
            [InlineKeyboardButton("🎵 موسيقى", callback_data="cat_music")],
            [InlineKeyboardButton("🎮 ألعاب", callback_data="cat_gaming")],
            [InlineKeyboardButton("📰 أخبار", callback_data="cat_news")],
            [InlineKeyboardButton("⚽ رياضة", callback_data="cat_sports")],
            [InlineKeyboardButton("📚 تعليم", callback_data="cat_education")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]
        ]
        
        await query.edit_message_text(
            "🔥 *تصفح الفيديوهات*\n\nاختر الفئة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
        """عرض فيديوهات فئة معينة"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            f"⏳ جاري تحميل {VIDEO_CATEGORIES.get(category, category)}...",
            parse_mode='Markdown'
        )
        
        try:
            # البحث عن فيديوهات
            search_queries = {
                'trending': 'trending',
                'music': 'music video',
                'gaming': 'gaming',
                'news': 'news today',
                'sports': 'sports',
                'education': 'educational'
            }
            
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch6:{search_queries.get(category, category)}", download=False)
                
                if results and 'entries' in results:
                    videos = []
                    for video in results['entries']:
                        if video and video.get('title'):
                            videos.append({
                                'id': video.get('id', ''),
                                'title': video.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={video.get('id', '')}",
                                'duration': video.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{video.get('id', '')}/hqdefault.jpg",
                                'channel': video.get('uploader', 'غير معروف'),
                                'views': video.get('view_count', 0)
                            })
                    
                    # حفظ في الجلسة
                    user_id = update.effective_user.id
                    if user_id not in self.browse_sessions:
                        self.browse_sessions[user_id] = {}
                    self.browse_sessions[user_id][category] = videos
                    
                    # عرض أول فيديو
                    await self.show_video(update, context, category, 0)
                    
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
    
    async def show_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, index: int):
        """عرض فيديو مع الصورة والوصف"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        videos = self.browse_sessions.get(user_id, {}).get(category, [])
        if not videos or index >= len(videos):
            await query.edit_message_text("❌ لا يوجد فيديو")
            return
        
        video = videos[index]
        
        # نص الوصف
        text = f"""
🎬 *{video['title'][:100]}*

📺 *القناة:* {video['channel']}
⏱ *المدة:* {self.format_time(video['duration'])}
👁 *المشاهدات:* {video['views']:,}

🔗 *للمشاهدة على يوتيوب:* 
[اضغط هنا للمشاهدة]({video['url']})
        """
        
        # أزرار التنقل
        keyboard = []
        
        # أزرار الفيديو الحالي
        keyboard.append([
            InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
            InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
        ])
        
        # أزرار التنقل بين الفيديوهات
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"nav_{category}_{index-1}"))
        if index < len(videos) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"nav_{category}_{index+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع للفئات", callback_data="browse")])
        
        # إرسال الصورة مع الوصف
        try:
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=user_id,
                photo=video['thumbnail'],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            # إذا فشل إرسال الصورة، أرسل نص فقط
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل"""
        text = update.message.text
        user = update.effective_user
        self.user_manager.add_user(user.id, user.username, user.first_name)
        
        # التحقق من الرابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة رابط فيديو"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # معلومات الفيديو
                title = info.get('title', 'فيديو')
                duration = info.get('duration', 0)
                channel = info.get('uploader', 'غير معروف')
                thumbnail = info.get('thumbnail', '')
                video_url = url
                
                text = f"""
🎬 *{title[:100]}*

📺 *القناة:* {channel}
⏱ *المدة:* {self.format_time(duration)}

🔗 *للمشاهدة على يوتيوب:* 
[اضغط هنا للمشاهدة]({video_url})
                """
                
                keyboard = [
                    [InlineKeyboardButton("▶️ مشاهدة", url=video_url)],
                    [InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video_url}")]
                ]
                
                # إرسال مع الصورة
                try:
                    await msg.delete()
                    await update.message.reply_photo(
                        photo=thumbnail,
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
                
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {str(e)[:100]}")
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: {query}...")
        
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                
                if results and 'entries' in results:
                    videos = []
                    for video in results['entries']:
                        if video and video.get('title'):
                            videos.append({
                                'id': video.get('id', ''),
                                'title': video.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={video.get('id', '')}",
                                'duration': video.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{video.get('id', '')}/hqdefault.jpg",
                                'channel': video.get('uploader', 'غير معروف')
                            })
                    
                    # حفظ نتائج البحث
                    user_id = update.effective_user.id
                    if user_id not in self.browse_sessions:
                        self.browse_sessions[user_id] = {}
                    self.browse_sessions[user_id]['search'] = videos
                    
                    # عرض أول نتيجة
                    await self.show_video(update, context, 'search', 0)
                    await msg.delete()
                    
                else:
                    await msg.edit_text("❌ لا توجد نتائج")
                    
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {str(e)[:100]}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # أزرار التنقل
        if data == "back_start":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "search":
            await query.edit_message_text(
                "🔍 *بحث*\n\nأرسل كلمة البحث",
                parse_mode='Markdown'
            )
        
        elif data == "help":
            help_text = """
❓ *المساعدة*

📥 *للتحميل:* أرسل رابط فيديو
🔍 *للبحث:* اكتب أي كلمة
🔥 *للتصفح:* استخدم قائمة التصفح

🎬 *المشاهدة:* اضغط على زر "مشاهدة"
📥 *التحميل:* اضغط على زر "تحميل"

⭐ *المفضلة:* قريباً
            """
            await query.edit_message_text(
                help_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_start")
                ]])
            )
        
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            await self.browse_category(update, context, category)
        
        elif data.startswith("nav_"):
            parts = data.replace("nav_", "").split("_")
            category = parts[0]
            index = int(parts[1])
            await self.show_video(update, context, category, index)
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.start_download(update, context, url)
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """بدء عملية التحميل"""
        query = update.callback_query
        
        # خيارات الجودة
        keyboard = []
        for q in ['360', '480', '720', 'best']:
            keyboard.append([InlineKeyboardButton(
                f"🎬 {QUALITIES[q]}", callback_data=f"quality_{q}_{url}"
            )])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        
        await query.edit_message_text(
            "📥 *اختر جودة التحميل:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def download_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, url: str):
        """تحميل الفيديو"""
        query = update.callback_query
        
        await query.edit_message_text("⬇️ جاري التحميل...")
        
        try:
            # إعدادات التحميل
            if quality == 'best':
                format_spec = 'best[ext=mp4]'
            else:
                format_spec = f'best[height<={quality}][ext=mp4]'
            
            filename = f"{DOWNLOAD_FOLDER}/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': filename,
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if os.path.exists(filename):
                    # إرسال الفيديو
                    with open(filename, 'rb') as f:
                        await context.bot.send_video(
                            chat_id=update.effective_user.id,
                            video=f,
                            caption="✅ تم التحميل بنجاح!",
                            supports_streaming=True
                        )
                    
                    os.remove(filename)
                    await query.delete_message()
                    
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
    
    # ========== تشغيل البوت ==========
    def run(self):
        """تشغيل البوت"""
        app = Application.builder().token(BOT_TOKEN).build()
        
        # الأوامر
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        print("=" * 50)
        print("🚀 بوت الفيديوهات المتطور")
        print("=" * 50)
        print("✅ البوت يعمل!")
        print("=" * 50)
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)

# ==================== التشغيل ====================
if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
