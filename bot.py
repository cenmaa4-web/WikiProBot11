import logging
import sqlite3
import qrcode
import barcode
from barcode.writer import ImageWriter
import io
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== الإعدادات ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"  # ضع التوكن هنا
DB_NAME = 'barcode_bot.db'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== قاعدة البيانات ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
            codes_count INTEGER DEFAULT 0, join_date TEXT)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            code_type TEXT, code_data TEXT, code_image TEXT, date TEXT)''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, 0, ?)", 
                           (user_id, username, first_name, str(datetime.now())))
        self.conn.commit()
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return self.cursor.fetchone()
    
    def update_count(self, user_id):
        self.cursor.execute("UPDATE users SET codes_count = codes_count + 1 WHERE user_id=?", (user_id,))
        self.conn.commit()
    
    def save_code(self, user_id, code_type, code_data, code_image):
        self.cursor.execute("INSERT INTO codes (user_id, code_type, code_data, code_image, date) VALUES (?, ?, ?, ?, ?)",
                           (user_id, code_type, code_data, code_image, str(datetime.now())))
        self.conn.commit()
        return self.cursor.lastrowid

db = Database()

# ==================== دوال إنشاء الباركود ====================
def create_qr_code(data, fill_color="black", back_color="white"):
    """إنشاء QR Code"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def create_barcode(data, barcode_type='code128'):
    """إنشاء باركود عادي"""
    try:
        # أنواع الباركود المدعومة: code128, code39, ean13, ean8, isbn13, issn, upca
        barcode_class = barcode.get_barcode_class(barcode_type)
        barcode_img = barcode_class(data, writer=ImageWriter())
        
        img_byte_arr = io.BytesIO()
        barcode_img.write(img_byte_arr)
        img_byte_arr.seek(0)
        return img_byte_arr
    except Exception as e:
        print(f"خطأ في إنشاء الباركود: {e}")
        return None

def generate_random_text(length=10):
    """توليد نص عشوائي للباركود"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ==================== لوحة المفاتيح ====================
