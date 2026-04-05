import os
import re
import tempfile
import requests
import yt_dlp

BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    """إرسال رسالة نصية"""
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def send_video(chat_id, video_path, caption):
    """إرسال فيديو مع نص أسفله"""
    with open(video_path, 'rb') as f:
        requests.post(
            f"{BASE_URL}/sendVideo", 
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}, 
            files={"video": f}
        )

def send_action(chat_id, action):
    """إظهار حالة الكتابة أو الرفع للمستخدم"""
    requests.post(f"{BASE_URL}/sendChatAction", json={"chat_id": chat_id, "action": action})

def download_video(url):
    """تحميل الفيديو بسرعة"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()
    
    ydl_opts = {
        'outtmpl': temp_path[:-4],
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best',
        'no_check_certificate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            final_path = f"{temp_path[:-4]}.mp4"
            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                return final_path
        return None
    except Exception as e:
        print(f"خطأ في التحميل: {e}")
        return None

def get_video_info(url):
    """جلب معلومات الفيديو (المشاهدات، الإعجابات، الناشر)"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            views = info.get('view_count', 0)
            likes = info.get('like_count', 0)
            comments = info.get('comment_count', 0)
            uploader = info.get('uploader', 'غير معروف')
            title = info.get('title', '')[:80]
            
            # تنسيق جميل للإحصائيات
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
            
            caption += f"━━━━━━━━━━━━━━━━━━━━\n✨ شكراً لاستخدام البوت!"
            
            return caption
    except Exception as e:
        print(f"خطأ في جلب المعلومات: {e}")
        return "✅ **تم التحميل بنجاح!**\n(لم نتمكن من جلب الإحصائيات الكاملة)"

def main():
    print("✅ البوت يعمل الآن...")
    print("👉 أرسل أي رابط فيديو من إنستقرام وسيرفعه فوراً")
    
    last_update_id = 0
    
    while True:
        try:
            # جلب الرسائل الجديدة
            url = f"{BASE_URL}/getUpdates"
            params = {"timeout": 30, "offset": last_update_id + 1 if last_update_id else None}
            response = requests.get(url, params=params)
            updates = response.json().get("result", [])
            
            for update in updates:
                last_update_id = update['update_id']
                
                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    text = msg.get('text', '')
                    
                    # أمر /start
                    if text == '/start':
                        send_message(
                            chat_id, 
                            "🎬 **بوت تحميل إنستقرام**\n\n"
                            "أرسل لي رابط فيديو وسأرسله لك فوراً مع الإحصائيات!\n\n"
                            "✅ **روابط مقبولة:**\n"
                            "• `https://www.instagram.com/reel/...`\n"
                            "• `https://www.instagram.com/p/...`\n"
                            "• `https://www.instagram.com/tv/...`"
                        )
                    
                    # رابط إنستقرام
                    elif 'instagram.com' in text and ('/reel/' in text or '/p/' in text or '/tv/' in text):
                        
                        # إظهار حالة الرفع للمستخدم
                        send_action(chat_id, "upload_video")
                        
                        # تحميل الفيديو
                        video_path = download_video(text)
                        
                        if video_path:
                            # جلب الإحصائيات
                            caption = get_video_info(text)
                            
                            # رفع الفيديو فوراً مع الإحصائيات أسفله
                            send_video(chat_id, video_path, caption)
                            
                            # حذف الملف المؤقت
                            os.unlink(video_path)
                        else:
                            send_message(chat_id, "❌ **فشل التحميل**\n\nتأكد من:\n• صحة الرابط\n• الفيديو لا يزال متاحاً")
                    
                    # أي رسالة أخرى
                    elif text and not text.startswith('/'):
                        send_message(
                            chat_id, 
                            "📎 **أرسل رابط فيديو من إنستقرام فقط**\n\n"
                            "مثال: `https://www.instagram.com/reel/xxxxx/`"
                        )
        
        except Exception as e:
            print(f"خطأ: {e}")
        
        import time
        time.sleep(1)

if __name__ == "__main__":
    main()
