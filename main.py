import os
import re
import json
import time
import tempfile
import requests
import yt_dlp

# ========== التوكن الخاص بك (غيره فوراً) ==========
BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"
# ================================================

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
COOKIES_FILE = "cookies.txt"  # ملف الكوكيز (اختياري لكن مفيد)

def send_message(chat_id, text, parse_mode="Markdown"):
    """إرسال رسالة نصية"""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    requests.post(url, json=payload)

def send_video(chat_id, video_path, caption):
    """رفع فيديو مع نص توضيحي"""
    url = f"{BASE_URL}/sendVideo"
    with open(video_path, "rb") as f:
        files = {"video": f}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
        requests.post(url, data=data, files=files)

def send_action(chat_id, action="upload_video"):
    """إظهار حالة رفع الفيديو"""
    url = f"{BASE_URL}/sendChatAction"
    requests.post(url, json={"chat_id": chat_id, "action": action})

def get_updates(offset=None):
    """جلب الرسائل الجديدة"""
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 30, "offset": offset} if offset else {"timeout": 30}
    resp = requests.get(url, params=params)
    return resp.json().get("result", [])

def download_instagram_video(url):
    """
    تحميل الفيديو باستخدام yt-dlp (مع دعم الكوكيز إن وجدت)
    يرجع مسار الملف المحمل أو None
    """
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_path = temp.name
    temp.close()
    outtmpl = temp_path[:-4]  # بدون .mp4

    ydl_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
    }
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE
        print("✅ استخدام ملف الكوكيز للمصادقة")
    else:
        print("⚠️ ملف cookies.txt غير موجود. قد يفشل تحميل الفيديوهات المحمية.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            final_path = f"{outtmpl}.mp4"
            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                return final_path
        return None
    except Exception as e:
        print(f"خطأ في التحميل: {e}")
        return None

def get_video_info(url):
    """جلب الإحصائيات (مشاهدات، إعجابات، ناشر)"""
    ydl_opts = {"quiet": True, "no_warnings": True}
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            views = info.get("view_count", 0)
            likes = info.get("like_count", 0)
            comments = info.get("comment_count", 0)
            uploader = info.get("uploader", "غير معروف")
            title = info.get("title", "")[:80]

            caption = (
                f"📊 **إحصائيات الفيديو**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👁️ **المشاهدات:** {views:,}\n"
                f"❤️ **الإعجابات:** {likes:,}\n"
                f"💬 **التعليقات:** {comments:,}\n"
                f"👤 **الناشر:** {uploader}\n"
            )
            if title:
                caption += f"📝 **الوصف:** {title}\n"
            caption += "━━━━━━━━━━━━━━━━━━━━\n✨ شكراً لاستخدام البوت!"
            return caption
    except Exception as e:
        print(f"خطأ في جلب المعلومات: {e}")
        return "✅ تم التحميل بنجاح!"

def main():
    print("🚀 بوت التحميل يعمل... (بدون python-telegram-bot)")
    print("👉 أرسل /start ثم رابط إنستقرام")
    last_update_id = 0

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                if "message" not in update:
                    continue
                msg = update["message"]
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")

                # أمر /start
                if text == "/start":
                    send_message(chat_id,
                        "🎬 **بوت تحميل إنستقرام**\n\n"
                        "أرسل رابط فيديو من إنستقرام وسأرسله لك مع الإحصائيات.\n\n"
                        "✅ روابط مقبولة:\n"
                        "• `https://www.instagram.com/reel/...`\n"
                        "• `https://www.instagram.com/p/...`\n"
                        "• `https://www.instagram.com/tv/...`\n\n"
                        "⚠️ ملاحظة: إذا فشل التحميل، يرجى وضع ملف `cookies.txt` (شرح بالأسفل)."
                    )
                    continue

                # التحقق من رابط إنستقرام
                if "instagram.com" in text and re.search(r'/(reel|p|tv)/', text):
                    send_action(chat_id)
                    send_message(chat_id, "⏳ جاري تجهيز الفيديو...")
                    video_path = download_instagram_video(text)
                    if video_path:
                        caption = get_video_info(text)
                        send_video(chat_id, video_path, caption)
                        os.unlink(video_path)
                        print(f"✅ تم إرسال الفيديو إلى {chat_id}")
                    else:
                        send_message(chat_id,
                            "❌ **فشل التحميل**\n\n"
                            "الأسباب المحتملة:\n"
                            "• الفيديو يتطلب تسجيل دخول (حساب خاص أو مقيد)\n"
                            "• الرابط غير صحيح\n\n"
                            "🔧 **الحل:** ضع ملف `cookies.txt` في مجلد البوت.\n"
                            "كيفية الحصول عليه: ثبّت إضافة 'Get cookies.txt' في متصفحك، سجل دخولك إلى إنستقرام، ثم صدّر الكوكيز."
                        )
                elif text and not text.startswith("/"):
                    send_message(chat_id, "📎 أرسل رابط إنستقرام فقط.\nمثال: `https://www.instagram.com/reel/xxxxx/`")

        except Exception as e:
            print(f"خطأ عام: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
