import os
import logging
import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# إعدادات البوت
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا مباشرة
DOWNLOAD_FOLDER = "downloads"

# إنشاء مجلد التحميلات إذا لم يكن موجوداً
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جودات الفيديو المتوفرة
QUALITIES = {
    '144': '144p (منخفضة)',
    '360': '360p (متوسطة)',
    '480': '480p (جيدة)',
    '720': '720p (عالية)',
    '1080': '1080p (فائقة)',
    'best': 'أفضل جودة'
}

class VideoBot:
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ترحيب البوت"""
        user = update.effective_user
        welcome = f"""
🎬 *مرحباً {user.first_name}!*

أنا بوت تحميل الفيديوهات الاحترافي 🤖

📥 *أرسل لي أي رابط فيديو وسأقوم بتحميله لك*
🔍 *أو اكتب كلمة للبحث عن فيديوهات*

✨ *المميزات:*
• تحميل من يوتيوب، تيك توك، انستغرام، فيسبوك، تويتر
• اختيار جودة التحميل (144p - 1080p)
• بحث سريع عن الفيديوهات
• تحميل مجاني وسريع

👇 *أرسل الرابط أو كلمة البحث الآن*
        """
        
        keyboard = [[
            InlineKeyboardButton("📱 المنصات المدعومة", callback_data="platforms"),
            InlineKeyboardButton("❓ المساعدة", callback_data="help")
        ]]
        
        await update.message.reply_text(
            welcome, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل"""
        text = update.message.text
        
        # التحقق إذا كان الرابط
        if re.match(r'https?://\S+', text):
            await self.handle_url(update, context, text)
        else:
            await self.handle_search(update, context, text)

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة روابط الفيديو"""
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
        
        try:
            # الحصول على معلومات الفيديو
            ydl_opts = {'quiet': True, 'no_warnings': True}
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # حفظ المعلومات
                context.user_data['url'] = url
                context.user_data['title'] = info.get('title', 'فيديو')
                
                # عرض خيارات الجودة
                keyboard = []
                for q_id, q_name in QUALITIES.items():
                    keyboard.append([InlineKeyboardButton(
                        f"🎬 {q_name}", callback_data=f"q_{q_id}"
                    )])
                keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                
                info_text = f"""
🎥 *معلومات الفيديو*

📹 العنوان: {info.get('title', 'غير معروف')[:100]}
⏱ المدة: {self.format_time(info.get('duration', 0))}
📊 المنصة: {info.get('extractor', 'غير معروفة')}

اختر الجودة المناسبة:
                """
                
                await msg.edit_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {str(e)[:100]}")

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """معالجة البحث"""
        msg = await update.message.reply_text(f"🔍 جاري البحث عن: {query}...")
        
        try:
            # البحث في يوتيوب
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                
                if results and 'entries' in results:
                    keyboard = []
                    for i, video in enumerate(results['entries'], 1):
                        if video:
                            title = video.get('title', 'بدون عنوان')[:40]
                            duration = self.format_time(video.get('duration', 0))
                            btn_text = f"{i}. {title} - {duration}"
                            url = f"https://youtube.com/watch?v={video.get('id', '')}"
                            keyboard.append([InlineKeyboardButton(
                                btn_text, callback_data=f"url_{url}"
                            )])
                    
                    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
                    
                    await msg.edit_text(
                        f"🔍 نتائج البحث عن: {query}\nاختر الفيديو:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await msg.edit_text("❌ لا توجد نتائج")
                    
        except Exception as e:
            await msg.edit_text(f"❌ خطأ في البحث: {str(e)[:100]}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "platforms":
            text = """
📱 *المنصات المدعومة:*

✅ يوتيوب - YouTube
✅ تيك توك - TikTok
✅ انستغرام - Instagram
✅ فيسبوك - Facebook
✅ تويتر - Twitter/X
✅ ريديت - Reddit
✅ بنترست - Pinterest
✅ فيميو - Vimeo
✅ ديلي موشن - Dailymotion

*والمزيد...*
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back")
                ]])
            )
            
        elif data == "help":
            text = """
❓ *كيفية الاستخدام:*

1️⃣ *لتحميل فيديو:*
   • أرسل رابط الفيديو
   • اختر الجودة المناسبة
   • انتظر التحميل

2️⃣ *للبحث:*
   • اكتب كلمة البحث
   • اختر الفيديو من النتائج
   • اختر الجودة

⚡ *ملاحظات:*
• الحد الأقصى 50 ميجابايت
• جميع الخدمات مجانية
• يتم حذف الفيديوهات بعد الإرسال
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back")
                ]])
            )
            
        elif data == "back":
            await query.message.delete()
            await self.start(update, context)
            
        elif data == "cancel":
            await query.edit_message_text("✅ تم الإلغاء")
            
        elif data.startswith("q_"):
            quality = data.replace("q_", "")
            await self.download_video(update, context, quality)
            
        elif data.startswith("url_"):
            url = data.replace("url_", "")
            await self.handle_url(update, context, url)

    async def download_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
        """تحميل الفيديو"""
        query = update.callback_query
        url = context.user_data.get('url')
        title = context.user_data.get('title', 'video')
        
        if not url:
            await query.edit_message_text("❌ الرابط غير صالح")
            return
        
        msg = await query.edit_message_text(
            f"⬇️ جاري التحميل...\n📹 {title[:50]}"
        )
        
        try:
            # إعدادات التحميل
            if quality == 'best':
                format_spec = 'best[ext=mp4]/best'
            else:
                format_spec = f'best[height<={quality}][ext=mp4]/best[height<={quality}]'
            
            filename = f"{DOWNLOAD_FOLDER}/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.%(ext)s"
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': filename,
                'quiet': True,
            }
            
            # التحميل
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
                
                if os.path.exists(file):
                    size = os.path.getsize(file)
                    
                    # إرسال الفيديو
                    with open(file, 'rb') as video:
                        caption = f"""
✅ *تم التحميل بنجاح*

📹 العنوان: {info.get('title', 'فيديو')[:100]}
⚡ الجودة: {QUALITIES.get(quality, quality)}
📦 الحجم: {self.format_size(size)}
⏱ المدة: {self.format_time(info.get('duration', 0))}
                        """
                        
                        await context.bot.send_video(
                            chat_id=update.effective_user.id,
                            video=video,
                            caption=caption,
                            parse_mode='Markdown'
                        )
                    
                    # حذف الملف
                    os.remove(file)
                    await msg.delete()
                    
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {str(e)[:100]}")

    def format_time(self, seconds):
        """تنسيق الوقت"""
        if not seconds:
            return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def format_size(self, bytes):
        """تنسيق الحجم"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024
        return f"{bytes:.1f} TB"

    def run(self):
        """تشغيل البوت"""
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        print("🤖 البوت يعمل... جاهز لاستقبال الروابط!")
        app.run_polling()

if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
