import logging
import sqlite3
import random
import string
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== الإعدادات ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ضع التوكن هنا
ADMIN_IDS = [123456789]
DB_NAME = 'bot_database.db'

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
            points INTEGER DEFAULT 0, join_date TEXT)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            title TEXT, content TEXT, date TEXT)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            task TEXT, status TEXT DEFAULT 'pending', date TEXT)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            url TEXT, code TEXT, clicks INTEGER DEFAULT 0, date TEXT)''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, 0, ?)", 
                           (user_id, username, first_name, str(datetime.now())))
        self.conn.commit()
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return self.cursor.fetchone()
    
    def add_points(self, user_id, points):
        self.cursor.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))
        self.conn.commit()
    
    def add_note(self, user_id, title, content):
        self.cursor.execute("INSERT INTO notes (user_id, title, content, date) VALUES (?, ?, ?, ?)",
                           (user_id, title, content, str(datetime.now())))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_notes(self, user_id):
        self.cursor.execute("SELECT * FROM notes WHERE user_id=? ORDER BY date DESC", (user_id,))
        return self.cursor.fetchall()
    
    def delete_note(self, note_id, user_id):
        self.cursor.execute("DELETE FROM notes WHERE id=? AND user_id=?", (note_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def add_task(self, user_id, task):
        self.cursor.execute("INSERT INTO tasks (user_id, task, date) VALUES (?, ?, ?)",
                           (user_id, task, str(datetime.now())))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_tasks(self, user_id, status='pending'):
        self.cursor.execute("SELECT * FROM tasks WHERE user_id=? AND status=? ORDER BY date DESC", 
                           (user_id, status))
        return self.cursor.fetchall()
    
    def complete_task(self, task_id, user_id):
        self.cursor.execute("UPDATE tasks SET status='completed' WHERE id=? AND user_id=?", 
                           (task_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def save_link(self, user_id, url, code):
        self.cursor.execute("INSERT INTO links (user_id, url, code, date) VALUES (?, ?, ?, ?)",
                           (user_id, url, code, str(datetime.now())))
        self.conn.commit()

db = Database()

# ==================== الدوال المساعدة ====================
def get_weather(city):
    try:
        res = requests.get(f"https://wttr.in/{city}?format=%c+%t+%w+%h", timeout=5)
        return res.text if res.status_code == 200 else "🌤 لا توجد معلومات"
    except: return "🌤 لا توجد معلومات"

def get_fact():
    facts = [
        "🐝 النحل يعرف وجوه البشر",
        "🐙 الأخطبوط له 3 قلوب",
        "🦒 الزرافة تنظف أذنيها بلسانها",
        "🐬 الدلفين ينام وعين مفتوحة",
        "🐘 الفيل لا يقفز",
        "🐫 الجمل يصبر على الماء أسبوعين"
    ]
    return random.choice(facts)

def get_joke():
    jokes = [
        "😄 مرة واحد قال لصاحبه أنا بحبك أوي قال له بحبك أنت كمان قال له يبقى نروح نعمل بصلة؟",
        "😄 مرة واحد سأل مراته إنتي بتحبيني؟ قالت له طبعاً قال لها طب ليه بتعملي الأكل وحش؟",
        "😄 مرة واحد دخل محل قال عايز جزمه مقاس 45 قال له مافيش قال له طيب عايز 45 جزمه مقاس 40"
    ]
    return random.choice(jokes)

def main_menu():
    keyboard = [
        [KeyboardButton("📝 ملاحظات"), KeyboardButton("✅ مهام")],
        [KeyboardButton("🔗 رابط"), KeyboardButton("🎲 ألعاب")],
        [KeyboardButton("📊 نقاطي"), KeyboardButton("🌤 طقس")],
        [KeyboardButton("ℹ️ حقائق"), KeyboardButton("😄 نكت")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== المتغيرات ====================
user_state = {}

# ==================== المعالجات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        f"🎉 مرحباً {user.first_name}\n"
        f"أهلاً بك في البوت\n"
        f"استخدم الأزرار للتحكم",
        reply_markup=main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📝 ملاحظات":
        keyboard = [
            [InlineKeyboardButton("➕ إضافة ملاحظة", callback_data="add_note")],
            [InlineKeyboardButton("📋 عرض ملاحظاتي", callback_data="show_notes")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        await update.message.reply_text("📝 اختر:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "✅ مهام":
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مهمة", callback_data="add_task")],
            [InlineKeyboardButton("📋 مهامي", callback_data="show_tasks")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        await update.message.reply_text("✅ اختر:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🎲 ألعاب":
        keyboard = [
            [InlineKeyboardButton("🎲 نرد", callback_data="game_dice")],
            [InlineKeyboardButton("✊ حجر/ورقة/مقص", callback_data="game_rps")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        await update.message.reply_text("🎲 اختر لعبة:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📊 نقاطي":
        user = db.get_user(user_id)
        points = user[3] if user else 0
        await update.message.reply_text(f"⭐ نقاطك: {points}")
    
    elif text == "🌤 طقس":
        await update.message.reply_text("🌤 اكتب اسم المدينة مع /weather\nمثال: /weather القاهرة")
    
    elif text == "ℹ️ حقائق":
        await update.message.reply_text(get_fact())
    
    elif text == "😄 نكت":
        await update.message.reply_text(get_joke())
    
    elif text == "🔗 رابط":
        user_state[user_id] = "waiting_link"
        await update.message.reply_text("🔗 أرسل الرابط الذي تريد تقصيره:")
    
    elif user_id in user_state:
        if user_state[user_id] == "waiting_note_title":
            context.user_data['note_title'] = text
            user_state[user_id] = "waiting_note_content"
            await update.message.reply_text("📝 أرسل محتوى الملاحظة:")
        
        elif user_state[user_id] == "waiting_note_content":
            note_id = db.add_note(user_id, context.user_data.get('note_title', 'ملاحظة'), text)
            db.add_points(user_id, 5)
            await update.message.reply_text(f"✅ تم حفظ الملاحظة (رقم {note_id})\n+5 نقاط")
            del user_state[user_id]
        
        elif user_state[user_id] == "waiting_task":
            task_id = db.add_task(user_id, text)
            db.add_points(user_id, 3)
            await update.message.reply_text(f"✅ تم إضافة المهمة (رقم {task_id})\n+3 نقاط")
            del user_state[user_id]
        
        elif user_state[user_id] == "waiting_link":
            code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            db.save_link(user_id, text, code)
            db.add_points(user_id, 2)
            await update.message.reply_text(f"✅ الرابط المختصر:\nhttps://t.me/yourbot?start={code}\n+2 نقاط")
            del user_state[user_id]
    
    else:
        await update.message.reply_text("❌ استخدم القوائم أو الأوامر")

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "back":
        await query.message.delete()
        await query.message.reply_text("القائمة الرئيسية", reply_markup=main_menu())
    
    elif data == "add_note":
        user_state[user_id] = "waiting_note_title"
        await query.message.reply_text("📝 أرسل عنوان الملاحظة:")
        await query.message.delete()
    
    elif data == "show_notes":
        notes = db.get_notes(user_id)
        if notes:
            text = "📝 ملاحظاتك:\n"
            for n in notes[:5]:
                text += f"\n🆔 {n[0]}\n📌 {n[2]}\n📄 {n[3][:50]}...\n"
            await query.message.reply_text(text)
        else:
            await query.message.reply_text("📝 لا توجد ملاحظات")
    
    elif data == "add_task":
        user_state[user_id] = "waiting_task"
        await query.message.reply_text("✅ أرسل المهمة:")
        await query.message.delete()
    
    elif data == "show_tasks":
        tasks = db.get_tasks(user_id)
        if tasks:
            for t in tasks:
                keyboard = [[InlineKeyboardButton("✅ تم الإنجاز", callback_data=f"done_{t[0]}")]]
                await query.message.reply_text(
                    f"🆔 {t[0]}\n📌 {t[2]}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await query.message.reply_text("✅ لا توجد مهام")
    
    elif data.startswith("done_"):
        task_id = int(data.split("_")[1])
        if db.complete_task(task_id, user_id):
            db.add_points(user_id, 10)
            await query.message.reply_text("✅ تم الإنجاز! +10 نقاط")
            await query.message.delete()
    
    elif data == "game_dice":
        user_dice = random.randint(1, 6)
        bot_dice = random.randint(1, 6)
        
        if user_dice > bot_dice:
            result = "🎉 فزت"
            points = 10
        elif user_dice < bot_dice:
            result = "😢 خسرت"
            points = 0
        else:
            result = "🤝 تعادل"
            points = 5
        
        db.add_points(user_id, points)
        await query.message.reply_text(
            f"🎲 أنت: {user_dice}\n"
            f"🤖 بوت: {bot_dice}\n"
            f"{result}\n"
            f"+{points} نقطة"
        )
    
    elif data == "game_rps":
        keyboard = [
            [
                InlineKeyboardButton("✊ حجر", callback_data="rps_rock"),
                InlineKeyboardButton("✋ ورقة", callback_data="rps_paper"),
                InlineKeyboardButton("✌️ مقص", callback_data="rps_scissors")
            ]
        ]
        await query.message.reply_text("✊ اختر:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data in ["rps_rock", "rps_paper", "rps_scissors"]:
        choices = {"rps_rock": "✊", "rps_paper": "✋", "rps_scissors": "✌️"}
        user_choice = choices[data]
        bot_choice = random.choice(["✊", "✋", "✌️"])
        
        if user_choice == bot_choice:
            result = "تعادل"
            points = 5
        elif (
            (user_choice == "✊" and bot_choice == "✌️") or
            (user_choice == "✋" and bot_choice == "✊") or
            (user_choice == "✌️" and bot_choice == "✋")
        ):
            result = "فزت"
            points = 10
        else:
            result = "خسرت"
            points = 0
        
        db.add_points(user_id, points)
        await query.message.reply_text(
            f"أنت: {user_choice}\n"
            f"بوت: {bot_choice}\n"
            f"{result}\n"
            f"+{points} نقطة"
        )

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        city = ' '.join(context.args)
        weather_info = get_weather(city)
        await update.message.reply_text(f"🌤 {weather_info}")
    else:
        await update.message.reply_text("❌ اكتب /weather المدينة")

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_fact())

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_joke())

# ==================== التشغيل ====================
def main():
    print("🚀 البوت يعمل...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback))
    
    # تشغيل البوت
    app.run_polling()

if __name__ == '__main__':
    main()
