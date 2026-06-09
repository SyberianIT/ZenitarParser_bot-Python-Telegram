import asyncio
import logging
import random
from typing import Callable, List, Optional

from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, InputUserDeactivated, PeerFlood,
    UserIsBlocked, PeerIdInvalid,
)

from modules.account_pool import AccountPool
from utils.identity import to_peer

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


def _pyrogram_button(button: str):
    """Build a Pyrogram InlineKeyboardMarkup from 'text|url' string."""
    if not button or "|" not in button:
        return None
    try:
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        text, url = button.split("|", 1)
        return InlineKeyboardMarkup([[InlineKeyboardButton(text.strip(), url=url.strip())]])
    except Exception:
        return None


def _aiogram_button(button: str):
    """Build an aiogram InlineKeyboardMarkup from 'text|url' string."""
    if not button or "|" not in button:
        return None
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        text, url = button.split("|", 1)
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=text.strip(), url=url.strip())]]
        )
    except Exception:
        return None


async def via_userbot(
    pool: AccountPool,
    users: List[dict],
    template: str,
    delay_min: float = 15,
    delay_max: float = 40,
    photo_path: Optional[str] = None,
    button: Optional[str] = None,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    """DM users from real accounts, rotating across the pool."""
    from modules.blacklist import is_blacklisted

    stats = {
        "success": 0, "blocked": 0, "flood": 0, "error": 0,
        "skip": 0, "total": len(users), "accounts_used": set(),
    }
    markup = _pyrogram_button(button)

    for i, u in enumerate(users):
        if stop and stop.is_set():
            break

        if await is_blacklisted(u):
            stats["skip"] += 1
            continue

        uid = to_peer(u.get("username") or u.get("id"))
        if not uid:
            stats["skip"] += 1
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
            if photo_path:
                await client.send_photo(uid, photo=photo_path, caption=text, reply_markup=markup)
            else:
                await client.send_message(uid, text, reply_markup=markup)
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
    photo_path: Optional[str] = None,
    button: Optional[str] = None,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    """Broadcast via Bot API, rotating across multiple bot tokens."""
    from aiogram import Bot
    from aiogram.types import FSInputFile
    from aiogram.exceptions import (
        TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter,
    )
    from modules.blacklist import is_blacklisted

    bots = [Bot(token=t) for t in bot_tokens]
    stats = {"success": 0, "blocked": 0, "flood": 0, "error": 0, "skip": 0, "total": len(users)}
    markup = _aiogram_button(button)
    photo_file = FSInputFile(photo_path) if photo_path else None

    try:
        for i, u in enumerate(users):
            if stop and stop.is_set():
                break

            if await is_blacklisted(u):
                stats["skip"] += 1
                continue

            uid = u.get("id")
            if not uid:
                stats["skip"] += 1
                continue

            bot = bots[i % len(bots)]
            text = _fmt(template, u)

            try:
                if photo_file:
                    await bot.send_photo(int(uid), photo=photo_file, caption=text, reply_markup=markup)
                else:
                    await bot.send_message(int(uid), text, reply_markup=markup)
                stats["success"] += 1
            except TelegramForbiddenError:
                stats["blocked"] += 1
            except TelegramRetryAfter as e:
                stats["flood"] += 1
                await asyncio.sleep(e.retry_after)
                try:
                    if photo_file:
                        await bot.send_photo(int(uid), photo=photo_file, caption=text, reply_markup=markup)
                    else:
                        await bot.send_message(int(uid), text, reply_markup=markup)
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
