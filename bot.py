"""
البوت المتطور - كود كامل جاهز للتشغيل
"""

import logging
import sqlite3
import random
import string
import hashlib
import requests
import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"

# تحميل المتغيرات من ملف .env
load_dotenv()

# ==================== الإعدادات ====================
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '123456789').split(',')]
DB_NAME = 'bot_database.db'

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================
class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # جدول المستخدمين
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    points INTEGER DEFAULT 0,
                    rank TEXT DEFAULT 'عضو',
                    language TEXT DEFAULT 'ar',
                    joined_date TIMESTAMP,
                    last_active TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            ''')
            
            # جدول الملاحظات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT,
                    content TEXT,
                    category TEXT DEFAULT 'عام',
                    created_date TIMESTAMP,
                    modified_date TIMESTAMP
                )
            ''')
            
            # جدول المهام
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task TEXT,
                    priority TEXT DEFAULT 'متوسط',
                    status TEXT DEFAULT 'pending',
                    due_date TIMESTAMP,
                    created_date TIMESTAMP
                )
            ''')
            
            # جدول الروابط المختصرة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    original_url TEXT,
                    short_code TEXT UNIQUE,
                    clicks INTEGER DEFAULT 0,
                    created_date TIMESTAMP
                )
            ''')
            
            # جدول التذكيرات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    reminder TEXT,
                    reminder_time TIMESTAMP,
                    created_date TIMESTAMP
                )
            ''')
            
            # جدول الإحصائيات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT,
                    user_id INTEGER,
                    used_time TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    # دوال المستخدمين
    def add_user(self, user_id, username, first_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, last_active)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, now, now))
            conn.commit()
    
    def get_user(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            return cursor.fetchone()
    
    def update_points(self, user_id, points):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (points, user_id))
            
            # تحديث الرتبة
            cursor.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
            total = cursor.fetchone()[0]
            
            if total < 100:
                rank = 'عضو جديد'
            elif total < 500:
                rank = 'عضو نشط'
            elif total < 1000:
                rank = 'عضو مميز'
            else:
                rank = 'عضو محترف'
            
            cursor.execute('UPDATE users SET rank = ? WHERE user_id = ?', (rank, user_id))
            conn.commit()
    
    # دوال الملاحظات
    def add_note(self, user_id, title, content, category='عام'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute('''
                INSERT INTO notes (user_id, title, content, category, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, title, content, category, now, now))
            conn.commit()
            return cursor.lastrowid
    
    def get_notes(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notes WHERE user_id = ? ORDER BY modified_date DESC', (user_id,))
            return cursor.fetchall()
    
    def delete_note(self, note_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
    
    # دوال المهام
    def add_task(self, user_id, task, priority='متوسط', due_date=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (user_id, task, priority, due_date, created_date, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (user_id, task, priority, due_date, datetime.now()))
            conn.commit()
            return cursor.lastrowid
    
    def get_tasks(self, user_id, status=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('SELECT * FROM tasks WHERE user_id = ? AND status = ?', (user_id, status))
            else:
                cursor.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
            return cursor.fetchall()
    
    def complete_task(self, task_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE tasks SET status = "completed" WHERE id = ? AND user_id = ?', (task_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
    
    # دوال الروابط
    def generate_short_code(self):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(6))
    
    def create_short_link(self, user_id, url):
        code = self.generate_short_code()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO links (user_id, original_url, short_code, created_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, url, code, datetime.now()))
            conn.commit()
            return code
    
    def get_user_links(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM links WHERE user_id = ? ORDER BY created_date DESC', (user_id,))
            return cursor.fetchall()
    
    # دوال التذكيرات
    def add_reminder(self, user_id, text, reminder_time):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reminders (user_id, reminder, reminder_time, created_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, text, reminder_time, datetime.now()))
            conn.commit()
            return cursor.lastrowid
    
    def get_due_reminders(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM reminders WHERE reminder_time <= ?', (datetime.now(),))
            return cursor.fetchall()
    
    def delete_reminder(self, reminder_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
            conn.commit()
    
    # الإحصائيات
    def log_command(self, command, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO stats (command, user_id, used_time) VALUES (?, ?, ?)',
                         (command, user_id, datetime.now()))
            conn.commit()
    
    def get_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT command, COUNT(*) FROM stats GROUP BY command ORDER BY COUNT(*) DESC')
            return cursor.fetchall()
    
    def get_users_count(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            return cursor.fetchone()[0]

# ==================== تهيئة قاعدة البيانات ====================
db = Database(DB_NAME)

# ==================== دوال مساعدة ====================
def generate_qr(data):
    """إنشاء رمز QR"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def get_weather(city):
    """الحصول على الطقس"""
    try:
        url = f"https://wttr.in/{city}?format=%l:+%c+%t,+%w,+%h"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return None

def get_random_fact():
    """حقيقة عشوائية"""
    facts = [
        "🐝 النحل يستطيع التعرف على وجوه البشر",
        "🐙 الأخطبوط لديه ثلاثة قلوب",
        "🦒 الزرافة تستطيع تنظيف أذنيها بلسانها",
        "🐬 الدولفين ينام وعين واحدة مفتوحة",
        "🐘 الفيل هو الحيوان الوحيد الذي لا يستطيع القفز",
        "🦉 البومة لا تستطيع تحريك عينيها",
        "🐫 الجمل يستطيع البقاء بدون ماء لمدة أسبوعين",
        "🦔 القنفذ لديه حوالي 5000 شوكة"
    ]
    return random.choice(facts)

def get_joke():
    """نكتة عشوائية"""
    jokes = [
        "😄 مرة واحد بيقول لصاحبه أنا بحبك أوي، قال له بحبك أنت كمان، قال له أنا بحبك أنت أكتر، قال له يبقى نروح نعمل بصلة؟",
        "😄 مرة واحد سأل مراته: إنتي بتحبيني؟ قالت له: طبعاً، قال لها: طب ليه بتعملي الأكل وحش؟",
        "😄 مرة واحد راح للدكتور قال له: أنا بخاف من الحاجة تحت السرير، قال له الدكتور: إنت مريض نفسي، قال له: ممكن تيجي البيت تتأكد؟"
    ]
    return random.choice(jokes)

def generate_password(length=12):
    """توليد كلمة مرور"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

# ==================== لوحات المفاتيح ====================
def main_menu():
    """القائمة الرئيسية"""
    keyboard = [
        [KeyboardButton("📝 ملاحظات"), KeyboardButton("✅ المهام")],
        [KeyboardButton("🔗 روابط مختصرة"), KeyboardButton("⏰ تذكيرات")],
        [KeyboardButton("🎲 ألعاب"), KeyboardButton("📊 إحصائيات")],
        [KeyboardButton("⚙️ إعدادات"), KeyboardButton("🆘 مساعدة")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def notes_menu():
    """قائمة الملاحظات"""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة ملاحظة", callback_data="add_note")],
        [InlineKeyboardButton("📋 عرض الملاحظات", callback_data="show_notes")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def tasks_menu():
    """قائمة المهام"""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مهمة", callback_data="add_task")],
        [InlineKeyboardButton("📋 المهام الحالية", callback_data="pending_tasks")],
        [InlineKeyboardButton("✅ المهام المكتملة", callback_data="completed_tasks")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def links_menu():
    """قائمة الروابط"""
    keyboard = [
        [InlineKeyboardButton("🔗 تقصير رابط", callback_data="shorten_link")],
        [InlineKeyboardButton("📋 روابطي", callback_data="my_links")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def games_menu():
    """قائمة الألعاب"""
    keyboard = [
        [InlineKeyboardButton("🎲 رمي النرد", callback_data="dice")],
        [InlineKeyboardButton("✊ حجر ورقة مقص", callback_data="rps")],
        [InlineKeyboardButton("⚽ كرة قدم", callback_data="soccer")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== تخزين حالات المستخدمين ====================
user_states = {}
user_data = {}

# ==================== معالجات الأوامر ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    db.log_command('/start', user.id)
    
    welcome = f"""
🎉 مرحباً بك {user.first_name} في البوت المتطور!

✨ مميزات البوت:
📝 إدارة الملاحظات
✅ إدارة المهام
🔗 تقصير الروابط
⏰ تذكيرات
🎲 ألعاب تفاعلية
📊 إحصائيات شخصية
والمزيد...

استخدم الأزرار للتنقل
    """
    
    await update.message.reply_text(welcome, reply_markup=main_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /help"""
    help_text = """
🆘 المساعدة

الأوامر المتاحة:
/start - بدء البوت
/help - عرض المساعدة
/stats - إحصائياتك
/id - معرفك
/time - الوقت
/weather [مدينة] - الطقس
/fact - حقيقة عشوائية
/joke - نكتة
/password - كلمة مرور
/qr - إنشاء QR

استخدم الأزرار للقوائم
    """
    await update.message.reply_text(help_text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /stats"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if user:
        notes = db.get_notes(user_id)
        tasks = db.get_tasks(user_id)
        links = db.get_user_links(user_id)
        
        text = f"""
📊 إحصائياتك:

👤 المستخدم: {user[2]}
⭐ النقاط: {user[3]}
🏆 الرتبة: {user[4]}
📝 ملاحظات: {len(notes)}
✅ مهام: {len(tasks)}
🔗 روابط: {len(links)}
        """
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("❌ لا توجد بيانات")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /id"""
    user = update.effective_user
    chat = update.effective_chat
    
    text = f"""
🆔 المعرفات:
👤 معرفك: {user.id}
👥 معرف المجموعة: {chat.id}
📝 اسم المستخدم: @{user.username}
    """
    await update.message.reply_text(text)

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /time"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"⏰ الوقت: {now}")

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /weather"""
    if context.args:
        city = ' '.join(context.args)
        weather_info = get_weather(city)
        if weather_info:
            await update.message.reply_text(f"🌤 {weather_info}")
        else:
            await update.message.reply_text("❌ مدينة غير موجودة")
    else:
        await update.message.reply_text("❌ اكتب /weather المدينة")

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /fact"""
    await update.message.reply_text(get_random_fact())

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /joke"""
    await update.message.reply_text(get_joke())

async def password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /password"""
    pwd = generate_password()
    await update.message.reply_text(f"🔐 كلمة المرور:\n{pwd}")

async def qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /qr"""
    user_id = update.effective_user.id
    user_states[user_id] = 'waiting_qr'
    await update.message.reply_text("📱 أرسل النص لتحويله QR")

# ==================== معالج الرسائل ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية"""
    text = update.message.text
    user_id = update.effective_user.id
    
    db.log_command(f"msg: {text[:30]}", user_id)
    
    # القوائم الرئيسية
    if text == "📝 ملاحظات":
        await update.message.reply_text("📝 قائمة الملاحظات", reply_markup=notes_menu())
    
    elif text == "✅ المهام":
        await update.message.reply_text("✅ قائمة المهام", reply_markup=tasks_menu())
    
    elif text == "🔗 روابط مختصرة":
        await update.message.reply_text("🔗 قائمة الروابط", reply_markup=links_menu())
    
    elif text == "⏰ تذكيرات":
        keyboard = [
            [InlineKeyboardButton("➕ إضافة تذكير", callback_data="add_reminder")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        await update.message.reply_text("⏰ التذكيرات", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🎲 ألعاب":
        await update.message.reply_text("🎲 اختر لعبة", reply_markup=games_menu())
    
    elif text == "📊 إحصائيات":
        await stats(update, context)
    
    elif text == "⚙️ إعدادات":
        await update.message.reply_text("⚙️ الإعدادات (قريباً)")
    
    elif text == "🆘 مساعدة":
        await help_command(update, context)
    
    # حالات المستخدم
    elif user_id in user_states:
        state = user_states[user_id]
        
        if state == 'waiting_note_title':
            user_data[user_id] = {'title': text}
            user_states[user_id] = 'waiting_note_content'
            await update.message.reply_text("📝 أرسل محتوى الملاحظة:")
        
        elif state == 'waiting_note_content':
            title = user_data.get(user_id, {}).get('title', 'بدون عنوان')
            note_id = db.add_note(user_id, title, text)
            await update.message.reply_text(f"✅ تم حفظ الملاحظة (ID: {note_id})")
            del user_states[user_id]
            if user_id in user_data:
                del user_data[user_id]
        
        elif state == 'waiting_task':
            task_id = db.add_task(user_id, text)
            db.update_points(user_id, 5)
            await update.message.reply_text(f"✅ تم إضافة المهمة (ID: {task_id})\n+5 نقاط")
            del user_states[user_id]
        
        elif state == 'waiting_link':
            code = db.create_short_link(user_id, text)
            short_url = f"https://t.me/yourbot?start={code}"  # غير الرابط
            await update.message.reply_text(f"✅ الرابط المختصر:\n{short_url}")
            del user_states[user_id]
        
        elif state == 'waiting_reminder':
            user_data[user_id] = {'reminder': text}
            user_states[user_id] = 'waiting_reminder_time'
            await update.message.reply_text("⏰ أرسل الوقت (YYYY-MM-DD HH:MM)\nمثال: 2024-12-31 23:59")
        
        elif state == 'waiting_reminder_time':
            try:
                rem_time = datetime.strptime(text, "%Y-%m-%d %H:%M")
                rem_text = user_data.get(user_id, {}).get('reminder', 'تذكير')
                rem_id = db.add_reminder(user_id, rem_text, rem_time)
                await update.message.reply_text(f"✅ تم ضبط التذكير (ID: {rem_id})")
            except:
                await update.message.reply_text("❌ صيغة الوقت خطأ")
            
            del user_states[user_id]
            if user_id in user_data:
                del user_data[user_id]
        
        elif state == 'waiting_qr':
            try:
                qr_img = generate_qr(text)
                await update.message.reply_photo(photo=qr_img, caption="✅ رمز QR الخاص بك")
            except:
                await update.message.reply_text("❌ فشل إنشاء QR")
            
            del user_states[user_id]
    
    else:
        await update.message.reply_text("❌ أمر غير معروف، استخدم القوائم")

# ==================== معالج الأزرار ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار التفاعلية"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "back_to_main":
        await query.message.reply_text("القائمة الرئيسية", reply_markup=main_menu())
        await query.message.delete()
    
    elif data == "add_note":
        user_states[user_id] = 'waiting_note_title'
        await query.message.reply_text("📝 أرسل عنوان الملاحظة:")
        await query.message.delete()
    
    elif data == "show_notes":
        notes = db.get_notes(user_id)
        if notes:
            text = "📝 ملاحظاتك:\n\n"
            for note in notes[:5]:
                text += f"🆔 {note[0]}: **{note[2]}**\n{note[3][:50]}...\n\n"
            await query.message.reply_text(text, parse_mode='Markdown')
        else:
            await query.message.reply_text("📝 لا توجد ملاحظات")
    
    elif data == "add_task":
        user_states[user_id] = 'waiting_task'
        await query.message.reply_text("✅ أرسل المهمة:")
        await query.message.delete()
    
    elif data == "pending_tasks":
        tasks = db.get_tasks(user_id, 'pending')
        if tasks:
            text = "⏳ المهام الحالية:\n\n"
            for task in tasks:
                text += f"🆔 {task[0]}: {task[2]}\n"
            await query.message.reply_text(text)
        else:
            await query.message.reply_text("✅ لا توجد مهام حالية")
    
    elif data == "completed_tasks":
        tasks = db.get_tasks(user_id, 'completed')
        if tasks:
            text = "✅ المهام المكتملة:\n\n"
            for task in tasks:
                text += f"✓ {task[2]}\n"
            await query.message.reply_text(text)
        else:
            await query.message.reply_text("📝 لا توجد مهام مكتملة")
    
    elif data == "shorten_link":
        user_states[user_id] = 'waiting_link'
        await query.message.reply_text("🔗 أرسل الرابط:")
        await query.message.delete()
    
    elif data == "my_links":
        links = db.get_user_links(user_id)
        if links:
            text = "🔗 روابطك:\n\n"
            for link in links[:5]:
                text += f"🆔 {link[0]}: {link[2][:30]}...\n📊 نقرات: {link[4]}\n\n"
            await query.message.reply_text(text)
        else:
            await query.message.reply_text("🔗 لا توجد روابط")
    
    elif data == "add_reminder":
        user_states[user_id] = 'waiting_reminder'
        await query.message.reply_text("⏰ أرسل نص التذكير:")
        await query.message.delete()
    
    elif data == "dice":
        user_dice = random.randint(1, 6)
        bot_dice = random.randint(1, 6)
        
        if user_dice > bot_dice:
            result = "🎉 فزت!"
            points = 10
        elif user_dice < bot_dice:
            result = "😢 خسرت!"
            points = 2
        else:
            result = "🤝 تعادل!"
            points = 5
        
        db.update_points(user_id, points)
        
        text = f"""
🎲 النرد:
أنت: {user_dice}
البوت: {bot_dice}

{result}
+{points} نقطة
        """
        await query.message.reply_text(text)
    
    elif data == "rps":
        keyboard = [
            [
                InlineKeyboardButton("✊ حجر", callback_data="rps_rock"),
                InlineKeyboardButton("✋ ورقة", callback_data="rps_paper"),
                InlineKeyboardButton("✌️ مقص", callback_data="rps_scissors")
            ]
        ]
        await query.message.reply_text("✊ اختر:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data in ["rps_rock", "rps_paper", "rps_scissors"]:
        choices = {"rps_rock": "✊ حجر", "rps_paper": "✋ ورقة", "rps_scissors": "✌️ مقص"}
        user_choice = choices[data]
        bot_choice = random.choice(list(choices.values()))
        
        if user_choice == bot_choice:
            result = "🤝 تعادل!"
            points = 5
        elif (
            (user_choice == "✊ حجر" and bot_choice == "✌️ مقص") or
            (user_choice == "✋ ورقة" and bot_choice == "✊ حجر") or
            (user_choice == "✌️ مقص" and bot_choice == "✋ ورقة")
        ):
            result = "🎉 فزت!"
            points = 10
        else:
            result = "😢 خسرت!"
            points = 2
        
        db.update_points(user_id, points)
        
        text = f"""
✊ اخترت: {user_choice}
🤖 البوت: {bot_choice}

{result}
+{points} نقطة
        """
        await query.message.reply_text(text)
    
    elif data == "soccer":
        user_score = random.randint(0, 5)
        bot_score = random.randint(0, 5)
        
        if user_score > bot_score:
            result = "🎉 فزت!"
            points = 15
        elif user_score < bot_score:
            result = "😢 خسرت!"
            points = 3
        else:
            result = "🤝 تعادل!"
            points = 7
        
        db.update_points(user_id, points)
        
        text = f"""
⚽ كرة قدم:
أنت: {user_score} - {bot_score} :البوت

{result}
+{points} نقطة
        """
        await query.message.reply_text(text)

# ==================== معالج التذكيرات ====================
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """التحقق من التذكيرات المستحقة"""
    reminders = db.get_due_reminders()
    for rem in reminders:
        try:
            await context.bot.send_message(
                chat_id=rem[1],
                text=f"⏰ تذكير:\n{rem[2]}"
            )
            db.delete_reminder(rem[0])
        except:
            pass

# ==================== معالج الأخطاء ====================
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء"""
    logger.error(f"خطأ: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ حدث خطأ، حاول مرة أخرى")
    except:
        pass

# ==================== الدالة الرئيسية ====================
def main():
    """تشغيل البوت"""
    print("🚀 جاري تشغيل البوت...")
    
    # إنشاء التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("password", password))
    app.add_handler(CommandHandler("qr", qr))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error)
    
    # جدولة التحقق من التذكيرات
    job_queue = app.job_queue
    job_queue.run_repeating(check_reminders, interval=60, first=10)
    
    print("✅ البوت يعمل الآن!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
