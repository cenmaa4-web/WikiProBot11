import os
import re
import time
import json
import logging
import subprocess
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

# ================== الإعدادات الأساسية ==================
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع توكن البوت هنا
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت

# إعداد المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/temp", exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== إعدادات yt-dlp ==================
YDL_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'restrictfilenames': True,
    'noplaylist': True,
    'geo_bypass': True,
    'socket_timeout': 30,
    'retries': 3,
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': f'{DOWNLOAD_DIR}/temp/%(title)s_%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# ================== دوال المساعدة ==================
def get_platform_name(url: str) -> str:
    """استخراج اسم المنصة من الرابط"""
    platforms = {
        'youtube.com': '📺 YouTube',
        'youtu.be': '📺 YouTube',
        'twitter.com': '🐦 Twitter',
        'x.com': '🐦 Twitter',
        'instagram.com': '📸 Instagram',
        'facebook.com': '📘 Facebook',
        'tiktok.com': '🎵 TikTok',
        'reddit.com': '👽 Reddit',
    }
    
    for key, value in platforms.items():
        if key in url.lower():
            return value
    return '🌐 منصة أخرى'

def format_size(size: int) -> str:
    """تحويل الحجم إلى صيغة مقروءة"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def format_duration(seconds: int) -> str:
    """تحويل المدة إلى صيغة مقروءة"""
    if not seconds:
        return "غير معروفة"
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def check_ffmpeg() -> bool:
    """التحقق من تثبيت FFmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

async def get_video_info(url: str) -> Tuple[Optional[Dict], Optional[str]]:
    """الحصول على معلومات الفيديو"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'فيديو'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'view_count': info.get('view_count', 0),
                'thumbnail': info.get('thumbnail', ''),
                'platform': get_platform_name(url),
            }, None
    except Exception as e:
        return None, str(e)

async def download_video(url: str, mode: str = 'video') -> Tuple[Optional[str], Optional[str]]:
    """تحميل الفيديو أو الصوت"""
    try:
        options = YDL_OPTIONS if mode == 'video' else AUDIO_OPTIONS
        
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # البحث عن الملف
            if mode == 'audio':
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            else:
                filename = ydl.prepare_filename(info)
                if not filename.endswith('.mp4'):
                    filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            if os.path.exists(filename):
                return filename, None
            return None, "لم يتم العثور على الملف"
            
    except Exception as e:
        return None, str(e)

def cleanup_temp_files():
    """تنظيف الملفات المؤقتة"""
    try:
        now = time.time()
        for file in Path(f"{DOWNLOAD_DIR}/temp").glob('*'):
            if file.is_file() and file.stat().st_mtime < now - 3600:
                file.unlink()
    except:
        pass

# ================== معالجات البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    user = update.effective_user
    ffmpeg_status = "✅ متوفر" if check_ffmpeg() else "⚠️ غير متوفر"
    
    welcome_text = f"""
🎬 <b>مرحباً بك {user.first_name} في بوت التحميل!</b>

✨ <b>المميزات:</b>
• تحميل من يوتيوب، تويتر، انستغرام، تيك توك
• اختيار جودة التحميل
• تحميل الصوت فقط MP3
• معلومات الفيديو قبل التحميل

📥 <b>أرسل الرابط وسأقوم بالباقي!</b>

⚙️ <b>الحالة:</b>
• FFmpeg: {ffmpeg_status}
• الحد الأقصى: {format_size(MAX_FILE_SIZE)}
    """
    
    keyboard = [
        [InlineKeyboardButton("❓ مساعدة", callback_data="help")],
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    help_text = """
📚 <b>كيفية الاستخدام:</b>

1️⃣ أرسل رابط الفيديو
2️⃣ اختر الجودة المناسبة
3️⃣ انتظر التحميل
4️⃣ استلم الملف

