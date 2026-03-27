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
logger.info(f"📁 {DOWNLOAD_FOLDER}")

# المنصات المدعومة
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
]

# إعدادات التحميل
YDL_OPTIONS = {
    'format': 'best[height<=720]',
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'socket_timeout': 30,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

# إحصائيات
stats = {
    'downloads': 0,
    'searches': 0,
    'start': datetime.now()
}

# ============= REPLY KEYBOARD (الكيبورد الرئيسي) =============
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📥 تحميل فيديو"), KeyboardButton("🎵 تحميل صوت")],
        [KeyboardButton("🔍 بحث في يوتيوب"), KeyboardButton("📊 إحصائيات")],
        [KeyboardButton("❓ مساعدة"), KeyboardButton("ℹ️ عن البوت")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# ============= دوال مساعدة =============

def format_duration(seconds):
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def is_youtube_url(url):
    domain = urlparse(url).netloc.lower()
    return 'youtube.com' in domain or 'youtu.be' in domain

def is_supported_url(url):
    domain = urlparse(url).netloc.lower()
    return any(site in domain for site in SUPPORTED_SITES)

# ============= دوال التحميل الأساسية =============

async def download_media(url, media_type='video'):
    """تحميل فيديو أو صوت"""
    try:
        loop = asyncio.get_event_loop()
        
        def download():
            try:
                options = YDL_OPTIONS.copy()
                
                if media_type == 'audio':
                    options['format'] = 'bestaudio/best'
                    options['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                    options['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.mp3')
                elif media_type == 'voice':
                    options['format'] = 'bestaudio/best'
                    options['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'ogg',
                        'preferredquality': '64',
                    }]
                    options['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(id)s.ogg')
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    
                    if media_type in ['audio', 'voice']:
                        ext = 'mp3' if media_type == 'audio' else 'ogg'
                        filename = filename.replace('.%(ext)s', f'.{ext}')
                    
                    if not os.path.exists(filename):
                        import glob
                        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
                        if files:
                            filename = max(files, key=os.path.getctime)
                    
                    if os.path.exists(filename):
                        return filename, info
                    return None, None
                    
            except Exception as e:
                logger.error(f"خطأ: {e}")
                return None, None
        
        return await loop.run_in_executor(None, download)
        
    except Exception as e:
        logger.error(f"خطأ عام: {e}")
        return None, None

async def get_video_info(url):
    """جلب معلومات الفيديو"""
    try:
        loop = asyncio.get_event_loop()
        
        def get_info():
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, get_info)
        
        if info:
            return {
                'title': info.get('title', 'بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'thumbnail': info.get('thumbnail', ''),
            }
        return None
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return None

async def search_youtube(query):
    """البحث في يوتيوب"""
    try:
        loop = asyncio.get_event_loop()
        
        def search():
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(f"ytsearch8:{query}", download=False)
                videos = []
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry and entry.get('id'):
                            videos.append({
                                'title': entry.get('title', 'بدون عنوان')[:70],
                                'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                'duration': entry.get('duration', 0),
                                'uploader': entry.get('uploader', 'غير معروف')[:25],
                                'views': entry.get('view_count', 0),
                                'thumbnail': entry.get('thumbnail', '')
                            })
                return videos[:6]
        
        return await loop.run_in_executor(None, search)
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")
        return []

# ============= أوامر البوت =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت مع الكيبورد"""
    await update.message.reply_text(
        "🎥 **مرحباً بك في بوت تحميل الفيديوهات!**\n\n"
        "📥 **أرسل رابط فيديو أو استخدم الأزرار أدناه**\n\n"
        "✅ **المنصات المدعومة:**\n"
        "يوتيوب - تيك توك - انستقرام - فيسبوك - بنترست - تويتر - ريديت - وغيرها",
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المساعدة"""
    await update.message.reply_text(
        "🆘 **المساعدة:**\n\n"
        "**📥 تحميل فيديو:**\n"
        "• أرسل الرابط مباشرة\n"
        "• أو اضغط على زر 'تحميل فيديو'\n\n"
        "**🎵 تحميل صوت:**\n"
        "• أرسل رابط يوتيوب واختر MP3\n"
        "• أو اضغط على زر 'تحميل صوت'\n\n"
        "**🔍 بحث في يوتيوب:**\n"
        "• اكتب كلمة البحث\n"
        "• أو اضغط على زر 'بحث في يوتيوب'\n\n"
        "**⚡ ملاحظات:**\n"
        "• الحد الأقصى للحجم: 50 ميجابايت\n"
        "• الفيديوهات الطويلة تحتاج وقت",
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الإحصائيات"""
    uptime = datetime.now() - stats['start']
    hours = uptime.total_seconds() // 3600
    
    await update.message.reply_text(
        f"📊 **الإحصائيات:**\n\n"
        f"📥 التحميلات: {stats['downloads']}\n"
        f"🔍 عمليات البحث: {stats['searches']}\n"
        f"⏱️ وقت التشغيل: {int(hours)} ساعة\n"
        f"🌐 المنصات: {len(SUPPORTED_SITES)}",
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات عن البوت"""
    await update.message.reply_text(
        "ℹ️ **عن البوت:**\n\n"
        "**الاسم:** بوت تحميل الفيديوهات\n"
        "**الإصدار:** 5.0 (النسخة السريعة)\n"
        "**المطور:** بوت متطور\n\n"
        "**المميزات:**\n"
        "• تحميل من جميع المنصات\n"
        "• تحميل صوت MP3 من يوتيوب\n"
        "• بحث متقدم في يوتيوب\n"
        "• واجهة سهلة الاستخدام\n\n"
        "🚀 **استمتع بالتحميل السريع!**",
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

# ============= معالجة أزرار الـ Reply Keyboard =============

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار الـ Reply Keyboard"""
    text = update.message.text
    
    if text == "📥 تحميل فيديو":
        await update.message.reply_text(
            "📥 **أرسل رابط الفيديو:**\n\n"
            "سأقوم بتحميله لك فوراً",
            parse_mode='Markdown'
        )
    
    elif text == "🎵 تحميل صوت":
        await update.message.reply_text(
            "🎵 **أرسل رابط يوتيوب:**\n\n"
            "سأقوم بتحميل الصوت بصيغة MP3",
            parse_mode='Markdown'
        )
    
    elif text == "🔍 بحث في يوتيوب":
        await update.message.reply_text(
            "🔍 **أكتب كلمة البحث:**\n\n"
            "مثال: 'أغاني حزينة' أو 'مقاطع مضحكة'",
            parse_mode='Markdown'
        )
    
    elif text == "📊 إحصائيات":
        await stats_command(update, context)
    
    elif text == "❓ مساعدة":
        await help_command(update, context)
    
    elif text == "ℹ️ عن البوت":
        await about_command(update, context)

# ============= معالجة روابط يوتيوب =============

async def handle_youtube(update: Update, url: str):
    """معالجة روابط يوتيوب"""
    msg = await update.message.reply_text("⏳ **جاري تحضير الفيديو...**", parse_mode='Markdown')
    
    try:
        info = await get_video_info(url)
        
        if info:
            # أزرار Inline Keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎬 فيديو", callback_data=f"dl_video_{url}"),
                    InlineKeyboardButton("🎵 MP3", callback_data=f"dl_audio_{url}"),
                    InlineKeyboardButton("🎤 بصمة", callback_data=f"dl_voice_{url}")
                ],
                [
                    InlineKeyboardButton("👁️ مشاهدة", url=url),
                    InlineKeyboardButton("🔍 بحث مشابه", callback_data=f"similar_{url}")
                ]
            ])
            
            duration = format_duration(info['duration'])
            views = format_number(info['views'])
            
            caption = (
                f"🎬 **{info['title'][:100]}**\n\n"
                f"👤 {info['uploader']}\n"
                f"⏱️ {duration} | 👁️ {views}\n\n"
                f"📥 **اختر نوع التحميل:**"
            )
            
            await msg.delete()
            
            # تحميل الصورة
            if info.get('thumbnail'):
                try:
                    import urllib.request
                    thumb_path = os.path.join(DOWNLOAD_FOLDER, 'thumb.jpg')
                    urllib.request.urlretrieve(info['thumbnail'], thumb_path)
                    with open(thumb_path, 'rb') as thumb:
                        await update.message.reply_photo(
                            photo=thumb,
                            caption=caption,
                            reply_markup=keyboard,
                            parse_mode='Markdown'
                        )
                    os.remove(thumb_path)
                except:
                    await update.message.reply_text(
                        caption,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        else:
            await msg.edit_text("❌ **فشل في جلب المعلومات**", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await msg.edit_text(f"❌ **خطأ:** {str(e)[:100]}", parse_mode='Markdown')

# ============= معالجة الروابط المباشرة =============

async def handle_direct(update: Update, url: str):
    """تحميل مباشر"""
    msg = await update.message.reply_text("⏳ **جاري التحميل...**", parse_mode='Markdown')
    
    try:
        file_path, info = await download_media(url, 'video')
        
        if file_path and os.path.exists(file_path):
            size = os.path.getsize(file_path) / (1024 * 1024)
            
            if size > 50:
                await msg.edit_text(f"❌ **كبير جداً**\n{size:.1f} MB", parse_mode='Markdown')
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
            stats['downloads'] += 1
            
        else:
            await msg.edit_text("❌ **فشل التحميل**\nتأكد من الرابط", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await msg.edit_text(f"❌ **خطأ:** {str(e)[:100]}", parse_mode='Markdown')

# ============= البحث في يوتيوب =============

async def handle_search(update: Update, query: str):
    """البحث في يوتيوب"""
    stats['searches'] += 1
    
    msg = await update.message.reply_text(f"🔍 **جاري البحث:** {query}", parse_mode='Markdown')
    
    try:
        videos = await search_youtube(query)
        
        if videos:
            await msg.delete()
            
            for i, video in enumerate(videos, 1):
                duration = format_duration(video['duration'])
                views = format_number(video['views'])
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🎬 فيديو", callback_data=f"dl_video_{video['url']}"),
                        InlineKeyboardButton("🎵 MP3", callback_data=f"dl_audio_{video['url']}")
                    ],
                    [InlineKeyboardButton("👁️ مشاهدة", url=video['url'])]
                ])
                
                caption = (
                    f"{i}. **{video['title']}**\n"
                    f"👤 {video['uploader']} | ⏱️ {duration} | 👁️ {views}"
                )
                
                # تحميل الصورة
                if video['thumbnail']:
                    try:
                        import urllib.request
                        thumb_path = os.path.join(DOWNLOAD_FOLDER, f"search_{i}.jpg")
                        urllib.request.urlretrieve(video['thumbnail'], thumb_path)
                        with open(thumb_path, 'rb') as thumb:
                            await update.message.reply_photo(
                                photo=thumb,
                                caption=caption,
                                reply_markup=keyboard,
                                parse_mode='Markdown'
                            )
                        os.remove(thumb_path)
                    except:
                        await update.message.reply_text(
                            caption,
                            reply_markup=keyboard,
                            parse_mode='Markdown'
                        )
                else:
                    await update.message.reply_text(
                        caption,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
        else:
            await msg.edit_text("❌ **لا توجد نتائج**\nجرب كلمات أخرى", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await msg.edit_text(f"❌ **خطأ:** {str(e)[:100]}", parse_mode='Markdown')

# ============= معالج الأزرار الداخلية (Inline) =============

async def inline_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة Inline Keyboard"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('dl_'):
        parts = data.split('_', 2)
        if len(parts) >= 3:
            media_type = parts[1]
            url = parts[2]
            
            await query.edit_message_caption(
                caption=f"⏳ **جاري التحميل...**",
                parse_mode='Markdown'
            )
            
            try:
                file_path, info = await download_media(url, media_type)
                
                if file_path and os.path.exists(file_path):
                    size = os.path.getsize(file_path) / (1024 * 1024)
                    
                    with open(file_path, 'rb') as f:
                        if media_type == 'video':
                            await query.message.reply_video(
                                video=f,
                                caption=f"✅ **تم التحميل!**\n📊 {size:.1f} MB",
                                supports_streaming=True
                            )
                        elif media_type == 'audio':
                            await query.message.reply_audio(
                                audio=f,
                                caption=f"✅ **ملف MP3**\n📊 {size:.1f} MB"
                            )
                        elif media_type == 'voice':
                            await query.message.reply_voice(
                                voice=f,
                                caption=f"✅ **بصمة صوتية**\n📊 {size:.1f} MB"
                            )
                    
                    os.remove(file_path)
                    stats['downloads'] += 1
                    
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
    
    elif data.startswith('similar_'):
        url = data.replace('similar_', '')
        await query.edit_message_caption(
            caption="🔍 **جاري البحث عن فيديوهات مشابهة...**",
            parse_mode='Markdown'
        )
        
        info = await get_video_info(url)
        if info:
            keywords = info['title'].split()[:3]
            await handle_search(update, ' '.join(keywords))

# ============= المعالج الرئيسي =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع الرسائل"""
    text = update.message.text
    
    # أزرار الـ Reply Keyboard
    if text in ["📥 تحميل فيديو", "🎵 تحميل صوت", "🔍 بحث في يوتيوب", "📊 إحصائيات", "❓ مساعدة", "ℹ️ عن البوت"]:
        await handle_button(update, context)
        return
    
    # رابط
    if text.startswith(('http://', 'https://')):
        if not is_supported_url(text):
            await update.message.reply_text(
                "⚠️ **الرابط غير مدعوم**\nالمنصات المدعومة في القائمة",
                parse_mode='Markdown',
                reply_markup=MAIN_KEYBOARD
            )
            return
        
        if is_youtube_url(text):
            await handle_youtube(update, text)
        else:
            await handle_direct(update, text)
    
    # بحث
    elif len(text) > 2:
        await handle_search(update, text)
    else:
        await update.message.reply_text(
            "❌ **كلمة البحث قصيرة جداً**\nاكتب كلمة أطول من حرفين",
            parse_mode='Markdown',
            reply_markup=MAIN_KEYBOARD
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ: {context.error}")

def cleanup():
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except:
        pass

def main():
    logger.info("🚀 بدء التشغيل...")
    
    app = Application.builder().token(TOKEN).build()
    
    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    # معالجات
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(inline_button_handler))
    app.add_error_handler(error_handler)
    
    print("\n" + "="*50)
    print("🤖 البوت السريع يعمل!")
    print(f"📁 {DOWNLOAD_FOLDER}")
    print("="*50 + "\n")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    cleanup()

if __name__ == '__main__':
    main()
