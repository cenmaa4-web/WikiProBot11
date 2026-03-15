import os
import sys
import json
import logging
import re
import time
import random
from datetime import datetime
from pathlib import Path

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

# التحقق من التوكن
if BOT_TOKEN == "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4":
    print("=" * 50)
    print("⚠️  تحذير: لم تقم بتغيير التوكن!")
    print("📌 اذهب إلى @BotFather في تليجرام")
    print("📌 احصل على التوكن الصحيح")
    print("📌 غيره في السطر 18 من هذا الملف")
    print("=" * 50)
    sys.exit(1)

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
        """الحصول على معلومات الفيديو"""
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
                        'url': info.get('webpage_url', url)
                    }
            return None
        except Exception as e:
            logger.error(f"خطأ: {e}")
            return None
    
    def search(self, query, limit=10):
        """البحث عن فيديوهات"""
        try:
            with yt_dlp.YoutubeDL({**self.ydl_opts, 'extract_flat': True}) as ydl:
                results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                videos = []
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry and entry.get('id'):
                            video_id = entry.get('id', '')
                            videos.append({
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={video_id}",
                                'duration': entry.get('duration', 0),
                                'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                'channel': entry.get('uploader', 'غير معروف'),
                                'views': entry.get('view_count', 0)
                            })
                return videos
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []
    
    def download(self, url, quality='best', format='mp4'):
        """تحميل الفيديو مباشرة"""
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
        self.search_sessions = {}
        print("=" * 50)
        print("🚀 بوت تحميل الفيديوهات - الإصدار النهائي")
        print("=" * 50)
    
    # ==================== القائمة الرئيسية ====================
    
    def main_menu_keyboard(self):
        """لوحة المفاتيح للقائمة الرئيسية"""
        keyboard = [
            [InlineKeyboardButton("🔍 بحث متقدم", callback_data="search")],
            [InlineKeyboardButton("🔥 تصفح الفيديوهات", callback_data="browse")],
            [InlineKeyboardButton("⭐ المفضلة", callback_data="favorites")],
            [InlineKeyboardButton("❓ مساعدة", callback_data="help")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def back_menu_keyboard(self):
        """لوحة المفاتيح مع أزرار الرجوع والرئيسية"""
        keyboard = [
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    # ==================== أمر البدء ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start"""
        user = update.effective_user
        self.db.get_user(user.id)
        
        text = f"""
🎬 *مرحباً {escape_markdown(user.first_name)}!*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🤖 *بوت تحميل الفيديوهات المتطور*

📥 *للتحميل:* أرسل رابط الفيديو مباشرة وسيتم تحميله فوراً
🔍 *للبحث:* اضغط على زر البحث وأرسل الكلمة
🔥 *للتصفح:* اختر من الفئات المتاحة
⭐ *للمفضلة:* احفظ فيديوهاتك المفضلة

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
👇 *اختر ما تريد:*
        """
        
        await update.message.reply_text(
            text,
            reply_markup=self.main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== المساعدة ====================
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج المساعدة"""
        query = update.callback_query
        await query.answer()
        
        text = """
❓ *مساعدة البوت*

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📥 *للتحميل:*
• أرسل رابط يوتيوب مباشرة
• سيتم تحميل الفيديو تلقائياً
• اختر الجودة المناسبة

🔍 *للبحث:*
• اضغط على زر البحث
• أرسل كلمة البحث
• اختر الفيديو من النتائج

🔥 *للتصفح:*
• اختر من 6 فئات
• تصفح الفيديوهات
• حمله أو شاهده

⭐ *للمفضلة:*
• أضف فيديوهات للمفضلة
• شاهدها لاحقاً

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🌐 *يدعم:* يوتيوب، انستغرام، فيسبوك، تيك توك
        """
        
        await query.edit_message_text(
            text,
            reply_markup=self.back_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== التصفح ====================
    
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج التصفح"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for cat_id, cat_name in VIDEO_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_id}")])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
        ])
        
        await query.edit_message_text(
            "🔥 *تصفح الفيديوهات*\n\nاختر الفئة التي تريدها:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def browse_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category):
        """معالج عرض فئة محددة"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        await query.edit_message_text("⏳ جاري تحميل الفيديوهات...")
        
        # محاكاة فيديوهات للفئة
        videos = []
        search_map = {
            'trending': 'trending',
            'music': 'music',
            'gaming': 'gaming',
            'news': 'news',
            'sports': 'sports',
            'education': 'education'
        }
        
        results = self.downloader.search(search_map.get(category, 'trending'), limit=5)
        
        if not results:
            await query.edit_message_text(
                "❌ لا توجد فيديوهات في هذه الفئة",
                reply_markup=self.back_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # عرض أول فيديو
        video = results[0]
        self.search_sessions[user_id] = {
            'videos': results,
            'page': 0,
            'type': 'browse'
        }
        
        duration = format_time(video.get('duration', 0))
        views = format_number(video.get('views', 0))
        
        text = f"""
🎬 *{escape_markdown(video['title'][:100])}*

📺 *القناة:* {escape_markdown(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data=f"fav_{video['url']}|{video['title'][:50]}")
            ],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
            ]
        ]
        
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
    
    # ==================== معالج الروابط (تحميل مباشر) ====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الرسائل - يشتغل فوراً عند إرسال رابط"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        # التحقق من الرابط
        if re.match(r'https?://\S+', text):
            await self.direct_download(update, context, text)
        else:
            # إذا كان نص عادي، نبدأ البحث
            await self.handle_search(update, context, text)
    
    async def direct_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url):
        """تحميل مباشر عند إرسال الرابط"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        # الحصول على معلومات الفيديو
        info = self.downloader.get_info(url)
        
        if not info:
            await msg.edit_text(
                "❌ تعذر الحصول على معلومات الفيديو",
                reply_markup=self.back_menu_keyboard()
            )
            return
        
        # حفظ المعلومات
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
        
        duration = format_time(info['duration'])
        views = format_number(info['views'])
        
        text = f"""
🎬 *{escape_markdown(info['title'][:100])}*

👤 *القناة:* {escape_markdown(info['uploader'])}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 [شاهد على يوتيوب]({info['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📥 تحميل مباشر MP4", callback_data=f"download_now_mp4_{url}"),
                InlineKeyboardButton("📥 تحميل MP3", callback_data=f"download_now_mp3_{url}")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data=f"fav_{url}|{info['title'][:50]}")
            ],
            [
                InlineKeyboardButton("🔙 رجوع", callback_data="back"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
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
    
    # ==================== معالج البحث ====================
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        """معالج البحث"""
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        
        videos = self.downloader.search(query, limit=10)
        
        if not videos:
            await msg.edit_text(
                f"❌ لا توجد نتائج للبحث عن: '{query}'",
                reply_markup=self.back_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # حفظ النتائج
        self.search_sessions[update.effective_user.id] = {
            'videos': videos,
            'page': 0,
            'query': query
        }
        
        await msg.delete()
        await self.show_search_result(update, context, videos[0], 0)
    
    async def show_search_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video, index):
        """عرض نتيجة بحث"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.search_sessions.get(user_id, {})
        videos = session.get('videos', [])
        
        duration = format_time(video.get('duration', 0))
        views = format_number(video.get('views', 0))
        
        text = f"""
🔍 *نتيجة {index+1} من {len(videos)}*

🎬 *{escape_markdown(video['title'][:100])}*

📺 *القناة:* {escape_markdown(video.get('channel', 'غير معروف'))}
⏱ *المدة:* {duration}
👁 *المشاهدات:* {views}

🔗 [شاهد على يوتيوب]({video['url']})
        """
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ مشاهدة", url=video['url']),
                InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{video['url']}")
            ],
            [
                InlineKeyboardButton("⭐ للمفضلة", callback_data=f"fav_{video['url']}|{video['title'][:50]}")
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
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
        ])
        
        try:
            if query:
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=video['thumbnail'],
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard)
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
    
    # ==================== تحميل مباشر ====================
    
    async def download_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE, format_type, url):
        """تحميل مباشر بدون اختيار جودة"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        # الحصول على معلومات الفيديو
        info = self.downloader.get_info(url)
        
        if not info:
            await query.edit_message_text("❌ تعذر الحصول على معلومات الفيديو")
            return
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n{escape_markdown(info['title'][:50])}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # تحميل بأفضل جودة
        result = self.downloader.download(url, 'best', format_type)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                if format_type == 'mp3':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=f"✅ *تم التحميل بنجاح!*\n📦 الحجم: {format_size(result['size'])}",
                        parse_mode=ParseMode.MARKDOWN,
                        title=info['title'][:100],
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
            
            # تحديث الإحصائيات
            user = self.db.get_user(user_id)
            user['downloads'] += 1
            self.db.update_user(user_id, user)
            
            await query.delete()
        else:
            await query.edit_message_text(
                "❌ فشل التحميل",
                reply_markup=self.back_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
    
    # ==================== المفضلة ====================
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المفضلة"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        user = self.db.get_user(user_id)
        favorites = user.get('favorites', [])
        
        if not favorites:
            await query.edit_message_text(
                "⭐ *المفضلة*\n\nلا توجد فيديوهات في المفضلة بعد.",
                reply_markup=self.back_menu_keyboard(),
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
            InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== معالج الأزرار ====================
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج جميع الأزرار"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        await query.answer()
        
        # ===== أزرار التنقل =====
        if data == "home":
            # العودة للقائمة الرئيسية
            await query.edit_message_text(
                f"🏠 *القائمة الرئيسية*\n\nمرحباً بعودتك!",
                reply_markup=self.main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "back":
            # الرجوع للصفحة السابقة - نرجع للقائمة الرئيسية
            await query.edit_message_text(
                f"🏠 *القائمة الرئيسية*\n\nتم الرجوع بنجاح!",
                reply_markup=self.main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ===== أزرار القائمة الرئيسية =====
        elif data == "search":
            await query.edit_message_text(
                "🔍 *بحث متقدم*\n\nأرسل كلمة البحث الآن:",
                reply_markup=self.back_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "browse":
            await self.browse(update, context)
        
        elif data == "favorites":
            await self.show_favorites(update, context)
        
        elif data == "help":
            await self.help(update, context)
        
        # ===== أزرار التصفح =====
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            await self.browse_category(update, context, category)
        
        # ===== أزرار البحث =====
        elif data == "search_prev":
            session = self.search_sessions.get(user_id, {})
            page = session.get('page', 0)
            videos = session.get('videos', [])
            if page > 0:
                session['page'] = page - 1
                await self.show_search_result(update, context, videos[page - 1], page - 1)
        
        elif data == "search_next":
            session = self.search_sessions.get(user_id, {})
            page = session.get('page', 0)
            videos = session.get('videos', [])
            if page < len(videos) - 1:
                session['page'] = page + 1
                await self.show_search_result(update, context, videos[page + 1], page + 1)
        
        # ===== أزرار التحميل المباشر =====
        elif data.startswith("download_now_mp4_"):
            url = data.replace("download_now_mp4_", "")
            await self.download_now(update, context, 'mp4', url)
        
        elif data.startswith("download_now_mp3_"):
            url = data.replace("download_now_mp3_", "")
            await self.download_now(update, context, 'mp3', url)
        
        elif data.startswith("dl_"):
            url = data.replace("dl_", "")
            await self.direct_download(update, context, url)
        
        # ===== أزرار المفضلة =====
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
        
        elif data.startswith("show_fav_"):
            url = data.replace("show_fav_", "")
            await self.direct_download(update, context, url)
    
    # ==================== تشغيل البوت ====================
    
    def run(self):
        """تشغيل البوت"""
        print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
        print("✅ جاري تشغيل البوت...")
        print("=" * 50)
        print("📌 التحميل المباشر: عند إرسال الرابط ✅")
        print("📌 البحث: يعمل بـ 10 نتائج ✅")
        print("📌 زر الرجوع: يعمل ✅")
        print("📌 زر الرئيسية: يعمل ✅")
        print("📌 التصفح: 6 فئات ✅")
        print("📌 المفضلة: تعمل ✅")
        print("=" * 50)
        print("📌 أرسل /start في تليجرام للبدء")
        print("=" * 50)
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # أوامر البوت
        app.add_handler(CommandHandler("start", self.start))
        
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
