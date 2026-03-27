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
from urllib.parse import urlparse

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

# قائمة المنصات المدعومة (التحميل المباشر)
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

# إعدادات yt-dlp المحسّنة
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

# خيارات بديلة للتحميل
FALLBACK_OPTIONS = [
    {'format': 'best[height<=480]'},
    {'format': 'best[height<=360]'},
    {'format': 'worst'},
]

# خيارات التحميل ليوتيوب فقط
YOUTUBE_DOWNLOAD_OPTIONS = {
    'video': {
        'name': '🎬 تحميل فيديو',
        'format': 'best[height<=720][filesize<50M]',
        'type': 'video'
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
    }
}

# إحصائيات
download_stats = {
    'total_downloads': 0,
    'total_searches': 0,
    'start_time': datetime.now()
}

# ============= دوال مساعدة =============

def format_number(num):
    """تنسيق الأرقام"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def format_duration(seconds):
    """تنسيق المدة"""
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    if hours > 0:
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

async def download_thumbnail(url: str, video_id: str) -> str:
    """تحميل الصورة المصغرة"""
    try:
        if not url:
            return None
        filename = os.path.join(THUMBNAIL_FOLDER, f"{video_id}.jpg")
        import urllib.request
        urllib.request.urlretrieve(url, filename)
        if os.path.exists(filename):
            return filename
    except Exception as e:
        logger.error(f"خطأ في تحميل الصورة: {e}")
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
                'description': info.get('description', ''),
                'thumbnail': info.get('thumbnail', ''),
                'url': url,
                'upload_date': info.get('upload_date', ''),
                'channel': info.get('channel', '')
            }
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب المعلومات: {e}")
        return None

async def download_media(url, download_type='video'):
    """تحميل الوسائط"""
    try:
        loop = asyncio.get_event_loop()
        
        def download_sync():
            try:
                options = YDL_OPTIONS.copy()
                
                if download_type in YOUTUBE_DOWNLOAD_OPTIONS:
                    opt = YOUTUBE_DOWNLOAD_OPTIONS[download_type]
                    options['format'] = opt['format']
                    if 'postprocessors' in opt:
                        options['postprocessors'] = opt['postprocessors']
                        # تغيير الامتداد للملفات الصوتية
                        if opt['type'] in ['audio', 'voice']:
                            ext = 'mp3' if opt['type'] == 'audio' else 'ogg'
                            options['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.' + ext)
                
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
                        if download_type in ['audio', 'voice']:
                            ext = 'mp3' if download_type == 'audio' else 'ogg'
                            test_filename = test_filename.rsplit('.', 1)[0] + '.' + ext
                        if os.path.exists(test_filename):
                            filename = test_filename
                    
                    if not filename or not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    if filename and os.path.exists(filename):
                        return filename, info
                    return None, None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل: {e}")
                return None, None
        
        result, info = await loop.run_in_executor(None, download_sync)
        return result, info
        
    except Exception as e:
        logger.error(f"خطأ عام: {e}")
        return None, None

# ============= البحث في يوتيوب =============

async def search_youtube(query: str, limit: int = 8):
    """البحث في يوتيوب"""
    try:
        search_query = f"ytsearch{limit}:{query}"
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(search_query, download=False)
            
            videos = []
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        videos.append({
                            'id': entry.get('id', ''),
                            'title': entry.get('title', 'بدون عنوان')[:80],
                            'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                            'duration': entry.get('duration', 0),
                            'uploader': entry.get('uploader', 'غير معروف')[:30],
                            'views': entry.get('view_count', 0),
                            'thumbnail': entry.get('thumbnail', '')
                        })
            return videos
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        return []

# ============= الأوامر الأساسية =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات!**\n\n"
        "📥 **طريقة الاستخدام:**\n\n"
        "**1️⃣ تحميل مباشر:**\n"
        "أرسل رابط من أي منصة وسأقوم بتحميل الفيديو فوراً\n"
        "• انستقرام - تيك توك - فيسبوك\n"
        "• بنترست - تويتر - وغيرها\n\n"
        "**2️⃣ تحميل من يوتيوب:**\n"
        "أرسل رابط يوتيوب، سأرسل لك:\n"
        "• صورة الفيديو مع رابط المشاهدة\n"
        "• 3 خيارات: فيديو - MP3 - بصمة صوتية\n\n"
        "**3️⃣ البحث في يوتيوب:**\n"
        "اكتب أي كلمة للبحث (مثل: 'أغاني حزينة')\n"
        "ستظهر نتائج متطورة مع صور ومعلومات\n\n"
        "✨ **فقط أرسل الرابط أو كلمة البحث!**"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مساعدة البوت"""
    help_msg = (
        "🆘 **دليل الاستخدام:**\n\n"
        "**📱 تحميل مباشر (جميع المنصات):**\n"
        "أرسل الرابط ← أستلم الفيديو\n\n"
        "**🎬 تحميل من يوتيوب:**\n"
        "أرسل رابط يوتيوب ← صورة + رابط مشاهدة + 3 أزرار\n\n"
        "**🔍 البحث في يوتيوب:**\n"
        "أكتب كلمة ← نتائج متطورة مع:\n"
        "• صورة الفيديو\n"
        "• معلومات كاملة\n"
        "• أزرار تحميل فيديو/صوت\n"
        "• مشاهدة مباشرة\n\n"
        "**📊 الأوامر:**\n"
        "/start - الصفحة الرئيسية\n"
        "/help - هذه المساعدة\n"
        "/stats - إحصائيات البوت\n\n"
        "**💡 أمثلة للبحث:**\n"
        "• 'موسيقى هادئة'\n"
        "• 'أهداف مباراة'\n"
        "• 'أفلام كرتون'\n"
        "• 'مقاطع مضحكة'"
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
        f"📥 **التحميلات:** {download_stats['total_downloads']}\n"
        f"🔍 **عمليات البحث:** {download_stats['total_searches']}\n"
        f"⏱️ **وقت التشغيل:** {int(hours)} ساعة {int(minutes)} دقيقة\n"
        f"🌐 **المنصات المدعومة:** {len(SUPPORTED_SITES)}\n\n"
        "🚀 **شكراً لاستخدامك البوت!**"
    )
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

