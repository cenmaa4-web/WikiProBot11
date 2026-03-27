import re
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ملف تخزين الروابط
DATA_FILE = "links.json"
STATS_FILE = "stats.json"

# تهيئة ملف JSON إذا لم يكن موجود
def init_files():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump({"channels": [], "groups": []}, f, indent=4, ensure_ascii=False)
    
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, "w", encoding='utf-8') as f:
            json.dump({"total_links": 0, "last_update": None, "users": {}}, f, indent=4, ensure_ascii=False)

# دالة لقراءة البيانات من JSON
def load_links() -> Dict:
    with open(DATA_FILE, "r", encoding='utf-8') as f:
        return json.load(f)

# دالة لحفظ البيانات في JSON
def save_links(data: Dict):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# دالة لقراءة الإحصائيات
def load_stats() -> Dict:
    with open(STATS_FILE, "r", encoding='utf-8') as f:
        return json.load(f)

# دالة لحفظ الإحصائيات
def save_stats(stats: Dict):
    with open(STATS_FILE, "w", encoding='utf-8') as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

# دالة لاستخراج روابط تلجرام - محسنة
def extract_telegram_links(text: str) -> List[str]:
    # نمط محسن لاستخراج روابط تيليجرام
    patterns = [
        r'https?://t\.me/[^\s]+',
        r'https?://telegram\.me/[^\s]+',
        r'https?://telegram\.dog/[^\s]+',
        r't\.me/[^\s]+',
        r'@[a-zA-Z0-9_]{5,}'
    ]
    
    links = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for link in found:
            # توحيد الروابط
            if link.startswith('@'):
                link = f"https://t.me/{link[1:]}"
            elif link.startswith('t.me/'):
                link = f"https://{link}"
            links.append(link)
    
    # إزالة التكرارات
    return list(set(links))

# دالة لتصنيف الروابط - محسنة
def classify_links(links: List[str]) -> Tuple[List[str], List[str]]:
    channels = []
    groups = []
    
    for link in links:
        # المجموعات تحتوي على + أو joinchat
        if "/+" in link or "/joinchat" in link or "joinchat" in link:
            groups.append(link)
        # القنوات العادية
        else:
            # استخراج اسم القناة
            match = re.search(r't\.me/([^/\s]+)', link)
            if match:
                channel_name = match.group(1)
                # التحقق من أنها قناة وليست مجموعة
                if not any(x in channel_name for x in ['+', 'joinchat']):
                    channels.append(link)
            else:
                channels.append(link)
    
    return channels, groups

