import os
import re
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple
import aiofiles
from PIL import Image
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# ================== الإعدادات الأساسية ==================
TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع توكن البوت هنا
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت حد تليجرام
ALLOWED_DOMAINS = [
    'youtube.com', 'youtu.be', 'twitter.com', 'x.com',
    'instagram.com', 'facebook.com', 'tiktok.com',
    'reddit.com', 'pinterest.com', 'dailymotion.com',
    'vimeo.com', 'twitch.tv'
]

# إعداد المجلدات
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(f"{DOWNLOAD_DIR}/temp", exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== إعدادات yt-dlp المتطورة ==================
YDL_OPTIONS = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/temp/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'restrictfilenames': True,
    'noplaylist': True,
    'geo_bypass': True,
    'socket_timeout': 30,
    'retries': 3,
    'fragment_retries': 3,
    'skip_unavailable_fragments': True,
}

# ================== دوال المساعدة ==================
def clean_filename(filename: str) -> str:
    """تنظيف اسم الملف من الرموز غير المسموحة"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)[:100]

def format_size(size: int) -> str:
    """تحويل الحجم إلى صيغة مقروءة"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def format_duration(seconds: int) -> str:
    """تحويل المدة إلى صيغة مقروءة"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

async def get_video_info(url: str) -> Tuple[Optional[dict], Optional[str]]:
    """الحصول على معلومات الفيديو"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info, None
    except Exception as e:
        return None, str(e)

async def download_video(url: str, quality: str = 'best', progress_callback=None) -> Tuple[Optional[str], Optional[str]]:
    """تحميل الفيديو بالجودة المطلوبة"""
    try:
        options = YDL_OPTIONS.copy()
        
        # تعديل الجودة حسب الطلب
        if quality == 'audio':
            options['format'] = 'bestaudio/best'
            options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        elif quality == 'low':
            options['format'] = 'worst[ext=mp4]/worst'
        elif quality == 'medium':
            options['format'] = 'best[height<=480][ext=mp4]/best'
        
        # إضافة callback للتقدم
        if progress_callback:
            options['progress_hooks'] = [progress_callback]
        
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # تعديل اسم الملف للملفات المحولة
            if quality == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            else:
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            return filename, None
    except Exception as e:
        return None, str(e)

