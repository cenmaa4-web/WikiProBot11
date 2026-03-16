import aiosqlite
from typing import Optional


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER NOT NULL,
                    pageid INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    added_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (user_id, pageid)
                );
                """
            )
            await db.commit()

    async def add_favorite(
        self, user_id: int, pageid: int, title: str, url: str, summary: str
    ) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO favorites(user_id, pageid, title, url, summary) VALUES(?,?,?,?,?)",
                    (user_id, pageid, title, url, summary or ""),
                )
                await db.commit()
            return True
        except Exception:
            # غالبًا Duplicate (المقالة محفوظة قبل كده)
            return False

    async def remove_favorite(self, user_id: int, pageid: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM favorites WHERE user_id=? AND pageid=?", (user_id, pageid)
            )
            await db.commit()

    async def list_favorites(self, user_id: int, limit: int = 50) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT pageid, title, url, summary, added_at
                FROM favorites
                WHERE user_id=?
                ORDER BY added_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_favorite(self, user_id: int, pageid: int) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT pageid, title, url, summary, added_at
                FROM favorites
                WHERE user_id=? AND pageid=?
                """,
                (user_id, pageid),
            )
            row = await cur.fetchone()
        return dict(row) if row else None