# دالة لتحديث الروابط الجديدة
def update_links(new_links: List[str], user_id: int = None) -> Dict:
    data = load_links()
    new_channels, new_groups = classify_links(new_links)
    
    added_channels = []
    added_groups = []
    
    # إضافة القنوات الجديدة بدون تكرار
    for ch in new_channels:
        if ch not in data["channels"]:
            data["channels"].append(ch)
            added_channels.append(ch)
    
    # إضافة المجموعات الجديدة بدون تكرار
    for gr in new_groups:
        if gr not in data["groups"]:
            data["groups"].append(gr)
            added_groups.append(gr)
    
    save_links(data)
    
    # تحديث الإحصائيات
    if added_channels or added_groups:
        stats = load_stats()
        stats["total_links"] += len(added_channels) + len(added_groups)
        stats["last_update"] = datetime.now().isoformat()
        
        if user_id:
            user_id_str = str(user_id)
            if user_id_str not in stats["users"]:
                stats["users"][user_id_str] = {"count": 0, "last_activity": None}
            stats["users"][user_id_str]["count"] += len(added_channels) + len(added_groups)
            stats["users"][user_id_str]["last_activity"] = datetime.now().isoformat()
        
        save_stats(stats)
    
    return data

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("📢 عرض القنوات", callback_data="show_channels"),
         InlineKeyboardButton("👥 عرض المجموعات", callback_data="show_groups")],
        [InlineKeyboardButton("🗑️ مسح الكل", callback_data="clear_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🌟 *مرحباً بك في بوت فرز روابط تيليجرام* 🌟\n\n"
        "📌 *ماذا يمكنني أن أفعل؟*\n"
        "• استقبال روابط تيليجرام وتصنيفها إلى قنوات ومجموعات\n"
        "• حفظ الروابط وعرضها عند الطلب\n"
        "• عرض إحصائيات الروابط المستلمة\n\n"
        "💡 *كيفية الاستخدام:*\n"
        "أرسل لي أي رابط تيليجرام وسأقوم بتصنيفه وحفظه تلقائياً!\n\n"
        "🎯 *الأوامر المتاحة:*\n"
        "/start - عرض هذه الرسالة\n"
        "/stats - عرض الإحصائيات\n"
        "/channels - عرض القنوات المحفوظة\n"
        "/groups - عرض المجموعات المحفوظة\n"
        "/clear - مسح جميع الروابط\n"
        "/help - المساعدة"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

# أمر /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 *دليل المساعدة*\n\n"
        "🔹 *إرسال الروابط:*\n"
        "يمكنك إرسال روابط تيليجرام بأي شكل:\n"
        "• https://t.me/username\n"
        "• t.me/joinchat/xxxx\n"
        "• @username\n\n"
        "🔹 *الأوامر:*\n"
        "/start - بدء البوت\n"
        "/stats - عرض الإحصائيات\n"
        "/channels - عرض جميع القنوات\n"
        "/groups - عرض جميع المجموعات\n"
        "/clear - مسح جميع الروابط\n"
        "/help - هذه الرسالة\n\n"
        "🔹 *الأزرار:*\n"
        "استخدم الأزرار أدناه للتنقل السريع"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# أمر /stats
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    data = load_links()
    
    stats_text = (
        "📊 *إحصائيات البوت*\n\n"
        f"📢 عدد القنوات: `{len(data['channels'])}`\n"
        f"👥 عدد المجموعات: `{len(data['groups'])}`\n"
        f"🔗 إجمالي الروابط: `{stats['total_links']}`\n"
        f"🕐 آخر تحديث: `{stats['last_update'] or 'لا يوجد'}`\n"
        f"👤 عدد المستخدمين: `{len(stats['users'])}`"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# أمر /channels
async def show_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_links()
    
    if not data["channels"]:
        await update.message.reply_text("📭 لا توجد قنوات محفوظة حالياً.")
        return
    
    # تقسيم القنوات إلى أجزاء (تليجرام يحد من طول الرسالة)
    channels_text = "📢 *القنوات المحفوظة:*\n\n"
    for i, link in enumerate(data["channels"], 1):
        channel_entry = f"{i}. {link}\n"
        if len(channels_text + channel_entry) > 4000:
            await update.message.reply_text(channels_text, parse_mode='Markdown')
            channels_text = channel_entry
        else:
            channels_text += channel_entry
    
    await update.message.reply_text(channels_text, parse_mode='Markdown')

# أمر /groups
async def show_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_links()
    
    if not data["groups"]:
        await update.message.reply_text("📭 لا توجد مجموعات محفوظة حالياً.")
        return
    
    groups_text = "👥 *المجموعات المحفوظة:*\n\n"
    for i, link in enumerate(data["groups"], 1):
        group_entry = f"{i}. {link}\n"
        if len(groups_text + group_entry) > 4000:
            await update.message.reply_text(groups_text, parse_mode='Markdown')
            groups_text = group_entry
        else:
            groups_text += group_entry
    
    await update.message.reply_text(groups_text, parse_mode='Markdown')

# أمر /clear
async def clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تأكيد الحذف
    keyboard = [
        [InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="confirm_clear"),
         InlineKeyboardButton("❌ لا، إلغاء", callback_data="cancel_clear")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚠️ *تحذير:* هل أنت متأكد من رغبتك في مسح جميع الروابط؟\n"
        "هذا الإجراء لا يمكن التراجع عنه.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

# استقبال الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # إظهار أن البوت يكتب
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    links = extract_telegram_links(text)
    
    if not links:
        await update.message.reply_text(
            "❌ لم أجد أي روابط تلجرام في رسالتك.\n\n"
            "💡 *تلميح:* يمكنك إرسال روابط بصيغة:\n"
            "• https://t.me/username\n"
            "• t.me/joinchat/xxxx\n"
            "• @username",
            parse_mode='Markdown'
        )
        return
    
    # معالجة الروابط
    data = update_links(links, user_id)
    new_channels, new_groups = classify_links(links)
    
    # إرسال النتائج
    result_text = "✅ *تمت المعالجة بنجاح!*\n\n"
    
    if new_channels:
        result_text += f"📢 تم إضافة {len(new_channels)} قناة جديدة\n"
    else:
        result_text += "📢 لم يتم إضافة قنوات جديدة (موجودة مسبقاً)\n"
    
    if new_groups:
        result_text += f"👥 تم إضافة {len(new_groups)} مجموعة جديدة\n"
    else:
        result_text += "👥 لم يتم إضافة مجموعات جديدة (موجودة مسبقاً)\n"
    
    result_text += f"\n📊 إجمالي القنوات: {len(data['channels'])}\n"
    result_text += f"📊 إجمالي المجموعات: {len(data['groups'])}"
    
    await update.message.reply_text(result_text, parse_mode='Markdown')

# معالجة أزرار الردود
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "stats":
        stats = load_stats()
        data = load_links()
        stats_text = (
            f"📊 *الإحصائيات*\n\n"
            f"📢 القنوات: {len(data['channels'])}\n"
            f"👥 المجموعات: {len(data['groups'])}\n"
            f"🔗 إجمالي الروابط: {stats['total_links']}\n"
            f"🕐 آخر تحديث: {stats['last_update'] or 'لا يوجد'}"
        )
        await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    elif query.data == "show_channels":
        data = load_links()
        if not data["channels"]:
            await query.edit_message_text("📭 لا توجد قنوات محفوظة.")
            return
        
        channels_text = "📢 *القنوات:*\n\n"
        for i, link in enumerate(data["channels"][:20], 1):  # عرض أول 20 فقط
            channels_text += f"{i}. {link}\n"
        
        if len(data["channels"]) > 20:
            channels_text += f"\n*و{len(data['channels']) - 20} قناة أخرى...*\nاستخدم /channels لعرض الكل"
        
        await query.edit_message_text(channels_text, parse_mode='Markdown')
    
    elif query.data == "show_groups":
        data = load_links()
        if not data["groups"]:
            await query.edit_message_text("📭 لا توجد مجموعات محفوظة.")
            return
        
        groups_text = "👥 *المجموعات:*\n\n"
        for i, link in enumerate(data["groups"][:20], 1):
            groups_text += f"{i}. {link}\n"
        
        if len(data["groups"]) > 20:
            groups_text += f"\n*و{len(data['groups']) - 20} مجموعة أخرى...*\nاستخدم /groups لعرض الكل"
        
        await query.edit_message_text(groups_text, parse_mode='Markdown')
    
    elif query.data == "clear_all":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="confirm_clear"),
             InlineKeyboardButton("❌ لا، إلغاء", callback_data="cancel_clear")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ *تحذير:* هل أنت متأكد؟ هذا الإجراء لا يمكن التراجع عنه.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif query.data == "confirm_clear":
        save_links({"channels": [], "groups": []})
        stats = load_stats()
        stats["total_links"] = 0
        stats["last_update"] = datetime.now().isoformat()
        save_stats(stats)
        await query.edit_message_text("✅ تم مسح جميع الروابط بنجاح!")
    
    elif query.data == "cancel_clear":
        await query.edit_message_text("❌ تم إلغاء عملية المسح.")

# نقطة البداية
def main():
    # تهيئة الملفات
    init_files()
    
    # توكن البوت
    TOKEN = "8753575669:AAHH6EXVMEVxIoG4RhFHhl9EafyuKoJmLSs"
    
    # إنشاء التطبيق
    app = ApplicationBuilder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("channels", show_channels))
    app.add_handler(CommandHandler("groups", show_groups))
    app.add_handler(CommandHandler("clear", clear_all))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # بدء البوت
    print("🚀 البوت يعمل الآن...")
    print(f"📁 ملف البيانات: {DATA_FILE}")
    print(f"📊 ملف الإحصائيات: {STATS_FILE}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
