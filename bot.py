from pyrogram import Client, filters
import yt_dlp
import os
import uuid

# ===== بياناتك =====
API_ID = 7924248487
API_HASH = "8783172268"
BOT_TOKEN = "8341748176:AAG5FH7qyTGahxpoCRBNoMq9-4noTO_xWc4"

app = Client(
    "downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ===== إعدادات التحميل =====
def download(url):
    unique_id = str(uuid.uuid4())
    output = f"{unique_id}.%(ext)s"

    ydl_opts = {
        "outtmpl": output,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            # تحويل الاسم إلى mp4 إذا لزم
            if not file_path.endswith(".mp4"):
                base = os.path.splitext(file_path)[0]
                new_file = base + ".mp4"
                if os.path.exists(new_file):
                    file_path = new_file

            return file_path

    except Exception as e:
        return None

# ===== استقبال الروابط =====
@app.on_message(filters.text & filters.private)
async def handler(client, message):
    url = message.text.strip()

    if "http" not in url:
        return await message.reply("❌ أرسل رابط صحيح")

    msg = await message.reply("⏳ جاري التحميل...")

    file_path = download(url)

    if not file_path or not os.path.exists(file_path):
        return await msg.edit("❌ فشل التحميل (الرابط غير مدعوم أو خاص)")

    try:
        await message.reply_video(
            file_path,
            caption="✅ تم التحميل بنجاح"
        )
        os.remove(file_path)

    except Exception:
        try:
            await message.reply_document(file_path)
            os.remove(file_path)
        except:
            await msg.edit("❌ فشل الإرسال")

# ===== تشغيل =====
print("Bot is running...")
app.run()
