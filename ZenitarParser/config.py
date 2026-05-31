import os

from dotenv import load_dotenv

load_dotenv()


def _int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


# ── Telegram credentials ──────────────────────────────────────────────────────
API_ID = _int("API_ID", 0)
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

_raw_admins = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().lstrip("-").isdigit()
]

# ── Storage paths ───────────────────────────────────────────────────────────────
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "sessions")
EXPORTS_DIR = os.getenv("EXPORTS_DIR", "exports")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")
LOGS_DIR = os.getenv("LOGS_DIR", "logs")
DB_PATH = os.getenv("DB_PATH", "zenitar.db")

# ── Optional persistent FSM (Redis) ───────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "")

# ── Per-account safety limits (anti-ban defaults, conservative) ────────────────
MAX_INVITES_PER_DAY = _int("MAX_INVITES_PER_DAY", 40)
MAX_MESSAGES_PER_DAY = _int("MAX_MESSAGES_PER_DAY", 30)
FLOOD_COOLDOWN = _int("FLOOD_COOLDOWN", 3600)  # seconds after PeerFlood

# ── Default action delays "min-max" seconds ────────────────────────────────────
DEFAULT_DELAY_INVITE = os.getenv("DEFAULT_DELAY_INVITE", "20-45")
DEFAULT_DELAY_SEND = os.getenv("DEFAULT_DELAY_SEND", "15-40")

# ── Logging ─────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def validate() -> list[str]:
    """Returns a list of human-readable configuration problems (empty = OK)."""
    problems = []
    if not API_ID:
        problems.append("API_ID не задан (получите на https://my.telegram.org)")
    if not API_HASH:
        problems.append("API_HASH не задан")
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN не задан (получите у @BotFather)")
    if not ADMIN_IDS or ADMIN_IDS == [0]:
        problems.append("ADMIN_IDS не задан (ваш Telegram ID)")
    return problems
