import asyncio
import csv
import os
from typing import List, Optional

import config

# Standard columns used across the app
USER_FIELDS = [
    "id", "username", "first_name", "last_name",
    "phone", "is_bot", "is_premium", "is_verified",
]


def _safe(value) -> str:
    """Guard against CSV injection (formula prefixes) while preserving the value."""
    s = "" if value is None else str(value)
    if s and s[0] in ("=", "+", "-", "@"):
        s = "'" + s
    return s


def _write_csv(data: List[dict], path: str):
    if not data:
        # still create the file with no rows
        open(path, "w", encoding="utf-8").close()
        return
    # Union of keys, stable order: known fields first, then any extras
    keys = [k for k in USER_FIELDS if any(k in row for row in data)]
    for row in data:
        for k in row:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow({k: _safe(row.get(k, "")) for k in keys})


async def to_csv(data: List[dict], filename: str) -> str:
    os.makedirs(config.EXPORTS_DIR, exist_ok=True)
    path = os.path.join(config.EXPORTS_DIR, filename)
    await asyncio.to_thread(_write_csv, data, path)
    return path


def _read_csv(path: str) -> List[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


async def load_csv(path: str) -> List[dict]:
    return await asyncio.to_thread(_read_csv, path)


def latest_export() -> Optional[str]:
    if not os.path.exists(config.EXPORTS_DIR):
        return None
    files = sorted(
        (f for f in os.listdir(config.EXPORTS_DIR) if f.endswith(".csv")),
        reverse=True,
    )
    return os.path.join(config.EXPORTS_DIR, files[0]) if files else None


def list_exports(n: int = 10) -> List[str]:
    if not os.path.exists(config.EXPORTS_DIR):
        return []
    return sorted(
        (f for f in os.listdir(config.EXPORTS_DIR) if f.endswith(".csv")),
        reverse=True,
    )[:n]
