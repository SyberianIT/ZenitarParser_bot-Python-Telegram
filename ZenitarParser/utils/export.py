import csv
import os
from typing import List, Optional

import aiofiles
import config


async def to_csv(data: List[dict], filename: str) -> str:
    os.makedirs(config.EXPORTS_DIR, exist_ok=True)
    path = os.path.join(config.EXPORTS_DIR, filename)
    if not data:
        return path
    keys = list(data[0].keys())
    async with aiofiles.open(path, "w", encoding="utf-8", newline="") as f:
        await f.write(",".join(keys) + "\n")
        for row in data:
            line = ",".join(str(row.get(k, "")).replace(",", ";").replace("\n", " ") for k in keys)
            await f.write(line + "\n")
    return path


async def to_txt(data: List[dict], filename: str, field: str = "username") -> str:
    os.makedirs(config.EXPORTS_DIR, exist_ok=True)
    path = os.path.join(config.EXPORTS_DIR, filename)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        lines = [str(row.get(field, "")) for row in data if row.get(field)]
        await f.write("\n".join(lines))
    return path


def load_csv(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_export() -> Optional[str]:
    if not os.path.exists(config.EXPORTS_DIR):
        return None
    files = sorted(
        [f for f in os.listdir(config.EXPORTS_DIR) if f.endswith(".csv")],
        reverse=True,
    )
    return os.path.join(config.EXPORTS_DIR, files[0]) if files else None


def list_exports(n: int = 10) -> List[str]:
    if not os.path.exists(config.EXPORTS_DIR):
        return []
    return sorted(
        [f for f in os.listdir(config.EXPORTS_DIR) if f.endswith(".csv")],
        reverse=True,
    )[:n]
