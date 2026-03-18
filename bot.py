import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت - ضع التوكن الخاص بك هنا
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# إعدادات yt-dlp
YDL_OPTIONS = {
    'format': 'best[height<=720]',  # أفضل جودة حتى 720p
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': True,
    'no_color': True,
}

# إنشاء مجلد التحميلات إذا لم يكن موجوداً
if not os.path.exists('downloads'):
    os.makedirs('downloads')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "👋 مرحباً! أنا بوت تحميل الفيديوهات\n\n"
        "📥 أرسل لي رابط فيديو من أي منصة وسأقوم بتحميله لك\n\n"
        "المنصات المدعومة:\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Twitter/X\n"
        "• Pinterest\n"
        "• وغيرها الكثير...\n\n"
        "✨ فقط أرسل الرابط وسأبدأ التحميل فوراً!"
    )
    await update.message.reply_text(welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل (الروابط)"""
    url = update.message.text.strip()
    
    # التحقق من أن النص يحتوي على رابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    # إرسال رسالة بأن التحميل بدأ
    progress_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو... الرجاء الانتظار")
    
    try:
        # تحميل الفيديو
        video_path = await download_video(url)
        
        if video_path and os.path.exists(video_path):
            # حذف رسالة التقدم
            await progress_msg.delete()
            
            # إرسال الفيديو
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ تم التحميل بنجاح!"
                )
            
            # حذف الفيديو بعد الإرسال لتوفير المساحة
            os.remove(video_path)
            
        else:
            await progress_msg.edit_text("❌ عذراً، لم أتمكن من تحميل الفيديو. تأكد من الرابط وحاول مرة أخرى")
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        await progress_msg.edit_text("❌ حدث خطأ أثناء التحميل. الرجاء التأكد من الرابط والمحاولة مرة أخرى")

async def download_video(url):
    """تحميل الفيديو باستخدام yt-dlp"""
    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            # استخراج معلومات الفيديو
            info = ydl.extract_info(url, download=True)
            
            # الحصول على مسار الملف المحمل
            if 'entries' in info:  # إذا كان قائمة تشغيل
                video = info['entries'][0]
            else:
                video = info
            
            filename = ydl.prepare_filename(video)
            
            # التأكد من وجود الملف
            if os.path.exists(filename):
                return filename
            
            # البحث عن الملف بامتدادات مختلفة
            for ext in ['.mp4', '.webm', '.mkv']:
                if os.path.exists(filename.replace('.%(ext)s' % video['ext'], ext)):
                    return filename.replace('.%(ext)s' % video['ext'], ext)
            
            return None
            
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        return None

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    
    # إضافة معالج للرسائل النصية (الروابط)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # إضافة معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # تشغيل البوت
    print("🤖 البوت يعمل الآن...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
