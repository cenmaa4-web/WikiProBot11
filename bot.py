# bot.py - بوت تحميل الفيديوهات من جميع منصات التواصل الاجتماعي
import os
import re
import asyncio
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# ===================== إعدادات البوت =====================
8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4 = "ضع_توكن_البوت_هنا"  # استبدل هذا بالتوكن من @BotFather

# رسالة الترحيب
START_MESSAGE = """
🎬 **مرحباً بك في بوت التحميل الشامل!**

📌 **طريقة الاستخدام:**
• أرسل رابط فيديو من أي منصة ← سيتم رفع الفيديو مباشرة
• أرسل رابط يوتيوب ← ستظهر لك خيارات التحميل
• أرسل أي كلمة بحث ← سأعطيك 4 نتائج من اليوتيوب مع الصور

✨ **المنصات المدعومة:**
✅ YouTube | ✅ TikTok | ✅ Instagram | ✅ Facebook
✅ Twitter/X | ✅ Reddit | ✅ Vimeo | ✅ Dailymotion
✅ Twitch | ✅ SoundCloud | ✅ والمزيد...

⚡ **مميزات يوتيوب:**
• تحميل فيديو بجودة عالية
• تحميل صوت MP3
• بصمة صوتية (30 ثانية)
• بحث مباشر في يوتيوب

🎯 **فقط أرسل الرابط أو كلمة البحث واترك الباقي علي!**
"""

