import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# تفعيل التسجيل للأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ضع توكن البوت الخاص بك هنا (من BotFather)
TOKEN = "8753575669:AAHH6EXVMEVxIoG4RhFHhl9EafyuKoJmLSs"

# ضع رابط تطبيقك المصغر هنا (من static.app أو غيره)
MINI_APP_URL = "https://comfortable-ducks.static2.website/upload-pdf"

# أمر /start
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🚀 فتح التطبيق المصغر", web_app={"url": MINI_APP_URL})],
        [InlineKeyboardButton("ℹ️ معلومات", callback_data="info")],
        [InlineKeyboardButton("📞 تواصل مع المطور", url="https://t.me/username")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✨ مرحباً بك في بوتي! ✨\n\n"
        "أنا بوت بسيط يمكنك من فتح التطبيق المصغر.\n"
        "اضغط على الزر أدناه لبدء التجربة:",
        reply_markup=reply_markup
    )

# التعامل مع الضغط على الأزرار (callback queries)
async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "info":
        await query.edit_message_text(
            "📱 *عن البوت:*\n\n"
            "هذا بوت بسيط تم إنشاؤه لعرض تطبيق مصغر على تليجرام.\n\n"
            "🛠 *التقنيات المستخدمة:*\n"
            "- Python + python-telegram-bot\n"
            "- HTML/CSS/JS للتطبيق المصغر\n"
            "- استضافة مجانية (Netlify/Static.app)\n\n"
            "💡 يمكنك تخصيص البوت كما تريد!",
            parse_mode="Markdown"
        )

# الرد على أي رسالة نصية عادية
async def echo(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "أنا بوت بسيط، أستخدم أمر /start للبدء!\n"
        "أو اضغط على الزر لفتح التطبيق المصغر."
    )

# تشغيل البوت
def main():
    # أنشئ التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # أضف المعالجات (handlers)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # ابدأ البوت
    print("✅ البوت يعمل... اضغط Ctrl+C للإيقاف")
    app.run_polling(allowed_updates=True)

if __name__ == "__main__":
    main()
