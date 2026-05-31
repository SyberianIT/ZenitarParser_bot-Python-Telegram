import aiosqlite
from datetime import datetime

DB = "zenitar.db"


async def init():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT UNIQUE NOT NULL,
                first_name TEXT,
                username TEXT,
                tg_id INTEGER,
                phone TEXT,
                dc_id INTEGER,
                status TEXT DEFAULT 'active',
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source TEXT,
                mode TEXT NOT NULL,
                total INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS parsed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                tg_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_bot INTEGER DEFAULT 0,
                FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bot_subs (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                mode TEXT NOT NULL,
                result_id INTEGER,
                text TEXT,
                media_id TEXT,
                media_type TEXT,
                account_ids TEXT,
                delay REAL DEFAULT 3.0,
                status TEXT DEFAULT 'done',
                sent INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invite_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                target_group TEXT NOT NULL,
                account_ids TEXT,
                delay REAL DEFAULT 5.0,
                status TEXT DEFAULT 'done',
                invited INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)
        await db.commit()


# ── Accounts ──────────────────────────────────────────────────────────────────

async def upsert_account(session_name, first_name, username, tg_id, phone, dc_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """INSERT INTO accounts (session_name, first_name, username, tg_id, phone, dc_id, status, added_at)
               VALUES (?,?,?,?,?,?,'active',?)
               ON CONFLICT(session_name) DO UPDATE SET
                 first_name=excluded.first_name, username=excluded.username,
                 tg_id=excluded.tg_id, phone=excluded.phone, dc_id=excluded.dc_id,
                 status='active'""",
            (session_name, first_name, username, tg_id, phone, dc_id, datetime.now().isoformat()),
        )
        await db.commit()


async def set_account_status(acc_id: int, status: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE accounts SET status=? WHERE id=?", (status, acc_id))
        await db.commit()


async def delete_account(acc_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
        await db.commit()


async def get_accounts(active_only=False) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM accounts" + (" WHERE status='active'" if active_only else "") + " ORDER BY id"
        async with db.execute(q) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_account(acc_id: int) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ── Parse results ──────────────────────────────────────────────────────────────

async def save_result(name: str, source: str, mode: str, users: list[dict]) -> int:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT INTO results (name, source, mode, total, created_at) VALUES (?,?,?,?,?)",
            (name, source, mode, len(users), datetime.now().isoformat()),
        )
        rid = cur.lastrowid
        await db.executemany(
            "INSERT INTO parsed (result_id, tg_id, username, first_name, last_name, is_bot) VALUES (?,?,?,?,?,?)",
            [(rid, u.get("id"), u.get("username"), u.get("first_name"), u.get("last_name"), int(u.get("is_bot", False))) for u in users],
        )
        await db.commit()
        return rid


async def get_results() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM results ORDER BY created_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_result(rid: int) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM results WHERE id=?", (rid,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_parsed(rid: int, users_only=False, with_username=False) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        conds = [f"result_id={rid}"]
        if users_only:
            conds.append("is_bot=0")
        if with_username:
            conds.append("username IS NOT NULL AND username != ''")
        q = "SELECT * FROM parsed WHERE " + " AND ".join(conds)
        async with db.execute(q) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_result(rid: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM parsed WHERE result_id=?", (rid,))
        await db.execute("DELETE FROM results WHERE id=?", (rid,))
        await db.commit()


# ── Bot subscribers ────────────────────────────────────────────────────────────

async def add_bot_sub(tg_id: int, username: str | None, first_name: str | None):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO bot_subs (tg_id, username, first_name, added_at) VALUES (?,?,?,?)",
            (tg_id, username, first_name, datetime.now().isoformat()),
        )
        await db.commit()


async def get_bot_subs() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_subs") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def count_bot_subs() -> int:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT COUNT(*) FROM bot_subs") as cur:
            return (await cur.fetchone())[0]


# ── Campaigns / invite jobs ────────────────────────────────────────────────────

async def save_campaign(name, mode, result_id, text, media_id, media_type, account_ids, delay, sent, failed, total):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """INSERT INTO campaigns
               (name, mode, result_id, text, media_id, media_type, account_ids, delay, sent, failed, total, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, mode, result_id, text, media_id, media_type,
             ",".join(str(i) for i in (account_ids or [])),
             delay, sent, failed, total, datetime.now().isoformat()),
        )
        await db.commit()


async def save_invite_job(result_id, target_group, account_ids, delay, invited, failed, total):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """INSERT INTO invite_jobs
               (result_id, target_group, account_ids, delay, invited, failed, total, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (result_id, target_group,
             ",".join(str(i) for i in (account_ids or [])),
             delay, invited, failed, total, datetime.now().isoformat()),
        )
        await db.commit()


async def get_campaigns() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 20") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_invite_jobs() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM invite_jobs ORDER BY created_at DESC LIMIT 20") as cur:
            return [dict(r) for r in await cur.fetchall()]
