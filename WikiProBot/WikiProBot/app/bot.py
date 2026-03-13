import asyncio

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .config import get_config
from .wiki_client import WikiClient
from .storage import Storage
from .handlers import cmd_start, cmd_help, on_text, on_button


async def main():
    cfg = get_config()

    wiki = WikiClient(lang=cfg.wiki_lang)
    store = Storage(cfg.db_path)
    await store.init()

    app = ApplicationBuilder().token(cfg.bot_token).build()

    # حقن الاعتمادات (Dependency Injection)
    app.bot_data["wiki"] = wiki
    app.bot_data["store"] = store

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    asyncio.run(main())
