import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# إعداد التسجيل (logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت - ضع التوكن الخاص بك هنا
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# مجلد مؤقت للتحميلات
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = """
🎥 مرحباً بك في بوت تحميل الفيديوهات!

📥 أرسل لي رابط الفيديو وسأقوم بتحميله لك.

💡 البوت يدعم:
• يوتيوب
• تويتر
• انستغرام
• فيسبوك
• تيك توك
• والعديد من المنصات الأخرى

⚠️ ملاحظة: قد يستغرق التحميل بعض الوقت حسب حجم الفيديو.
    """
    await update.message.reply_text(welcome_msg)

async def download_video(url: str, update: Update) -> str:
    """تحميل الفيديو وإرجاع مسار الملف"""
    
    # إعدادات yt-dlp
    ydl_opts = {
        'format': 'best[ext=mp4]/best',  # أفضل جودة بصيغة mp4
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),  # مسار الحفظ
        'quiet': True,  # إخفاء المخرجات
        'no_warnings': True,
        'restrictfilenames': True,  # أسماء ملفات آمنة
        'max_filesize': 50 * 1024 * 1024,  # حد أقصى 50 ميجابايت
        'socket_timeout': 30,  # timeout 30 ثانية
    }
    
    try:
        # إرسال رسالة انتظار
        await update.message.reply_text("⏳ جاري تحميل الفيديو...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # استخراج معلومات الفيديو
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # التأكد من الامتداد الصحيح
            if not filename.endswith('.mp4'):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            return filename, info.get('title', 'فيديو')
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "URL" in error_msg:
            raise Exception("❌ الرابط غير صالح أو غير مدعوم")
        elif "filesize" in error_msg:
            raise Exception("❌ الفيديو كبير جداً (الحد الأقصى 50 ميجابايت)")
        else:
            raise Exception(f"❌ خطأ في التحميل: {error_msg[:100]}")
    except Exception as e:
        raise Exception(f"❌ حدث خطأ: {str(e)[:100]}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الروابط المرسلة"""
    
    # التحقق من أن الرسالة تحتوي على رابط
    text = update.message.text
    if not text.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    # إعلام المستخدم ببدء المعالجة
    status_msg = await update.message.reply_text("🔍 جاري معالجة الرابط...")
    
    try:
        # تحميل الفيديو
        filepath, title = await download_video(text, update)
        
        # التحقق من حجم الملف
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:  # 50 ميجابايت
            os.remove(filepath)
            await status_msg.edit_text("❌ الفيديو كبير جداً (الحد الأقصى 50 ميجابايت)")
            return
        
        # إرسال الفيديو
        await status_msg.edit_text("📤 جاري رفع الفيديو...")
        
        with open(filepath, 'rb') as video:
            await update.message.reply_video(
                video=video,
                caption=f"✅ تم التحميل بنجاح!\n📹 {title[:50]}",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=60
            )
        
        # حذف الملف بعد الإرسال
        os.remove(filepath)
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(str(e))
        # تنظيف الملفات في حالة الخطأ
        for file in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except:
                pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى."
        )

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # إضافة معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # تشغيل البوت
    print("✅ البوت يعمل... أرسل /start للبدء")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
