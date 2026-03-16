لإنشاء بوت تلجرام يقوم بتحميل الفيديوهات من وسائل التواصل الاجتماعي مثل إنستجرام باستخدام ملفين، هنا تفاصيل كل ملف.

### 1. محتوى ملف `library.txt`
هذا الملف يمكن أن يحتوي على روابط مفيدة أو تعليمات حول كيفية استخدام البوت. يمكنك إدراجه كالتالي:

```txt
# مكتبة لروابط مفيدة لتحميل الوسائط
# استخدم البوت بمشاركة رابط الفيديو ليقوم بتحميله
```

### 2. محتوى ملف `bot.py`
هذا هو البرنامج الرئيسي للبوت الذي يستقبل الروابط من المستخدمين ويقوم بتحميل الفيديوهات.

```python
import logging
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import re
import os

# إعداد التوكن الخاص بالبوت
API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("مرحباً! أرسل لي رابط فيديو من أي وسيلة تواصل اجتماعي.")

def download_instagram_video(url: str):
    # يمكنك استخدام مكتبة مثل `youtube_dl` لتحميل الفيديو
    try:
        import youtube_dl

        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        return os.path.join('downloads', f"{ydl.extract_info(url, download=False)['title']}.mp4")
    except Exception as e:
        return str(e)

def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    
    if 'instagram.com' in url:
        video_path = download_instagram_video(url)
        if os.path.exists(video_path):
            with open(video_path, 'rb') as video_file:
                update.message.reply_video(video_file)
            os.remove(video_path)  # حذف الفيديو بعد الإرسال
        else:
            update.message.reply_text(f"حدث خطأ: {video_path}")
    else:
        update.message.reply_text("يرجى مشاركة رابط فيديو من إنستجرام.")

def main():
    # الطريقة لإنشاء البوت
    updater = Updater(API_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    # إنشاء المجلد لتنزيل الفيديوهات
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    main()
```

### خطوات التنفيذ
1. **تثبيت المكتبات المطلوبة:**
   تأكد من تثبيت المكتبات اللازمة عبر استخدام الأمر:
   ```bash
   pip install python-telegram-bot youtube_dl
   ```

2. **تعديل الكود:**
   استبدل `YOUR_TELEGRAM_BOT_TOKEN` بالتوكن الخاص ببوت تلجرام الخاص بك.

3. **تشغيل البوت:**
   بعد تحرير الملفات، يمكنك تشغيل البوت عبر تنفيذ:
   ```bash
   python bot.py
   ```

### ملاحظات
- تأكد من أن المجلد `downloads` موجود حيث يتم حفظ الفيديوهات.
- قد تحتاج إلى ضبط خيارات المكتبة `youtube_dl` لتناسب احتياجاتك الخاصة.

إذا كان لديك أي استفسارات إضافية أو تحتاج لمزيد من التفاصيل، لا تتردد في السؤال!
