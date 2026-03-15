#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import re
import time
import random
from datetime import datetime
from pathlib import Path

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== التوكن ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # غير هذا برقم التوكن الخاص بك

if BOT_TOKEN == "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4":
    print("=" * 50)
    print("⚠️  تحذير: لم تقم بتغيير التوكن!")
    print("📌 اذهب إلى @BotFather في تليجرام")
    print("📌 أنشئ بوت جديد أو احصل على التوكن")
    print("📌 غيره في السطر 16 من هذا الملف")
    print("=" * 50)
    sys.exit(1)

# ==================== الإعدادات ====================
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== إعدادات الفيديو ====================
QUALITIES = {
    '360': '360p',
    '480': '480p',
    '720': '720p',
    '1080': '1080p',
    'best': 'أفضل جودة'
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

# ==================== معالج الفيديو ====================
class VideoDownloader:
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
                return {
                    'title': info.get('title', 'بدون عنوان'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'غير معروف'),
                    'thumbnail': info.get('thumbnail', ''),
                    'url': info.get('webpage_url', url)
                }
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
    
    def download(self, url, quality='best'):
        try:
            if quality == 'best':
                format_spec = 'best[ext=mp4]/best'
            else:
                format_spec = f'best[height<={quality}][ext=mp4]/best'
            
            filename = DOWNLOAD_DIR / f"video_{int(time.time())}_{random.randint(1000,9999)}.mp4"
            
            ydl_opts = {
                **self.ydl_opts,
                'format': format_spec,
                'outtmpl': str(filename),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # البحث عن الملف
                for ext in ['.mp4', '.webm']:
                    test_file = str(filename).replace('.mp4', ext)
                    if Path(test_file).exists():
                        file = test_file
                        break
                else:
                    file = str(filename)
                
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

# ==================== البوت ====================
class Bot:
    def __init__(self):
        self.downloader = VideoDownloader()
        self.user_data = {}
        print("✅ البوت بدأ التهيئة...")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        print(f"👤 مستخدم جديد: {user.first_name}")
        
        text = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات من يوتيوب 🚀

📥 *أرسل رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات:*
• تحميل فيديوهات يوتيوب
• اختيار الجودة (360p - 1080p)
• بحث سريع مع صور
• تحميل مباشر

⚡ *الأوامر:*
/start - القائمة الرئيسية
/help - المساعدة
        """
        
        keyboard = [
            [InlineKeyboardButton("🔍 بحث", callback_data="search")],
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

📥 *للتحميل:* أرسل رابط يوتيوب
🔍 *للبحث:* اكتب أي كلمة
⚡ *للتحميل بجودة محددة:* اختر من القائمة

🌐 *يدعم:*
• يوتيوب
• يوتيوب شورتس
• قوائم التشغيل
        """
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        user_id = update.effective_user.id
        print(f"📩 رسالة من {user_id}: {text[:50]}")
        
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url):
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        info = self.downloader.get_info(url)
        
        if not info:
            await msg.edit_text("❌ لا يمكن الحصول على معلومات الفيديو")
            return
        
        self.user_data[update.effective_user.id] = {'url': url, 'info': info}
        
        text = f"""
🎬 *{info['title'][:100]}*

👤 {info['uploader']}
⏱ {format_time(info['duration'])}

🔗 [شاهد على يوتيوب]({info['url']})
        """
        
        keyboard = [
            [InlineKeyboardButton("📥 تحميل", callback_data="download_menu")],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
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
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: {query}...")
        
        videos = self.downloader.search(query, limit=5)
        
        if not videos:
            await msg.edit_text("❌ لا توجد نتائج")
            return
        
        keyboard = []
        for i, video in enumerate(videos, 1):
            text = f"{i}. {video['title'][:50]} - {video['channel']}"
            keyboard.append([InlineKeyboardButton(
                text, callback_data=f"select_{i-1}"
            )])
        
        self.user_data[update.effective_user.id] = {'search': videos}
        
        await msg.edit_text(
            "🔍 *نتائج البحث:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def download_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = self.user_data.get(user_id, {})
        
        if not data.get('url'):
            await query.edit_message_text("❌ لا توجد معلومات فيديو")
            return
        
        keyboard = []
        for q in ['360', '480', '720', '1080', 'best']:
            keyboard.append([InlineKeyboardButton(
                f"🎬 {QUALITIES[q]}", callback_data=f"dl_{q}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        
        await query.edit_message_text(
            "📥 *اختر الجودة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality):
        query = update.callback_query
        user_id = update.effective_user.id
        data = self.user_data.get(user_id, {})
        url = data.get('url')
        title = data.get('info', {}).get('title', 'فيديو')
        
        if not url:
            await query.edit_message_text("❌ لا يوجد رابط")
            return
        
        await query.edit_message_text(
            f"⬇️ *جاري التحميل...*\n\n{title[:50]}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        result = self.downloader.download(url, quality)
        
        if result['success']:
            with open(result['file'], 'rb') as f:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=f,
                    caption=f"✅ تم التحميل بنجاح!\n📦 {format_size(result['size'])}",
                    supports_streaming=True
                )
            
            Path(result['file']).unlink()
            await query.delete()
        else:
            await query.edit_message_text("❌ فشل التحميل")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        print(f"🔘 كلك: {data} من {user_id}")
        
        await query.answer()
        
        if data == "main_menu":
            await query.message.delete()
            await self.start(update, context)
        
        elif data == "search":
            await query.edit_message_text(
                "🔍 *بحث*\n\nأرسل كلمة البحث:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "help":
            await self.help(update, context)
        
        elif data == "download_menu":
            await self.download_menu(update, context)
        
        elif data.startswith("select_"):
            index = int(data.replace("select_", ""))
            videos = self.user_data.get(user_id, {}).get('search', [])
            if index < len(videos):
                video = videos[index]
                await self.handle_url(update, context, video['url'])
        
        elif data.startswith("dl_"):
            quality = data.replace("dl_", "")
            await self.start_download(update, context, quality)
    
    def run(self):
        print("=" * 50)
        print("🚀 بوت تحميل الفيديوهات - الإصدار النهائي")
        print("=" * 50)
        print(f"✅ التوكن: {BOT_TOKEN[:15]}...")
        print("✅ جاري تشغيل البوت...")
        print("=" * 50)
        print("📌 أرسل /start في تليجرام")
        print("=" * 50)
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        app.run_polling()

# ==================== التشغيل ====================
if __name__ == "__main__":
    bot = Bot()
    bot.run()
