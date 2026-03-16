import os
import re
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple
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

# ================== الإعدادات السريعة ==================
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع توكن البوت هنا
DOWNLOAD_DIR = "downloads"
MAX_SIZE = 50 * 1024 * 1024  # 50 ميجابايت

# إعداد المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# إعداد التسجيل (خفي)
logging.basicConfig(level=logging.ERROR)

# ================== إعدادات yt-dlp السريعة ==================
YDL_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '128',
    }],
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# ================== دوال سريعة ==================
def get_platform(url: str) -> str:
    """كشف سريع للمنصة"""
    url = url.lower()
    if 'youtube.com' in url or 'youtu.be' in url:
        return '📺 يوتيوب'
    elif 'instagram.com' in url:
        return '📸 انستغرام'
    elif 'tiktok.com' in url:
        return '🎵 تيك توك'
    elif 'twitter.com' in url or 'x.com' in url:
        return '🐦 تويتر'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return '📘 فيسبوك'
    return '🌐 رابط'

def format_size(size: int) -> str:
    """تحويل الحجم"""
    if size < 1024:
        return f"{size}B"
    elif size < 1024**2:
        return f"{size/1024:.0f}KB"
    elif size < 1024**3:
        return f"{size/1024**2:.1f}MB"
    return f"{size/1024**3:.1f}GB"

def clean_old_files():
    """تنظيف سريع"""
    try:
        now = time.time()
        for f in Path(DOWNLOAD_DIR).glob('*'):
            if f.is_file() and now - f.stat().st_mtime > 300:  # 5 دقائق
                f.unlink()
    except:
        pass

async def get_info_fast(url: str) -> Tuple[Optional[dict], Optional[str]]:
    """جلب المعلومات بسرعة"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'فيديو')[:50],
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'thumb': info.get('thumbnail', ''),
            }, None
    except Exception as e:
        return None, str(e)

async def download_fast(url: str, audio: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """تحميل سريع"""
    try:
        opts = AUDIO_OPTIONS if audio else YDL_OPTIONS
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if audio:
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            else:
                filename = ydl.prepare_filename(info)
                if not filename.endswith('.mp4'):
                    filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            if os.path.exists(filename):
                return filename, None
            return None, "الملف غير موجود"
    except Exception as e:
        return None, str(e)

# ================== معالجات البوت السريعة ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية سريعة"""
    text = """
🎬 <b>بوت التحميل السريع</b>

📥 <b>أرسل الرابط</b> وسأحمل لك الفيديو فوراً

⚡ <b>مميزات:</b>
• تحميل فوري بدون تعقيد
• يدعم يوتيوب، انستغرام، تيك توك، تويتر
• خيار فيديو أو صوت MP3
• حجم حتى 50 ميجابايت
    """
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة سريعة للرابط"""
    url = update.message.text.strip()
    
    # تنظيف سريع
    clean_old_files()
    
    # تحقق سريع من الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ أرسل رابط صحيح")
        return
    
    # رسالة انتظار سريعة
    platform = get_platform(url)
    msg = await update.message.reply_text(f"⏳ جاري تحميل {platform}...")
    
    try:
        # جلب المعلومات بسرعة
        info, error = await get_info_fast(url)
        if error:
            await msg.edit_text("❌ الرابط غير صالح")
            return
        
        # حفظ المعلومات
        context.user_data['url'] = url
        context.user_data['title'] = info['title']
        
        # إنشاء الأزرار بسرعة
        keyboard = [
            [
                InlineKeyboardButton("🎬 فيديو", callback_data="video"),
                InlineKeyboardButton("🎵 صوت", callback_data="audio")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        
        # إرسال سريع
        text = f"""
{platform} ✅

📹 {info['title']}
👤 {info['uploader']}
⏱️ {info['duration']//60}:{info['duration']%60:02d}
👁️ {info['views']:,}

اختر التحميل:
        """
        
        await msg.delete()
        
        if info['thumb']:
            try:
                await update.message.reply_photo(
                    photo=info['thumb'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        await msg.edit_text("❌ خطأ غير متوقع")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة سريعة للأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("✅ تم الإلغاء")
        return
    
    url = context.user_data.get('url')
    title = context.user_data.get('title', 'فيديو')
    
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً")
        return
    
    audio = query.data == "audio"
    type_text = "🎵 صوت" if audio else "🎬 فيديو"
    
    await query.edit_message_text(f"⏳ جاري تحميل {type_text}...")
    
    try:
        # تحميل سريع
        filename, error = await download_fast(url, audio)
        
        if error:
            await query.edit_message_text(f"❌ {error}")
            return
        
        if not filename or not os.path.exists(filename):
            await query.edit_message_text("❌ فشل التحميل")
            return
        
        # تحقق سريع من الحجم
        size = os.path.getsize(filename)
        if size > MAX_SIZE:
            os.remove(filename)
            await query.edit_message_text(f"❌ الحجم كبير {format_size(size)}")
            return
        
        # رفع سريع
        await query.edit_message_text("📤 جاري الرفع...")
        
        with open(filename, 'rb') as f:
            if audio:
                await query.message.reply_audio(
                    audio=f,
                    title=title,
                    caption="✅ تم التحميل"
                )
            else:
                await query.message.reply_video(
                    video=f,
                    caption="✅ تم التحميل",
                    supports_streaming=True
                )
        
        # حذف الملف
        os.remove(filename)
        await query.delete_message()
        
    except Exception as e:
        await query.edit_message_text("❌ خطأ في التحميل")

def main():
    """تشغيل سريع"""
    print("⚡ بوت التحميل السريع يعمل...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.run_polling()

if __name__ == '__main__':
    main()
