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
import subprocess
import sys

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
DOWNLOAD_FOLDER = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_DURATION = 600  # 10 دقائق
USERS_FILE = "users.json"
COOKIES_FILE = "cookies.txt"  # ملف الكوكيز للمنصات التي تحتاج تسجيل دخول

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
    'best': 'أفضل جودة متاحة'
}

# صيغ الفيديو
FORMATS = {
    'mp4': 'MP4',
    'webm': 'WEBM',
    'mkv': 'MKV',
    'mp3': 'MP3 (صوت فقط)'
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
        self.check_ffmpeg()
    
    def check_ffmpeg(self):
        """التحقق من تثبيت ffmpeg"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            logger.info("FFmpeg مثبت بشكل صحيح")
        except FileNotFoundError:
            logger.warning("FFmpeg غير مثبت. بعض الميزات قد لا تعمل.")
            print("⚠️ FFmpeg غير مثبت. يرجى تثبيته لتحميل MP3 وبعض الصيغ الأخرى")
    
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
        """تنظيف النص من الأحرف الخاصة بتنسيق تليجرام"""
        # استبدال الأحرف الخاصة التي تسبب مشاكل في Markdown
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
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
• اختيار جودة التحميل (144p - 1080p)
• اختيار صيغة الفيديو (MP4, WEBM, MKV, MP3)
• بحث متقدم عن الفيديوهات
• إحصائيات شخصية للمستخدم
• إعدادات مخصصة لكل مستخدم
• معاينة الفيديو قبل التحميل

👥 *عدد المستخدمين:* {len(self.user_manager.users)}

🔰 *الأوامر المتاحة:*
/start - بدء البوت
/help - المساعدة
/settings - الإعدادات
/stats - إحصائياتك
/history - سجل التحميلات
/about - عن البوت

👇 *أرسل الرابط أو كلمة البحث الآن*
        """
        
        keyboard = [
            [InlineKeyboardButton("📱 المنصات المدعومة", callback_data="platforms"),
             InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats"),
             InlineKeyboardButton("❓ المساعدة", callback_data="help")],
            [InlineKeyboardButton("ℹ️ عن البوت", callback_data="about")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• الحذف التلقائي
• الإشعارات

⚠️ *ملاحظات مهمة:*
• بعض منصات التواصل تحتاج تسجيل دخول (مثل إنستغرام)
• يمكنك استخدام روابط عامة فقط
• الحد الأقصى للحجم: 50 ميجابايت
• الحد الأقصى للمدة: 10 دقائق

📌 *للدعم والإقتراحات:* @YourSupport
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

اختر الإعداد الذي تريد تعديله:
        """
        
        keyboard = [
            [InlineKeyboardButton("🎬 الجودة الافتراضية", callback_data="set_default_quality")],
            [InlineKeyboardButton("🗑 الحذف التلقائي", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton("🔔 الإشعارات", callback_data="toggle_notifications")],
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
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عن البوت"""
        about_text = f"""
ℹ️ *عن البوت*

🤖 *الاسم:* بوت تحميل الفيديوهات المتطور
📊 *الإصدار:* 2.0
👨‍💻 *المطور:* @YourUsername
📅 *تاريخ التحديث:* 2024

✨ *المميزات:*
• تحميل من 20+ منصة
• جودات متعددة حتى 1080p
• صيغ متعددة (MP4, MP3, MKV)
• بحث متقدم
• إحصائيات شخصية
• إعدادات مخصصة

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
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة الروابط"""
        msg = await update.message.reply_text("⏳ *جاري معالجة الرابط...*", parse_mode='Markdown')
        
        try:
            # إعدادات yt-dlp مع دعم أفضل للمنصات
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'ignoreerrors': True,
                'no_color': True,
                'geo_bypass': True,
            }
            
            # إضافة ملف الكوكيز إذا وجد
            if os.path.exists(COOKIES_FILE):
                ydl_opts['cookiefile'] = COOKIES_FILE
            
            # محاولة استخراج المعلومات
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    error_msg = str(e)
                    if "login required" in error_msg.lower() or "rate-limit" in error_msg.lower():
                        await msg.edit_text(
                            "❌ *هذه المنصة تحتاج تسجيل دخول*\n\n"
                            "للأسف، إنستغرام ومنصات أخرى تطلب تسجيل دخول.\n"
                            "جرب روابط من يوتيوب أو تيك توك أو فيسبوك العامة.",
                            parse_mode='Markdown'
                        )
                        return
                    elif "unsupported url" in error_msg.lower():
                        await msg.edit_text(
                            "❌ *الرابط غير مدعوم*\n\n"
                            "هذا الرابط غير مدعوم حالياً. جرب روابط من:\n"
                            "• يوتيوب\n"
                            "• تيك توك\n"
                            "• فيسبوك\n"
                            "• تويتر\n"
                            "• انستغرام (قد لا يعمل)",
                            parse_mode='Markdown'
                        )
                        return
                    else:
                        raise e
                
                # حفظ المعلومات
                context.user_data['url'] = url
                context.user_data['info'] = info
                
                # معلومات الفيديو
                title = info.get('title', 'غير معروف')
                duration = info.get('duration', 0)
                platform = info.get('extractor', 'غير معروفة')
                views = info.get('view_count', 0)
                uploader = info.get('uploader', 'غير معروف')
                
                # تنظيف النص من الأحرف الخاصة
                clean_title = self.clean_text_for_telegram(title[:100])
                clean_uploader = self.clean_text_for_telegram(uploader)
                
                # التحقق من القيود
                if duration > MAX_DURATION:
                    await msg.edit_text(
                        f"❌ عذراً، مدة الفيديو ({self.format_time(duration)}) تتجاوز الحد المسموح ({self.format_time(MAX_DURATION)})"
                    )
                    return
                
                # عرض معلومات الفيديو
                info_text = f"""
{self.get_platform_emoji(platform)} *معلومات الفيديو*

📹 *العنوان:* {clean_title}
⏱ *المدة:* {self.format_time(duration)}
📊 *المنصة:* {platform}
👤 *الرافع:* {clean_uploader}
👁 *المشاهدات:* {views:,}

👇 *اختر خيارات التحميل:*
                """
                
                # أزرار الجودة
                keyboard = []
                
                # صف الجودات الأول
                quality_row1 = []
                for q_id, q_name in list(QUALITIES.items())[:3]:
                    quality_row1.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row1)
                
                # صف الجودات الثاني
                quality_row2 = []
                for q_id, q_name in list(QUALITIES.items())[3:6]:
                    quality_row2.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row2)
                
                # صف الجودات الثالث
                quality_row3 = []
                for q_id, q_name in list(QUALITIES.items())[6:]:
                    quality_row3.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row3)
                
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
            error_message = str(e)
            logger.error(f"URL processing error: {error_message}")
            
            # رسائل خطأ مخصصة
            if "video unavailable" in error_message.lower():
                await msg.edit_text("❌ الفيديو غير متاح أو تم حذفه")
            elif "private" in error_message.lower():
                await msg.edit_text("❌ هذا الفيديو خاص ولا يمكن الوصول إليه")
            elif "copyright" in error_message.lower():
                await msg.edit_text("❌ هذا الفيديو محمي بحقوق النشر")
            elif "age" in error_message.lower() or "18" in error_message:
                await msg.edit_text("❌ هذا الفيديو مخصص للكبار فقط ( +18 )")
            else:
                await msg.edit_text(f"❌ خطأ في معالجة الرابط: {error_message[:200]}")
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 *جاري البحث عن:* '{query}'...", parse_mode='Markdown')
        
        try:
            # البحث في يوتيوب
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
                'ignoreerrors': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch8:{query}", download=False)
                
                if results and 'entries' in results:
                    keyboard = []
                    for i, video in enumerate(results['entries'][:8], 1):
                        if video and video.get('title'):
                            title = video.get('title', 'بدون عنوان')[:45]
                            duration = self.format_time(video.get('duration', 0))
                            channel = video.get('uploader', 'غير معروف')[:15]
                            
                            btn_text = f"{i}. {title} - {channel} ({duration})"
                            url = f"https://youtube.com/watch?v={video.get('id', '')}"
                            
                            keyboard.append([InlineKeyboardButton(
                                btn_text, callback_data=f"url_{url}"
                            )])
                    
                    if keyboard:
                        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                        
                        await msg.edit_text(
                            f"🔍 *نتائج البحث عن:* '{query}'\n\nاختر الفيديو المطلوب:",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                    else:
                        await msg.edit_text("❌ لم يتم العثور على نتائج")
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
            await self.settings_command(update, context)
            return
        
        elif data == "platforms":
            text = """
📱 *المنصات المدعومة بالكامل:*

✅ *يوتيوب* - YouTube (يعمل 100%)
✅ *تيك توك* - TikTok (يعمل 100%)
✅ *فيسبوك* - Facebook (يعمل 100%)
✅ *تويتر* - Twitter/X (يعمل 100%)
✅ *انستغرام* - Instagram (قد يحتاج تسجيل دخول)
✅ *ريديت* - Reddit (يعمل 100%)
✅ *تويش* - Twitch (يعمل 100%)
✅ *ساوند كلاود* - SoundCloud (يعمل 100%)
✅ *ديلي موشن* - Dailymotion (يعمل 100%)

⚠️ *ملاحظة:* بعض منصات التواصل تحتاج تسجيل دخول
📌 *يفضل استخدام روابط يوتيوب للحصول على أفضل نتيجة*
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
        
        elif data == "help":
            await self.help_command(update, context)
        
        elif data == "settings":
            await self.settings_command(update, context)
        
        elif data == "stats":
            await self.stats_command(update, context)
        
        elif data == "about":
            await self.about_command(update, context)
        
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
                clean_title = self.clean_text_for_telegram(info.get('fulltitle', info.get('title', 'غير معروف')))
                clean_uploader = self.clean_text_for_telegram(info.get('uploader', 'غير معروف'))
                
                more_text = f"""
ℹ️ *معلومات إضافية*

📹 *العنوان الكامل:* {clean_title}
👤 *رافع الفيديو:* {clean_uploader}
📅 *تاريخ الرفع:* {info.get('upload_date', 'غير معروف')}
🎵 *الصوت متوفر:* {'✅' if info.get('acodec') != 'none' else '❌'}
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
                        InlineKeyboardButton("🔙 رجوع للتحميل", callback_data="back_to_qualities")
                    ]])
                )
        
        elif data == "back_to_qualities":
            # العودة لاختيار الجودة
            info = context.user_data.get('info', {})
            if info:
                clean_title = self.clean_text_for_telegram(info.get('title', 'غير معروف')[:100])
                
                info_text = f"""
{self.get_platform_emoji(info.get('extractor', ''))} *معلومات الفيديو*

📹 *العنوان:* {clean_title}
⏱ *المدة:* {self.format_time(info.get('duration', 0))}
📊 *المنصة:* {info.get('extractor', 'غير معروفة')}

👇 *اختر الجودة:*
                """
                
                keyboard = []
                
                # صف الجودات الأول
                quality_row1 = []
                for q_id, q_name in list(QUALITIES.items())[:3]:
                    quality_row1.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row1)
                
                # صف الجودات الثاني
                quality_row2 = []
                for q_id, q_name in list(QUALITIES.items())[3:6]:
                    quality_row2.append(InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"quality_{q_id}"
                    ))
                keyboard.append(quality_row2)
                
                # صف الجودات الثالث
                quality_row3 = []
                for q_id, q_name in list(QUALITIES.items())[6:]:
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
        )
        
        try:
            # إعدادات التحميل
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
            
            # إضافة postprocessors للصوت
            if fmt == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            # إضافة ملف الكوكيز إذا وجد
            if os.path.exists(COOKIES_FILE):
                ydl_opts['cookiefile'] = COOKIES_FILE
            
            # التحميل
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    downloaded_info = ydl.extract_info(url, download=True)
                except Exception as e:
                    error_msg = str(e)
                    if "login required" in error_msg.lower() or "rate-limit" in error_msg.lower():
                        await progress_msg.edit_text(
                            "❌ *فشل التحميل*\n\n"
                            "هذه المنصة تحتاج تسجيل دخول. جرب رابط من منصة أخرى.",
                            parse_mode='Markdown'
                        )
                        return
                    else:
                        raise e
                
                # الحصول على اسم الملف
                file = ydl.prepare_filename(downloaded_info)
                
                # تعديل اسم الملف للصيغ المختلفة
                if fmt == 'mp3':
                    file = file.replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
                else:
                    # تغيير الامتداد إذا كان مختلفاً
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test_file = file.replace('%(ext)s', ext).replace('.*', ext)
                        if os.path.exists(test_file):
                            file = test_file
                            break
                
                if os.path.exists(file):
                    size = os.path.getsize(file)
                    
                    # تحديث إحصائيات المستخدم
                    user_id = update.effective_user.id
                    video_info = {
                        'title': downloaded_info.get('title', 'فيديو'),
                        'extractor': downloaded_info.get('extractor', 'Unknown'),
                        'quality': quality,
                        'filesize': size
                    }
                    self.user_manager.update_stats(user_id, video_info)
                    
                    # إرسال الملف حسب نوعه
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
                    
                    # حذف الملف بعد الإرسال
                    os.remove(file)
                    
                    # حذف رسالة التحميل
                    await progress_msg.delete()
                    
                else:
                    await progress_msg.edit_text("❌ فشل في العثور على الملف المحمل")
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Download error: {error_msg}")
            
            if "requested format not available" in error_msg.lower():
                await progress_msg.edit_text("❌ الجودة المطلوبة غير متوفرة لهذا الفيديو")
            elif "video unavailable" in error_msg.lower():
                await progress_msg.edit_text("❌ الفيديو غير متاح حالياً")
            else:
                await progress_msg.edit_text(f"❌ خطأ في التحميل: {error_msg[:200]}")
    
    # ========== تشغيل البوت ==========
    def run(self):
        """تشغيل البوت"""
        try:
            # إنشاء التطبيق
            app = Application.builder().token(BOT_TOKEN).build()
            
            # إضافة معالجات الأوامر
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CommandHandler("help", self.help_command))
            app.add_handler(CommandHandler("settings", self.settings_command))
            app.add_handler(CommandHandler("stats", self.stats_command))
            app.add_handler(CommandHandler("history", self.history_command))
            app.add_handler(CommandHandler("about", self.about_command))
            
            # إضافة معالج الرسائل النصية
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # إضافة معالج الأزرار
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # معالج الأخطاء
            app.add_error_handler(self.error_handler)
            
            # تشغيل البوت
            print("=" * 50)
            print("🚀 بوت تحميل الفيديوهات الاحترافي")
            print("=" * 50)
            print(f"✅ البوت يعمل بنجاح!")
            print(f"👥 عدد المستخدمين المسجلين: {len(self.user_manager.users)}")
            print(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")
            print(f"⚡ جاهز لاستقبال الروابط والبحث...")
            print("=" * 50)
            print("📌 ملاحظة: إنستغرام قد لا يعمل بسبب تحديثات الموقع")
            print("📌 يوتيوب وتيك توك وفيسبوك تعمل بشكل ممتاز")
            print("=" * 50)
            
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ خطأ في تشغيل البوت: {e}")
            logger.error(f"Bot startup error: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأخطاء"""
        logger.error(f"حدث خطأ: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى لاحقاً."
                )
        except:
            pass

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    # إنشاء وتشغيل البوت
    bot = AdvancedVideoBot()
    bot.run()
