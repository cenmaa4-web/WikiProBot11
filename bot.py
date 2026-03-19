#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
import json
import time
import shutil
import tempfile
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any, List, Tuple

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# Video download
import yt_dlp
from yt_dlp.utils import DownloadError

# Image processing
from PIL import Image

# Video processing
import moviepy.editor as mp

# HTTP requests
import aiohttp
import requests
from bs4 import BeautifulSoup

# إعداد التسجيل المتقدم
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# توكن البوت
TOKEN = os.environ.get("TOKEN", "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# مجلد مؤقت
DOWNLOAD_FOLDER = tempfile.mkdtemp()
THUMBNAIL_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'thumbnails')
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# قائمة المنصات المدعومة (محدثة)
SUPPORTED_PLATFORMS = {
    'youtube': ['youtube.com', 'youtu.be', 'm.youtube.com'],
    'tiktok': ['tiktok.com', 'vm.tiktok.com'],
    'instagram': ['instagram.com', 'instagr.am'],
    'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
    'twitter': ['twitter.com', 'x.com'],
    'pinterest': ['pinterest.com', 'pin.it'],
    'reddit': ['reddit.com', 'redd.it'],
    'linkedin': ['linkedin.com'],
    'dailymotion': ['dailymotion.com', 'dai.ly'],
    'vimeo': ['vimeo.com'],
    'twitch': ['twitch.tv', 'clips.twitch.tv'],
    'tumblr': ['tumblr.com'],
    'vk': ['vk.com', 'vkontakte.ru'],
    'telegram': ['t.me', 'telegram.org'],
    'whatsapp': ['whatsapp.com'],
    'snapchat': ['snapchat.com'],
    'discord': ['discord.com', 'discord.gg'],
    'spotify': ['spotify.com'],
    'soundcloud': ['soundcloud.com'],
    'rumble': ['rumble.com'],
    'odysee': ['odysee.com'],
    'bitchute': ['bitchute.com'],
    'odysee': ['odysee.com'],
    'lbry': ['lbry.tv'],
    'twitter_space': ['twitter.com/i/spaces'],
    'kick': ['kick.com'],
    'threads': ['threads.net'],
    'bluesky': ['bsky.app'],
    'mastodon': ['mastodon.social'],
}

# إعدادات yt-dlp المتقدمة
YDL_OPTIONS = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'extract_flat': False,
    'socket_timeout': 30,
    'retries': 10,
    'fragment_retries': 10,
    'file_access_retries': 5,
    'extractor_retries': 5,
    'continuedl': True,
    'buffersize': 1024,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
}

