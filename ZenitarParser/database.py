from datetime import date

import aiosqlite

import config

DB = config.DB_PATH


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bot_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token      TEXT UNIQUE NOT NULL,
                username   TEXT,
                status     TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS accounts (
                name           TEXT PRIMARY KEY,
                proxy          TEXT DEFAULT '',
                status         TEXT DEFAULT 'active',   -- active / flood / banned / disabled
                flood_until    INTEGER DEFAULT 0,       -- unix ts
                invites_today  INTEGER DEFAULT 0,
                messages_today INTEGER DEFAULT 0,
                last_reset     TEXT DEFAULT '',
                added_at       DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stats (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,        -- parse / invite / send
                detail TEXT DEFAULT '',
                count  INTEGER DEFAULT 0,
                ts     DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()


# ── settings ──────────────────────────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value)
        )
        await db.commit()


# ── bot tokens ──────────────────────────────────────────────────────────────────

async def get_bot_tokens() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_tokens WHERE status='active'") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_bot_tokens() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_tokens ORDER BY id") as cur:
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


# ── accounts (health & limits) ────────────────────────────────────────────────

async def upsert_account(name: str, proxy: str = ""):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO accounts (name, proxy, last_reset) VALUES (?,?,?)",
            (name, proxy, date.today().isoformat()),
        )
        await db.commit()


async def delete_account(name: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM accounts WHERE name=?", (name,))
        await db.commit()


async def get_accounts() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM accounts") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_account(name: str) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM accounts WHERE name=?", (name,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def update_account(name: str, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [name]
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE accounts SET {cols} WHERE name=?", vals)
        await db.commit()


async def reset_daily_if_needed():
    today = date.today().isoformat()
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE accounts SET invites_today=0, messages_today=0, last_reset=? "
            "WHERE last_reset != ?",
            (today, today),
        )
        # auto-recover accounts whose flood cooldown is documented per-call;
        # reset 'flood' status rows back to active on a new day
        await db.execute(
            "UPDATE accounts SET status='active', flood_until=0 "
            "WHERE status='flood' AND last_reset=?",
            (today,),
        )
        await db.commit()


# ── stats ──────────────────────────────────────────────────────────────────────

async def log_stat(action: str, detail: str, count: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO stats (action, detail, count) VALUES (?,?,?)",
            (action, detail, count),
        )
        await db.commit()


async def stats_summary() -> dict:
    async with aiosqlite.connect(DB) as db:
        result = {}
        for action in ("parse", "invite", "send"):
            async with db.execute(
                "SELECT COALESCE(SUM(count),0), COUNT(*) FROM stats WHERE action=?",
                (action,),
            ) as cur:
                total, runs = await cur.fetchone()
            result[action] = {"total": total, "runs": runs}
        return result


async def recent_stats(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM stats ORDER BY id DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
