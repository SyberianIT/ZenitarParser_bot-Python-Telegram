import asyncio
import logging
import random
from typing import Callable, List, Optional

from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, InputUserDeactivated, PeerFlood,
    UserIsBlocked, PeerIdInvalid,
)

from modules.account_pool import AccountPool

logger = logging.getLogger(__name__)


def _fmt(template: str, user: dict) -> str:
    uname = ("@" + user["username"]) if user.get("username") else ""
    try:
        return template.format(
            name=user.get("first_name", "") or "",
            username=uname,
            last_name=user.get("last_name", "") or "",
            full_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            id=user.get("id", ""),
        )
    except (KeyError, IndexError, ValueError):
        return template


async def via_userbot(
    pool: AccountPool,
    users: List[dict],
    template: str,
    delay_min: float = 15,
    delay_max: float = 40,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    """DM users from real accounts, rotating across the pool."""
    stats = {
        "success": 0, "blocked": 0, "flood": 0, "error": 0,
        "total": len(users), "accounts_used": set(),
    }

    for i, u in enumerate(users):
        if stop and stop.is_set():
            break

        uid = u.get("username") or u.get("id")
        if not uid:
            stats["error"] += 1
            continue

        acc = await pool.acquire("send")
        if not acc:
            logger.warning("No healthy accounts left for sending")
            stats["no_accounts"] = True
            break
        name, client = acc
        stats["accounts_used"].add(name)
        text = _fmt(template, u)

        try:
            await client.send_message(uid, text)
            stats["success"] += 1
            await pool.report_success(name, "send")
        except (UserPrivacyRestricted, UserIsBlocked):
            stats["blocked"] += 1
        except (InputUserDeactivated, PeerIdInvalid):
            stats["error"] += 1
        except PeerFlood:
            stats["flood"] += 1
            await pool.mark_flood(name)
        except FloodWait as e:
            stats["flood"] += 1
            await pool.mark_flood(name, int(e.value))
        except Exception as e:
            stats["error"] += 1
            logger.error("userbot send to %s via %s: %s", uid, name, e)

        if on_progress and (i + 1) % 10 == 0:
            await on_progress(i + 1, len(users), stats)

        await asyncio.sleep(random.uniform(delay_min, delay_max))

    stats["accounts_used"] = len(stats["accounts_used"])
    return stats


async def via_bot(
    bot_tokens: List[str],
    users: List[dict],
    template: str,
    delay_min: float = 0.05,
    delay_max: float = 0.3,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    """Broadcast via Bot API, rotating across multiple bot tokens.
    Recipients must have started at least one of the bots."""
    from aiogram import Bot
    from aiogram.exceptions import (
        TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter,
    )

    bots = [Bot(token=t) for t in bot_tokens]
    stats = {"success": 0, "blocked": 0, "flood": 0, "error": 0, "total": len(users)}

    try:
        for i, u in enumerate(users):
            if stop and stop.is_set():
                break

            uid = u.get("id")
            if not uid:
                stats["error"] += 1
                continue

            bot = bots[i % len(bots)]
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
        for b in bots:
            await b.session.close()

    return stats