def main_menu():
    keyboard = [
        [KeyboardButton("📱 QR Code"), KeyboardButton("📦 Barcode")],
        [KeyboardButton("🎨 QR ملون"), KeyboardButton("🔢 عشوائي")],
        [KeyboardButton("📊 إحصائياتي"), KeyboardButton("🆘 مساعدة")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def qr_options():
    keyboard = [
        [InlineKeyboardButton("⚫ أسود/أبيض", callback_data="qr_black")],
        [InlineKeyboardButton("🔴 أحمر", callback_data="qr_red")],
        [InlineKeyboardButton("🔵 أزرق", callback_data="qr_blue")],
        [InlineKeyboardButton("🟢 أخضر", callback_data="qr_green")],
        [InlineKeyboardButton("🟡 أصفر", callback_data="qr_yellow")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def barcode_options():
    keyboard = [
        [InlineKeyboardButton("🔲 Code 128", callback_data="barcode_code128")],
        [InlineKeyboardButton("🔲 Code 39", callback_data="barcode_code39")],
        [InlineKeyboardButton("🔲 EAN-13", callback_data="barcode_ean13")],
        [InlineKeyboardButton("🔲 EAN-8", callback_data="barcode_ean8")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== المتغيرات ====================
user_state = {}
user_data = {}

# ==================== المعالجات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome = f"""
🎉 مرحباً بك {user.first_name} في بوت الباركود!

✨ مميزات البوت:
• إنشاء QR Code
• إنشاء Barcode عادي
• QR Code ملون
• أنواع متعددة من الباركود
• توليد عشوائي
• حفظ الباركودات

📝 أرسل أي نص وسأحوله لك
استخدم الأزرار للتحكم
    """
    
    await update.message.reply_text(welcome, reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📱 QR Code":
        user_state[user_id] = "waiting_qr"
        await update.message.reply_text("📝 أرسل النص أو الرابط لتحويله QR")
    
    elif text == "📦 Barcode":
        keyboard = barcode_options()
        await update.message.reply_text("📦 اختر نوع الباركود:", reply_markup=keyboard)
    
    elif text == "🎨 QR ملون":
        await update.message.reply_text("🎨 اختر اللون:", reply_markup=qr_options())
    
    elif text == "🔢 عشوائي":
        random_text = generate_random_text()
        qr_img = create_qr_code(random_text)
        
        await update.message.reply_photo(
            photo=qr_img,
            caption=f"🔢 نص عشوائي: {random_text}"
        )
        db.update_count(user_id)
        db.save_code(user_id, "qr_random", random_text, "qr_random.png")
    
    elif text == "📊 إحصائياتي":
        user = db.get_user(user_id)
        count = user[3] if user else 0
        await update.message.reply_text(f"📊 عدد الباركودات التي أنشأتها: {count}")
    
    elif text == "🆘 مساعدة":
        help_text = """
🆘 المساعدة:

• أرسل أي نص وسيتم تحويله QR
• استخدم الأزرار لأنواع مختلفة
• اختر الألوان للـ QR
• اختر نوع الباركود

الأوامر:
/start - بدء البوت
/random - نص عشوائي
/qr [نص] - QR مباشر
        """
        await update.message.reply_text(help_text)
    
    elif user_id in user_state:
        if user_state[user_id] == "waiting_qr":
            qr_img = create_qr_code(text)
            await update.message.reply_photo(
                photo=qr_img,
                caption=f"✅ QR Code للنص:\n{text[:100]}"
            )
            db.update_count(user_id)
            db.save_code(user_id, "qr", text, "qr.png")
            del user_state[user_id]
        
        elif user_state[user_id].startswith("waiting_qr_color_"):
            color = user_state[user_id].replace("waiting_qr_color_", "")
            colors = {
                "red": "🔴", "blue": "🔵", "green": "🟢", "yellow": "🟡"
            }
            color_map = {
                "red": "#FF0000", "blue": "#0000FF", 
                "green": "#00FF00", "yellow": "#FFFF00"
            }
            
            qr_img = create_qr_code(text, fill_color=color_map.get(color, "black"))
            await update.message.reply_photo(
                photo=qr_img,
                caption=f"{colors.get(color, '')} QR Code ملون\n{text[:100]}"
            )
            db.update_count(user_id)
            db.save_code(user_id, f"qr_{color}", text, f"qr_{color}.png")
            del user_state[user_id]
        
        elif user_state[user_id].startswith("waiting_barcode_"):
            barcode_type = user_state[user_id].replace("waiting_barcode_", "")
            barcode_img = create_barcode(text, barcode_type)
            
            if barcode_img:
                await update.message.reply_photo(
                    photo=barcode_img,
                    caption=f"✅ {barcode_type.upper()}\nالبيانات: {text}"
                )
                db.update_count(user_id)
                db.save_code(user_id, f"barcode_{barcode_type}", text, f"barcode_{barcode_type}.png")
            else:
                await update.message.reply_text("❌ البيانات غير مناسبة لهذا النوع من الباركود")
            
            del user_state[user_id]
    
    else:
        # إذا كان نص عادي حوله QR
        qr_img = create_qr_code(text)
        await update.message.reply_photo(
            photo=qr_img,
            caption=f"✅ QR Code للنص:\n{text[:100]}"
        )
        db.update_count(user_id)
        db.save_code(user_id, "qr", text, "qr.png")

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "back":
        await query.message.delete()
        await query.message.reply_text("القائمة الرئيسية", reply_markup=main_menu())
    
    elif data == "qr_black":
        user_state[user_id] = "waiting_qr"
        await query.message.reply_text("📝 أرسل النص لتحويله QR أسود/أبيض")
        await query.message.delete()
    
    elif data == "qr_red":
        user_state[user_id] = "waiting_qr_color_red"
        await query.message.reply_text("📝 أرسل النص لتحويله QR أحمر")
        await query.message.delete()
    
    elif data == "qr_blue":
        user_state[user_id] = "waiting_qr_color_blue"
        await query.message.reply_text("📝 أرسل النص لتحويله QR أزرق")
        await query.message.delete()
    
    elif data == "qr_green":
        user_state[user_id] = "waiting_qr_color_green"
        await query.message.reply_text("📝 أرسل النص لتحويله QR أخضر")
        await query.message.delete()
    
    elif data == "qr_yellow":
        user_state[user_id] = "waiting_qr_color_yellow"
        await query.message.reply_text("📝 أرسل النص لتحويله QR أصفر")
        await query.message.delete()
    
    elif data == "barcode_code128":
        user_state[user_id] = "waiting_barcode_code128"
        await query.message.reply_text("📝 أرسل البيانات (أرقام وحروف فقط)")
        await query.message.delete()
    
    elif data == "barcode_code39":
        user_state[user_id] = "waiting_barcode_code39"
        await query.message.reply_text("📝 أرسل البيانات (أحرف كبيرة وأرقام)")
        await query.message.delete()
    
    elif data == "barcode_ean13":
        user_state[user_id] = "waiting_barcode_ean13"
        await query.message.reply_text("📝 أرسل 13 رقم (EAN-13)")
        await query.message.delete()
    
    elif data == "barcode_ean8":
        user_state[user_id] = "waiting_barcode_ean8"
        await query.message.reply_text("📝 أرسل 8 أرقام (EAN-8)")
        await query.message.delete()

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /random"""
    random_text = generate_random_text()
    qr_img = create_qr_code(random_text)
    
    await update.message.reply_photo(
        photo=qr_img,
        caption=f"🔢 نص عشوائي: {random_text}"
    )
    db.update_count(update.effective_user.id)

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /qr"""
    if context.args:
        text = ' '.join(context.args)
        qr_img = create_qr_code(text)
        await update.message.reply_photo(
            photo=qr_img,
            caption=f"✅ QR Code:\n{text[:100]}"
        )
        db.update_count(update.effective_user.id)
    else:
        await update.message.reply_text("❌ اكتب /qr النص الذي تريده")

# ==================== التشغيل ====================
def main():
    print("🚀 بوت الباركود يعمل...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("qr", qr_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback))
    
    app.run_polling()

if __name__ == '__main__':
    main()
