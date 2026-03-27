import os
import logging
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# 1. تحميل الإعدادات من ملف .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("8753575669:AAHH6EXVMEVxIoG4RhFHhl9EafyuKoJmLSs")
GEMINI_API_KEY = os.getenv("AIzaSyA6N7tA80pmCnuLnCUz-Zys_YBsv6iqzXc")

# 2. إعداد مكتبة Gemini الجديدة
client = genai.Client(api_key=GEMINI_API_KEY)

# إعداد سجلات الأخطاء
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! أنا البوت المحدث. كيف يمكنني مساعدتك؟")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # إرسال النص لـ Gemini باستخدام المكتبة الجديدة
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=update.message.text
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء المعالجة.")

if __name__ == '__main__':
    # بناء البوت
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("البوت يعمل الآن بالمكتبة الجديدة...")
    application.run_polling()
