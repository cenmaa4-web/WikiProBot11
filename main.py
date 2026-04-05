import os
import re
import asyncio
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import tempfile

# التوكن الخاص بك
BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    await update.message.reply_text(
        "🎬 **مرحباً! البوت يعمل ✅**\n\n"
        "أرسل لي رابط فيديو من إنستقرام وسأرسله لك مع الإحصائيات.\n\n"
        "📌 أمثلة:\n"
        "• `https://www.instagram.com/reel/xxxxx/`\n"
        "• `https://www.instagram.com/p/xxxxx/`",
        parse_mode='Markdown'
    )

async def get_instagram_info(url: str):
    """جلب معلومات الفيديو"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stats = {
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'comments': info.get('comment_count', 0),
                'uploader': info.get('uploader', 'غير معروف'),
            }
            return stats
    except Exception as e:
        logger.error(f"خطأ في جلب المعلومات: {e}")
        return None

async def download_instagram_video(url: str):
    """تحميل الفيديو"""
    # إنشاء ملف مؤقت
    temp_dir = tempfile.gettempdir()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4', dir=temp_dir)
    temp_path = temp_file.name
    temp_file.close()
    
    # إعدادات التحميل
    ydl_opts = {
        'outtmpl': temp_path[:-4],  # حذف .mp4 مؤقتاً
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # تحميل الفيديو
            ydl.download([url])
            
            # البحث عن الملف المحمل
            possible_paths = [f"{temp_path[:-4]}.mp4", temp_path]
            for path in possible_paths:
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    return path
            return None
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        return None

def format_stats(stats):
    """تنسيق الإحصائيات"""
    if not stats:
        return "✅ تم التحميل بنجاح!"
    
    message = "📊 **إحصائيات الفيديو**\n━━━━━━━━━━━━━━━━━━━━\n"
    if stats.get('views'):
        message += f"👁️ **المشاهدات:** {stats['views']:,}\n"
    if stats.get('likes'):
        message += f"❤️ **الإعجابات:** {stats['likes']:,}\n"
    if stats.get('comments'):
        message += f"💬 **التعليقات:** {stats['comments']:,}\n"
    if stats.get('uploader'):
        message += f"👤 **الناشر:** {stats['uploader']}\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n✨ شكراً لاستخدام البوت!"
    
    return message

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط"""
    url = update.message.text.strip()
    
    # رسالة انتظار
    wait_message = await update.message.reply_text("⏳ **جاري تحميل الفيديو...**\nيرجى الانتظار قليلاً", parse_mode='Markdown')
    
    try:
        # تحميل الفيديو
        video_path = await download_instagram_video(url)
        
        if not video_path:
            await wait_message.edit_text(
                "❌ **فشل التحميل**\n\n"
                "تأكد من:\n"
                "• الرابط صحيح\n"
                "• الفيديو لا يزال متاحاً\n"
                "• الحساب عام",
                parse_mode='Markdown'
            )
            return
        
        # جلب الإحصائيات
        stats = await get_instagram_info(url)
        caption = format_stats(stats)
        
        # إرسال الفيديو
        with open(video_path, 'rb') as video:
            await update.message.reply_video(
                video=InputFile(video, filename="instagram_video.mp4"),
                caption=caption,
                parse_mode='Markdown'
            )
        
        # حذف رسالة الانتظار
        await wait_message.delete()
        
        # حذف الملف المؤقت
        try:
            os.unlink(video_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await wait_message.edit_text(f"⚠️ **حدث خطأ:** {str(e)[:100]}", parse_mode='Markdown')

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على الرسائل غير المعروفة"""
    await update.message.reply_text(
        "📎 **أرسل رابط فيديو من إنستقرام فقط**\n\n"
        "مثال: `https://www.instagram.com/reel/xxxxx/`",
        parse_mode='Markdown'
    )

async def main():
    """تشغيل البوت"""
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'instagram\.com|instagr\.am'), handle_link))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))
    
    # بدء البوت
    print("✅ البوت يعمل الآن...")
    print(f"👉 اذهب إلى تليجرام وابحث عن البوت الخاص بك")
    print("👉 أرسل له /start ثم رابط فيديو من إنستقرام")
    
    # بدء polling
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