# ================== معالجات البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب مع أزرار تفاعلية"""
    welcome_text = """
🎬 <b>مرحباً بك في بوت تحميل الفيديوهات المتطور!</b>

✨ <b>المميزات:</b>
• تحميل من 20+ منصة مختلفة
• اختيار جودة التحميل
• تحميل الصوت فقط (MP3)
• معلومات مفصلة عن الفيديو
• واجهة تفاعلية بالعربية
• تحميل سريع وآمن

📥 <b>فقط أرسل الرابط وسأقوم بالباقي!</b>

<b>المنصات المدعومة:</b>
YouTube - Twitter - Instagram - Facebook - TikTok
Reddit - Pinterest - Dailymotion - Vimeo - Twitch
والمزيد...

⚠️ <b>ملاحظة:</b> الحد الأقصى للحجم 50 ميجابايت
    """
    
    keyboard = [
        [InlineKeyboardButton("📱 قناة البوت", url="https://t.me/your_channel")],
        [InlineKeyboardButton("👨‍💻 المطور", url="https://t.me/your_username")],
        [InlineKeyboardButton("❓ مساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    help_text = """
❓ <b>كيفية استخدام البوت:</b>

1️⃣ أرسل رابط الفيديو مباشرة
2️⃣ اختر جودة التحميل من القائمة
3️⃣ انتظر قليلاً حتى يتم التحميل
4️⃣ استلم الفيديو مباشرة في الدردشة

🎯 <b>الأوامر المتاحة:</b>
/start - بدء استخدام البوت
/help - عرض هذه المساعدة
/info - معلومات عن البوت
/stats - إحصائيات (للمشرفين)

📌 <b>نصائح:</b>
• الروابط القصيرة مدعومة
• يمكنك تحميل الصوت فقط باختيار MP3
• الفيديوهات الطويلة قد تستغرق وقتاً أطول
    """
    await update.message.reply_text(help_text, parse_mode='HTML')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط المرسل"""
    url = update.message.text.strip()
    
    # التحقق من صحة الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    # إرسال رسالة جاري المعالجة
    status_message = await update.message.reply_text(
        "🔍 <b>جاري تحليل الرابط...</b>",
        parse_mode='HTML'
    )
    
    try:
        # الحصول على معلومات الفيديو
        info, error = await get_video_info(url)
        
        if error:
            await status_message.edit_text(
                f"❌ <b>خطأ في تحليل الرابط</b>\n\n{error[:200]}",
                parse_mode='HTML'
            )
            return
        
        if not info:
            await status_message.edit_text(
                "❌ <b>عذراً، لم نتمكن من تحليل هذا الرابط</b>",
                parse_mode='HTML'
            )
            return
        
        # حفظ معلومات الفيديو في context
        context.user_data['video_info'] = info
        context.user_data['video_url'] = url
        
        # استخراج المعلومات
        title = info.get('title', 'فيديو')
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'غير معروف')
        views = info.get('view_count', 0)
        likes = info.get('like_count', 0)
        
        # تحضير رسالة المعلومات
        info_text = f"""
🎬 <b>معلومات الفيديو:</b>

📹 <b>العنوان:</b> {title[:100]}
👤 <b>القناة:</b> {uploader}
⏱️ <b>المدة:</b> {format_duration(duration)}
👁️ <b>المشاهدات:</b> {views:,}
❤️ <b>الإعجابات:</b> {likes:,}

📥 <b>اختر جودة التحميل:</b>
        """
        
        # إنشاء أزرار الجودة
        keyboard = [
            [
                InlineKeyboardButton("🎥 عالية (HD)", callback_data="quality_best"),
                InlineKeyboardButton("📺 متوسطة", callback_data="quality_medium")
            ],
            [
                InlineKeyboardButton("📱 منخفضة", callback_data="quality_low"),
                InlineKeyboardButton("🎵 صوت فقط (MP3)", callback_data="quality_audio")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الصورة المصغرة إن وجدت
        thumbnail = info.get('thumbnail')
        if thumbnail:
            try:
                await update.message.reply_photo(
                    photo=thumbnail,
                    caption=info_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                await status_message.delete()
            except:
                await status_message.edit_text(
                    info_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
        else:
            await status_message.edit_text(
                info_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
    except Exception as e:
        await status_message.edit_text(
            f"❌ <b>حدث خطأ غير متوقع</b>\n\n{str(e)[:200]}",
            parse_mode='HTML'
        )
        logger.error(f"Error in handle_url: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية")
        return
    
    if query.data == "help":
        await help_command(update, context)
        return
    
    if query.data.startswith("quality_"):
        quality = query.data.replace("quality_", "")
        
        # الحصول على المعلومات المحفوظة
        info = context.user_data.get('video_info')
        url = context.user_data.get('video_url')
        
        if not info or not url:
            await query.edit_message_text("❌ انتهت صلاحية الجلسة، الرجاء إرسال الرابط مرة أخرى")
            return
        
        # تحديث رسالة الحالة
        await query.edit_message_text(
            "⏳ <b>جاري التحميل...</b>\n\n"
            "قد يستغرق هذا بعض الوقت حسب حجم الفيديو",
            parse_mode='HTML'
        )
        
        try:
            # تحميل الفيديو
            filename, error = await download_video(url, quality)
            
            if error:
                await query.edit_message_text(
                    f"❌ <b>خطأ في التحميل</b>\n\n{error[:200]}",
                    parse_mode='HTML'
                )
                return
            
            if not filename or not os.path.exists(filename):
                await query.edit_message_text(
                    "❌ <b>فشل تحميل الفيديو</b>",
                    parse_mode='HTML'
                )
                return
            
            # التحقق من حجم الملف
            file_size = os.path.getsize(filename)
            if file_size > MAX_FILE_SIZE:
                os.remove(filename)
                await query.edit_message_text(
                    "❌ <b>الملف كبير جداً</b>\n\n"
                    f"الحد الأقصى المسموح به: {format_size(MAX_FILE_SIZE)}\n"
                    f"حجم الملف: {format_size(file_size)}",
                    parse_mode='HTML'
                )
                return
            
            # إرسال الملف
            await query.edit_message_text(
                "📤 <b>جاري رفع الملف...</b>",
                parse_mode='HTML'
            )
            
            with open(filename, 'rb') as file:
                if quality == 'audio':
                    await query.message.reply_audio(
                        audio=file,
                        title=info.get('title', 'صوت'),
                        performer=info.get('uploader', 'غير معروف'),
                        caption="✅ تم التحميل بنجاح!"
                    )
                else:
                    await query.message.reply_video(
                        video=file,
                        caption=f"✅ تم التحميل بنجاح!\n\n🎬 {info.get('title', '')[:100]}",
                        supports_streaming=True,
                        width=info.get('width'),
                        height=info.get('height'),
                        duration=info.get('duration')
                    )
            
            # حذف الملف المؤقت
            os.remove(filename)
            
            # حذف رسالة الحالة
            await query.delete_message()
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ <b>حدث خطأ</b>\n\n{str(e)[:200]}",
                parse_mode='HTML'
            )
            logger.error(f"Error in button_callback: {e}")
            
            # تنظيف الملفات المؤقتة
            for file in os.listdir(f"{DOWNLOAD_DIR}/temp"):
                try:
                    os.remove(os.path.join(f"{DOWNLOAD_DIR}/temp", file))
                except:
                    pass

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات البوت (للمشرفين)"""
    user_id = update.effective_user.id
    admin_ids = [123456789]  # ضع معرفات المشرفين هنا
    
    if user_id not in admin_ids:
        await update.message.reply_text("❌ هذه الخاصية متاحة فقط للمشرفين")
        return
    
    # حساب إحصائيات المجلد
    total_files = 0
    total_size = 0
    
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        for file in files:
            filepath = os.path.join(root, file)
            total_files += 1
            total_size += os.path.getsize(filepath)
    
    stats_text = f"""
📊 <b>إحصائيات البوت:</b>

📁 <b>المجلدات المؤقتة:</b>
• الملفات الموجودة: {total_files}
• المساحة المستخدمة: {format_size(total_size)}

⚙️ <b>حالة البوت:</b>
• يعمل بشكل طبيعي ✅
• آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

async def cleanup_temp_files():
    """تنظيف الملفات المؤقتة القديمة"""
    while True:
        try:
            now = datetime.now().timestamp()
            for file in os.listdir(f"{DOWNLOAD_DIR}/temp"):
                filepath = os.path.join(f"{DOWNLOAD_DIR}/temp", file)
                if os.path.getmtime(filepath) < now - 3600:  # أقدم من ساعة
                    os.remove(filepath)
                    logger.info(f"Cleaned up old file: {file}")
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
        
        await asyncio.sleep(1800)  # تنظيف كل 30 دقيقة

# ================== تشغيل البوت ==================
def main():
    """الدالة الرئيسية لتشغيل البوت"""
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # بدء مهمة التنظيف التلقائي
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(cleanup_temp_files())
    
    # تشغيل البوت
    print("🤖 البوت يعمل بنجاح...")
    print(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
    print("✅ اضغط Ctrl+C للإيقاف")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
