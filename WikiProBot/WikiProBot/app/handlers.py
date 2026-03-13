import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .keyboards import search_results_keyboard, article_keyboard
from .wiki_client import WikiClient
from .storage import Storage


def _short(text: str, limit: int = 900) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلا بيك!\n"
        "ابعتلي أي موضوع وانا هطلع لك نتائج من ويكيبيديا.\n\n"
        "مثال: الذكاء الاصطناعي"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "طريقة الاستخدام:\n"
        "1) ابعت كلمة/موضوع\n"
        "2) اختار نتيجة\n"
        "3) استخدم الأزرار: ملخص / تفاصيل / معلومات سريعة / حفظ\n"
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wiki: WikiClient = context.bot_data["wiki"]

    text = (update.message.text or "").strip()
    if not text:
        return

    results = await wiki.search(text, limit=6)
    if not results:
        await update.message.reply_text("ملقتش نتائج. جرّب صياغة تانية.")
        return

    await update.message.reply_text(
        "اختار النتيجة الصح:", reply_markup=search_results_keyboard(results)
    )


async def _send_article_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pageid: int, mode: str = "summary"
):
    wiki: WikiClient = context.bot_data["wiki"]

    qi = await wiki.quick_info(pageid)
    if not qi:
        await update.effective_message.reply_text("مش لاقي الصفحة دي.")
        return

    title = qi["title"]
    url = qi["fullurl"]

    thumb = None
    if mode == "summary":
        s = await wiki.summary(title)
        extract = s.get("extract") or ""
        thumb = (s.get("thumbnail") or {}).get("source")
        body = _short(extract or "ملقتش ملخص واضح.")
    else:
        details = await wiki.extract_plain(pageid, chars=2500)
        body = _short(details or "ملقتش تفاصيل نصية.")

    caption = f"<b>{html.escape(title)}</b>\n\n{html.escape(body)}"

    # بنبعت رسالة جديدة لتفادي مشاكل تعديل (Text vs Photo)
    if thumb:
        await update.effective_message.reply_photo(
            photo=thumb,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=article_keyboard(pageid, url),
        )
    else:
        await update.effective_message.reply_text(
            caption,
            parse_mode=ParseMode.HTML,
            reply_markup=article_keyboard(pageid, url),
            disable_web_page_preview=False,
        )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wiki: WikiClient = context.bot_data["wiki"]
    store: Storage = context.bot_data["store"]

    q = update.callback_query
    await q.answer()

    data = q.data or ""
    user_id = q.from_user.id

    if data == "random":
        r = await wiki.random_summary()
        title = r.get("title", "")
        extract = r.get("extract", "")
        thumb = (r.get("thumbnail") or {}).get("source")
        url = ((r.get("content_urls") or {}).get("desktop") or {}).get("page", "")

        msg = f"<b>{html.escape(title)}</b>\n\n{html.escape(_short(extract))}"
        if thumb:
            await q.message.reply_photo(photo=thumb, caption=msg, parse_mode=ParseMode.HTML)
        else:
            await q.message.reply_text(
                msg, parse_mode=ParseMode.HTML, disable_web_page_preview=False
            )
        if url:
            await q.message.reply_text(url)
        return

    if data.startswith("open|"):
        pageid = int(data.split("|", 1)[1])
        await _send_article_message(update, context, pageid, mode="summary")
        return

    if data.startswith("mode|"):
        _, mode, pageid_s = data.split("|", 2)
        pageid = int(pageid_s)
        await _send_article_message(update, context, pageid, mode=mode)
        return

    if data.startswith("quick|"):
        pageid = int(data.split("|", 1)[1])
        qi = await wiki.quick_info(pageid)
        if not qi:
            await q.message.reply_text("مش لاقي معلومات للصفحة دي.")
            return

        text = (
            f"<b>{html.escape(qi['title'])}</b>\n\n"
            f"📏 الحجم: {qi['length']} بايت\n"
            f"🧾 آخر رقم تعديل: {qi['lastrevid']}\n"
            f"🔗 الرابط: {html.escape(qi['fullurl'])}"
        )
        await q.message.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=False
        )
        return

    if data.startswith("fav_add|"):
        pageid = int(data.split("|", 1)[1])
        qi = await wiki.quick_info(pageid)
        if not qi:
            await q.message.reply_text("مش لاقي الصفحة دي.")
            return

        title = qi["title"]
        url = qi["fullurl"]
        s = await wiki.summary(title)
        summary = s.get("extract") or ""

        ok = await store.add_favorite(user_id, pageid, title, url, summary)
        await q.message.reply_text(
            "اتحفظت في المفضلة ⭐" if ok else "المقالة محفوظة قبل كده ⭐"
        )
        return

    if data == "fav_list":
        favs = await store.list_favorites(user_id, limit=50)
        if not favs:
            await q.message.reply_text("المفضلة فاضية.")
            return

        lines = []
        for f in favs[:30]:
            lines.append(
                f"• <a href='{html.escape(f['url'])}'>{html.escape(f['title'])}</a>"
            )

        await q.message.reply_text(
            "<b>⭐ مفضلاتك:</b>\n" + "\n".join(lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    if data.startswith("fav_del|"):
        pageid = int(data.split("|", 1)[1])
        await store.remove_favorite(user_id, pageid)
        await q.message.reply_text("اتحذفت من المفضلة.")
        return
