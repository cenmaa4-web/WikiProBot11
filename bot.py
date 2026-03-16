import os
import re
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from urllib.parse import urlparse
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

# ================== الإعدادات ==================
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت

# إنشاء المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/videos", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/audios", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/images", exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/temp", exist_ok=True)

# ================== قائمة المنصات المدعومة ==================
PLATFORMS = {
    # منصات فيديو
    'youtube.com': {'name': '📺 YouTube', 'type': 'video', 'quality': True},
    'youtu.be': {'name': '📺 YouTube', 'type': 'video', 'quality': True},
    'youtube.com/shorts': {'name': '📱 YouTube Shorts', 'type': 'video', 'quality': True},
    
    # منصات التواصل
    'instagram.com': {'name': '📸 Instagram', 'type': 'all', 'quality': True},
    'instagram.com/p/': {'name': '📷 Instagram Post', 'type': 'all', 'quality': True},
    'instagram.com/reel/': {'name': '📱 Instagram Reel', 'type': 'video', 'quality': True},
    'instagram.com/stories/': {'name': '📖 Instagram Story', 'type': 'all', 'quality': True},
    
    'tiktok.com': {'name': '🎵 TikTok', 'type': 'video', 'quality': True},
    'tiktok.com/@': {'name': '🎵 TikTok', 'type': 'video', 'quality': True},
    
    'twitter.com': {'name': '🐦 Twitter', 'type': 'all', 'quality': True},
    'x.com': {'name': '🐦 Twitter', 'type': 'all', 'quality': True},
    
    'facebook.com': {'name': '📘 Facebook', 'type': 'all', 'quality': True},
    'fb.watch': {'name': '📘 Facebook', 'type': 'video', 'quality': True},
    'facebook.com/watch': {'name': '📘 Facebook Watch', 'type': 'video', 'quality': True},
    
    'reddit.com': {'name': '👽 Reddit', 'type': 'all', 'quality': True},
    'redd.it': {'name': '👽 Reddit', 'type': 'all', 'quality': True},
    
    'pinterest.com': {'name': '📌 Pinterest', 'type': 'all', 'quality': True},
    'pin.it': {'name': '📌 Pinterest', 'type': 'all', 'quality': True},
    
    'tumblr.com': {'name': '📱 Tumblr', 'type': 'all', 'quality': True},
    
    'linkedin.com': {'name': '💼 LinkedIn', 'type': 'video', 'quality': True},
    
    # منصات فيديو أخرى
    'dailymotion.com': {'name': '🎬 Dailymotion', 'type': 'video', 'quality': True},
    'vimeo.com': {'name': '🎥 Vimeo', 'type': 'video', 'quality': True},
    'twitch.tv': {'name': '🎮 Twitch', 'type': 'video', 'quality': True},
    'twitch.tv/clips': {'name': '🎮 Twitch Clip', 'type': 'video', 'quality': True},
    
    'bilibili.com': {'name': '🇨🇳 Bilibili', 'type': 'video', 'quality': True},
    'nicovideo.jp': {'name': '🇯🇵 NicoNico', 'type': 'video', 'quality': True},
    
    'rumble.com': {'name': '📹 Rumble', 'type': 'video', 'quality': True},
    'odysee.com': {'name': '🔗 Odysee', 'type': 'video', 'quality': True},
    'lbry.tv': {'name': '🔗 LBRY', 'type': 'video', 'quality': True},
    
    'streamable.com': {'name': '🎥 Streamable', 'type': 'video', 'quality': True},
    'gfycat.com': {'name': '🎞️ Gfycat', 'type': 'video', 'quality': True},
    'imgur.com': {'name': '🖼️ Imgur', 'type': 'all', 'quality': True},
    
    'vk.com': {'name': '🇷🇺 VK', 'type': 'all', 'quality': True},
    'ok.ru': {'name': '🇷🇺 OK', 'type': 'video', 'quality': True},
    
    'telegram.org': {'name': '✈️ Telegram', 'type': 'all', 'quality': False},
    't.me': {'name': '✈️ Telegram', 'type': 'all', 'quality': False},
    
    'whatsapp.com': {'name': '💬 WhatsApp', 'type': 'all', 'quality': False},
    
    'snapchat.com': {'name': '👻 Snapchat', 'type': 'all', 'quality': False},
    
    'weibo.com': {'name': '🇨🇳 Weibo', 'type': 'all', 'quality': True},
    'tieba.com': {'name': '🇨🇳 Baidu Tieba', 'type': 'all', 'quality': True},
    
    'naver.com': {'name': '🇰🇷 Naver', 'type': 'video', 'quality': True},
    'daum.net': {'name': '🇰🇷 Daum', 'type': 'video', 'quality': True},
    'kakao.com': {'name': '🇰🇷 Kakao', 'type': 'video', 'quality': True},
    
    'flickr.com': {'name': '📷 Flickr', 'type': 'image', 'quality': True},
    '500px.com': {'name': '📷 500px', 'type': 'image', 'quality': True},
    'unsplash.com': {'name': '📷 Unsplash', 'type': 'image', 'quality': True},
    'pexels.com': {'name': '📷 Pexels', 'type': 'all', 'quality': True},
    'pixabay.com': {'name': '📷 Pixabay', 'type': 'all', 'quality': True},
    
    'soundcloud.com': {'name': '🎵 SoundCloud', 'type': 'audio', 'quality': True},
    'spotify.com': {'name': '🎵 Spotify', 'type': 'audio', 'quality': True},
    'deezer.com': {'name': '🎵 Deezer', 'type': 'audio', 'quality': True},
    'tidal.com': {'name': '🎵 Tidal', 'type': 'audio', 'quality': True},
    'bandcamp.com': {'name': '🎵 Bandcamp', 'type': 'audio', 'quality': True},
    'mixcloud.com': {'name': '🎵 Mixcloud', 'type': 'audio', 'quality': True},
    'audiomack.com': {'name': '🎵 Audiomack', 'type': 'audio', 'quality': True},
    
    'bbc.co.uk': {'name': '📻 BBC', 'type': 'audio', 'quality': True},
    'npr.org': {'name': '📻 NPR', 'type': 'audio', 'quality': True},
    
    'v Live': {'name': '🇰🇷 V Live', 'type': 'video', 'quality': True},
    'vlive.tv': {'name': '🇰🇷 V Live', 'type': 'video', 'quality': True},
    
    'ted.com': {'name': '🎤 TED', 'type': 'video', 'quality': True},
    'coursera.org': {'name': '📚 Coursera', 'type': 'video', 'quality': True},
    'udemy.com': {'name': '📚 Udemy', 'type': 'video', 'quality': True},
}

