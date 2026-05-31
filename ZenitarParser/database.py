import aiosqlite
import config

DB = config.DB_PATH


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS bot_tokens (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                token    TEXT UNIQUE NOT NULL,
                username TEXT,
                status   TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        await db.commit()


async def get_bot_tokens() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_tokens WHERE status='active'") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_bot_tokens() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_tokens") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_bot_token(token: str, username: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_tokens (token,username,status) VALUES (?,?,'active')",
            (token, username),
        )
        await db.commit()


async def delete_bot_token(bot_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM bot_tokens WHERE id=?", (bot_id,))
        await db.commit()