def is_youtube_url(url):
    """التحقق إذا كان الرابط من يوتيوب"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    return 'youtube.com' in domain or 'youtu.be' in domain

def is_supported_url(url):
    """التحقق من أن الرابط مدعوم"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    if domain.startswith('www.'):
        domain = domain[4:]
    
    for site in SUPPORTED_SITES:
        if site in domain:
            return True
    
    # روابط مختصرة
    shorteners = ['bit.ly', 'tinyurl', 'shorturl', 'ow.ly', 'is.gd']
    if any(shortener in domain for shortener in shorteners):
        return True
    
    return False

# ============= معالج الروابط =============

async def handle_youtube_url(update: Update, url: str):
    """معالجة روابط يوتيوب (مع صورة وأزرار)"""
    progress_msg = await update.message.reply_text(
        "⏳ **جاري تحضير الفيديو...**",
        parse_mode='Markdown'
    )
    
    try:
        info = await get_video_info(url)
        
        if info:
            # تحميل الصورة المصغرة
            thumb_path = None
            if info['thumbnail']:
                thumb_path = await download_thumbnail(info['thumbnail'], str(int(time.time())))
            
            # تجهيز الأزرار
            keyboard = [
                [
                    InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"yt_video_{url}"),
                    InlineKeyboardButton("🎵 ملف MP3", callback_data=f"yt_audio_{url}"),
                    InlineKeyboardButton("🎤 بصمة صوتية", callback_data=f"yt_voice_{url}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # تجهيز المعلومات
            duration_str = format_duration(info['duration'])
            views_str = format_number(info['views'])
            
            caption = (
                f"🎬 **{info['title'][:100]}**\n\n"
                f"👤 **{info['uploader']}**\n"
                f"⏱️ **المدة:** {duration_str}\n"
                f"👁️ **المشاهدات:** {views_str}\n"
                f"❤️ **الإعجابات:** {format_number(info['likes'])}\n\n"
                f"👁️ **لمشاهدة الفيديو اضغط هنا:**\n[اضغط للمشاهدة مباشرة]({url})\n\n"
                f"📥 **اختر نوع التحميل:**"
            )
            
            await progress_msg.delete()
            
            if thumb_path and os.path.exists(thumb_path):
                with open(thumb_path, 'rb') as thumb_file:
                    await update.message.reply_photo(
                        photo=thumb_file,
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                try:
                    os.remove(thumb_path)
                except:
                    pass
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        else:
            await progress_msg.edit_text("❌ **فشل في جلب معلومات الفيديو**", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

async def handle_direct_url(update: Update, url: str):
    """معالجة الروابط المباشرة (تحميل فوري)"""
    progress_msg = await update.message.reply_text(
        "⏳ **جاري تحميل الفيديو...**\nالرجاء الانتظار",
        parse_mode='Markdown'
    )
    
    try:
        logger.info(f"تحميل مباشر: {url}")
        
        video_path = await download_video_direct(url, progress_msg)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            
            if file_size > 50:
                await progress_msg.edit_text(
                    f"❌ **الفيديو كبير جداً**\nالحجم: {file_size:.1f} MB\nالحد الأقصى: 50 MB",
                    parse_mode='Markdown'
                )
                os.remove(video_path)
                return
            
            await progress_msg.delete()
            
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"✅ **تم التحميل بنجاح!**\n📊 الحجم: {file_size:.1f} MB",
                    supports_streaming=True,
                    parse_mode='Markdown'
                )
            
            os.remove(video_path)
            download_stats['total_downloads'] += 1
            logger.info(f"✅ تم التحميل: {video_path}")
            
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
        logger.error(f"خطأ: {e}")
        await progress_msg.edit_text(
            f"❌ **حدث خطأ**\n{str(e)[:100]}",
            parse_mode='Markdown'
        )

async def download_video_direct(url, progress_msg=None):
    """تحميل الفيديو مباشرة (للمنصات الأخرى)"""
    
    async def update_progress(text):
        if progress_msg:
            try:
                await progress_msg.edit_text(text)
            except:
                pass
    
    try:
        loop = asyncio.get_event_loop()
        
        def try_download():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    filename = None
                    if 'requested_downloads' in info and info['requested_downloads']:
                        for download in info['requested_downloads']:
                            if 'filepath' in download:
                                filename = download['filepath']
                                break
                    
                    if not filename or not os.path.exists(filename):
                        test_filename = ydl.prepare_filename(info)
                        if os.path.exists(test_filename):
                            filename = test_filename
                    
                    if not filename or not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    return filename
            except Exception as e:
                logger.error(f"خطأ في التحميل: {e}")
                return None
        
        await update_progress("⏳ جاري تحميل الفيديو...")
        result = await loop.run_in_executor(None, try_download)
        return result
        
    except Exception as e:
        logger.error(f"خطأ عام: {e}")
        return None

# ============= البحث في يوتيوب =============

async def handle_search(update: Update, query: str):
    """معالجة البحث في يوتيوب"""
    download_stats['total_searches'] += 1
    
    progress_msg = await update.message.reply_text(
        f"🔍 **جاري البحث عن:** {query}\nالرجاء الانتظار...",
        parse_mode='Markdown'
    )
    
    try:
        videos = await search_youtube(query, limit=8)
        
        if videos:
            await progress_msg.delete()
            
            for i, video in enumerate(videos, 1):
                thumb_path = None
                if video['thumbnail']:
                    thumb_path = await download_thumbnail(video['thumbnail'], f"search_{i}_{int(time.time())}")
                
                duration_str = format_duration(video['duration'])
                views_str = format_number(video['views'])
                
                # أزرار لكل نتيجة
                keyboard = [
                    [
                        InlineKeyboardButton("🎬 فيديو", callback_data=f"yt_video_{video['url']}"),
                        InlineKeyboardButton("🎵 MP3", callback_data=f"yt_audio_{video['url']}"),
                        InlineKeyboardButton("🎤 بصمة", callback_data=f"yt_voice_{video['url']}")
                    ],
                    [
                        InlineKeyboardButton("👁️ مشاهدة", callback_data=f"watch_{video['url']}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                caption = (
                    f"{i}. **{video['title']}**\n"
                    f"👤 {video['uploader']} | ⏱️ {duration_str} | 👁️ {views_str}\n\n"
                    f"👁️ [لمشاهدة الفيديو اضغط هنا]({video['url']})"
                )
                
                if thumb_path and os.path.exists(thumb_path):
                    with open(thumb_path, 'rb') as thumb_file:
                        await update.message.reply_photo(
                            photo=thumb_file,
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    try:
                        os.remove(thumb_path)
                    except:
                        pass
                else:
                    await update.message.reply_text(
                        caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
        else:
            await progress_msg.edit_text(
                "❌ **لا توجد نتائج**\nجرب كلمات أخرى",
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
    
    # أزرار تحميل يوتيوب
    if data.startswith('yt_'):
        parts = data.split('_', 2)
        dl_type = parts[1]  # video, audio, voice
        url = parts[2]
        
        await query.edit_message_caption(
            caption=f"⏳ **جاري التحميل...**\n{YOUTUBE_DOWNLOAD_OPTIONS[dl_type]['name']}"
        )
        
        try:
            file_path, info = await download_media(url, dl_type)
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                
                with open(file_path, 'rb') as file:
                    if dl_type == 'video':
                        await query.message.reply_video(
                            video=file,
                            caption=f"✅ **تم التحميل!**\n📊 {file_size:.1f} MB\n{info.get('title', '')[:50]}",
                            supports_streaming=True
                        )
                    elif dl_type == 'voice':
                        await query.message.reply_voice(
                            voice=file,
                            caption=f"✅ **بصمة صوتية**\n📊 {file_size:.1f} MB"
                        )
                    elif dl_type == 'audio':
                        await query.message.reply_audio(
                            audio=file,
                            caption=f"✅ **ملف MP3**\n📊 {file_size:.1f} MB",
                            title=info.get('title', 'صوت')[:50]
                        )
                
                os.remove(file_path)
                download_stats['total_downloads'] += 1
                
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
    
    # مشاهدة مباشرة
    elif data.startswith('watch_'):
        url = data.replace('watch_', '')
        await query.edit_message_caption(
            caption=f"👁️ **مشاهدة مباشرة:**\n[اضغط هنا]({url})",
            parse_mode='Markdown'
        )

# ============= المعالج الرئيسي =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل الرئيسية"""
    text = update.message.text.strip()
    
    # التحقق إذا كان رابط
    if text.startswith(('http://', 'https://')):
        # التحقق من الرابط
        if not is_supported_url(text):
            await update.message.reply_text(
                "⚠️ **الرابط غير مدعوم**\n"
                "المنصات المدعومة: يوتيوب، تيك توك، انستقرام، فيسبوك، تويتر، بنترست وغيرها",
                parse_mode='Markdown'
            )
            return
        
        # إذا كان يوتيوب
        if is_youtube_url(text):
            await handle_youtube_url(update, text)
        else:
            # تحميل مباشر للمنصات الأخرى
            await handle_direct_url(update, text)
    else:
        # بحث في يوتيوب
        if len(text) > 2:
            await handle_search(update, text)
        else:
            await update.message.reply_text(
                "❌ **كلمة البحث قصيرة جداً**\nالرجاء كتابة كلمة أطول من حرفين",
                parse_mode='Markdown'
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ **حدث خطأ في البوت**\nالرجاء المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    except:
        pass

def cleanup():
    """تنظيف الملفات المؤقتة"""
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم تنظيف الملفات المؤقتة")
    except Exception as e:
        logger.error(f"خطأ في التنظيف: {e}")

def main():
    """تشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت...")
    
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
        print("🤖 البوت يعمل الآن!".center(60))
        print("="*60)
        print(f"📝 توكن: {TOKEN[:15]}...")
        print(f"📁 المجلد: {DOWNLOAD_FOLDER}")
        print(f"🌐 المنصات: {len(SUPPORTED_SITES)}")
        print("="*60)
        print("🎬 يوتيوب: صورة + رابط + 3 أزرار")
        print("📱 منصات أخرى: تحميل مباشر")
        print("🔍 بحث متطور في يوتيوب")
        print("="*60 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    from datetime import datetime
    main()
