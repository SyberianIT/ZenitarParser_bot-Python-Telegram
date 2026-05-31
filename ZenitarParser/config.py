import os

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

_raw = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS: list[int] = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]

SESSIONS_DIR = "sessions"
EXPORTS_DIR = "exports"
DB_PATH = "zenitar.db"
