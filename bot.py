import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# تحميل الإعدادات من ملف .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("8753575669:AAHH6EXVMEVxIoG4RhFHhl9EafyuKoJmLSs")
GEMINI_API_KEY = os.getenv("AIzaSyA6N7tA80pmCnuLnCUz-Zys_YBsv6iqzXc")

# إعداد Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# إعداد سجلات الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! أنا بوت ذكاء اصطناعي محمي وجاهز للعمل. أرسل لي أي سؤال!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # إرسال النص لـ Gemini
        response = model.generate_content(update.message.text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("عذراً، حدث خطأ في الاتصال.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("البوت يعمل الآن بأمان...")
    application.run_polling()
