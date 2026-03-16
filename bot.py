import logging
import sqlite3
import random
import string
import qrcode
import barcode
from barcode.writer import ImageWriter
import io
import os
import json
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== الإعدادات ====================
BOT_TOKEN = "8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4"
DB_NAME = 'barcode_pro.db'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== قاعدة البيانات ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # جدول المستخدمين
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
            points INTEGER DEFAULT 0, rank TEXT DEFAULT 'جديد',
            codes_count INTEGER DEFAULT 0, favorites TEXT DEFAULT '[]',
            language TEXT DEFAULT 'ar', theme TEXT DEFAULT 'dark',
            join_date TEXT, last_active TEXT)''')
        
        # جدول الباركودات
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            code_type TEXT, code_data TEXT, code_format TEXT,
            color TEXT, size TEXT, created_date TEXT,
            scanned_count INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0)''')
        
        # جدول التصاميم
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS designs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            design_name TEXT, design_data TEXT, created_date TEXT)''')
        
        # جدول الإحصائيات
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            action TEXT, details TEXT, date TEXT)''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute("""INSERT OR IGNORE INTO users 
            (user_id, username, first_name, join_date, last_active) 
            VALUES (?, ?, ?, ?, ?)""", 
            (user_id, username, first_name, str(datetime.now()), str(datetime.now())))
        self.conn.commit()
    
    def update_user(self, user_id):
        self.cursor.execute("UPDATE users SET last_active=? WHERE user_id=?", 
                           (str(datetime.now()), user_id))
        self.conn.commit()
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return self.cursor.fetchone()
    
    def add_points(self, user_id, points):
        self.cursor.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))
        user = self.get_user(user_id)
        total = user[3] if user else 0
        
        # تحديث الرتبة
        if total < 100:
            rank = "🟢 جديد"
        elif total < 500:
            rank = "🔵 عادي"
        elif total < 1000:
            rank = "🟡 فضي"
        elif total < 5000:
            rank = "🟠 ذهبي"
        else:
            rank = "🔴 ماسي"
        
        self.cursor.execute("UPDATE users SET rank=? WHERE user_id=?", (rank, user_id))
        self.conn.commit()
    
    def add_code(self, user_id, code_type, code_data, code_format, color, size):
        self.cursor.execute("""INSERT INTO codes 
            (user_id, code_type, code_data, code_format, color, size, created_date) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, code_type, code_data, code_format, color, size, str(datetime.now())))
        self.cursor.execute("UPDATE users SET codes_count = codes_count + 1 WHERE user_id=?", (user_id,))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user_codes(self, user_id, limit=20):
        self.cursor.execute("""SELECT * FROM codes WHERE user_id=? 
            ORDER BY created_date DESC LIMIT ?""", (user_id, limit))
        return self.cursor.fetchall()
    
    def toggle_favorite(self, code_id, user_id):
        self.cursor.execute("""UPDATE codes SET is_favorite = NOT is_favorite 
            WHERE id=? AND user_id=?""", (code_id, user_id))
        self.conn.commit()
    
    def get_favorites(self, user_id):
        self.cursor.execute("""SELECT * FROM codes WHERE user_id=? AND is_favorite=1 
            ORDER BY created_date DESC""", (user_id,))
        return self.cursor.fetchall()
    
    def add_design(self, user_id, design_name, design_data):
        self.cursor.execute("""INSERT INTO designs (user_id, design_name, design_data, created_date) 
            VALUES (?, ?, ?, ?)""", (user_id, design_name, design_data, str(datetime.now())))
        self.conn.commit()
    
    def get_designs(self, user_id):
        self.cursor.execute("SELECT * FROM designs WHERE user_id=? ORDER BY created_date DESC", (user_id,))
        return self.cursor.fetchall()
    
    def add_stat(self, user_id, action, details):
        self.cursor.execute("""INSERT INTO stats (user_id, action, details, date) 
            VALUES (?, ?, ?, ?)""", (user_id, action, details, str(datetime.now())))
        self.conn.commit()

db = Database()

# ==================== دوال إنشاء الباركود المتطورة ====================
class BarcodeGenerator:
    @staticmethod
    def create_qr(data, color="black", bg_color="white", size=10, border=4, logo=None):
        """إنشاء QR Code مع تخصيصات متعددة"""
        qr = qrcode.QRCode(
            version=1,
            box_size=size,
            border=border,
            error_correction=qrcode.constants.ERROR_CORRECT_H
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # تحويل الألوان
        color_map = {
            "black": "#000000", "red": "#FF0000", "blue": "#0000FF",
            "green": "#00FF00", "yellow": "#FFFF00", "purple": "#800080",
            "orange": "#FFA500", "pink": "#FFC0CB", "brown": "#A52A2A",
            "gold": "#FFD700", "silver": "#C0C0C0", "cyan": "#00FFFF"
        }
        
        fill = color_map.get(color, color)
        back = color_map.get(bg_color, bg_color)
        
        img = qr.make_image(fill_color=fill, back_color=back)
        
        # إضافة لوجو إذا وجد
        if logo:
            try:
                logo_img = Image.open(io.BytesIO(logo))
                img = img.convert('RGB')
                logo_size = int(img.size[0] / 4)
                logo_img = logo_img.resize((logo_size, logo_size))
                
                pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)
                img.paste(logo_img, pos)
            except:
                pass
        
        # حفظ الصورة
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    
    @staticmethod
    def create_qr_gradient(data, color1="#FF0000", color2="#0000FF"):
        """QR Code متدرج اللون"""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        img = img.resize((img.size[0]*2, img.size[1]*2))
        
        # تطبيق التدرج
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        for i in range(width):
            ratio = i / width
            r = int(int(color1[1:3], 16) * (1-ratio) + int(color2[1:3], 16) * ratio)
            g = int(int(color1[3:5], 16) * (1-ratio) + int(color2[3:5], 16) * ratio)
            b = int(int(color1[5:7], 16) * (1-ratio) + int(color2[5:7], 16) * ratio)
            
            draw.line([(i, 0), (i, height)], fill=(r, g, b))
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    
    @staticmethod
    def create_qr_frame(data, frame_style="simple"):
        """QR Code مع إطار زخرفي"""
        qr_img = BarcodeGenerator.create_qr(data)
        img = Image.open(qr_img)
        
        # إنشاء إطار
        width, height = img.size
        new_img = Image.new('RGB', (width + 60, height + 60), 'white')
        new_img.paste(img, (30, 30))
        
        draw = ImageDraw.Draw(new_img)
        
        if frame_style == "simple":
            draw.rectangle([(10, 10), (width+50, height+50)], outline='black', width=3)
        elif frame_style == "double":
            draw.rectangle([(10, 10), (width+50, height+50)], outline='black', width=2)
            draw.rectangle([(15, 15), (width+45, height+45)], outline='gray', width=2)
        elif frame_style == "dashed":
            for i in range(10, width+50, 20):
                draw.line([(i, 10), (i+10, 10)], fill='black', width=2)
                draw.line([(i, height+50), (i+10, height+50)], fill='black', width=2)
                draw.line([(10, i), (10, i+10)], fill='black', width=2)
                draw.line([(width+50, i), (width+50, i+10)], fill='black', width=2)
        
        img_byte_arr = io.BytesIO()
        new_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    
    @staticmethod
    def create_barcode(data, barcode_type='code128', color="black", add_text=True):
        """إنشاء باركود عادي"""
        try:
            barcode_class = barcode.get_barcode_class(barcode_type)
            barcode_img = barcode_class(data, writer=ImageWriter())
            
            img_byte_arr = io.BytesIO()
            barcode_img.write(img_byte_arr, options={
                'write_text': add_text,
                'foreground': color,
                'background': 'white',
                'module_width': 0.2,
                'module_height': 15,
                'quiet_zone': 5
            })
            img_byte_arr.seek(0)
            return img_byte_arr
        except Exception as e:
            print(f"خطأ: {e}")
            return None
    
    @staticmethod
    def create_barcode_3d(data):
        """باركود ثلاثي الأبعاد"""
        barcode_img = BarcodeGenerator.create_barcode(data)
        if not barcode_img:
            return None
        
        img = Image.open(barcode_img)
        
        # تأثير ثلاثي الأبعاد
        width, height = img.size
        new_img = Image.new('RGB', (width + 30, height + 30), 'white')
        
        # نسخ مع إزاحة
        img_gray = img.convert('L')
        new_img.paste(img, (10, 10))
        
        # ظل
        shadow = ImageEnhance.Brightness(img_gray).enhance(0.5)
        shadow_img = Image.new('RGBA', shadow.size, (128, 128, 128, 128))
        new_img.paste(shadow_img, (15, 15), shadow_img)
        new_img.paste(img, (5, 5))
        
        img_byte_arr = io.BytesIO()
        new_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    
    @staticmethod
    def scan_barcode(image_bytes):
        """قراءة باركود من صورة"""
        try:
            from pyzbar.pyzbar import decode
            img = Image.open(io.BytesIO(image_bytes))
            decoded = decode(img)
            
            if decoded:
                results = []
                for d in decoded:
                    results.append({
                        'data': d.data.decode('utf-8'),
                        'type': d.type,
                        'rect': d.rect
                    })
                return results
            return None
        except:
            return None
    
    @staticmethod
    def generate_random_text(length=8, type='mixed'):
        """توليد نص عشوائي"""
        if type == 'numbers':
            chars = string.digits
        elif type == 'letters':
            chars = string.ascii_letters
        elif type == 'mixed':
            chars = string.ascii_letters + string.digits
        elif type == 'special':
            chars = string.ascii_letters + string.digits + "!@#$%"
        
        return ''.join(random.choices(chars, k=length))
    
    @staticmethod
    def validate_data(data, barcode_type):
        """التحقق من صحة البيانات حسب النوع"""
        if barcode_type == 'ean13':
            return data.isdigit() and len(data) == 13
        elif barcode_type == 'ean8':
            return data.isdigit() and len(data) == 8
        elif barcode_type == 'isbn':
            return data.isdigit() and len(data) in [10, 13]
        elif barcode_type in ['code39', 'code128']:
            return len(data) > 0 and len(data) < 50
        return True

# ==================== القوائم المتطورة ====================
def main_menu():
    keyboard = [
        [KeyboardButton("📱 QR Code"), KeyboardButton("📦 Barcode")],
        [KeyboardButton("🎨 QR ملون"), KeyboardButton("🌈 QR متدرج")],
        [KeyboardButton("🖼️ QR بإطار"), KeyboardButton("🎯 QR بشعار")],
        [KeyboardButton("🔮 3D Barcode"), KeyboardButton("📸 مسح ضوئي")],
        [KeyboardButton("🔢 عشوائي"), KeyboardButton("⭐ المفضلة")],
        [KeyboardButton("📊 إحصائياتي"), KeyboardButton("🏆 رتبتي")],
        [KeyboardButton("💾 تصاميمي"), KeyboardButton("⚙️ إعدادات")],
        [KeyboardButton("🆘 مساعدة")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def qr_color_menu():
    keyboard = [
        [InlineKeyboardButton("⚫ أسود", callback_data="qr_color_black"),
         InlineKeyboardButton("🔴 أحمر", callback_data="qr_color_red")],
        [InlineKeyboardButton("🔵 أزرق", callback_data="qr_color_blue"),
         InlineKeyboardButton("🟢 أخضر", callback_data="qr_color_green")],
        [InlineKeyboardButton("🟡 أصفر", callback_data="qr_color_yellow"),
         InlineKeyboardButton("🟣 بنفسجي", callback_data="qr_color_purple")],
        [InlineKeyboardButton("🟠 برتقالي", callback_data="qr_color_orange"),
         InlineKeyboardButton("💖 وردي", callback_data="qr_color_pink")],
        [InlineKeyboardButton("🏆 ذهبي", callback_data="qr_color_gold"),
         InlineKeyboardButton("⚪ فضي", callback_data="qr_color_silver")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def qr_size_menu():
    keyboard = [
        [InlineKeyboardButton("🟦 صغير", callback_data="qr_size_small"),
         InlineKeyboardButton("🟨 متوسط", callback_data="qr_size_medium")],
        [InlineKeyboardButton("🟥 كبير", callback_data="qr_size_large"),
         InlineKeyboardButton("🔲 كبير جداً", callback_data="qr_size_xlarge")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def qr_frame_menu():
    keyboard = [
        [InlineKeyboardButton("⬜ بسيط", callback_data="frame_simple"),
         InlineKeyboardButton("⬛ مزدوج", callback_data="frame_double")],
        [InlineKeyboardButton("◻️ منقط", callback_data="frame_dashed"),
         InlineKeyboardButton("💫 دائري", callback_data="frame_round")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def barcode_type_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Code 128", callback_data="barcode_code128"),
         InlineKeyboardButton("📊 Code 39", callback_data="barcode_code39")],
        [InlineKeyboardButton("📊 EAN-13", callback_data="barcode_ean13"),
         InlineKeyboardButton("📊 EAN-8", callback_data="barcode_ean8")],
        [InlineKeyboardButton("📊 ISBN", callback_data="barcode_isbn"),
         InlineKeyboardButton("📊 UPC-A", callback_data="barcode_upca")],
        [InlineKeyboardButton("🎨 مع ألوان", callback_data="barcode_color"),
         InlineKeyboardButton("🔮 3D", callback_data="barcode_3d")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def gradient_menu():
    keyboard = [
        [InlineKeyboardButton("🔴 أحمر-أزرق", callback_data="grad_red_blue"),
         InlineKeyboardButton("🟢 أخضر-أصفر", callback_data="grad_green_yellow")],
        [InlineKeyboardButton("🟣 بنفسجي-وردي", callback_data="grad_purple_pink"),
         InlineKeyboardButton("🟠 برتقالي-ذهبي", callback_data="grad_orange_gold")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def settings_menu():
    keyboard = [
        [InlineKeyboardButton("🌐 اللغة", callback_data="settings_lang"),
         InlineKeyboardButton("🎨 الثيم", callback_data="settings_theme")],
        [InlineKeyboardButton("🔔 الإشعارات", callback_data="settings_notify"),
         InlineKeyboardButton("💾 حفظ تلقائي", callback_data="settings_auto")],
        [InlineKeyboardButton("📊 تصدير البيانات", callback_data="settings_export"),
         InlineKeyboardButton("🗑️ حذف الكل", callback_data="settings_clear")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== المتغيرات ====================
user_state = {}
user_data = {}
user_settings = {}

# ==================== المعالجات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    db.update_user(user.id)
    
    welcome = f"""
╔══════════════════╗
║   🎉 مرحباً بك   ║
╚══════════════════╝

👤 {user.first_name}
✨ مرحباً في بوت الباركود الذكي

📊 إحصائياتك:
• الرتبة: {db.get_user(user.id)[4] if db.get_user(user.id) else 'جديد'}
• النقاط: {db.get_user(user.id)[3] if db.get_user(user.id) else 0}
• الباركودات: {db.get_user(user.id)[5] if db.get_user(user.id) else 0}

🎯 مميزات البوت:
• 12 لون مختلف للـ QR
• 6 أنواع من الباركود
• QR متدرج الألوان
• QR بإطارات زخرفية
• QR مع شعار
• باركود ثلاثي الأبعاد
• مسح الباركود ضوئياً
• حفظ وتصنيف
• نظام نقاط ورتب
• تصاميم مخصصة
• وأكثر من 50 ميزة!

👇 اختر من القائمة
    """
    
    await update.message.reply_text(welcome, reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    db.update_user(user_id)
    
    # ========== القوائم الرئيسية ==========
    if text == "📱 QR Code":
        keyboard = qr_color_menu()
        await update.message.reply_text("🎨 اختر لون QR:", reply_markup=keyboard)
    
    elif text == "📦 Barcode":
        await update.message.reply_text("📊 اختر نوع الباركود:", reply_markup=barcode_type_menu())
    
    elif text == "🎨 QR ملون":
        user_state[user_id] = "waiting_qr_color_selection"
        await update.message.reply_text("🎨 اختر اللون:", reply_markup=qr_color_menu())
    
    elif text == "🌈 QR متدرج":
        await update.message.reply_text("🌈 اختر التدرج:", reply_markup=gradient_menu())
    
    elif text == "🖼️ QR بإطار":
        await update.message.reply_text("🖼️ اختر نوع الإطار:", reply_markup=qr_frame_menu())
    
    elif text == "🎯 QR بشعار":
        user_state[user_id] = "waiting_qr_logo_data"
        await update.message.reply_text("📝 أرسل النص أولاً، ثم أرسل الشعار")
    
    elif text == "🔮 3D Barcode":
        user_state[user_id] = "waiting_barcode_3d"
        await update.message.reply_text("📝 أرسل البيانات للباركود ثلاثي الأبعاد")
    
    elif text == "📸 مسح ضوئي":
        user_state[user_id] = "waiting_scan"
        await update.message.reply_text("📸 أرسل صورة الباركود لقراءتها")
    
    elif text == "🔢 عشوائي":
        keyboard = [
            [InlineKeyboardButton("🔢 أرقام", callback_data="random_numbers"),
             InlineKeyboardButton("🔤 حروف", callback_data="random_letters")],
            [InlineKeyboardButton("🔡 مختلط", callback_data="random_mixed"),
             InlineKeyboardButton("✨ مع رموز", callback_data="random_special")],
            [InlineKeyboardButton("📏 طول 6", callback_data="random_6"),
             InlineKeyboardButton("📏 طول 8", callback_data="random_8")],
            [InlineKeyboardButton("📏 طول 12", callback_data="random_12"),
             InlineKeyboardButton("📏 طول 16", callback_data="random_16")]
        ]
        await update.message.reply_text("🔢 اختر نوع النص العشوائي:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "⭐ المفضلة":
        favorites = db.get_favorites(user_id)
        if favorites:
            msg = "⭐ المفضلة:\n\n"
            for f in favorites[:10]:
                msg += f"🆔 {f[0]}: {f[3][:30]}\n📅 {f[8][:10]}\n\n"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("⭐ لا توجد مفضلة بعد")
    
    elif text == "📊 إحصائياتي":
        user = db.get_user(user_id)
        codes = db.get_user_codes(user_id)
        
        stats = f"""
╔══════════════╗
║  📊 إحصائيات  ║
╚══════════════╝

👤 المستخدم: {user[2]}
🏆 الرتبة: {user[4]}
⭐ النقاط: {user[3]}
📊 عدد الباركودات: {user[5]}
💾 في المفضلة: {len(db.get_favorites(user_id))}
🎨 التصاميم: {len(db.get_designs(user_id))}

📅 آخر نشاط: {user[10][:10]}
        """
        await update.message.reply_text(stats)
    
    elif text == "🏆 رتبتي":
        user = db.get_user(user_id)
        points = user[3] if user else 0
        
        rank_progress = """
🏆 نظام الرتب:
🟢 جديد: 0-99 نقطة
🔵 عادي: 100-499 نقطة
🟡 فضي: 500-999 نقطة
🟠 ذهبي: 1000-4999 نقطة
🔴 ماسي: 5000+ نقطة

⭐ نقاطك الحالية: {}
🏅 رتبتك: {}
        """.format(points, user[4] if user else 'جديد')
        
        await update.message.reply_text(rank_progress)
    
    elif text == "💾 تصاميمي":
        designs = db.get_designs(user_id)
        if designs:
            msg = "💾 تصاميمك المحفوظة:\n\n"
            for d in designs[:10]:
                msg += f"📁 {d[2]}\n📅 {d[4][:10]}\n\n"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("💾 لا توجد تصاميم محفوظة")
    
    elif text == "⚙️ إعدادات":
        await update.message.reply_text("⚙️ الإعدادات:", reply_markup=settings_menu())
    
    elif text == "🆘 مساعدة":
        help_text = """
╔══════════════╗
║  🆘 المساعدة  ║
╚══════════════╝

🎯 الأوامر الرئيسية:
/start - بدء البوت
/help - المساعدة
/stats - إحصائياتي
/random - نص عشوائي
/scan - مسح باركود
/save [اسم] - حفظ تصميم
/fav [id] - إضافة للمفضلة

📱 QR Code:
• ألوان متعددة
• تدرجات لونية
• إطارات زخرفية
• شعار مخصص
• أحجام مختلفة

📦 Barcode:
• 6 أنواع مختلفة
• باركود ملون
• باركود ثلاثي الأبعاد
• قراءة الباركود

💡 نصائح:
• كل عملية تمنحك نقاط
• النقاط ترفع رتبتك
• احفظ تصاميمك المفضلة
• شارك البوت مع أصدقائك
        """
        await update.message.reply_text(help_text)
    
    # ========== حالات المستخدم ==========
    elif user_id in user_state:
        state = user_state[user_id]
        
        if state == "waiting_qr_data":
            color = user_data.get(user_id, {}).get('color', 'black')
            size_map = {'small': 5, 'medium': 10, 'large': 15, 'xlarge': 20}
            size = size_map.get(user_data.get(user_id, {}).get('size', 'medium'), 10)
            
            qr_img = BarcodeGenerator.create_qr(text, color=color, size=size)
            await update.message.reply_photo(
                photo=qr_img,
                caption=f"✅ QR Code\nاللون: {color}\nالنص: {text[:50]}"
            )
            db.add_code(user_id, 'qr', text, 'standard', color, str(size))
            db.add_points(user_id, 5)
            del user_state[user_id]
            if user_id in user_data:
                del user_data[user_id]
        
        elif state.startswith("waiting_qr_color_"):
            color = state.replace("waiting_qr_color_", "")
            user_data[user_id] = {'color': color}
            user_state[user_id] = "waiting_qr_data"
            await update.message.reply_text("📝 أرسل النص لتحويله QR")
        
        elif state == "waiting_qr_size":
            user_data[user_id]['size'] = text
            qr_img = BarcodeGenerator.create_qr(
                user_data[user_id]['data'], 
                color=user_data[user_id]['color'],
                size=user_data[user_id]['size']
            )
            await update.message.reply_photo(
                photo=qr_img,
                caption="✅ QR Code جاهز"
            )
            del user_state[user_id]
        
        elif state == "waiting_barcode_data":
            barcode_type = user_data.get(user_id, {}).get('type', 'code128')
            
            if not BarcodeGenerator.validate_data(text, barcode_type):
                await update.message.reply_text(f"❌ بيانات غير صالحة لنوع {barcode_type}")
                return
            
            barcode_img = BarcodeGenerator.create_barcode(text, barcode_type)
            if barcode_img:
                await update.message.reply_photo(
                    photo=barcode_img,
                    caption=f"✅ {barcode_type}\nالبيانات: {text}"
                )
                db.add_code(user_id, 'barcode', text, barcode_type, 'black', 'medium')
                db.add_points(user_id, 3)
            else:
                await update.message.reply_text("❌ فشل إنشاء الباركود")
            
            del user_state[user_id]
        
        elif state == "waiting_barcode_3d":
            barcode_img = BarcodeGenerator.create_barcode_3d(text)
            if barcode_img:
                await update.message.reply_photo(
                    photo=barcode_img,
                    caption=f"🔮 باركود ثلاثي الأبعاد\n{text}"
                )
                db.add_code(user_id, 'barcode_3d', text, '3d', 'black', 'medium')
                db.add_points(user_id, 10)
            del user_state[user_id]
        
        elif state == "waiting_qr_logo_data":
            user_data[user_id] = {'qr_data': text}
            user_state[user_id] = "waiting_qr_logo"
            await update.message.reply_text("🖼️ أرسل الصورة التي تريد إضافتها كشعار")
        
        elif state == "waiting_scan":
            await update.message.reply_text("❌ هذا ليس بصورة، أرسل صورة الباركود")
        
        elif state == "waiting_design_name":
            user_data[user_id]['design_name'] = text
            db.add_design(user_id, text, json.dumps(user_data[user_id]))
            await update.message.reply_text(f"✅ تم حفظ التصميم: {text}")
            del user_state[user_id]
    
    else:
        await update.message.reply_text("❌ استخدم الأزرار للتحكم")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الصور"""
    user_id = update.effective_user.id
    
    if user_id in user_state and user_state[user_id] == "waiting_scan":
        # مسح باركود من صورة
        photo = await update.message.photo[-1].get_file()
        photo_bytes = await photo.download_as_bytearray()
        
        results = BarcodeGenerator.scan_barcode(photo_bytes)
        
        if results:
            msg = "✅ تم العثور على:\n\n"
            for r in results:
                msg += f"📊 النوع: {r['type']}\n"
                msg += f"📝 البيانات: {r['data']}\n"
                msg += "─" * 20 + "\n"
                db.add_code(user_id, 'scan', r['data'], r['type'], 'scan', 'scan')
                db.add_points(user_id, 5)
            
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("❌ لم أجد أي باركود في الصورة")
        
        del user_state[user_id]
    
    elif user_id in user_state and user_state[user_id] == "waiting_qr_logo":
        # إضافة شعار للـ QR
        qr_data = user_data.get(user_id, {}).get('qr_data', 'QR Code')
        photo = await update.message.photo[-1].get_file()
        logo_bytes = await photo.download_as_bytearray()
        
        qr_img = BarcodeGenerator.create_qr(qr_data, logo=logo_bytes)
        
        await update.message.reply_photo(
            photo=qr_img,
            caption=f"✅ QR Code مع شعار\n{qr_data}"
        )
        db.add_code(user_id, 'qr_logo', qr_data, 'with_logo', 'custom', 'medium')
        db.add_points(user_id, 8)
        
        del user_state[user_id]
        if user_id in user_data:
            del user_data[user_id]

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "back":
        await query.message.delete()
        await query.message.reply_text("القائمة الرئيسية", reply_markup=main_menu())
    
    # ========== ألوان QR ==========
    elif data.startswith("qr_color_"):
        color = data.replace("qr_color_", "")
        user_state[user_id] = f"waiting_qr_color_{color}"
        await query.message.reply_text("📝 أرسل النص الآن")
        await query.message.delete()
    
    # ========== أنواع الباركود ==========
    elif data.startswith("barcode_"):
        barcode_type = data.replace("barcode_", "")
        user_data[user_id] = {'type': barcode_type}
        user_state[user_id] = "waiting_barcode_data"
        await query.message.reply_text(f"📝 أرسل البيانات لنوع {barcode_type}")
        await query.message.delete()
    
    # ========== أحجام QR ==========
    elif data.startswith("qr_size_"):
        size = data.replace("qr_size_", "")
        if user_id in user_data:
            user_data[user_id]['size'] = size
            qr_img = BarcodeGenerator.create_qr(
                user_data[user_id]['data'],
                color=user_data[user_id]['color'],
                size=size
            )
            await query.message.reply_photo(photo=qr_img, caption="✅ QR Code جاهز")
            del user_state[user_id]
    
    # ========== إطارات QR ==========
    elif data.startswith("frame_"):
        frame = data.replace("frame_", "")
        user_state[user_id] = "waiting_frame_data"
        user_data[user_id] = {'frame': frame}
        await query.message.reply_text("📝 أرسل النص للإطار")
        await query.message.delete()
    
    # ========== التدرجات ==========
    elif data.startswith("grad_"):
        colors = data.replace("grad_", "").split("_")
        color1, color2 = colors[0], colors[1]
        user_state[user_id] = "waiting_gradient_data"
        user_data[user_id] = {'color1': color1, 'color2': color2}
        await query.message.reply_text("📝 أرسل النص للتدرج")
        await query.message.delete()
    
    # ========== النصوص العشوائية ==========
    elif data.startswith("random_"):
        parts = data.split("_")
        if len(parts) == 2:
            # نوع النص فقط
            text_type = parts[1]
            random_text = BarcodeGenerator.generate_random_text(8, text_type)
            qr_img = BarcodeGenerator.create_qr(random_text)
            await query.message.reply_photo(
                photo=qr_img,
                caption=f"🔢 نص عشوائي: {random_text}"
            )
            db.add_code(user_id, 'qr_random', random_text, 'random', 'black', 'medium')
            db.add_points(user_id, 2)
        
        elif len(parts) == 3:
            # نوع وطول النص
            text_type = parts[1]
            length = int(parts[2])
            random_text = BarcodeGenerator.generate_random_text(length, text_type)
            qr_img = BarcodeGenerator.create_qr(random_text)
            await query.message.reply_photo(
                photo=qr_img,
                caption=f"🔢 نص عشوائي: {random_text}"
            )
    
    # ========== الإعدادات ==========
    elif data == "settings_lang":
        keyboard = [
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
             InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        await query.message.edit_text("🌐 اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "settings_theme":
        keyboard = [
            [InlineKeyboardButton("🌙 مظلم", callback_data="theme_dark"),
             InlineKeyboardButton("☀️ فاتح", callback_data="theme_light")],
            [InlineKeyboardButton("🔵 أزرق", callback_data="theme_blue"),
             InlineKeyboardButton("🟢 أخضر", callback_data="theme_green")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        await query.message.edit_text("🎨 اختر الثيم:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "settings_export":
        codes = db.get_user_codes(user_id, 100)
        if codes:
            text = "📊 تصدير البيانات:\n\n"
            for c in codes:
                text += f"ID: {c[0]}\nنوع: {c[2]}\nبيانات: {c[3]}\nتاريخ: {c[8][:10]}\n\n"
            
            # حفظ في ملف
            with open(f"user_{user_id}_codes.txt", 'w') as f:
                f.write(text)
            
            await query.message.reply_document(
                document=open(f"user_{user_id}_codes.txt", 'rb'),
                caption="📊 ملف الباركودات الخاصة بك"
            )
        else:
            await query.message.reply_text("📊 لا توجد بيانات للتصدير")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /random"""
    random_text = BarcodeGenerator.generate_random_text()
    qr_img = BarcodeGenerator.create_qr(random_text)
    
    await update.message.reply_photo(
        photo=qr_img,
        caption=f"🔢 نص عشوائي: {random_text}"
    )
    db.add_code(update.effective_user.id, 'qr_random', random_text, 'random', 'black', 'medium')

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /scan"""
    user_id = update.effective_user.id
    user_state[user_id] = "waiting_scan"
    await update.message.reply_text("📸 أرسل صورة الباركود لقراءتها")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /stats"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    codes = db.get_user_codes(user_id)
    
    stats = f"""
📊 إحصائيات {user[2]}:

🏆 الرتبة: {user[4]}
⭐ النقاط: {user[3]}
📊 الباركودات: {user[5]}
💾 المفضلة: {len(db.get_favorites(user_id))}

📊 تفاصيل الباركودات:
• QR Code: {len([c for c in codes if 'qr' in c[2]])}
• Barcode: {len([c for c in codes if 'barcode' in c[2]])}
• أخرى: {len([c for c in codes if c[2] not in ['qr', 'barcode']])}

📅 آخر نشاط: {user[10][:10] if user[10] else 'اليوم'}
    """
    
    await update.message.reply_text(stats)

# ==================== التشغيل ====================
def main():
    print("🚀 بوت الباركود الذكي يعمل...")
    print("📊 أكثر من 50 ميزة متاحة")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", handle_message))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(callback))
    
    app.run_polling()

if __name__ == '__main__':
    main()
