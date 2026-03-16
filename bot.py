import os
import re
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
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

# ================== الإعدادات ==================
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
DOWNLOAD_DIR = "downloads"
MAX_SIZE = 50 * 1024 * 1024  # 50 ميجابايت

# إنشاء المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== إعدادات yt-dlp ==================
YDL_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'retries': 5,
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# ================== دوال سريعة ==================
def get_platform(url: str) -> str:
    """كشف المنصة"""
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
    elif 'pinterest.com' in url or 'pin.it' in url:
        return '📌 بنترست'
    elif 'reddit.com' in url:
        return '👽 ريديت'
    return '🌐 رابط'

def format_size(size: int) -> str:
    """تنسيق الحجم"""
    if size < 1024:
        return f"{size}B"
    elif size < 1024**2:
        return f"{size/1024:.0f}KB"
    elif size < 1024**3:
        return f"{size/1024**2:.1f}MB"
    return f"{size/1024**3:.1f}GB"

async def get_info_fast(url: str) -> Tuple[Optional[dict], Optional[str]]:
    """جلب المعلومات بسرعة"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'فيديو')[:100],
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'thumb': info.get('thumbnail', ''),
                'platform': get_platform(url),
            }, None
    except Exception as e:
        return None, str(e)

async def download_media(url: str, is_audio: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """تحميل الوسائط"""
    try:
        opts = AUDIO_OPTIONS if is_audio else YDL_OPTIONS
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # الحصول على اسم الملف
            if is_audio:
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            else:
                filename = ydl.prepare_filename(info)
                if not filename.endswith('.mp4'):
                    filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            # التحقق من وجود الملف
            if os.path.exists(filename):
                return filename, None
            
            # البحث بامتدادات مختلفة
            base = filename.rsplit('.', 1)[0]
            for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                test = base + ext
                if os.path.exists(test):
                    return test, None
            
            return None, "لم يتم العثور على الملف"
            
    except Exception as e:
        return None, str(e)

async def upload_to_telegram(update: Update, file_path: str, info: dict, is_audio: bool):
    """رفع الملف إلى تليجرام مع ضمان النجاح"""
    try:
        file_size = os.path.getsize(file_path)
        
        # فتح الملف وإرساله
        with open(file_path, 'rb') as f:
            if is_audio:
                await update.message.reply_audio(
                    audio=f,
                    title=info.get('title', 'صوت'),
                    performer=info.get('uploader', 'غير معروف'),
                    duration=info.get('duration', 0),
                    caption=f"✅ تم التحميل\n📊 {format_size(file_size)}"
                )
            else:
                # محاولة إرسال كفيديو
                try:
                    await update.message.reply_video(
                        video=f,
                        caption=f"✅ {info.get('platform', '')}\n📹 {info.get('title', '')[:50]}\n📊 {format_size(file_size)}",
                        supports_streaming=True,
                        duration=info.get('duration', 0)
                    )
                except Exception as video_error:
                    # إذا فشل إرسال كفيديو، أرسل كمستند
                    f.seek(0)
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(file_path),
                        caption=f"✅ تم التحميل (كمستند)\n📊 {format_size(file_size)}"
                    )
        
        return True
    except Exception as e:
        print(f"خطأ في الرفع: {e}")
        return False

# ================== معالجات البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية البوت"""
    text = """
🎬 <b>بوت التحميل السريع</b>

📥 <b>أرسل الرابط</b> وسأحمل لك:
• 🎬 فيديو
• 🎵 صوت MP3

⚡ تحميل ورفع فوري
📊 حجم حتى 50 ميجابايت
🌐 يدوم يوتيوب، انستغرام، تيك توك، تويتر، فيسبوك، بنترست...
    """
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ أرسل رابط صحيح")
        return
    
    platform = get_platform(url)
    msg = await update.message.reply_text(f"🔍 جاري تحليل {platform}...")
    
    try:
        # جلب المعلومات
        info, error = await get_info_fast(url)
        
        if error or not info:
            await msg.edit_text(
                f"❌ لا يمكن تحليل الرابط\n\n"
                f"💡 تأكد من:\n"
                f"• الرابط صحيح\n"
                f"• المحتوى عام\n"
                f"• جرب رابط آخر"
            )
            return
        
        # حفظ المعلومات
        context.user_data['url'] = url
        context.user_data['info'] = info
        
        # أزرار التحميل
        keyboard = [
            [
                InlineKeyboardButton("🎬 فيديو", callback_data="dl_video"),
                InlineKeyboardButton("🎵 صوت", callback_data="dl_audio")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        
        # معلومات سريعة
        duration = f"{info['duration']//60}:{info['duration']%60:02d}" if info['duration'] else "00:00"
        views = f"{info['views']:,}" if info['views'] else "?"
        
        text = f"""
{info['platform']} ✅

📹 {info['title']}
👤 {info['uploader']}
⏱️ {duration} | 👁️ {views}

اختر التحميل:
        """
        
        await msg.delete()
        
        # إرسال مع الصورة
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
    
    is_audio = query.data == "dl_audio"
    type_text = "🎵 صوت" if is_audio else "🎬 فيديو"
    
    await query.edit_message_text(f"⏳ جاري تحميل {type_text}...")
    
    try:
        # تحميل الملف
        file_path, error = await download_media(url, is_audio)
        
        if error or not file_path:
            await query.edit_message_text(f"❌ فشل التحميل: {error or 'غير معروف'}")
            return
        
        if not os.path.exists(file_path):
            await query.edit_message_text("❌ الملف غير موجود")
            return
        
        # التحقق من الحجم
        size = os.path.getsize(file_path)
        if size > MAX_SIZE:
            os.remove(file_path)
            await query.edit_message_text(f"❌ الحجم كبير: {format_size(size)}")
            return
        
        # رفع الملف
        await query.edit_message_text("📤 جاري الرفع إلى تليجرام...")
        
        # رفع مع ضمان النجاح
        success = await upload_to_telegram(update, file_path, info, is_audio)
        
        if success:
            # حذف الملف بعد الرفع
            try:
                os.remove(file_path)
            except:
                pass
            
            # حذف رسالة الحالة
            await query.delete_message()
        else:
            await query.edit_message_text("❌ فشل الرفع إلى تليجرام")
            
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ: {str(e)[:100]}")
        print(f"Error details: {e}")

def main():
    """تشغيل البوت"""
    print("="*50)
    print("🤖 بوت التحميل السريع يعمل...")
    print("="*50)
    print(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
    print(f"📊 الحد الأقصى: {format_size(MAX_SIZE)}")
    print("="*50)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.run_polling()

if __name__ == '__main__':
    main()