# خيارات تحميل متعددة
QUALITY_OPTIONS = {
    'ultra': {'format': 'best[height<=1080]', 'name': '🎥 فائقة (1080p)'},
    'high': {'format': 'best[height<=720]', 'name': '📹 عالية (720p)'},
    'medium': {'format': 'best[height<=480]', 'name': '📺 متوسطة (480p)'},
    'low': {'format': 'worst', 'name': '📱 منخفضة (للمساحة)'},
    'audio': {'format': 'bestaudio/best', 'name': '🎵 صوت فقط', 'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]}
}

class VideoDownloader:
    """كلاس متخصص لتحميل الفيديوهات"""
    
    def __init__(self):
        self.download_folder = DOWNLOAD_FOLDER
        self.thumbnail_folder = THUMBNAIL_FOLDER
        self.download_history = {}
        
    def detect_platform(self, url: str) -> Tuple[str, str]:
        """كشف المنصة من الرابط"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower().replace('www.', '')
        
        for platform, domains in SUPPORTED_PLATFORMS.items():
            for d in domains:
                if d in domain:
                    return platform, d
        return 'unknown', domain
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """الحصول على معلومات الفيديو"""
        try:
            loop = asyncio.get_event_loop()
            
            def extract_info():
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    return ydl.extract_info(url, download=False)
            
            info = await loop.run_in_executor(None, extract_info)
            
            if info:
                return {
                    'title': info.get('title', 'فيديو'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'غير معروف'),
                    'views': info.get('view_count', 0),
                    'likes': info.get('like_count', 0),
                    'description': info.get('description', '')[:200],
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': info.get('formats', []),
                    'filesize': self._get_filesize(info),
                }
            return None
            
        except Exception as e:
            logger.error(f"خطأ في استخراج المعلومات: {e}")
            return None
    
    def _get_filesize(self, info: Dict) -> float:
        """حساب حجم الملف"""
        if 'filesize' in info and info['filesize']:
            return info['filesize'] / (1024 * 1024)
        elif 'filesize_approx' in info and info['filesize_approx']:
            return info['filesize_approx'] / (1024 * 1024)
        return 0
    
    async def download_video(self, url: str, quality: str = 'high', progress_callback=None) -> Optional[Dict]:
        """تحميل الفيديو بالجودة المطلوبة"""
        try:
            loop = asyncio.get_event_loop()
            
            # اختيار الجودة
            quality_option = QUALITY_OPTIONS.get(quality, QUALITY_OPTIONS['high'])
            options = YDL_OPTIONS.copy()
            options.update(quality_option)
            
            # إضافة معالج التقدم
            if progress_callback:
                options['progress_hooks'] = [lambda d: self._progress_hook(d, progress_callback)]
            
            def download():
                with yt_dlp.YoutubeDL(options) as ydl:
                    try:
                        # تحميل الفيديو
                        info = ydl.extract_info(url, download=True)
                        
                        # البحث عن الملف
                        filename = self._find_downloaded_file(info, ydl)
                        
                        if filename and os.path.exists(filename):
                            file_size = os.path.getsize(filename) / (1024 * 1024)
                            return {
                                'path': filename,
                                'title': info.get('title', 'فيديو'),
                                'size': file_size,
                                'duration': info.get('duration', 0),
                                'thumbnail': info.get('thumbnail', ''),
                                'format': quality_option['name']
                            }
                        return None
                        
                    except Exception as e:
                        logger.error(f"خطأ في التحميل: {e}")
                        return None
            
            # تنفيذ التحميل
            result = await loop.run_in_executor(None, download)
            return result
            
        except Exception as e:
            logger.error(f"خطأ عام في التحميل: {e}")
            return None
    
    def _find_downloaded_file(self, info: Dict, ydl: yt_dlp.YoutubeDL) -> Optional[str]:
        """البحث عن الملف المحمل"""
        filename = None
        
        # الطريقة 1: من requested_downloads
        if 'requested_downloads' in info and info['requested_downloads']:
            for download in info['requested_downloads']:
                if 'filepath' in download:
                    filename = download['filepath']
                    break
        
        # الطريقة 2: prepare_filename
        if not filename or not os.path.exists(filename):
            test_filename = ydl.prepare_filename(info)
            if os.path.exists(test_filename):
                filename = test_filename
        
        # الطريقة 3: البحث في المجلد
        if not filename or not os.path.exists(filename):
            import glob
            files = glob.glob(os.path.join(self.download_folder, '*'))
            if files:
                filename = max(files, key=os.path.getctime)
        
        return filename if filename and os.path.exists(filename) else None
    
    def _progress_hook(self, d: Dict, callback):
        """معالج تقدم التحميل"""
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                asyncio.create_task(callback(f"⏳ جاري التحميل... {percent:.1f}%"))
            elif 'total_bytes_estimate' in d:
                percent = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                asyncio.create_task(callback(f"⏳ جاري التحميل... {percent:.1f}%"))
    
    async def download_thumbnail(self, url: str, video_id: str) -> Optional[str]:
        """تحميل الصورة المصغرة"""
        try:
            if not url:
                return None
            
            filename = os.path.join(self.thumbnail_folder, f"{video_id}.jpg")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(filename, 'wb') as f:
                            f.write(await resp.read())
                        return filename
            return None
            
        except Exception as e:
            logger.error(f"خطأ في تحميل الصورة: {e}")
            return None
    
    def cleanup(self, file_path: str):
        """تنظيف الملفات المؤقتة"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"✅ تم حذف: {file_path}")
        except Exception as e:
            logger.error(f"خطأ في التنظيف: {e}")

class TelegramBot:
    """كلاس البوت الرئيسي"""
    
    def __init__(self, token: str):
        self.token = token
        self.downloader = VideoDownloader()
        self.user_sessions = {}
        self.stats = {
            'total_downloads': 0,
            'total_users': 0,
            'start_time': datetime.now()
        }
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر /start"""
        user = update.effective_user
        self.stats['total_users'] += 1
        
        welcome_text = (
            f"🌟 **مرحباً {user.first_name}!**\n\n"
            f"أنا **أقوى بوت تحميل في العالم** 🌍\n\n"
            f"✨ **المميزات:**\n"
            f"• تحميل من **أكثر من 50 منصة**\n"
            f"• اختيار **الجودة** التي تريد\n"
            f"• تحميل **صوت فقط** MP3\n"
            f"• معلومات تفصيلية عن الفيديو\n"
            f"• سرعة تحميل خارقة 🚀\n\n"
            f"📥 **أرسل لي أي رابط وسأبدأ فوراً!**"
        )
        
        # أزرار التحكم
        keyboard = [
            [
                InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
                InlineKeyboardButton("❓ المساعدة", callback_data="help")
            ],
            [
                InlineKeyboardButton("🌟 المنصات المدعومة", callback_data="platforms"),
                InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        
        # التحقق من الرابط
        if not url.startswith(('http://', 'https://')):
            await update.message.reply_text(
                "❌ **رابط غير صحيح**\n\n"
                "الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https://",
                parse_mode='Markdown'
            )
            return
        
        # كشف المنصة
        platform, domain = self.downloader.detect_platform(url)
        
        # إرسال رسالة التحميل
        progress_msg = await update.message.reply_text(
            f"🔍 **جاري تحليل الرابط...**\n\n"
            f"🌐 **المنصة:** {platform.title()}\n"
            f"📎 **الرابط:** {domain}",
            parse_mode='Markdown'
        )
        
        try:
            # الحصول على معلومات الفيديو
            video_info = await self.downloader.get_video_info(url)
            
            if video_info:
                # حفظ الجلسة
                self.user_sessions[user_id] = {'url': url, 'info': video_info}
                
                # عرض معلومات الفيديو
                duration_min = video_info['duration'] // 60
                duration_sec = video_info['duration'] % 60
                
                info_text = (
                    f"📹 **معلومات الفيديو**\n\n"
                    f"**العنوان:** {video_info['title'][:100]}\n"
                    f"**الناشر:** {video_info['uploader']}\n"
                    f"**المدة:** {duration_min}:{duration_sec:02d}\n"
                    f"**المشاهدات:** {video_info['views']:,}\n"
                    f"**الإعجابات:** {video_info['likes']:,}\n"
                )
                
                if video_info['filesize'] > 0:
                    info_text += f"**الحجم التقريبي:** {video_info['filesize']:.1f} MB\n"
                
                # أزرار اختيار الجودة
                keyboard = []
                row = []
                
                for i, (key, quality) in enumerate(QUALITY_OPTIONS.items()):
                    if i % 2 == 0 and row:
                        keyboard.append(row)
                        row = []
                    row.append(InlineKeyboardButton(
                        quality['name'], 
                        callback_data=f"quality_{key}"
                    ))
                
                if row:
                    keyboard.append(row)
                
                # أزرار إضافية
                keyboard.append([
                    InlineKeyboardButton("ℹ️ تفاصيل أكثر", callback_data="more_info"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await progress_msg.edit_text(
                    info_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
            else:
                # إذا فشل استخراج المعلومات، نحاول التحميل مباشرة
                await progress_msg.edit_text(
                    "⏳ **جاري التحميل المباشر...**\n"
                    "قد يستغرق هذا دقيقة",
                    parse_mode='Markdown'
                )
                
                # تحميل الفيديو
                result = await self.downloader.download_video(
                    url, 
                    'high',
                    lambda text: self.update_progress(progress_msg, text)
                )
                
                if result:
                    await self.send_video(update, result, progress_msg)
                else:
                    await progress_msg.edit_text(
                        "❌ **فشل التحميل**\n\n"
                        "تأكد من:\n"
                        "• الرابط صحيح\n"
                        "• الفيديو متاح\n"
                        "• جرب رابط آخر",
                        parse_mode='Markdown'
                    )
                    
        except Exception as e:
            logger.error(f"خطأ في معالجة الرابط: {e}")
            await progress_msg.edit_text(
                f"❌ **حدث خطأ**\n\n"
                f"الخطأ: {str(e)[:100]}\n\n"
                f"حاول مرة أخرى أو جرب رابط آخر",
                parse_mode='Markdown'
            )
    
    async def update_progress(self, message, text):
        """تحديث رسالة التقدم"""
        try:
            await message.edit_text(text, parse_mode='Markdown')
        except:
            pass
    
    async def send_video(self, update: Update, result: Dict, progress_msg):
        """إرسال الفيديو"""
        try:
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(result['path'], 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=(
                        f"✅ **تم التحميل بنجاح!**\n\n"
                        f"📹 **{result['title'][:50]}**\n"
                        f"📊 **الحجم:** {result['size']:.1f} MB\n"
                        f"⚡ **الجودة:** {result['format']}\n\n"
                        f"⭐ **شكراً لاستخدام البوت**"
                    ),
                    supports_streaming=True,
                    parse_mode='Markdown',
                    read_timeout=60,
                    write_timeout=60
                )
            
            # تحديث الإحصائيات
            self.stats['total_downloads'] += 1
            
            # تنظيف
            self.downloader.cleanup(result['path'])
            
        except Exception as e:
            logger.error(f"خطأ في إرسال الفيديو: {e}")
            await update.message.reply_text(
                "❌ **حدث خطأ في إرسال الفيديو**\n\n"
                "حاول مرة أخرى",
                parse_mode='Markdown'
            )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data == "stats":
            # إحصائيات البوت
            uptime = datetime.now() - self.stats['start_time']
            hours = uptime.total_seconds() // 3600
            
            stats_text = (
                f"📊 **إحصائيات البوت**\n\n"
                f"📥 **التحميلات:** {self.stats['total_downloads']}\n"
                f"👥 **المستخدمين:** {self.stats['total_users']}\n"
                f"⏱️ **وقت التشغيل:** {int(hours)} ساعة\n"
                f"📁 **المساحة المستخدمة:** {self.get_folder_size():.1f} MB\n"
            )
            
            await query.edit_message_text(
                stats_text,
                parse_mode='Markdown'
            )
            
        elif data == "help":
            help_text = (
                "❓ **المساعدة**\n\n"
                "**كيفية الاستخدام:**\n"
                "1. أرسل رابط الفيديو\n"
                "2. اختر الجودة المناسبة\n"
                "3. انتظر التحميل\n\n"
                "**الأوامر:**\n"
                "/start - بدء البوت\n"
                "/stats - الإحصائيات\n"
                "/help - المساعدة\n"
                "/platforms - المنصات المدعومة\n\n"
                "**ملاحظات:**\n"
                "• الحد الأقصى 50 ميجابايت\n"
                "• الفيديوهات الطويلة تحتاج وقت\n"
                "• تأكد من أن الفيديو عام"
            )
            
            await query.edit_message_text(
                help_text,
                parse_mode='Markdown'
            )
            
        elif data == "platforms":
            platforms_text = "**🌟 المنصات المدعومة:**\n\n"
            
            for platform, domains in SUPPORTED_PLATFORMS.items():
                if platform != 'unknown':
                    platforms_text += f"• **{platform.title()}**\n"
            
            platforms_text += "\n✨ **وغيرها الكثير من المنصات!**"
            
            await query.edit_message_text(
                platforms_text,
                parse_mode='Markdown'
            )
            
        elif data.startswith("quality_"):
            quality = data.replace("quality_", "")
            
            if user_id in self.user_sessions:
                session = self.user_sessions[user_id]
                url = session['url']
                
                await query.edit_message_text(
                    f"⏳ **جاري التحميل بجودة {QUALITY_OPTIONS[quality]['name']}...**\n"
                    "الرجاء الانتظار",
                    parse_mode='Markdown'
                )
                
                # تحميل الفيديو
                result = await self.downloader.download_video(
                    url, 
                    quality,
                    lambda text: self.update_progress(query.message, text)
                )
                
                if result:
                    await self.send_video(update, result, query.message)
                else:
                    await query.edit_message_text(
                        "❌ **فشل التحميل**\n\n"
                        "حاول بجودة أقل أو جرب رابط آخر",
                        parse_mode='Markdown'
                    )
                    
        elif data == "more_info":
            if user_id in self.user_sessions:
                info = self.user_sessions[user_id]['info']
                
                more_info = (
                    f"ℹ️ **تفاصيل إضافية**\n\n"
                    f"**الوصف:**\n{info['description'][:500]}\n\n"
                    f"**عدد التنسيقات المتاحة:** {len(info['formats'])}\n"
                )
                
                await query.edit_message_text(
                    more_info,
                    parse_mode='Markdown'
                )
                
        elif data == "cancel":
            await query.edit_message_text(
                "✅ **تم الإلغاء**\n\n"
                "أرسل رابط جديد للتحميل",
                parse_mode='Markdown'
            )
            
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
    
    def get_folder_size(self) -> float:
        """حساب حجم المجلد"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(DOWNLOAD_FOLDER):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)
    
    def run(self):
        """تشغيل البوت"""
        logger.info("🚀 تشغيل البوت الخارق...")
        
        # إنشاء التطبيق
        application = Application.builder().token(self.token).build()
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.start_command))
        application.add_handler(CommandHandler("stats", self.start_command))
        application.add_handler(CommandHandler("platforms", self.start_command))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # بدء البوت
        logger.info("✅ البوت الخارق جاهز!")
        print("\n" + "="*60)
        print("🤖 **البوت الخارق يعمل الآن!**".center(60))
        print("="*60)
        print(f"📝 التوكن: {self.token[:15]}...")
        print(f"📁 المجلد: {DOWNLOAD_FOLDER}")
        print(f"🌟 المنصات: {len(SUPPORTED_PLATFORMS)} منصة")
        print("="*60 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def cleanup_all():
    """تنظيف كل الملفات المؤقتة"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم تنظيف كل الملفات المؤقتة")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

def main():
    """الدالة الرئيسية"""
    bot = TelegramBot(TOKEN)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 إيقاف البوت...")
    except Exception as e:
        logger.error(f"خطأ fatal: {e}")
    finally:
        cleanup_all()

if __name__ == '__main__':
    main()
