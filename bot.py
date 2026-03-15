import os
import logging
import re
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
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

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
DOWNLOAD_FOLDER = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_DURATION = 600  # 10 دقائق
USERS_FILE = "users.json"

# حالات المحادثة
QUALITY_SELECTION, DOWNLOAD_CONFIRM, SETTINGS_MENU = range(3)

# إنشاء المجلدات
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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

# اللغات
LANGUAGES = {
    'ar': 'العربية',
    'en': 'English'
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
                'language': 'ar',
                'settings': {
                    'default_quality': 'best',
                    'auto_delete': True,
                    'notifications': True
                },
                'download_history': []
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
                'size': video_info.get('filesize', 0)
            })
            # Keep last 50 downloads
            if len(self.users[user_id]['download_history']) > 50:
                self.users[user_id]['download_history'] = self.users[user_id]['download_history'][-50:]
            self.save_users()

# ==================== البوت الرئيسي ====================
class AdvancedVideoBot:
    def __init__(self):
        self.user_manager = UserManager()
        self.active_downloads = {}
    
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
    
    # ========== أوامر البوت ==========
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر البدء"""
        user = update.effective_user
        self.user_manager.add_user(user.id, user.username, user.first_name)
        
        welcome_text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات الاحترافي الإصدار المتطور 🚀

📥 *أرسل لي رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات المتطورة:*
• تحميل من جميع المنصات (يوتيوب، تيك توك، انستغرام، فيسبوك، تويتر)
• اختيار جودة التحميل (144p - 4K)
• اختيار صيغة الفيديو (MP4, WEBM, MKV, MP3)
• بحث متقدم عن الفيديوهات
• إحصائيات شخصية للمستخدم
• إعدادات مخصصة لكل مستخدم
• دعم اللغات (العربية - الإنجليزية قريباً)
• تحميل قوائم التشغيل كاملة
• معاينة الفيديو قبل التحميل

👥 *عدد المستخدمين:* {len(self.user_manager.users)}

🔰 *الأوامر المتاحة:*
/start - بدء البوت
/help - المساعدة
/settings - الإعدادات
/stats - إحصائياتك
/history - سجل التحميلات
/about - عن البوت
/cancel - إلغاء العملية

👇 *أرسل الرابط أو كلمة البحث الآن*
        """
        
        keyboard = [
            [InlineKeyboardButton("📱 المنصات المدعومة", callback_data="platforms"),
             InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
             InlineKeyboardButton("❓ المساعدة", callback_data="help")],
            [InlineKeyboardButton("🎯 قناتي على يوتيوب", url="https://youtube.com"),
             InlineKeyboardButton("📢 قناة البوت", url="https://t.me/your_channel")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر المساعدة"""
        help_text = """
❓ *دليل استخدام البوت*

📥 *تحميل فيديو:*
1. أرسل رابط الفيديو من أي منصة
2. اختر الجودة المناسبة
3. اختر الصيغة المطلوبة
4. انتظر التحميل
5. استلم الفيديو

🔍 *البحث عن فيديوهات:*
1. اكتب أي كلمة للبحث
2. اختر الفيديو من النتائج
3. اتبع خطوات التحميل

⚙️ *الإعدادات المتوفرة:*
• الجودة الافتراضية
• صيغة التحميل المفضلة
• الحذف التلقائي
• اللغة

🎯 *الميزات الخاصة:*
• تحميل قوائم التشغيل كاملة
• تحميل الصوت فقط (MP3)
• معاينة الفيديو
• استئناف التحميل المتقطع

📊 *الإحصائيات:*
• عدد التحميلات
• إجمالي حجم التحميل
• سجل التحميلات

⚠️ *القيود:*
• الحد الأقصى للحجم: 50 ميجابايت
• الحد الأقصى للمدة: 10 دقائق

📌 *للدعم والإقتراحات:* @YourSupport
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
        await update.message.reply_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر الإعدادات"""
        user_id = str(update.effective_user.id)
        user_settings = self.user_manager.users.get(user_id, {}).get('settings', {})
        
        settings_text = f"""
⚙️ *الإعدادات الشخصية*

🔰 *الإعدادات الحالية:*
• الجودة الافتراضية: {QUALITIES.get(user_settings.get('default_quality', 'best'), 'أفضل جودة')}
• الحذف التلقائي: {'✅' if user_settings.get('auto_delete', True) else '❌'}
• الإشعارات: {'✅' if user_settings.get('notifications', True) else '❌'}
• اللغة: العربية

اختر الإعداد الذي تريد تعديله:
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 الجودة الافتراضية", callback_data="set_default_quality")],
            [InlineKeyboardButton("🗑 الحذف التلقائي", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton("🔔 الإشعارات", callback_data="toggle_notifications")],
            [InlineKeyboardButton("🌐 تغيير اللغة", callback_data="change_language")],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
        ]
        
        await update.message.reply_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS_MENU
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الإحصائيات"""
        user_id = str(update.effective_user.id)
        user_data = self.user_manager.users.get(user_id, {})
        
        # حساب إجمالي حجم التحميلات
        total_size = sum(d.get('size', 0) for d in user_data.get('download_history', []))
        
        stats_text = f"""
📊 *إحصائياتك الشخصية*

👤 *المستخدم:* {user_data.get('first_name', 'Unknown')}
📅 *تاريخ الانضمام:* {user_data.get('joined_date', 'Unknown')[:10]}

📥 *الإحصائيات:*
• عدد التحميلات: {user_data.get('downloads_count', 0)}
• إجمالي التحميلات: {user_data.get('total_downloads', 0)}
• حجم التحميلات: {self.format_size(total_size)}

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
    
    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض سجل التحميلات"""
        user_id = str(update.effective_user.id)
        user_data = self.user_manager.users.get(user_id, {})
        history = user_data.get('download_history', [])[-10:]
        
        if not history:
            await update.message.reply_text("📭 لا يوجد سجل تحميلات بعد")
            return
        
        history_text = "📜 *آخر 10 تحميلات:*\n\n"
        for i, item in enumerate(reversed(history), 1):
            date = item.get('date', '')[:10]
            title = item.get('title', 'Unknown')[:40]
            platform = item.get('platform', 'Unknown')
            quality = item.get('quality', 'Unknown')
            emoji = self.get_platform_emoji(platform)
            
            history_text += f"{i}. {emoji} {title}\n"
            history_text += f"   📅 {date} | ⚡ {quality} | {platform}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
        await update.message.reply_text(
            history_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عن البوت"""
        about_text = """
ℹ️ *عن البوت*

🤖 *الاسم:* بوت تحميل الفيديوهات المتطور
📊 *الإصدار:* 2.0
👨‍💻 *المطور:* @YourUsername
📅 *تاريخ التحديث:* 2024

✨ *المميزات:*
• تحميل من 20+ منصة
• جودات متعددة حتى 4K
• صيغ متعددة (MP4, MP3, MKV)
• بحث متقدم
• إحصائيات شخصية
• إعدادات مخصصة
• دعم اللغات

⚡ *الإحصائيات العامة:*
• عدد المستخدمين: {len(self.user_manager.users)}
• إجمالي التحميلات: {sum(u.get('total_downloads', 0) for u in self.user_manager.users.values())}

📊 *حالة البوت:* 🟢 نشط

🔰 *قنوات التواصل:*
• قناة التحديثات: @YourChannel
• الدعم الفني: @YourSupport

شكراً لاستخدامك البوت! ❤️
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]]
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
        else:
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
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # حفظ المعلومات
                context.user_data['url'] = url
                context.user_data['info'] = info
                
                # معلومات الفيديو
                title = info.get('title', 'غير معروف')
                duration = info.get('duration', 0)
                platform = info.get('extractor', 'غير معروفة')
                views = info.get('view_count', 0)
                likes = info.get('like_count', 0)
                uploader = info.get('uploader', 'غير معروف')
                
                # التحقق من القيود
                if duration > MAX_DURATION:
                    await msg.edit_text(
                        f"❌ عذراً، مدة الفيديو ({self.format_time(duration)}) تتجاوز الحد المسموح ({self.format_time(MAX_DURATION)})"
                    )
                    return
                
                # عرض معلومات الفيديو
                info_text = f"""
{self.get_platform_emoji(platform)} *معلومات الفيديو*

📹 *العنوان:* {title[:100]}
⏱ *المدة:* {self.format_time(duration)}
📊 *المنصة:* {platform}
👤 *الرافع:* {uploader}
👁 *المشاهدات:* {views:,}
❤️ *الإعجابات:* {likes:,}

👇 *اختر خيارات التحميل:*
                """
                
                # أزرار الجودة والصيغة
                keyboard = []
                
                # أزرار الجودة
                quality_row = []
                for i, (q_id, q_name) in enumerate(list(QUALITIES.items())[:3]):
                    quality_row.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row)
                
                quality_row2 = []
                for i, (q_id, q_name) in enumerate(list(QUALITIES.items())[3:6]):
                    quality_row2.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row2)
                
                quality_row3 = []
                for i, (q_id, q_name) in enumerate(list(QUALITIES.items())[6:9]):
                    quality_row3.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row3)
                
                # أزرار الصيغ
                format_row = []
                for fmt_id, fmt_name in FORMATS.items():
                    format_row.append(InlineKeyboardButton(
                        f"📁 {fmt_name}", callback_data=f"format_{fmt_id}"
                    ))
                keyboard.append(format_row)
                
                # أزرار إضافية
                keyboard.append([
                    InlineKeyboardButton("ℹ️ معلومات إضافية", callback_data="more_info"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
                ])
                
                await msg.edit_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await msg.edit_text(f"❌ خطأ في معالجة الرابط: {str(e)[:200]}")
            logger.error(f"URL processing error: {e}")
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 *جاري البحث عن:* '{query}'...", parse_mode='Markdown')
        
        try:
            # البحث في منصات متعددة
            platforms_to_search = [
                f"ytsearch5:{query}",  # يوتيوب
                # يمكن إضافة المزيد من المنصات هنا
            ]
            
            all_results = []
            
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for search_query in platforms_to_search:
                    try:
                        results = ydl.extract_info(search_query, download=False)
                        if results and 'entries' in results:
                            all_results.extend(results['entries'])
                    except:
                        continue
            
            if all_results:
                keyboard = []
                for i, video in enumerate(all_results[:8], 1):
                    if video:
                        title = video.get('title', 'بدون عنوان')[:45]
                        duration = self.format_time(video.get('duration', 0))
                        channel = video.get('uploader', 'غير معروف')[:15]
                        
                        btn_text = f"{i}. {title} - {channel} ({duration})"
                        url = f"https://youtube.com/watch?v={video.get('id', '')}"
                        
                        keyboard.append([InlineKeyboardButton(
                            btn_text, callback_data=f"url_{url}"
                        )])
                
                keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                
                await msg.edit_text(
                    f"🔍 *نتائج البحث عن:* '{query}'\n\nاختر الفيديو المطلوب:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await msg.edit_text("❌ لم يتم العثور على نتائج")
                
        except Exception as e:
            await msg.edit_text(f"❌ خطأ في البحث: {str(e)[:200]}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # قوائم التنقل الرئيسية
        if data == "back_to_start":
            await query.message.delete()
            await self.start(update, context)
            return
        
        elif data == "back_to_settings":
            await query.message.delete()
            await self.settings(update, context)
            return
        
        elif data == "platforms":
            text = """
📱 *المنصات المدعومة بالكامل:*

🎬 *يوتيوب* - YouTube
🎵 *تيك توك* - TikTok
📷 *انستغرام* - Instagram
📘 *فيسبوك* - Facebook
🐦 *تويتر* - Twitter/X
👽 *ريديت* - Reddit
📌 *بنترست* - Pinterest
🎥 *فيميو* - Vimeo
🎮 *تويش* - Twitch
🎵 *ساوند كلاود* - SoundCloud
📺 *ديلي موشن* - Dailymotion
🎬 *فيسبوك ووتش* - Facebook Watch

✨ *قريباً:* المزيد من المنصات!

📥 *أرسل الرابط وسأقوم بتحميله فوراً*
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
        
        elif data == "help":
            await self.help(update, context)
        
        elif data == "settings":
            await self.settings(update, context)
        
        elif data == "stats":
            await self.stats(update, context)
        
        elif data == "cancel":
            await query.edit_message_text("✅ *تم الإلغاء بنجاح*", parse_mode='Markdown')
        
        # معالجة إعدادات المستخدم
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
            user_id = str(update.effective_user.id)
            
            if user_id in self.user_manager.users:
                self.user_manager.users[user_id]['settings']['default_quality'] = quality
                self.user_manager.save_users()
            
            await query.edit_message_text(
                f"✅ *تم حفظ الجودة الافتراضية:* {QUALITIES.get(quality, quality)}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                ]])
            )
        
        elif data == "toggle_auto_delete":
            user_id = str(update.effective_user.id)
            if user_id in self.user_manager.users:
                current = self.user_manager.users[user_id]['settings'].get('auto_delete', True)
                self.user_manager.users[user_id]['settings']['auto_delete'] = not current
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
            user_id = str(update.effective_user.id)
            if user_id in self.user_manager.users:
                current = self.user_manager.users[user_id]['settings'].get('notifications', True)
                self.user_manager.users[user_id]['settings']['notifications'] = not current
                self.user_manager.save_users()
                
                status = "✅ مفعل" if not current else "❌ معطل"
                await query.edit_message_text(
                    f"✅ *تم تغيير إعداد الإشعارات:* {status}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                    ]])
                )
        
        elif data == "change_language":
            keyboard = [
                [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
                [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_settings")]
            ]
            
            await query.edit_message_text(
                "🌐 *اختر اللغة المناسبة:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("lang_"):
            lang = data.replace("lang_", "")
            user_id = str(update.effective_user.id)
            
            if user_id in self.user_manager.users:
                self.user_manager.users[user_id]['language'] = lang
                self.user_manager.save_users()
            
            lang_name = "العربية" if lang == 'ar' else "English"
            await query.edit_message_text(
                f"✅ *تم تغيير اللغة إلى:* {lang_name}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_to_settings")
                ]])
            )
        
        # معالجة التحميل
        elif data.startswith("url_"):
            url = data.replace("url_", "")
            await self.handle_url(update, context, url)
        
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            context.user_data['selected_quality'] = quality
            
            # عرض خيارات الصيغة بعد اختيار الجودة
            keyboard = []
            for fmt_id, fmt_name in FORMATS.items():
                keyboard.append([InlineKeyboardButton(
                    f"📁 {fmt_name}", callback_data=f"download_{quality}_{fmt_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_qualities")])
            
            await query.edit_message_text(
                f"⚡ *الجودة المختارة:* {QUALITIES.get(quality, quality)}\n\n📁 *اختر الصيغة:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("download_"):
            parts = data.replace("download_", "").split("_")
            quality = parts[0]
            fmt = parts[1] if len(parts) > 1 else 'mp4'
            
            await self.download_video(update, context, quality, fmt)
        
        elif data == "more_info":
            info = context.user_data.get('info', {})
            if info:
                more_text = f"""
ℹ️ *معلومات إضافية*

📹 *العنوان الكامل:* {info.get('fulltitle', info.get('title', 'غير معروف'))}
👤 *رافع الفيديو:* {info.get('uploader', 'غير معروف')}
📅 *تاريخ الرفع:* {info.get('upload_date', 'غير معروف')}
🔗 *رابط القناة:* {info.get('uploader_url', 'غير متوفر')}
🎵 *الصوت متوفر:* {'✅' if info.get('acodec') != 'none' else '❌'}
🖼 *الدقة المتوفرة:* {info.get('resolution', 'غير معروف')}
⚡ *معدل الإطارات:* {info.get('fps', 'غير معروف')} fps
🔊 *معدل الصوت:* {info.get('abr', 'غير معروف')} kbps

📊 *إحصائيات متقدمة:*
• 👍 الإعجابات: {info.get('like_count', 0):,}
• 👎 عدم الإعجاب: {info.get('dislike_count', 0):,}
• 👁 المشاهدات: {info.get('view_count', 0):,}
• 💬 التعليقات: {info.get('comment_count', 0):,}

🎯 *المنصة:* {info.get('extractor', 'غير معروفة')}
📦 *الحجم التقريبي:* {self.format_size(info.get('filesize', 0))}
                """
                
                await query.edit_message_text(
                    more_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع للتحميل", callback_data="back_to_qualities")
                    ]])
                )
        
        elif data == "back_to_qualities":
            # العودة لاختيار الجودة
            info = context.user_data.get('info', {})
            if info:
                info_text = f"""
{self.get_platform_emoji(info.get('extractor', ''))} *معلومات الفيديو*

📹 *العنوان:* {info.get('title', 'غير معروف')[:100]}
⏱ *المدة:* {self.format_time(info.get('duration', 0))}
📊 *المنصة:* {info.get('extractor', 'غير معروفة')}

👇 *اختر الجودة:*
                """
                
                keyboard = []
                quality_row = []
                for i, (q_id, q_name) in enumerate(list(QUALITIES.items())[:3]):
                    quality_row.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row)
                
                quality_row2 = []
                for i, (q_id, q_name) in enumerate(list(QUALITIES.items())[3:6]):
                    quality_row2.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row2)
                
                quality_row3 = []
                for i, (q_id, q_name) in enumerate(list(QUALITIES.items())[6:9]):
                    quality_row3.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row3)
                
                keyboard.append([
                    InlineKeyboardButton("ℹ️ معلومات إضافية", callback_data="more_info"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
                ])
                
                await query.edit_message_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
    
    async def download_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str, fmt: str = 'mp4'):
        """تحميل الفيديو"""
        query = update.callback_query
        url = context.user_data.get('url')
        info = context.user_data.get('info', {})
        title = info.get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text("❌ الرابط غير صالح، أرسل الرابط مرة أخرى")
            return
        
        # بدء التحميل
        progress_msg = await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n"
            f"📹 *العنوان:* {title[:50]}\n"
            f"⚡ *الجودة:* {QUALITIES.get(quality, quality)}\n"
            f"📁 *الصيغة:* {FORMATS.get(fmt, fmt).upper()}\n\n"
            f"⏳ يرجى الانتظار...",
            parse_mode='Markdown'
