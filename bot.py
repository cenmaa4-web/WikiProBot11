#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp
import tempfile
import shutil
import re
import time
import json
from urllib.parse import urlparse, quote
from datetime import datetime, timedelta
import requests
from io import BytesIO

# ============= الكود الأصلي بالكامل =============

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت
TOKEN = os.environ.get("TOKEN", "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4")

# مجلد مؤقت للتحميلات
DOWNLOAD_FOLDER = tempfile.mkdtemp()
THUMBNAIL_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'thumbnails')
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
logger.info(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")

# ============= إضافات جديدة مع الحفاظ على القائمة الأصلية =============

# قائمة المنصات المدعومة الأصلية (كما هي)
SUPPORTED_SITES = [
    "youtube.com", "youtu.be",
    "tiktok.com",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "pinterest.com",
    "reddit.com",
    "linkedin.com",
    "dailymotion.com",
    "vimeo.com",
    "twitch.tv",
    "tumblr.com",
    "vk.com",
    "telegram.org",
    "whatsapp.com"
]

# إضافة منصات جديدة
EXTRA_SITES = [
    "snapchat.com",
    "discord.com",
    "spotify.com",
    "soundcloud.com",
    "rumble.com",
    "odysee.com",
    "bitchute.com",
    "lbry.tv",
    "kick.com",
    "threads.net",
    "bsky.app",
    "mastodon.social",
]

ALL_SUPPORTED_SITES = SUPPORTED_SITES + EXTRA_SITES

# إعدادات yt-dlp الأصلية
YDL_OPTIONS = {
    'format': 'best[height<=720][filesize<50M]',
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'extract_flat': False,
    'socket_timeout': 30,
    'retries': 5,
    'fragment_retries': 5,
    'file_access_retries': 3,
    'extractor_retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

# خيارات بديلة إذا فشل التحميل الأول
FALLBACK_OPTIONS = [
    {'format': 'best[height<=480]'},
    {'format': 'best[height<=360]'},
    {'format': 'worst'},
]

# ============= الميزات الجديدة المطلوبة =============

# خيارات التحميل (بدون اختيار جودة - أعلى جودة تلقائياً)
DOWNLOAD_OPTIONS = {
    'video': {
        'name': '🎬 تحميل فيديو',
        'format': 'best[height<=1080][filesize<50M]',  # أعلى جودة ممكنة
        'type': 'video'
    },
    'voice': {
        'name': '🎤 بصمة صوتية',
        'format': 'bestaudio/best',
        'type': 'voice',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'ogg',
            'preferredquality': '64',
        }]
    },
    'audio': {
        'name': '🎵 ملف صوتي MP3',
        'format': 'bestaudio/best',
        'type': 'audio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }
}

# خيارات إضافية
EXTRA_OPTIONS = {
    'watch': {
        'name': '👁️ مشاهدة مباشرة',
        'action': 'watch'
    },
    'info': {
        'name': 'ℹ️ معلومات الفيديو',
        'action': 'info'
    },
    'similar': {
        'name': '🔍 فيديوهات مشابهة',
        'action': 'similar'
    }
}

user_sessions = {}
download_stats = {
    'total_downloads': 0,
    'total_users': 0,
    'start_time': datetime.now()
}

# ============= دوال البحث =============

async def search_videos(query: str, limit: int = 5):
    """البحث عن فيديوهات"""
    try:
        search_query = f"ytsearch{limit}:{query}"
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if 'entries' in info:
                videos = []
                for entry in info['entries']:
                    videos.append({
                        'title': entry.get('title', 'بدون عنوان'),
                        'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                        'duration': entry.get('duration', 0),
                        'uploader': entry.get('uploader', 'غير معروف'),
                        'views': entry.get('view_count', 0),
                        'thumbnail': entry.get('thumbnail', '')
                    })
                return videos
        return []
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        return []

async def download_thumbnail(url: str, video_id: str) -> str:
    """تحميل الصورة المصغرة"""
    try:
        if not url:
            return None
        filename = os.path.join(THUMBNAIL_FOLDER, f"{video_id}.jpg")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return filename
    except Exception as e:
        logger.error(f"خطأ في تحميل الصورة: {e}")
    return None

# ============= الدوال الأصلية (بدون تغيير) =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب الأصلية + إضافات"""
    welcome_msg = (
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات المتطور جداً!**\n\n"
        "📥 **أرسل لي رابط فيديو أو كلمة للبحث وسأقوم بتحميله لك**\n\n"
        "✅ **المنصات المدعومة:**\n"
        "• YouTube - TikTok - Instagram\n"
        "• Facebook - Twitter/X - Pinterest\n"
        "• Reddit - LinkedIn - Dailymotion\n"
        "• Vimeo - Twitch - Tumblr\n"
        "• VK - Telegram - WhatsApp\n"
        "• Snapchat - Discord - Spotify\n"
        "• SoundCloud - Rumble - Odysee\n"
        "• **وغيرها الكثير...**\n\n"
        "⚡ **مميزات البوت:**\n"
        "• تحميل بأعلى جودة تلقائياً\n"
        "• 3 خيارات: فيديو - بصمة صوتية - MP3\n"
        "• البحث بالكلمات (لليوتيوب)\n"
        "• مشاهدة مباشرة للفيديو\n"
        "• فيديوهات مشابهة\n"
        "• معلومات تفصيلية\n\n"
        "✨ **أرسل الرابط أو اكتب كلمة للبحث!**"
    )
    
    # أزرار تفاعلية
    keyboard = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
            InlineKeyboardButton("❓ المساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton("🌐 جميع المنصات", callback_data="all_platforms"),
            InlineKeyboardButton("🔍 بحث متقدم", callback_data="search_help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=reply_markup)
    download_stats['total_users'] += 1

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مساعدة البوت"""
    help_msg = (
        "🆘 **كيفية استخدام البوت:**\n\n"
        "1️⃣ **لتحميل فيديو:** أرسل الرابط مباشرة\n"
        "2️⃣ **للبحث:** اكتب أي كلمة (مثل: 'قطط مضحكة')\n\n"
        "📝 **عند إرسال الرابط:**\n"
        "• ستظهر صورة الفيديو مع 3 أزرار:\n"
        "  🎬 **تحميل فيديو** - أعلى جودة تلقائياً\n"
        "  🎤 **بصمة صوتية** - رسالة صوتية\n"
        "  🎵 **ملف MP3** - صوت بجودة عالية\n\n"
        "🔍 **عند البحث:**\n"
        "• ستظهر نتائج البحث مع:\n"
        "  👁️ **مشاهدة مباشرة**\n"
        "  ℹ️ **معلومات الفيديو**\n"
        "  🔍 **فيديوهات مشابهة**\n\n"
        "📊 **الأوامر:**\n"
        "/start - بدء البوت\n"
        "/stats - الإحصائيات\n"
        "/help - المساعدة\n"
        "/search - بحث متقدم"
    )
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات البوت"""
    uptime = datetime.now() - download_stats['start_time']
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    stats_msg = (
        "📊 **إحصائيات البوت:**\n\n"
        f"✅ **الحالة:** يعمل\n"
        f"📥 **إجمالي التحميلات:** {download_stats['total_downloads']}\n"
        f"👥 **إجمالي المستخدمين:** {download_stats['total_users']}\n"
        f"⏱️ **وقت التشغيل:** {int(hours)} ساعة {int(minutes)} دقيقة\n"
        f"🌐 **المنصات المدعومة:** {len(ALL_SUPPORTED_SITES)}\n"
        f"⚡ **الإصدار:** 4.0 (النسخة الذهبية)\n\n"
        "🚀 **شكراً لاستخدامك البوت!**"
    )
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

def is_supported_url(url):
    """التحقق من أن الرابط مدعوم"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    if domain.startswith('www.'):
        domain = domain[4:]
    
    for site in ALL_SUPPORTED_SITES:
        if site in domain:
            return True
    
    shorteners = ['bit.ly', 'tinyurl', 'shorturl', 'ow.ly', 'is.gd']
    if any(shortener in domain for shortener in shorteners):
        return True
    
    return False

async def download_media(url, download_type='video'):
    """تحميل الوسائط (فيديو/صوت)"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            try:
                options = YDL_OPTIONS.copy()
                
                if download_type in DOWNLOAD_OPTIONS:
                    opt = DOWNLOAD_OPTIONS[download_type]
                    options['format'] = opt['format']
                    if 'postprocessors' in opt:
                        options['postprocessors'] = opt['postprocessors']
                        if opt.get('type') in ['voice', 'audio']:
                            options['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s')
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # البحث عن الملف
                    filename = None
                    
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                filename = download['filepath']
                                break
                    
                    if not filename or not os.path.exists(filename):
                        test_filename = ydl.prepare_filename(info)
                        # تغيير الامتداد للملفات الصوتية
                        if download_type in ['voice', 'audio']:
                            test_filename = test_filename.rsplit('.', 1)[0] + '.mp3'
                            if os.path.exists(test_filename):
                                filename = test_filename
                        elif os.path.exists(test_filename):
                            filename = test_filename
                    
                    if not filename or not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    if filename and os.path.exists(filename):
                        return filename
                    return None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل: {e}")
                return None
        
        result = await loop.run_in_executor(None, download_sync)
        return result
        
    except Exception as e:
        logger.error(f"خطأ عام: {e}")
        return None

async def get_video_info(url):
    """الحصول على معلومات الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def get_info():
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, get_info)
        
        if info:
            return {
                'title': info.get('title', 'بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'description': info.get('description', '')[:200],
                'thumbnail': info.get('thumbnail', ''),
                'url': url
            }
        return None
        
    except Exception as e:
        logger.error(f"خطأ في جلب المعلومات: {e}")
        return None

# ============= معالج الرسائل الرئيسي =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل (روابط أو بحث)"""
    text = update.message.text.strip()
    
    # التحقق إذا كان الرابط
    if text.startswith(('http://', 'https://')):
        await handle_url(update, context, text)
    else:
        # إذا كان بحث
        await handle_search(update, context, text)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """معالجة الروابط"""
    if not is_supported_url(url):
        await update.message.reply_text(
            "⚠️ **الرابط غير مدعوم**\n"
            "تأكد من الرابط أو جرب البحث بالكلمات",
            parse_mode='Markdown'
        )
        return
    
    # رسالة انتظار
    progress_msg = await update.message.reply_text(
        "⏳ **جاري تحضير الفيديو...**",
        parse_mode='Markdown'
    )
    
    try:
        # الحصول على معلومات الفيديو
        info = await get_video_info(url)
        
        if info:
            # تحميل الصورة المصغرة
            thumb_path = None
            if info['thumbnail']:
                thumb_path = await download_thumbnail(info['thumbnail'], str(time.time()))
            
            # تجهيز الأزرار (3 أزرار شفافة)
            keyboard = [
                [
                    InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"dl_video_{url}"),
                    InlineKeyboardButton("🎤 بصمة صوتية", callback_data=f"dl_voice_{url}"),
                    InlineKeyboardButton("🎵 ملف MP3", callback_data=f"dl_audio_{url}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # تجهيز معلومات الفيديو
            duration_min = info['duration'] // 60
            duration_sec = info['duration'] % 60
            
            caption = (
                f"🎬 **{info['title'][:100]}**\n\n"
                f"👤 **الناشر:** {info['uploader']}\n"
                f"⏱️ **المدة:** {duration_min}:{duration_sec:02d}\n"
                f"👁️ **المشاهدات:** {info['views']:,}\n"
                f"❤️ **الإعجابات:** {info['likes']:,}\n\n"
                f"📥 **اختر نوع التحميل:**"
            )
            
            await progress_msg.delete()
            
            if thumb_path:
                with open(thumb_path, 'rb') as thumb_file:
                    await update.message.reply_photo(
                        photo=thumb_file,
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                os.remove(thumb_path)
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
        else:
            # إذا فشل جلب المعلومات، نحاول التحميل المباشر
            await progress_msg.edit_text(
                "⏳ **جاري التحميل المباشر...**",
                parse_mode='Markdown'
            )
            
            video_path = await download_media(url, 'video')
            
            if video_path and os.path.exists(video_path):
                file_size = os.path.getsize(video_path) / (1024 * 1024)
                
                await progress_msg.delete()
                
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"✅ **تم التحميل بنجاح!**\n📊 الحجم: {file_size:.1f} MB",
                        supports_streaming=True
                    )
                
                os.remove(video_path)
                download_stats['total_downloads'] += 1
            else:
                await progress_msg.edit_text("❌ **فشل التحميل**", parse_mode='Markdown')
                
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """معالجة البحث بالكلمات"""
    progress_msg = await update.message.reply_text(
        f"🔍 **جاري البحث عن:** {query}",
        parse_mode='Markdown'
    )
    
    try:
        # البحث عن فيديوهات
        videos = await search_videos(query, limit=5)
        
        if videos:
            await progress_msg.delete()
            
            for i, video in enumerate(videos, 1):
                # تحميل الصورة المصغرة
                thumb_path = None
                if video['thumbnail']:
                    thumb_path = await download_thumbnail(video['thumbnail'], f"search_{i}")
                
                # أزرار إضافية
                keyboard = [
                    [
                        InlineKeyboardButton("👁️ مشاهدة", callback_data=f"watch_{video['url']}"),
                        InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{video['url']}"),
                        InlineKeyboardButton("🔍 مشابهة", callback_data=f"similar_{video['url']}")
                    ],
                    [
                        InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"dl_video_{video['url']}"),
                        InlineKeyboardButton("🎵 صوت", callback_data=f"dl_audio_{video['url']}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                duration_min = video['duration'] // 60
                duration_sec = video['duration'] % 60
                
                caption = (
                    f"{i}. **{video['title'][:100]}**\n"
                    f"👤 {video['uploader']} | ⏱️ {duration_min}:{duration_sec:02d} | 👁️ {video['views']:,}\n"
                )
                
                if thumb_path:
                    with open(thumb_path, 'rb') as thumb_file:
                        await update.message.reply_photo(
                            photo=thumb_file,
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    os.remove(thumb_path)
                else:
                    await update.message.reply_text(
                        caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
        else:
            await progress_msg.edit_text(
                "❌ **لا توجد نتائج للبحث**\nجرب كلمات أخرى",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ في البحث**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

# ============= معالج الأزرار =============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # أزرار التحميل
    if data.startswith('dl_'):
        parts = data.split('_', 2)
        dl_type = parts[1]  # video, voice, audio
        url = parts[2]
        
        await query.edit_message_caption(
            caption=f"⏳ **جاري التحميل...**\n{DOWNLOAD_OPTIONS[dl_type]['name']}"
        )
        
        try:
            file_path = await download_media(url, dl_type)
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                
                # إرسال حسب النوع
                with open(file_path, 'rb') as file:
                    if dl_type == 'video':
                        await query.message.reply_video(
                            video=file,
                            caption=f"✅ **تم التحميل!**\n📊 الحجم: {file_size:.1f} MB",
                            supports_streaming=True
                        )
                    elif dl_type == 'voice':
                        await query.message.reply_voice(
                            voice=file,
                            caption=f"✅ **بصمة صوتية**\n📊 الحجم: {file_size:.1f} MB"
                        )
                    elif dl_type == 'audio':
                        await query.message.reply_audio(
                            audio=file,
                            caption=f"✅ **ملف MP3**\n📊 الحجم: {file_size:.1f} MB",
                            title=os.path.basename(file_path)
                        )
                
                os.remove(file_path)
                download_stats['total_downloads'] += 1
                
                # إعادة الصورة الأصلية
                await query.edit_message_caption(
                    caption=query.message.caption_html,
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_caption(
                    caption="❌ **فشل التحميل**\nحاول مرة أخرى"
                )
                
        except Exception as e:
            logger.error(f"خطأ: {e}")
            await query.edit_message_caption(
                caption=f"❌ **خطأ:** {str(e)[:100]}"
            )
    
    # أزرار البحث الإضافية
    elif data.startswith('watch_'):
        url = data.replace('watch_', '')
        await query.edit_message_caption(
            caption=f"👁️ **مشاهدة مباشرة:**\n{url}"
        )
    
    elif data.startswith('info_'):
        url = data.replace('info_', '')
        await query.edit_message_caption(
            caption="⏳ **جلب المعلومات...**"
        )
        
        info = await get_video_info(url)
        if info:
            duration_min = info['duration'] // 60
            duration_sec = info['duration'] % 60
            
            info_text = (
                f"ℹ️ **معلومات الفيديو**\n\n"
                f"**العنوان:** {info['title'][:200]}\n"
                f"**الناشر:** {info['uploader']}\n"
                f"**المدة:** {duration_min}:{duration_sec:02d}\n"
                f"**المشاهدات:** {info['views']:,}\n"
                f"**الإعجابات:** {info['likes']:,}\n"
                f"**الوصف:** {info['description'][:300]}"
            )
            await query.edit_message_caption(caption=info_text)
        else:
            await query.edit_message_caption(caption="❌ **لا يمكن جلب المعلومات**")
    
    elif data.startswith('similar_'):
        url = data.replace('similar_', '')
        await query.edit_message_caption(
            caption="🔍 **جاري البحث عن فيديوهات مشابهة...**"
        )
        
        # استخدام عنوان الفيديو للبحث
        info = await get_video_info(url)
        if info:
            query_text = info['title'].split()[0:3]  # أول 3 كلمات
            query_text = ' '.join(query_text)
            await handle_search(update, context, query_text)
        else:
            await query.edit_message_caption(caption="❌ **لا يمكن العثور على فيديوهات مشابهة**")
    
    # أزرار القائمة الرئيسية
    elif data == "stats":
        uptime = datetime.now() - download_stats['start_time']
        hours = uptime.total_seconds() // 3600
        minutes = (uptime.total_seconds() % 3600) // 60
        
        stats_text = (
            "📊 **إحصائيات البوت:**\n\n"
            f"📥 **التحميلات:** {download_stats['total_downloads']}\n"
            f"👥 **المستخدمين:** {download_stats['total_users']}\n"
            f"⏱️ **وقت التشغيل:** {int(hours)} ساعة {int(minutes)} دقيقة\n"
            f"🌐 **المنصات:** {len(ALL_SUPPORTED_SITES)}"
        )
        await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "all_platforms":
        platforms_text = "**🌐 المنصات المدعومة:**\n\n"
        for i, site in enumerate(ALL_SUPPORTED_SITES, 1):
            platforms_text += f"{i}. {site}\n"
        await query.edit_message_text(platforms_text, parse_mode='Markdown')
    
    elif data == "search_help":
        search_text = (
            "🔍 **البحث المتقدم:**\n\n"
            "• اكتب أي كلمة للبحث\n"
            "• مثال: 'موسيقى هادئة'\n"
            "• مثال: 'مباراة كرة قدم'\n"
            "• مثال: 'أفلام كرتون'\n\n"
            "⚡ **نتائج البحث تشمل:**\n"
            "• صورة الفيديو\n"
            "• معلومات سريعة\n"
            "• مشاهدة مباشرة\n"
            "• فيديوهات مشابهة\n"
            "• تحميل فيديو أو صوت"
        )
        await query.edit_message_text(search_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ **حدث خطأ في البوت**\n"
                "الرجاء المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    except:
        pass

def cleanup():
    """تنظيف الملفات المؤقتة"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم التنظيف")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت الذهبي...")
    
    try:
        application = Application.builder().token(TOKEN).build()
        
        # الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # معالج الرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # معالج الأزرار
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # معالج الأخطاء
        application.add_error_handler(error_handler)
        
        print("\n" + "="*60)
        print("🤖 البوت الذهبي يعمل الآن!".center(60))
        print("="*60)
        print(f"📝 توكن: {TOKEN[:15]}...")
        print(f"📁 المجلد: {DOWNLOAD_FOLDER}")
        print(f"🌐 المنصات: {len(ALL_SUPPORTED_SITES)}")
        print("="*60 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
