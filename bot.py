import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create downloads folder
DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Supported platforms
SUPPORTED_PLATFORMS = [
    'youtube', 'youtu.be', 'instagram', 'facebook', 
    'twitter', 'x.com', 'tiktok', 'reddit', 'pinterest'
]

# Video qualities
QUALITIES = {
    '144': '144p (Low)',
    '360': '360p (Medium)',
    '480': '480p (Good)',
    '720': '720p (HD)',
    '1080': '1080p (Full HD)',
    'best': 'Best Quality'
}

class VideoDownloaderBot:
    def __init__(self):
        self.user_data = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        welcome_msg = f"""
🎬 *مرحباً بك {user.first_name} في بوت تحميل الفيديوهات الاحترافي!*

📥 *أرسل لي رابط فيديو من أي منصة وسأقوم بتحميله لك*

✨ *المميزات:*
• تحميل من يوتيوب، انستغرام، تيك توك، تويتر، فيسبوك
• اختيار جودة الفيديو (144p حتى 1080p)
• بحث عن فيديوهات بإرسال الكلمات المفتاحية
• تحميل سريع ومباشر
• دفع آمن ومجاني

🔍 *للبحث:* فقط اكتب الكلمة التي تريد البحث عنها
📎 *للتحميل:* أرسل رابط الفيديو

👇 *أرسل الرابط الآن وابدأ التحميل!*
        """
        
        # Create buttons
        keyboard = [
            [InlineKeyboardButton("📱 المنصات المدعومة", callback_data="platforms")],
            [InlineKeyboardButton("❓ طريقة الاستخدام", callback_data="help"),
             InlineKeyboardButton("ℹ️ عن البوت", callback_data="about")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_msg,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages (URLs or search queries)"""
        text = update.message.text.strip()
        
        # Check if it's a URL
        if text.startswith(('http://', 'https://')):
            await self.handle_url(update, context, text)
        else:
            # It's a search query
            await self.handle_search(update, context, text)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """Handle video URL"""
        msg = await update.message.reply_text("🔄 جاري معالجة الرابط...")
        
        try:
            # Get video info
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Store info in context
                context.user_data['video_url'] = url
                context.user_data['video_title'] = info.get('title', 'فيديو')
                context.user_data['video_duration'] = info.get('duration', 0)
                context.user_data['video_thumbnail'] = info.get('thumbnail', '')
                
                # Create quality selection buttons
                keyboard = []
                for quality_id, quality_name in QUALITIES.items():
                    keyboard.append([InlineKeyboardButton(
                        f"🎥 {quality_name}", 
                        callback_data=f"dl_{quality_id}"
                    )])
                
                keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Show video info
                info_text = f"""
🎬 *معلومات الفيديو*

📹 *العنوان:* {info.get('title', 'غير معروف')[:100]}
⏱ *المدة:* {self.format_duration(info.get('duration', 0))}
📊 *المنصة:* {info.get('extractor_key', 'غير معروفة')}

👇 *اختر جودة التحميل:*
                """
                
                await msg.edit_text(
                    info_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await msg.edit_text(f"❌ حدث خطأ: {str(e)[:200]}")
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """Handle search queries"""
        search_msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")
        
        try:
            # Search on YouTube
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            search_query = f"ytsearch5:{query}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(search_query, download=False)
                
                if results and 'entries' in results:
                    keyboard = []
                    for idx, video in enumerate(results['entries'][:5], 1):
                        if video:
                            title = video.get('title', 'بدون عنوان')[:50]
                            duration = self.format_duration(video.get('duration', 0))
                            button_text = f"{idx}. {title} ({duration})"
                            keyboard.append([InlineKeyboardButton(
                                button_text,
                                callback_data=f"search_{video.get('webpage_url', '')}"
                            )])
                    
                    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await search_msg.edit_text(
                        f"🔍 *نتائج البحث عن:* '{query}'\n\nاختر الفيديو الذي تريد تحميله:",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await search_msg.edit_text("❌ لم يتم العثور على نتائج")
                    
        except Exception as e:
            await search_msg.edit_text(f"❌ خطأ في البحث: {str(e)[:200]}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "platforms":
            platforms_text = """
📱 *المنصات المدعومة:*

✅ YouTube
✅ Instagram
✅ Facebook
✅ TikTok
✅ Twitter/X
✅ Reddit
✅ Pinterest
✅ Vimeo
✅ Dailymotion
✅ والعديد من المنصات الأخرى!

📥 *أرسل الرابط وسأقوم بتحميله فوراً*
            """
            await query.edit_message_text(
                platforms_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
            
        elif data == "help":
            help_text = """
❓ *طريقة استخدام البوت:*

1️⃣ *لتحميل فيديو:*
   • أرسل رابط الفيديو من أي منصة
   • اختر الجودة المناسبة
   • انتظر قليلاً وسيصلك الفيديو

2️⃣ *للبحث عن فيديوهات:*
   • اكتب الكلمة التي تريد البحث عنها
   • اختر الفيديو من النتائج
   • اختر الجودة واستلم الفيديو

⚡ *مميزات إضافية:*
• تحميل بجودة عالية تصل إلى 1080p
• دعم جميع المنصات
• سرعة تحميل عالية
• مجاني تماماً

📌 *ملاحظة:* الحد الأقصى لحجم الملف 50 ميجابايت
            """
            await query.edit_message_text(
                help_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
            
        elif data == "about":
            about_text = """
ℹ️ *عن البوت:*

🎬 *الاسم:* فيديو داونلودر برو
🤖 *الإصدار:* 1.0
👨‍💻 *المطور:* @YourUsername
📅 *التحديث:* 2024

✨ *المميزات:*
• تحميل من 20+ منصة
• اختيار جودة الفيديو
• بحث متقدم
• واجهة سهلة الاستخدام
• تحديثات مستمرة

⚡ *بوت احترافي لتحميل الفيديوهات من جميع المنصات*
            """
            await query.edit_message_text(
                about_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")
                ]])
            )
            
        elif data == "back_to_start":
            await query.message.delete()
            await self.start(update, context)
            
        elif data.startswith("dl_"):
            quality = data.replace("dl_", "")
            await self.download_video(update, context, quality)
            
        elif data.startswith("search_"):
            url = data.replace("search_", "")
            await self.handle_url(update, context, url)
            
        elif data == "cancel":
            await query.edit_message_text("❌ تم الإلغاء")
    
    async def download_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        """Download video with selected quality"""
        query = update.callback_query
        url = context.user_data.get('video_url')
        title = context.user_data.get('video_title', 'video')
        
        if not url:
            await query.edit_message_text("❌ الرابط غير صالح، أرسل الرابط مرة أخرى")
            return
        
        download_msg = await query.edit_message_text(
            f"⬇️ جاري تحميل الفيديو...\n📹 {title[:50]}\n⚡ الجودة: {QUALITIES.get(quality, quality)}"
        )
        
        try:
            # Configure download options
            if quality == 'best':
                format_spec = 'best[ext=mp4]/best'
            else:
                format_spec = f'best[height<={quality}][ext=mp4]/best[height<={quality}]'
            
            filename = f"{DOWNLOAD_FOLDER}/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.%(ext)s"
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': filename,
                'quiet': True,
                'no_warnings': True,
            }
            
            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                
                # Check if file exists
                if os.path.exists(downloaded_file):
                    file_size = os.path.getsize(downloaded_file)
                    
                    # Send video
                    with open(downloaded_file, 'rb') as video:
                        caption = f"""
🎬 *تم التحميل بنجاح!*

📹 *العنوان:* {info.get('title', 'فيديو')[:100]}
⚡ *الجودة:* {QUALITIES.get(quality, quality)}
📦 *الحجم:* {self.format_size(file_size)}
⏱ *المدة:* {self.format_duration(info.get('duration', 0))}
                        """
                        
                        await context.bot.send_video(
                            chat_id=update.effective_user.id,
                            video=video,
                            caption=caption,
                            parse_mode='Markdown',
                            supports_streaming=True
                        )
                    
                    # Clean up
                    os.remove(downloaded_file)
                    await download_msg.delete()
                    
                else:
                    await download_msg.edit_text("❌ فشل التحميل")
                    
        except Exception as e:
            await download_msg.edit_text(f"❌ خطأ في التحميل: {str(e)[:200]}")
    
    def format_duration(self, seconds):
        """Format duration in seconds to MM:SS or HH:MM:SS"""
        if not seconds:
            return "00:00"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    def format_size(self, bytes):
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024
        return f"{bytes:.1f} TB"
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى."
            )
    
    def run(self):
        """Run the bot"""
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_error_handler(self.error_handler)
        
        # Start bot
        print("🤖 البوت يعمل... جاهز لاستقبال الروابط والبحث!")
        app.run_polling()

if __name__ == "__main__":
    bot = VideoDownloaderBot()
    bot.run()
