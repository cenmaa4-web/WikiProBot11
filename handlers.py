from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import re
import os
from config import WELCOME_MESSAGE, HELP_MESSAGE, ERROR_MESSAGE, MAX_FILE_SIZE
from downloader import VideoDownloader

# إنشاء كائن التحميل
downloader = VideoDownloader()

def is_valid_url(url: str) -> bool:
    """التحقق من صحة الرابط"""
    url_pattern = re.compile(
        r'^https?://'  # http:// أو https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ip
        r'(?::\d+)?'  # port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    await update.message.reply_text(WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /help"""
    await update.message.reply_text(HELP_MESSAGE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية (الروابط)"""
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # التحقق من صحة الرابط
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ الرابط غير صحيح. الرجاء إرسال رابط صحيح."
        )
        return
    
    # إرسال رسالة انتظار
    waiting_msg = await update.message.reply_text(
        "⏳ جاري تحميل الفيديو... يرجى الانتظار قليلاً."
    )
    
    try:
        # محاولة تحميل الفيديو
        filepath, filename, file_size = await downloader.download_video(url)
        
        if filepath is None:
            if file_size == "large_file":
                await waiting_msg.edit_text(
                    "❌ حجم الفيديو كبير جداً.\n"
                    "الحد الأقصى المسموح به هو 50 ميجابايت."
                )
            else:
                await waiting_msg.edit_text(ERROR_MESSAGE)
            return
        
        # التحقق من حجم الملف
        if file_size > MAX_FILE_SIZE:
            await waiting_msg.edit_text(
                "❌ حجم الفيديو يتجاوز 50 ميجابايت.\n"
                "لا يمكن إرساله عبر تليجرام."
            )
            downloader.cleanup(filepath)
            return
        
        # إرسال الفيديو
        with open(filepath, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="✅ تم التحميل بنجاح!",
                supports_streaming=True
            )
        
        # حذف رسالة الانتظار
        await waiting_msg.delete()
        
        # تنظيف الملف
        downloader.cleanup(filepath)
        
    except Exception as e:
        await waiting_msg.edit_text(
            f"❌ حدث خطأ: {str(e)[:100]}"
        )
        
        # تنظيف في حالة وجود ملف
        if 'filepath' in locals() and filepath and os.path.exists(filepath):
            downloader.cleanup(filepath)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء"""
    print(f"Update {update} caused error {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى لاحقاً."
            )
    except:
        pass