# ================== إعدادات yt-dlp المتعددة ==================
def get_ydl_opts(media_type: str = 'auto', quality: str = 'best', url: str = ''):
    """إعدادات مخصصة حسب نوع الوسائط والمنصة"""
    
    base_opts = {
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'noplaylist': True,
        'geo_bypass': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
    }
    
    # تحديد نوع التحميل
    if media_type == 'audio':
        base_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif media_type == 'image':
        base_opts.update({
            'format': 'best',
        })
    else:  # video or auto
        if quality == 'best':
            base_opts['format'] = 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
        elif quality == 'medium':
            base_opts['format'] = 'best[height<=720][ext=mp4]/best[height<=720]'
        elif quality == 'low':
            base_opts['format'] = 'worst[ext=mp4]/worst'
        else:
            base_opts['format'] = 'best[ext=mp4]/best'
    
    # إعدادات خاصة للمنصات الصعبة
    if 'pinterest' in url:
        base_opts['extractor_args'] = {'pinterest': {'webpage': ['1']}}
        base_opts['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    
    if 'instagram' in url:
        base_opts['extractor_args'] = {'instagram': {'webpage': ['1']}}
        base_opts['headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)',
        }
    
    if 'tiktok' in url:
        base_opts['headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
    
    # قالب الحفظ
    base_opts['outtmpl'] = f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s.%(ext)s'
    
    return base_opts

# ================== دوال المساعدة ==================
def detect_platform(url: str) -> Tuple[str, str, bool]:
    """كشف المنصة ونوع المحتوى"""
    url_lower = url.lower()
    
    for domain, info in PLATFORMS.items():
        if domain in url_lower:
            return info['name'], info['type'], info['quality']
    
    # إذا لم نجد المنصة
    if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        return '🖼️ صورة مباشرة', 'image', True
    elif any(ext in url_lower for ext in ['.mp4', '.webm', '.mkv', '.avi']):
        return '🎬 فيديو مباشر', 'video', True
    elif any(ext in url_lower for ext in ['.mp3', '.wav', '.m4a', '.ogg']):
        return '🎵 صوت مباشر', 'audio', True
    
    return '🌐 رابط', 'unknown', True

def format_size(size: int) -> str:
    """تنسيق الحجم"""
    if size < 1024:
        return f"{size}B"
    elif size < 1024**2:
        return f"{size/1024:.1f}KB"
    elif size < 1024**3:
        return f"{size/1024**2:.1f}MB"
    return f"{size/1024**3:.1f}GB"

def format_duration(seconds: int) -> str:
    """تنسيق المدة"""
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def clean_old_files():
    """تنظيف الملفات القديمة"""
    try:
        now = time.time()
        for folder in ['temp', 'videos', 'audios', 'images']:
            folder_path = Path(f"{DOWNLOAD_DIR}/{folder}")
            if folder_path.exists():
                for f in folder_path.glob('*'):
                    if f.is_file() and now - f.stat().st_mtime > 600:  # 10 دقائق
                        f.unlink()
    except:
        pass

async def extract_info_smart(url: str) -> Tuple[Optional[Dict], Optional[str]]:
    """استخراج المعلومات بذكاء مع محاولات متعددة"""
    
    # محاولات متعددة
    attempts = [
        {'headers': None},
        {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}},
        {'headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'}},
        {'cookies': True},
    ]
    
    platform_name, media_type, has_quality = detect_platform(url)
    
    for attempt in attempts:
        try:
            opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'socket_timeout': 15,
            }
            
            if 'headers' in attempt and attempt['headers']:
                opts['headers'] = attempt['headers']
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info:
                    return {
                        'title': info.get('title', 'محتوى')[:100],
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', info.get('channel', 'غير معروف')),
                        'views': info.get('view_count', 0),
                        'likes': info.get('like_count', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'platform': platform_name,
                        'type': media_type,
                        'has_quality': has_quality,
                        'filesize': info.get('filesize', info.get('filesize_approx', 0)),
                        'width': info.get('width', 0),
                        'height': info.get('height', 0),
                        'extractor': info.get('extractor', ''),
                    }, None
                    
        except Exception as e:
            continue
    
    return None, "لم نتمكن من تحليل الرابط"

async def download_smart(url: str, media_type: str = 'auto', quality: str = 'best') -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """تحميل ذكي مع محاولات متعددة"""
    
    attempts = 0
    max_attempts = 3
    last_error = None
    
    while attempts < max_attempts:
        try:
            opts = get_ydl_opts(media_type, quality, url)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # البحث عن الملف
                if media_type == 'audio':
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = ydl.prepare_filename(info)
                    if not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'
                
                # التحقق من وجود الملف
                if os.path.exists(filename):
                    size = os.path.getsize(filename)
                    if size <= MAX_FILE_SIZE:
                        return filename, None, info
                    else:
                        os.remove(filename)
                        return None, f"الملف كبير ({format_size(size)})", info
                
                # البحث بامتدادات مختلفة
                base = filename.rsplit('.', 1)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.jpg', '.png', '.gif']:
                    test_file = base + ext
                    if os.path.exists(test_file):
                        size = os.path.getsize(test_file)
                        if size <= MAX_FILE_SIZE:
                            return test_file, None, info
                        else:
                            os.remove(test_file)
                            return None, f"الملف كبير ({format_size(size)})", info
                
                attempts += 1
                await asyncio.sleep(1)
                
        except Exception as e:
            last_error = str(e)
            attempts += 1
            await asyncio.sleep(1)
    
    return None, last_error or "فشل التحميل بعد عدة محاولات", None

# ================== معالجات البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية البوت"""
    text = """
🎯 <b>بوت التحميل الشامل</b>

📥 <b>أرسل أي رابط</b> من أي منصة وسأحمل لك:
• 🎬 فيديو
• 🎵 صوت
• 🖼️ صور
• 📱 قصص
• 🎞️ GIF

<b>المنصات المدعومة:</b>
• يوتيوب • انستغرام • تيك توك • تويتر • فيسبوك
• بنترست • ريديت • سناب شات • واتساب • تليجرام
• ساوند كلاود • سبوتيفاي • والمئات غيرها

⚡ <b>فقط أرسل الرابط!</b>
    """
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ أرسل رابط صحيح")
        return
    
    clean_old_files()
    
    # رسالة انتظار
    msg = await update.message.reply_text("🔍 جاري تحليل الرابط...")
    
    try:
        # استخراج المعلومات
        info, error = await extract_info_smart(url)
        
        if error or not info:
            await msg.edit_text(
                f"❌ {error or 'لا يمكن تحليل الرابط'}\n\n"
                "💡 تأكد من:\n"
                "• صحة الرابط\n"
                "• المحتوى عام وليس خاص\n"
                "• جرب رابط آخر"
            )
            return
        
        # حفظ المعلومات
        context.user_data['url'] = url
        context.user_data['info'] = info
        
        # تحضير الأزرار حسب نوع المحتوى
        keyboard = []
        
        if info['type'] in ['video', 'all', 'unknown']:
            if info['has_quality']:
                keyboard.append([
                    InlineKeyboardButton("🎬 HD", callback_data="dl_video_hd"),
                    InlineKeyboardButton("🎬 720p", callback_data="dl_video_720"),
                    InlineKeyboardButton("🎬 480p", callback_data="dl_video_480")
                ])
            else:
                keyboard.append([InlineKeyboardButton("🎬 تحميل فيديو", callback_data="dl_video")])
        
        if info['type'] in ['audio', 'all', 'unknown']:
            keyboard.append([
                InlineKeyboardButton("🎵 MP3", callback_data="dl_audio"),
            ])
        
        if info['type'] in ['image', 'all', 'unknown']:
            keyboard.append([
                InlineKeyboardButton("🖼️ صور", callback_data="dl_image"),
            ])
        
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        
        # رسالة المعلومات
        duration = format_duration(info.get('duration', 0))
        views = f"{info.get('views', 0):,}" if info.get('views') else "غير معروف"
        
        text = f"""
{info['platform']} ✅

📹 <b>{info['title']}</b>
👤 {info['uploader']}
⏱️ المدة: {duration}
👁️ المشاهدات: {views}

📥 <b>اختر نوع التحميل:</b>
        """
        
        await msg.delete()
        
        # إرسال مع الصورة إن وجدت
        if info.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await update.message.reply_text(
                text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {str(e)[:100]}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("✅ تم الإلغاء")
        return
    
    url = context.user_data.get('url')
    info = context.user_data.get('info', {})
    
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً")
        return
    
    # تحديد نوع التحميل
    dl_type = query.data.replace("dl_", "")
    media_type = 'video'
    quality = 'best'
    
    if dl_type == 'video_hd':
        media_type = 'video'
        quality = 'best'
    elif dl_type == 'video_720':
        media_type = 'video'
        quality = 'medium'
    elif dl_type == 'video_480':
        media_type = 'video'
        quality = 'low'
    elif dl_type == 'video':
        media_type = 'video'
    elif dl_type == 'audio':
        media_type = 'audio'
    elif dl_type == 'image':
        media_type = 'image'
    
    # رسالة التحميل
    type_names = {
        'video_hd': '🎬 فيديو HD',
        'video_720': '🎬 فيديو 720p',
        'video_480': '🎬 فيديو 480p',
        'video': '🎬 فيديو',
        'audio': '🎵 صوت MP3',
        'image': '🖼️ صور',
    }
    
    await query.edit_message_text(
        f"⏳ جاري تحميل {type_names.get(dl_type, dl_type)}..."
    )
    
    try:
        # تحميل الملف
        filename, error, file_info = await download_smart(url, media_type, quality)
        
        if error:
            await query.edit_message_text(f"❌ {error}")
            return
        
        if not filename or not os.path.exists(filename):
            await query.edit_message_text("❌ فشل التحميل")
            return
        
        # التحقق من الحجم
        size = os.path.getsize(filename)
        if size > MAX_FILE_SIZE:
            os.remove(filename)
            await query.edit_message_text(f"❌ الحجم كبير: {format_size(size)}")
            return
        
        # رفع الملف
        await query.edit_message_text("📤 جاري الرفع...")
        
        with open(filename, 'rb') as f:
            if media_type == 'audio':
                await query.message.reply_audio(
                    audio=f,
                    title=info.get('title', 'صوت'),
                    performer=info.get('uploader', 'غير معروف'),
                    duration=info.get('duration'),
                    caption=f"✅ تم التحميل\n📊 {format_size(size)}"
                )
            elif media_type == 'image':
                await query.message.reply_photo(
                    photo=f,
                    caption=f"✅ تم التحميل\n📊 {format_size(size)}"
                )
            else:
                await query.message.reply_video(
                    video=f,
                    caption=f"✅ تم التحميل\n📊 {format_size(size)}",
                    supports_streaming=True,
                    duration=info.get('duration')
                )
        
        # حذف الملف
        os.remove(filename)
        await query.delete_message()
        
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ في التحميل")

def main():
    """تشغيل البوت"""
    print("="*60)
    print("🤖 بوت التحميل الشامل يعمل...")
    print("="*60)
    print(f"📁 المجلد: {DOWNLOAD_DIR}")
    print(f"📊 الحد الأقصى: {format_size(MAX_FILE_SIZE)}")
    print(f"🌐 المنصات المدعومة: {len(PLATFORMS)}+")
    print("="*60)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.run_polling()

if __name__ == '__main__':
    main()
