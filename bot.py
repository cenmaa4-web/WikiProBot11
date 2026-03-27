#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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

# مجلد مؤقت
DOWNLOAD_FOLDER = tempfile.mkdtemp()

# الكيبورد الرئيسي
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📥 تحميل فيديو"), KeyboardButton("🎵 تحميل صوت")],
        [KeyboardButton("🔍 بحث في يوتيوب"), KeyboardButton("📊 إحصائيات")]
    ],
    resize_keyboard=True
)

# إحصائيات
stats = {'downloads': 0, 'searches': 0, 'start': datetime.now()}

# ============= دوال مساعدة =============

def is_youtube_url(url):
    domain = urlparse(url).netloc.lower()
    return 'youtube.com' in domain or 'youtu.be' in domain

def format_duration(seconds):
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ============= دوال التحميل الأساسية =============

async def download_video(url):
    """تحميل فيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def download():
            opts = {
                'format': 'best[height<=720]',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'socket_timeout': 30,
                'http_headers': {'User-Agent': 'Mozilla/5.0'}
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                if os.path.exists(filename):
                    return filename, info
                return None, None
        
        return await loop.run_in_executor(None, download)
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return None, None

async def download_audio(url):
    """تحميل صوت MP3"""
    try:
        loop = asyncio.get_event_loop()
        
        def download():
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'http_headers': {'User-Agent': 'Mozilla/5.0'}
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filename = filename.replace('.%(ext)s', '.mp3')
                
                if os.path.exists(filename):
                    return filename, info
                return None, None
        
        return await loop.run_in_executor(None, download)
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return None, None

async def get_info(url):
    """جلب معلومات الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def get():
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, get)
        if info:
            return {
                'title': info.get('title', 'فيديو'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'thumbnail': info.get('thumbnail', '')
            }
        return None
    except:
        return None

async def search_youtube(query):
    """البحث في يوتيوب"""
    try:
        loop = asyncio.get_event_loop()
        
        def search():
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                results = []
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            results.append({
                                'title': entry.get('title', 'بدون عنوان')[:60],
                                'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                'duration': entry.get('duration', 0),
                                'uploader': entry.get('uploader', 'غير معروف'),
                                'views': entry.get('view_count', 0),
                                'thumbnail': entry.get('thumbnail', '')
                            })
                return results[:5]
        
        return await loop.run_in_executor(None, search)
    except Exception as e:
        logger.error(f"بحث خطأ: {e}")
        return []

# ============= أوامر البوت =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 **بوت تحميل الفيديوهات**\n\n"
        "📥 أرسل رابط فيديو للتحميل\n"
        "🔍 اكتب كلمة للبحث في يوتيوب\n\n"
        "✅ يدعم: يوتيوب - تيك توك - انستقرام - فيسبوك - بنترست",
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 **المساعدة:**\n\n"
        "• أرسل رابط فيديو → تحميل فوري\n"
        "• أرسل رابط يوتيوب → صورة + 3 أزرار\n"
        "• اكتب كلمة → بحث في يوتيوب\n\n"
        "/start - البداية\n/stats - الإحصائيات",
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = (datetime.now() - stats['start']).total_seconds() // 3600
    await update.message.reply_text(
        f"📊 **الإحصائيات:**\n\n"
        f"📥 تحميلات: {stats['downloads']}\n"
        f"🔍 بحوث: {stats['searches']}\n"
        f"⏱️ وقت التشغيل: {int(uptime)} ساعة",
        parse_mode='Markdown'
    )

# ============= معالجة الروابط =============

async def handle_youtube(update: Update, url: str):
    """معالجة رابط يوتيوب"""
    msg = await update.message.reply_text("⏳ جاري التحضير...")
    
    info = await get_info(url)
    
    if not info:
        await msg.edit_text("❌ فشل في جلب المعلومات")
        return
    
    # أزرار
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 فيديو", callback_data=f"video_{url}"),
            InlineKeyboardButton("🎵 MP3", callback_data=f"audio_{url}")
        ]
    ])
    
    duration = format_duration(info['duration'])
    views = f"{info['views']:,}" if info['views'] else "0"
    
    caption = (
        f"🎬 **{info['title'][:80]}**\n\n"
        f"👤 {info['uploader']}\n"
        f"⏱️ {duration} | 👁️ {views}\n\n"
        f"📥 اختر نوع التحميل:"
    )
    
    await msg.delete()
    
    # إرسال مع صورة
    if info['thumbnail']:
        try:
            import urllib.request
            thumb = os.path.join(DOWNLOAD_FOLDER, 'thumb.jpg')
            urllib.request.urlretrieve(info['thumbnail'], thumb)
            with open(thumb, 'rb') as f:
                await update.message.reply_photo(f, caption=caption, reply_markup=keyboard, parse_mode='Markdown')
            os.remove(thumb)
        except:
            await update.message.reply_text(caption, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(caption, reply_markup=keyboard, parse_mode='Markdown')

async def handle_direct(update: Update, url: str):
    """تحميل مباشر"""
    msg = await update.message.reply_text("⏳ جاري التحميل...")
    
    file_path, info = await download_video(url)
    
    if not file_path:
        await msg.edit_text("❌ فشل التحميل\nتأكد من الرابط")
        return
    
    size = os.path.getsize(file_path) / (1024 * 1024)
    
    if size > 50:
        await msg.edit_text(f"❌ الفيديو كبير {size:.1f} MB")
        os.remove(file_path)
        return
    
    await msg.delete()
    
    with open(file_path, 'rb') as f:
        await update.message.reply_video(f, caption=f"✅ تم التحميل!\n📊 {size:.1f} MB")
    
    os.remove(file_path)
    stats['downloads'] += 1

# ============= البحث =============

async def handle_search(update: Update, query: str):
    """البحث في يوتيوب"""
    stats['searches'] += 1
    
    msg = await update.message.reply_text(f"🔍 جاري البحث عن: {query}")
    
    videos = await search_youtube(query)
    
    if not videos:
        await msg.edit_text("❌ لا توجد نتائج\nجرب كلمات أخرى")
        return
    
    await msg.delete()
    
    for video in videos:
        duration = format_duration(video['duration'])
        views = f"{video['views']:,}" if video['views'] else "0"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 فيديو", callback_data=f"video_{video['url']}"),
                InlineKeyboardButton("🎵 MP3", callback_data=f"audio_{video['url']}")
            ]
        ])
        
        caption = f"**{video['title']}**\n👤 {video['uploader']} | ⏱️ {duration} | 👁️ {views}"
        
        if video['thumbnail']:
            try:
                import urllib.request
                thumb = os.path.join(DOWNLOAD_FOLDER, 'search_thumb.jpg')
                urllib.request.urlretrieve(video['thumbnail'], thumb)
                with open(thumb, 'rb') as f:
                    await update.message.reply_photo(f, caption=caption, reply_markup=keyboard, parse_mode='Markdown')
                os.remove(thumb)
            except:
                await update.message.reply_text(caption, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.message.reply_text(caption, reply_markup=keyboard, parse_mode='Markdown')

# ============= معالج الأزرار =============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('video_'):
        url = data.replace('video_', '')
        await query.edit_message_caption("⏳ جاري تحميل الفيديو...")
        
        file_path, info = await download_video(url)
        
        if file_path:
            size = os.path.getsize(file_path) / (1024 * 1024)
            with open(file_path, 'rb') as f:
                await query.message.reply_video(f, caption=f"✅ تم التحميل!\n📊 {size:.1f} MB")
            os.remove(file_path)
            stats['downloads'] += 1
            await query.edit_message_caption(caption=query.message.caption_html, parse_mode='HTML')
        else:
            await query.edit_message_caption("❌ فشل التحميل")
    
    elif data.startswith('audio_'):
        url = data.replace('audio_', '')
        await query.edit_message_caption("⏳ جاري تحميل الصوت...")
        
        file_path, info = await download_audio(url)
        
        if file_path:
            size = os.path.getsize(file_path) / (1024 * 1024)
            with open(file_path, 'rb') as f:
                await query.message.reply_audio(f, caption=f"✅ تم التحميل!\n📊 {size:.1f} MB")
            os.remove(file_path)
            stats['downloads'] += 1
            await query.edit_message_caption(caption=query.message.caption_html, parse_mode='HTML')
        else:
            await query.edit_message_caption("❌ فشل التحميل")

# ============= معالجة أزرار الكيبورد =============

async def button_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "📥 تحميل فيديو":
        await update.message.reply_text("📥 أرسل رابط الفيديو:")
    elif text == "🎵 تحميل صوت":
        await update.message.reply_text("🎵 أرسل رابط يوتيوب لتحميل MP3:")
    elif text == "🔍 بحث في يوتيوب":
        await update.message.reply_text("🔍 اكتب كلمة البحث:")
    elif text == "📊 إحصائيات":
        await stats_command(update, context)

# ============= المعالج الرئيسي =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # أزرار الكيبورد
    if text in ["📥 تحميل فيديو", "🎵 تحميل صوت", "🔍 بحث في يوتيوب", "📊 إحصائيات"]:
        await button_reply(update, context)
        return
    
    # رابط
    if text.startswith(('http://', 'https://')):
        if is_youtube_url(text):
            await handle_youtube(update, text)
        else:
            await handle_direct(update, text)
        return
    
    # بحث (إذا كان نص عادي)
    if len(text) >= 2:
        await handle_search(update, text)
    else:
        await update.message.reply_text("❌ كلمة البحث قصيرة جداً")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ: {context.error}")

def cleanup():
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except:
        pass

def main():
    print("\n" + "="*50)
    print("🤖 البوت يعمل الآن!")
    print("="*50 + "\n")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    cleanup()

if __name__ == '__main__':
    main()
