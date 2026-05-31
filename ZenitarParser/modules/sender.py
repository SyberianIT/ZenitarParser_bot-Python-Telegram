import asyncio
import random
import logging
from typing import Callable, List, Optional

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, InputUserDeactivated, PeerFlood,
)

logger = logging.getLogger(__name__)


def _fmt(template: str, user: dict) -> str:
    uname = ("@" + user["username"]) if user.get("username") else ""
    return template.format(
        name=user.get("first_name", ""),
        username=uname,
        last_name=user.get("last_name", ""),
        full_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        id=user.get("id", ""),
    )


async def via_userbot(
    client: Client,
    users: List[dict],
    template: str,
    delay_min: float = 3,
    delay_max: float = 10,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    stats = {"success": 0, "blocked": 0, "flood": 0, "error": 0, "total": len(users)}

    for i, u in enumerate(users):
        if stop and stop.is_set():
            break

        uid = u.get("username") or u.get("id")
        if not uid:
            stats["error"] += 1
            continue

        text = _fmt(template, u)

        try:
            await client.send_message(uid, text)
            stats["success"] += 1
        except UserPrivacyRestricted:
            stats["blocked"] += 1
        except InputUserDeactivated:
            stats["error"] += 1
        except PeerFlood:
            stats["flood"] += 1
            logger.warning("PeerFlood — stopping userbot sender")
            break
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.send_message(uid, text)
                stats["success"] += 1
            except Exception:
                stats["error"] += 1
        except Exception as e:
            stats["error"] += 1
            logger.error("userbot send to %s: %s", uid, e)

        if on_progress and (i + 1) % 10 == 0:
            await on_progress(i + 1, len(users), stats)

        await asyncio.sleep(random.uniform(delay_min, delay_max))

    return stats


async def via_bot(
    bot_token: str,
    users: List[dict],
    template: str,
    delay_min: float = 0.05,
    delay_max: float = 0.3,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    from aiogram import Bot
    from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

    bot = Bot(token=bot_token)
    stats = {"success": 0, "blocked": 0, "flood": 0, "error": 0, "total": len(users)}

    try:
        for i, u in enumerate(users):
            if stop and stop.is_set():
                break

            uid = u.get("id")
            if not uid:
                stats["error"] += 1
                continue

            text = _fmt(template, u)

            try:
                await bot.send_message(int(uid), text)
                stats["success"] += 1
            except TelegramForbiddenError:
                stats["blocked"] += 1
            except TelegramRetryAfter as e:
                stats["flood"] += 1
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_message(int(uid), text)
                    stats["success"] += 1
                    stats["flood"] -= 1
                except Exception:
                    stats["error"] += 1
            except TelegramBadRequest:
                stats["error"] += 1
            except Exception as e:
                stats["error"] += 1
                logger.error("bot send to %s: %s", uid, e)

            if on_progress and (i + 1) % 20 == 0:
                await on_progress(i + 1, len(users), stats)

            await asyncio.sleep(random.uniform(delay_min, delay_max))
    finally:
        await bot.session.close()

    return stats
