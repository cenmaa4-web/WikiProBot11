import os
import re
import tempfile
import requests
import yt_dlp

BOT_TOKEN = "8382754822:AAFMJwBsW83k_tXXdhqb1hBx5sj390R_Sf0"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def send_video(chat_id, video_path, caption):
    with open(video_path, 'rb') as f:
        requests.post(f"{BASE_URL}/sendVideo", data={"chat_id": chat_id, "caption": caption}, files={"video": f})

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 30, "offset": offset} if offset else {"timeout": 30}
    response = requests.get(url, params=params)
    return response.json().get("result", [])

def download_video(url):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()
    
    ydl_opts = {
        'outtmpl': temp_path[:-4],
        'quiet': True,
        'format': 'best[ext=mp4]/best',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            final_path = f"{temp_path[:-4]}.mp4"
            if os.path.exists(final_path):
                return final_path
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_info(url):
    ydl_opts = {'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return f"📊 إحصائيات\n👁️ مشاهدات: {info.get('view_count', 0):,}\n❤️ إعجابات: {info.get('like_count', 0):,}\n👤 ناشر: {info.get('uploader', 'غير معروف')}"
    except:
        return "✅ تم التحميل بنجاح!"

def main():
    print("✅ البوت يعمل...")
    last_update_id = 0
    
    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            
            for update in updates:
                last_update_id = update['update_id']
                
                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    text = msg.get('text', '')
                    
                    if text == '/start':
                        send_message(chat_id, "🎬 أرسل رابط فيديو من إنستقرام")
                    
                    elif 'instagram.com' in text:
                        send_message(chat_id, "⏳ جاري التحميل...")
                        video_path = download_video(text)
                        
                        if video_path:
                            caption = get_info(text)
                            send_video(chat_id, video_path, caption)
                            os.unlink(video_path)
                        else:
                            send_message(chat_id, "❌ فشل التحميل")
        
        except Exception as e:
            print(f"Error: {e}")
        
        import time
        time.sleep(1)

if __name__ == "__main__":
    main()