<b>الجودات المتاحة:</b>
🎥 عالية - أفضل جودة
📺 متوسطة - 480p
📱 منخفضة - 240p
🎵 صوت فقط - MP3

<b>المنصات المدعومة:</b>
• YouTube
• Twitter/X
• Instagram
• TikTok
• Facebook
• Reddit
    """
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(help_text, parse_mode='HTML')

async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح")
        return
    
    cleanup_temp_files()
    
    status = await update.message.reply_text("🔄 جاري تحليل الرابط...")
    
    try:
        info, error = await get_video_info(url)
        
        if error:
            await status.edit_text(f"❌ خطأ: {error[:100]}")
            return
        
        if not info:
            await status.edit_text("❌ لم نتمكن من تحليل الرابط")
            return
        
        context.user_data['video_info'] = info
        context.user_data['video_url'] = url
        
        # تحضير رسالة المعلومات
        duration = format_duration(info.get('duration', 0))
        
        text = f"""
{info['platform']} <b>معلومات الفيديو:</b>

📹 <b>العنوان:</b> {info['title'][:100]}
👤 <b>القناة:</b> {info['uploader']}
⏱️ <b>المدة:</b> {duration}
👁️ <b>المشاهدات:</b> {info.get('view_count', 0):,}

📥 <b>اختر الجودة:</b>
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🎥 عالية", callback_data="q_best"),
                InlineKeyboardButton("📺 متوسطة", callback_data="q_medium")
            ],
            [
                InlineKeyboardButton("📱 منخفضة", callback_data="q_low"),
                InlineKeyboardButton("🎵 صوت", callback_data="q_audio")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        
        if info.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=info['thumbnail'],
                    caption=text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await status.delete()
            except:
                await status.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await status.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        await status.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")
        logger.error(f"Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("✅ تم الإلغاء")
        return
    
    if query.data == "help":
        await help_command(update, context)
        return
    
    if query.data == "back":
        await back_callback(update, context)
        return
    
    if query.data.startswith("q_"):
        quality = query.data.replace("q_", "")
        
        info = context.user_data.get('video_info', {})
        url = context.user_data.get('video_url')
        
        if not url:
            await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً")
            return
        
        quality_names = {
            'best': '🎥 عالية',
            'medium': '📺 متوسطة',
            'low': '📱 منخفضة',
            'audio': '🎵 صوت'
        }
        
        await query.edit_message_text(
            f"⏳ جاري التحميل...\n"
            f"الجودة: {quality_names.get(quality, quality)}\n"
            f"الرجاء الانتظار"
        )
        
        try:
            mode = 'audio' if quality == 'audio' else 'video'
            filename, error = await download_video(url, mode)
            
            if error:
                await query.edit_message_text(f"❌ {error}")
                return
            
            if not filename or not os.path.exists(filename):
                await query.edit_message_text("❌ فشل التحميل")
                return
            
            file_size = os.path.getsize(filename)
            if file_size > MAX_FILE_SIZE:
                os.remove(filename)
                await query.edit_message_text(f"❌ الملف كبير: {format_size(file_size)}")
                return
            
            await query.edit_message_text("📤 جاري الرفع...")
            
            with open(filename, 'rb') as f:
                if quality == 'audio':
                    await query.message.reply_audio(
                        audio=f,
                        title=info.get('title', 'صوت'),
                        performer=info.get('uploader', 'غير معروف'),
                        caption="✅ تم التحميل"
                    )
                else:
                    await query.message.reply_video(
                        video=f,
                        caption=f"✅ تم التحميل\n{info.get('title', '')[:100]}",
                        supports_streaming=True
                    )
            
            os.remove(filename)
            await query.delete_message()
            
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
            logger.error(f"Download error: {e}")
            cleanup_temp_files()

def main():
    """تشغيل البوت"""
    print("="*50)
    print("🤖 بوت التحميل يعمل...")
    print("="*50)
    
    # إنشاء التطبيق بالطريقة المبسطة
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
