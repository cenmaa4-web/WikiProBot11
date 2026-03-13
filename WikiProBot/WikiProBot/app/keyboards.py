from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def search_results_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in results:
        title = item.get("title", "بدون عنوان")
        pageid = item.get("pageid", 0)
        rows.append([InlineKeyboardButton(title, callback_data=f"open|{pageid}")])

    rows.append([InlineKeyboardButton("🎲 مقالة عشوائية", callback_data="random")])
    rows.append([InlineKeyboardButton("⭐ المفضلة", callback_data="fav_list")])
    return InlineKeyboardMarkup(rows)


def article_keyboard(pageid: int, fullurl: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📄 ملخص", callback_data=f"mode|summary|{pageid}"),
            InlineKeyboardButton("📚 تفاصيل", callback_data=f"mode|details|{pageid}"),
        ],
        [
            InlineKeyboardButton("📊 معلومات سريعة", callback_data=f"quick|{pageid}"),
            InlineKeyboardButton("⭐ حفظ بالمفضلة", callback_data=f"fav_add|{pageid}"),
        ],
        [
            InlineKeyboardButton("📜 عرض المفضلة", callback_data="fav_list"),
            InlineKeyboardButton("🔗 اقرأ المزيد", url=fullurl),
        ],
    ]
    return InlineKeyboardMarkup(rows)
