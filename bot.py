import re
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ملف تخزين الروابط
DATA_FILE = "links.json"

# تهيئة ملف JSON إذا لم يكن موجود
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"channels": [], "groups": []}, f, indent=4)

# دالة لقراءة البيانات من JSON
def load_links():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

# دالة لحفظ البيانات في JSON
def save_links(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# دالة لاستخراج روابط تلجرام
def extract_telegram_links(text):
    return re.findall(r'https?://t\.me/\S+', text)

# دالة لتصنيف الروابط
def classify_links(links):
    channels = []
    groups = []
    for link in links:
        if "/+" in link or "/joinchat" in link:
            groups.append(link)
        else:
            channels.append(link)
    return channels, groups

# دالة لتحديث الروابط الجديدة
def update_links(new_links):
    data = load_links()
    new_channels, new_groups = classify_links(new_links)

    # إضافة القنوات الجديدة بدون تكرار
    for ch in new_channels:
        if ch not in data["channels"]:
            data["channels"].append(ch)
    
    # إضافة المجموعات الجديدة بدون تكرار
    for gr in new_groups:
        if gr not in data["groups"]:
            data["groups"].append(gr)
    
    save_links(data)
    return data

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلا بك! أرسل لي روابط تلجرام وسأفرزها لك إلى قنوات ومجموعات.")

# استقبال الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    links = extract_telegram_links(text)
    if not links:
        await update.message.reply_text("لم أجد أي روابط تلجرام في رسالتك.")
        return
    
    data = update_links(links)

    # إرسال القنوات
    if data["channels"]:
        channels_text = "📢 القنوات:\n" + "\n".join([f"{i+1}- {link}" for i, link in enumerate(data["channels"])])
        await update.message.reply_text(channels_text)
    
    # إرسال المجموعات
    if data["groups"]:
        groups_text = "👥 المجموعات:\n" + "\n".join([f"{i+1}- {link}" for i, link in enumerate(data["groups"])])
        await update.message.reply_text(groups_text)

# نقطة البداية
def main():
    TOKEN = "8753575669:AAHH6EXVMEVxIoG4RhFHhl9EafyuKoJmLSs"  # ضع توكن البوت هنا
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
