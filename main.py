import os
import tempfile
import requests
import yt_dlp
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging

# التوكن الخاص بك
BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"

# إعداد التسجيل للأخطاء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# مسار ملف الكوكيز (ستقوم بإنشائه مرة واحدة)
COOKIES_FILE = "cookies.txt"

def get_video_info_and_url(url: str):
    """
    جلب رابط التحميل المباشر ومعلومات الفيديو باستخدام yt-dlp
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
    }
    
    # إذا كان ملف الكوكيز موجوداً، استخدمه
    if os.path.exists(COOKIES_FILE):
        ydl_opts['cookiefile'] = COOKIES_FILE
        logger.info("✅ جاري استخدام ملف الكوكيز للمصادقة")
    else:
        logger.warning("⚠️ ملف cookies.txt غير موجود. قد يفشل التحميل إذا كان الفيديو يتطلب تسجيل دخول.")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # الحصول على أفضل رابط فيديو متاح
            video_url = None
            if 'url' in info:
                video_url = info['url']
            elif 'requested_formats' in info:
                for f in info['requested_formats']:
                    if f.get('vcodec') != 'none':
                        video_url = f.get('url')
                        break
            
            # جمع الإحصائيات
            stats = {
                'views': info.get('view_count', 0),
                'likes': info.get('like_count', 0),
                'comments': info.get('comment_count', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'title': info.get('title', '')[:80],
            }
            return video_url, stats
    except Exception as e:
        logger.error(f"خطأ في yt-dlp: {e}")
        return None, None

def download_video_direct(video_url: str):
    """تحميل الفيديو من الرابط المباشر إلى ملف مؤقت"""
    try:
        resp = requests.get(video_url, stream=True, timeout=30)
        if resp.status_code == 200:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            for chunk in resp.iter_content(8192):
                temp.write(chunk)
            temp.close()
            return temp.name
    except Exception as e:
        logger.error(f"خطأ في تحميل الفيديو: {e}")
    return None

def format_stats(stats):
    if not stats or stats.get('views') == 0:
        return "✅ تم التحميل بنجاح!"
    msg = (
        f"📊 **إحصائيات الفيديو**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👁️ **المشاهدات:** {stats['views']:,}\n"
        f"❤️ **الإعجابات:** {stats['likes']:,}\n"
        f"💬 **التعليقات:** {stats['comments']:,}\n"
        f"👤 **الناشر:** {stats['uploader']}\n"
    )
    if stats['title']:
        msg += f"📝 **الوصف:** {stats['title']}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n✨ شكراً!"
    return msg

async def start(update: Update, context):
    await update.message.reply_text(
        "🎬 **بوت تحميل إنستقرام**\n\n"
        "أرسل رابط فيديو من إنستقرام وسأرسله لك مع الإحصائيات.\n\n"
        "⚠️ **ملاحظة:** إذا فشل التحميل، فأنت بحاجة لملف `cookies.txt`.\n"
        "لإنشائه: استخدم إضافة متصفح مثل 'Get cookies.txt' ثم ضع الملف في نفس مجلد البوت."
    )

async def handle_link(update: Update, context):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ جاري تجهيز الفيديو...")
    
    try:
        # جلب رابط الفيديو المباشر والإحصائيات
        video_url, stats = get_video_info_and_url(url)
        if not video_url:
            await msg.edit_text(
                "❌ **فشل التحميل**\n\n"
                "الأسباب المحتملة:\n"
                "• الفيديو يتطلب تسجيل دخول (حساب خاص أو مقيد)\n"
                "• إنستقرام غير متاح حالياً\n\n"
                "🔧 **الحل:** ضع ملف `cookies.txt` في مجلد البوت.\n"
                "طريقة الحصول عليه: اشرح في متصفحك إضافة 'Get cookies.txt'، سجل الدخول إلى إنستقرام، ثم صدّر الكوكيز."
            )
            return
        
        # تحميل الفيديو من الرابط المباشر
        video_path = download_video_direct(video_url)
        if not video_path:
            await msg.edit_text("❌ فشل في تحميل الفيديو إلى الخادم.")
            return
        
        # إرسال الفيديو مع الإحصائيات
        caption = format_stats(stats)
        with open(video_path, 'rb') as f:
            await update.message.reply_video(
                video=InputFile(f, filename="instagram.mp4"),
                caption=caption,
                parse_mode='Markdown'
            )
        
        await msg.delete()
        os.unlink(video_path)
        
    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"⚠️ خطأ غير متوقع: {str(e)[:100]}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'instagram\.com'), handle_link))
    
    print("✅ البوت يعمل...")
    if not os.path.exists(COOKIES_FILE):
        print("⚠️ ملاحظة: ملف cookies.txt غير موجود. قد لا تعمل الروابط التي تتطلب تسجيل دخول.")
        print("   لإنشاء الملف: ثبت إضافة 'Get cookies.txt' في متصفحك، اسجل دخولك إلى إنستقرام، ثم صدّر الكوكيز.")
    app.run_polling()

if __name__ == "__main__":
    main()
