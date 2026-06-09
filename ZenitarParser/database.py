import time
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

            CREATE TABLE IF NOT EXISTS blacklist (
                ident    TEXT PRIMARY KEY,    -- 'id:123' or 'un:username'
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at     INTEGER NOT NULL,
                mode       TEXT NOT NULL,      -- userbot / bot
                csv_path   TEXT NOT NULL,
                template   TEXT DEFAULT '',
                photo_path TEXT DEFAULT '',
                button     TEXT DEFAULT '',    -- 'text|url'
                status     TEXT DEFAULT 'pending',  -- pending / running / done / failed
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    now = int(time.time())
    async with aiosqlite.connect(DB) as db:
        # New day → reset per-day counters
        await db.execute(
            "UPDATE accounts SET invites_today=0, messages_today=0, last_reset=? "
            "WHERE last_reset != ?",
            (today, today),
        )
        # Recover accounts whose flood cooldown has actually elapsed
        await db.execute(
            "UPDATE accounts SET status='active', flood_until=0 "
            "WHERE status='flood' AND flood_until>0 AND flood_until<=?",
            (now,),
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


# ── blacklist ──────────────────────────────────────────────────────────────────

async def blacklist_add(ident: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO blacklist (ident) VALUES (?)", (ident,))
        await db.commit()


async def blacklist_remove(ident: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM blacklist WHERE ident=?", (ident,))
        await db.commit()


async def blacklist_check(ident: str) -> bool:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT 1 FROM blacklist WHERE ident=?", (ident,)) as cur:
            return await cur.fetchone() is not None


async def blacklist_get_all() -> list[str]:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT ident FROM blacklist ORDER BY added_at DESC") as cur:
            return [row[0] for row in await cur.fetchall()]


async def blacklist_clear():
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM blacklist")
        await db.commit()


# ── scheduled jobs ─────────────────────────────────────────────────────────────

async def job_add(run_at: int, mode: str, csv_path: str, template: str,
                  photo_path: str = "", button: str = "") -> int:
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "INSERT INTO scheduled_jobs (run_at, mode, csv_path, template, photo_path, button) "
            "VALUES (?,?,?,?,?,?)",
            (run_at, mode, csv_path, template, photo_path, button),
        ) as cur:
            job_id = cur.lastrowid
        await db.commit()
    return job_id


async def job_get_pending() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM scheduled_jobs WHERE status='pending' ORDER BY run_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def job_get_all() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM scheduled_jobs ORDER BY id DESC LIMIT 30"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def job_update_status(job_id: int, status: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE scheduled_jobs SET status=? WHERE id=?", (status, job_id)
        )
        await db.commit()


async def job_delete(job_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM scheduled_jobs WHERE id=?", (job_id,))
        await db.commit()
