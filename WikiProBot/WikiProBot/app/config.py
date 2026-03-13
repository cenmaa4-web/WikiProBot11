import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    wiki_lang: str = "ar"
    db_path: str = "./data/wiki_bot.db"


def get_config() -> Config:
    token = (os.getenv("8783172268:AAGySqhbboqeW5DoFO334F-IYxjTr1fJUz4") or "").strip()
    if not token:
        raise RuntimeError("Missing BOT_TOKEN. Put it in .env file.")

    return Config(
        bot_token=token,
        wiki_lang=(os.getenv("WIKI_LANG") or "ar").strip(),
        db_path=(os.getenv("DB_PATH") or "./data/wiki_bot.db").strip(),
    )