# ===================== كلاس تحميل الفيديوهات =====================
class VideoDownloader:
    def __init__(self):
        self.downloads_folder = "downloads"
        os.makedirs(self.downloads_folder, exist_ok=True)
        
    def is_youtube_link(self, url: str) -> bool:
        """التحقق إذا كان الرابط من يوتيوب"""
        youtube_patterns = [
            r'(youtube\.com/watch\?v=)',
            r'(youtu\.be/)',
            r'(youtube\.com/shorts/)',
            r'(youtube\.com/embed/)'
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
    def is_social_link(self, url: str) -> bool:
        """التحقق إذا كان الرابط من منصة تواصل اجتماعي"""
        social_sites = [
            'tiktok.com', 'instagram.com', 'facebook.com', 
            'fb.com', 'twitter.com', 'x.com', 'reddit.com', 
            'vimeo.com', 'dailymotion.com', 'twitch.tv',
            'soundcloud.com', 'tumblr.com', 'pinterest.com'
        ]
        return any(site in url.lower() for site in social_sites)
    
    async def download_video(self, url: str) -> str:
        """تحميل فيديو من أي منصة"""
        ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': f'{self.downloads_folder}/%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False,
            'force_generic_extractor': False,
        }
        
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                if info and 'requested_downloads' in info:
                    filename = info['requested_downloads'][0]['filepath']
                elif info and 'entries' in info:
                    filename = ydl.prepare_filename(info['entries'][0])
                else:
                    filename = ydl.prepare_filename(info)
                return filename
        except Exception as e:
            raise Exception(f"فشل التحميل: {str(e)}")
    
    async def download_audio(self, url: str) -> str:
        """تحميل الصوت فقط من يوتيوب بصيغة MP3"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{self.downloads_folder}/audio_%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.opus', '.mp3')
                return filename
        except Exception as e:
            raise Exception(f"فشل تحميل الصوت: {str(e)}")
    
    async def download_audio_preview(self, url: str, duration: int = 30) -> str:
        """تحميل بصمة صوتية (مقتطف قصير)"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': f'{self.downloads_folder}/preview_%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
                
                # قص الصوت إلى 30 ثانية إذا كان ffmpeg موجود
                output_preview = filename.replace('.mp3', '_preview.mp3')
                try:
                    import subprocess
                    subprocess.run([
                        'ffmpeg', '-i', filename, '-t', str(duration), 
                        '-acodec', 'copy', output_preview, '-y'
                    ], capture_output=True, check=False)
                    if os.path.exists(output_preview):
                        os.remove(filename)
                        return output_preview
                except:
                    pass
                return filename
        except Exception as e:
            raise Exception(f"فشل تحميل البصمة: {str(e)}")
    
    async def search_youtube(self, query: str, max_results: int = 4) -> list:
        """البحث في يوتيوب"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
        }
        
        try:
            loop = asyncio.get_event_loop()
            search_query = f"ytsearch{max_results}:{query}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(search_query, download=False))
                results = []
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            duration = entry.get('duration', 0) or 0
                            minutes = duration // 60
                            seconds = duration % 60
                            results.append({
                                'title': entry.get('title', 'بدون عنوان'),
                                'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                                'thumbnail': entry.get('thumbnail', ''),
                                'duration': f"{minutes}:{seconds:02d}",
                                'duration_seconds': duration,
                                'channel': entry.get('uploader', 'غير معروف')
                            })
                return results
        except Exception as e:
            raise Exception(f"فشل البحث: {str(e)}")

# ===================== دوال الأزرار =====================
def get_youtube_buttons(video_url: str) -> InlineKeyboardMarkup:
    """إنشاء أزرار تحميل اليوتيوب"""
    # ترميز الرابط لاستخدامه في callback data
    encoded_url = video_url.replace('&', '&amp;')
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"dl_video_{encoded_url}"),
            InlineKeyboardButton("🎵 تحميل صوت MP3", callback_data=f"dl_audio_{encoded_url}"),
        ],
        [
            InlineKeyboardButton("🔊 بصمة صوتية (30 ث)", callback_data=f"dl_preview_{encoded_url}"),
            InlineKeyboardButton("🔍 بحث في اليوتيوب", switch_inline_query_current_chat=""),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_search_result_buttons(video_url: str) -> InlineKeyboardMarkup:
    """إنشاء زر تحميل لنتائج البحث"""
    encoded_url = video_url.replace('&', '&amp;')
    keyboard = [[
        InlineKeyboardButton("🎬 تحميل الفيديو", callback_data=f"dl_video_{encoded_url}")
    ]]
    return InlineKeyboardMarkup(keyboard)

# ===================== معالجات البوت =====================
downloader = VideoDownloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start"""
    await update.message.reply_text(START_MESSAGE, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع الرسائل الواردة"""
    user_message = update.message.text.strip()
    
    if not user_message:
        return
    
    # إرسال رسالة "جاري المعالجة"
    processing_msg = await update.message.reply_text("⏳ **جاري معالجة طلبك...**", parse_mode='Markdown')
    
    # التحقق من وجود رابط
    if 'http://' in user_message or 'https://' in user_message:
        # حالة 1: رابط يوتيوب
        if downloader.is_youtube_link(user_message):
            buttons = get_youtube_buttons(user_message)
            await processing_msg.edit_text(
                "📹 **✅ تم اكتشاف رابط يوتيوب!**\n\n"
                "🎯 **اختر ما تريد تحميله:**\n"
                "• فيديو عالي الجودة\n"
                "• صوت MP3 فقط\n"
                "• بصمة صوتية 30 ثانية\n"
                "• أو ابحث عن فيديو آخر",
                reply_markup=buttons,
                parse_mode='Markdown'
            )
        
        # حالة 2: رابط منصة تواصل اجتماعي
        elif downloader.is_social_link(user_message):
            await processing_msg.edit_text("📥 **جاري تحميل الفيديو من المنصة...**\n⏱️ قد يستغرق هذا بضع ثوانٍ", parse_mode='Markdown')
            try:
                video_path = await downloader.download_video(user_message)
                
                # إرسال الفيديو
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="✅ **تم التحميل بنجاح!** 🎉\nشكراً لاستخدام البوت",
                        supports_streaming=True,
                        parse_mode='Markdown'
                    )
                
                # حذف الملف بعد الإرسال
                os.remove(video_path)
                await processing_msg.delete()
                
            except Exception as e:
                await processing_msg.edit_text(f"❌ **فشل التحميل!**\n\nالسبب: {str(e)[:200]}", parse_mode='Markdown')
        
        # حالة 3: رابط غير مدعوم
        else:
            await processing_msg.edit_text(
                "❌ **عذراً، هذا الرابط غير مدعوم حالياً!**\n\n"
                "📋 **المنصات المدعومة:**\n"
                "YouTube | TikTok | Instagram | Facebook | Twitter | Reddit | Vimeo",
                parse_mode='Markdown'
            )
    
    # حالة 4: نص عادي (بحث في يوتيوب)
    else:
        await processing_msg.edit_text(f"🔍 **جاري البحث عن:** `{user_message}`\n⏱️ يرجى الانتظار...", parse_mode='Markdown')
        try:
            results = await downloader.search_youtube(user_message, max_results=4)
            
            if not results:
                await processing_msg.edit_text("❌ **لم يتم العثور على نتائج**\nحاول بكلمات مختلفة", parse_mode='Markdown')
                return
            
            # إرسال النتائج مع الصور
            await processing_msg.edit_text("📊 **نتائج البحث:**", parse_mode='Markdown')
            
            for i, result in enumerate(results, 1):
                caption = (
                    f"🎥 **{result['title'][:60]}**\n\n"
                    f"⏱️ **المدة:** {result['duration']}\n"
                    f"📺 **القناة:** {result['channel']}\n"
                    f"🔗 **الرابط:** [اضغط للمشاهدة]({result['url']})"
                )
                
                # إرسال الصورة المصغرة مع زر التحميل
                try:
                    if result['thumbnail']:
                        await update.message.reply_photo(
                            photo=result['thumbnail'],
                            caption=caption,
                            reply_markup=get_search_result_buttons(result['url']),
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            caption,
                            reply_markup=get_search_result_buttons(result['url']),
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    await update.message.reply_text(
                        caption,
                        reply_markup=get_search_result_buttons(result['url']),
                        parse_mode='Markdown'
                    )
            
            await processing_msg.delete()
            
        except Exception as e:
            await processing_msg.edit_text(f"❌ **فشل البحث!**\n\nالسبب: {str(e)[:200]}", parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # استخراج نوع التحميل والرابط
    if not data.startswith('dl_'):
        return
    
    parts = data.split('_', 2)
    if len(parts) < 3:
        return
    
    dl_type = parts[1]  # video, audio, preview
    url = parts[2].replace('&amp;', '&')  # فك ترميز الرابط
    
    # إرسال رسالة جاري التحميل
    await query.edit_message_text("⏳ **جاري التحميل...**\n📥 يرجى الانتظار قليلاً", parse_mode='Markdown')
    
    try:
        if dl_type == 'video':
            video_path = await downloader.download_video(url)
            with open(video_path, 'rb') as video_file:
                await query.message.reply_video(
                    video=video_file,
                    caption="✅ **تم تحميل الفيديو بنجاح!** 🎬\nاستمتع بالمشاهدة",
                    supports_streaming=True,
                    parse_mode='Markdown'
                )
            os.remove(video_path)
            
        elif dl_type == 'audio':
            audio_path = await downloader.download_audio(url)
            with open(audio_path, 'rb') as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    title="🎵 تحميل من يوتيوب",
                    performer="YouTube Downloader Bot",
                    caption="✅ **تم تحميل الصوت بنجاح!** 🎧"
                )
            os.remove(audio_path)
            
        elif dl_type == 'preview':
            preview_path = await downloader.download_audio_preview(url, duration=30)
            with open(preview_path, 'rb') as preview_file:
                await query.message.reply_audio(
                    audio=preview_file,
                    title="🔊 بصمة صوتية (30 ثانية)",
                    performer="YouTube Preview",
                    caption="✅ **تم تحميل البصمة الصوتية!** 🎵"
                )
            os.remove(preview_path)
        
        # حذف رسالة "جاري التحميل"
        await query.delete_message()
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ **فشل التحميل!**\n\n"
            f"⚠️ **السبب:** {str(e)[:200]}\n\n"
            f"💡 **نصيحة:** تأكد من صحة الرابط وحاول مرة أخرى",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    print(f"حدث خطأ: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ **حدث خطأ غير متوقع!**\n"
            "يرجى المحاولة مرة أخرى لاحقاً",
            parse_mode='Markdown'
        )

# ===================== تشغيل البوت =====================
async def main():
    """الوظيفة الرئيسية لتشغيل البوت"""
    # التحقق من توكن البوت
    if BOT_TOKEN == "ضع_توكن_البوت_هنا":
        print("❌ خطأ: يرجى وضع توكن البوت الصحيح في المتغير BOT_TOKEN")
        print("احصل على توكن من @BotFather على تليجرام")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالجات الأوامر والرسائل
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    # بدء البوت
    print("=" * 50)
    print("🚀 بوت التحميل الشامل يعمل الآن...")
    print("📱 اذهب إلى تليجرام وابدأ باستخدام البوت")
    print("💡 أرسل /start لبدء الاستخدام")
    print("=" * 50)
    
    # بدء polling
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
