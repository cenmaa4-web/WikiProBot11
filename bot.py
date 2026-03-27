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
from urllib.parse import urlparse
from datetime import datetime

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
logger.info(f"📁 مجلد التحميلات: {DOWNLOAD_FOLDER}")

# قائمة المنصات المدعومة
SUPPORTED_SITES = [
    "youtube.com", "youtu.be",
    "tiktok.com",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "pinterest.com",
]

# إعدادات yt-dlp الأساسية
YDL_OPTIONS = {
    'format': 'best[height<=720]',
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'no_color': True,
    'socket_timeout': 30,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

# إحصائيات
download_stats = {
    'total_downloads': 0,
    'total_searches': 0,
    'start_time': datetime.now()
}

# ============= دوال التحميل =============

async def download_video(url, is_youtube=False, download_type='video'):
    """دالة تحميل الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def download():
            try:
                options = YDL_OPTIONS.copy()
                
                # إذا كان يوتيوب ونوع الصوت
                if is_youtube and download_type in ['audio', 'voice']:
                    options['format'] = 'bestaudio/best'
                    if download_type == 'audio':
                        options['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }]
                        options['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.mp3')
                    elif download_type == 'voice':
                        options['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'ogg',
                            'preferredquality': '64',
                        }]
                        options['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.ogg')
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # البحث عن الملف
                    filename = ydl.prepare_filename(info)
                    
                    # إذا كان ملف صوتي، تغيير الامتداد
                    if download_type == 'audio':
                        filename = filename.replace('.%(ext)s', '.mp3')
                    elif download_type == 'voice':
                        filename = filename.replace('.%(ext)s', '.ogg')
                    
                    # إذا لم يوجد الملف، ابحث في المجلد
                    if not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    if os.path.exists(filename):
                        return filename, info
                    return None, None
                    
            except Exception as e:
                logger.error(f"خطأ في التحميل: {e}")
                return None, None
        
        result, info = await loop.run_in_executor(None, download)
        return result, info
        
    except Exception as e:
        logger.error(f"خطأ عام: {e}")
        return None, None

# ============= البحث في يوتيوب =============

async def search_youtube(query):
    """البحث في يوتيوب"""
    try:
        loop = asyncio.get_event_loop()
        
        def search():
            search_query = f"ytsearch5:{query}"
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(search_query, download=False)
                videos = []
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry and entry.get('id'):
                            videos.append({
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                'duration': entry.get('duration', 0),
                                'uploader': entry.get('uploader', 'غير معروف'),
                                'views': entry.get('view_count', 0),
                                'thumbnail': entry.get('thumbnail', '')
                            })
                return videos
        
        return await loop.run_in_executor(None, search)
        
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        return []

# ============= دوال مساعدة =============

def format_duration(seconds):
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    seconds = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def is_youtube_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return 'youtube.com' in domain or 'youtu.be' in domain

def is_supported_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    for site in SUPPORTED_SITES:
        if site in domain:
            return True
    return False

# ============= أوامر البوت =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات!**\n\n"
        "📥 **طريقة الاستخدام:**\n\n"
        "**1️⃣ تحميل مباشر:**\n"
        "أرسل رابط من أي منصة (انستقرام، تيك توك، فيسبوك، بنترست)\n"
        "سأقوم بتحميل الفيديو فوراً\n\n"
        "**2️⃣ تحميل من يوتيوب:**\n"
        "أرسل رابط يوتيوب ← سأرسل صورة + 3 أزرار\n\n"
        "**3️⃣ البحث في يوتيوب:**\n"
        "اكتب كلمة للبحث (مثل: 'أغاني')\n"
        "ستظهر 5 نتائج مع صور\n\n"
        "✨ **جرب الآن!**"
    )
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🆘 **المساعدة:**\n\n"
        "• أرسل رابط فيديو للتحميل المباشر\n"
        "• أرسل رابط يوتيوب لتحميل فيديو/صوت\n"
        "• اكتب كلمة للبحث في يوتيوب\n\n"
        "**الأوامر:**\n"
        "/start - البداية\n"
        "/help - المساعدة\n"
        "/stats - الإحصائيات"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - download_stats['start_time']
    hours = uptime.total_seconds() // 3600
    
    stats = (
        f"📊 **الإحصائيات:**\n\n"
        f"📥 التحميلات: {download_stats['total_downloads']}\n"
        f"🔍 عمليات البحث: {download_stats['total_searches']}\n"
        f"⏱️ وقت التشغيل: {int(hours)} ساعة\n"
        f"🌐 المنصات: {len(SUPPORTED_SITES)}"
    )
    await update.message.reply_text(stats, parse_mode='Markdown')

# ============= معالج الروابط =============

async def handle_youtube_url(update: Update, url: str):
    """معالجة روابط يوتيوب"""
    msg = await update.message.reply_text("⏳ **جاري تحضير الفيديو...**", parse_mode='Markdown')
    
    try:
        # الحصول على معلومات الفيديو
        info = None
        loop = asyncio.get_event_loop()
        
        def get_info():
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, get_info)
        
        if info:
            # تجهيز الأزرار
            keyboard = [
                [
                    InlineKeyboardButton("🎬 فيديو", callback_data=f"yt_video_{url}"),
                    InlineKeyboardButton("🎵 MP3", callback_data=f"yt_audio_{url}"),
                    InlineKeyboardButton("🎤 بصمة", callback_data=f"yt_voice_{url}")
                ]
            ]
            
            duration = format_duration(info.get('duration', 0))
            views = format_number(info.get('view_count', 0))
            
            caption = (
                f"🎬 **{info.get('title', 'فيديو')[:100]}**\n\n"
                f"👤 {info.get('uploader', 'غير معروف')}\n"
                f"⏱️ {duration} | 👁️ {views}\n\n"
                f"[👁️ مشاهدة الفيديو]({url})\n\n"
                f"📥 **اختر نوع التحميل:**"
            )
            
            await msg.delete()
            
            # إرسال الصورة إن وجدت
            if info.get('thumbnail'):
                try:
                    with open(os.path.join(DOWNLOAD_FOLDER, 'thumb.jpg'), 'wb') as f:
                        import urllib.request
                        urllib.request.urlretrieve(info['thumbnail'], f.name)
                    with open(f.name, 'rb') as thumb:
                        await update.message.reply_photo(
                            photo=thumb,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                    os.remove(f.name)
                except:
                    await update.message.reply_text(
                        caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        else:
            await msg.edit_text("❌ **فشل في جلب المعلومات**", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await msg.edit_text(f"❌ **خطأ:** {str(e)[:100]}", parse_mode='Markdown')

async def handle_direct_url(update: Update, url: str):
    """معالجة الروابط المباشرة"""
    msg = await update.message.reply_text("⏳ **جاري تحميل الفيديو...**", parse_mode='Markdown')
    
    try:
        file_path, _ = await download_video(url, is_youtube=False)
        
        if file_path and os.path.exists(file_path):
            size = os.path.getsize(file_path) / (1024 * 1024)
            
            if size > 50:
                await msg.edit_text(f"❌ **الفيديو كبير جداً**\nالحجم: {size:.1f} MB", parse_mode='Markdown')
                os.remove(file_path)
                return
            
            await msg.delete()
            
            with open(file_path, 'rb') as f:
                await update.message.reply_video(
                    video=f,
                    caption=f"✅ **تم التحميل!**\n📊 {size:.1f} MB",
                    supports_streaming=True
                )
            
            os.remove(file_path)
            download_stats['total_downloads'] += 1
            
        else:
            await msg.edit_text("❌ **فشل التحميل**\nتأكد من الرابط", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await msg.edit_text(f"❌ **خطأ:** {str(e)[:100]}", parse_mode='Markdown')

# ============= البحث =============

async def handle_search(update: Update, query: str):
    """معالجة البحث"""
    download_stats['total_searches'] += 1
    
    msg = await update.message.reply_text(f"🔍 **جاري البحث عن:** {query}", parse_mode='Markdown')
    
    try:
        videos = await search_youtube(query)
        
        if videos:
            await msg.delete()
            
            for i, video in enumerate(videos, 1):
                duration = format_duration(video['duration'])
                views = format_number(video['views'])
                
                keyboard = [[
                    InlineKeyboardButton("🎬 فيديو", callback_data=f"yt_video_{video['url']}"),
                    InlineKeyboardButton("🎵 MP3", callback_data=f"yt_audio_{video['url']}"),
                    InlineKeyboardButton("🎤 بصمة", callback_data=f"yt_voice_{video['url']}")
                ]]
                
                caption = (
                    f"{i}. **{video['title']}**\n"
                    f"👤 {video['uploader']} | ⏱️ {duration} | 👁️ {views}\n\n"
                    f"[👁️ مشاهدة]({video['url']})"
                )
                
                # تحميل الصورة
                thumb_path = None
                if video['thumbnail']:
                    try:
                        import urllib.request
                        thumb_path = os.path.join(DOWNLOAD_FOLDER, f"thumb_{i}.jpg")
                        urllib.request.urlretrieve(video['thumbnail'], thumb_path)
                    except:
                        pass
                
                if thumb_path and os.path.exists(thumb_path):
                    with open(thumb_path, 'rb') as thumb:
                        await update.message.reply_photo(
                            photo=thumb,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                    os.remove(thumb_path)
                else:
                    await update.message.reply_text(
                        caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
        else:
            await msg.edit_text("❌ **لا توجد نتائج**\nجرب كلمات أخرى", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        await msg.edit_text(f"❌ **خطأ في البحث**\n{str(e)[:100]}", parse_mode='Markdown')

# ============= معالج الأزرار =============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('yt_'):
        parts = data.split('_', 2)
        if len(parts) >= 3:
            dl_type = parts[1]
            url = parts[2]
            
            await query.edit_message_caption(
                caption=f"⏳ **جاري التحميل...**\n{ 'فيديو' if dl_type == 'video' else 'MP3' if dl_type == 'audio' else 'بصمة' }",
                parse_mode='Markdown'
            )
            
            try:
                file_path, _ = await download_video(url, is_youtube=True, download_type=dl_type)
                
                if file_path and os.path.exists(file_path):
                    size = os.path.getsize(file_path) / (1024 * 1024)
                    
                    with open(file_path, 'rb') as f:
                        if dl_type == 'video':
                            await query.message.reply_video(
                                video=f,
                                caption=f"✅ **تم التحميل!**\n📊 {size:.1f} MB",
                                supports_streaming=True
                            )
                        elif dl_type == 'audio':
                            await query.message.reply_audio(
                                audio=f,
                                caption=f"✅ **ملف MP3**\n📊 {size:.1f} MB"
                            )
                        elif dl_type == 'voice':
                            await query.message.reply_voice(
                                voice=f,
                                caption=f"✅ **بصمة صوتية**\n📊 {size:.1f} MB"
                            )
                    
                    os.remove(file_path)
                    download_stats['total_downloads'] += 1
                    
                    await query.edit_message_caption(
                        caption=query.message.caption_html,
                        parse_mode='HTML'
                    )
                else:
                    await query.edit_message_caption(
                        caption="❌ **فشل التحميل**\nحاول مرة أخرى",
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                logger.error(f"خطأ: {e}")
                await query.edit_message_caption(
                    caption=f"❌ **خطأ:** {str(e)[:100]}",
                    parse_mode='Markdown'
                )

# ============= المعالج الرئيسي =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # رابط
    if text.startswith(('http://', 'https://')):
        if not is_supported_url(text):
            await update.message.reply_text(
                "⚠️ **الرابط غير مدعوم**\nالمنصات: يوتيوب، تيك توك، انستقرام، فيسبوك، بنترست، تويتر",
                parse_mode='Markdown'
            )
            return
        
        if is_youtube_url(text):
            await handle_youtube_url(update, text)
        else:
            await handle_direct_url(update, text)
    
    # بحث
    elif len(text) > 2:
        await handle_search(update, text)
    else:
        await update.message.reply_text(
            "❌ **كلمة البحث قصيرة جداً**\nاكتب كلمة أطول من حرفين",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"حدث خطأ: {context.error}")

def cleanup():
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        logger.info("✅ تم التنظيف")
    except:
        pass

def main():
    logger.info("🚀 بدء تشغيل البوت...")
    
    try:
        app = Application.builder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_error_handler(error_handler)
        
        print("\n" + "="*50)
        print("🤖 البوت يعمل الآن!")
        print(f"📁 {DOWNLOAD_FOLDER}")
        print("="*50 + "\n")
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
