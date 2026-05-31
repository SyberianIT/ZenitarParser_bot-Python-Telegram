import asyncio
import logging
import random
from typing import Callable, List, Optional

from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, InputUserDeactivated,
    PeerFlood, UserBannedInChannel, UserNotMutualContact,
    UserAlreadyParticipant, UserChannelsTooMuch,
)

from modules.account_pool import AccountPool

logger = logging.getLogger(__name__)


async def invite(
    pool: AccountPool,
    group: str,
    users: List[dict],
    delay_min: float = 20,
    delay_max: float = 45,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    """Invite users into `group`, rotating across all healthy accounts.
    Each account is auto-skipped when it floods or hits its daily limit."""
    stats = {
        "success": 0, "privacy": 0, "flood": 0, "error": 0,
        "skip": 0, "total": len(users), "accounts_used": set(),
    }
    chat_cache: dict[str, object] = {}  # per-account resolved chat

    for i, u in enumerate(users):
        if stop and stop.is_set():
            break

        uid = u.get("username") or u.get("id")
        if not uid:
            stats["skip"] += 1
            continue

        acc = await pool.acquire("invite")
        if not acc:
            logger.warning("No healthy accounts left for inviting")
            stats["no_accounts"] = True
            break
        name, client = acc
        stats["accounts_used"].add(name)

        try:
            chat = chat_cache.get(name)
            if chat is None:
                chat = await client.get_chat(group)
                chat_cache[name] = chat

            await client.add_chat_members(chat.id, uid)
            stats["success"] += 1
            await pool.report_success(name, "invite")

        except UserAlreadyParticipant:
            stats["skip"] += 1
        except UserPrivacyRestricted:
            stats["privacy"] += 1
        except PeerFlood:
            stats["flood"] += 1
            await pool.mark_flood(name)
            chat_cache.pop(name, None)
        except FloodWait as e:
            stats["flood"] += 1
            await pool.mark_flood(name, int(e.value))
            chat_cache.pop(name, None)
        except UserChannelsTooMuch:
            stats["error"] += 1
        except (InputUserDeactivated, UserBannedInChannel, UserNotMutualContact):
            stats["error"] += 1
        except Exception as e:
            stats["error"] += 1
            logger.error("invite %s via %s: %s", uid, name, e)

        if on_progress and (i + 1) % 5 == 0:
            await on_progress(i + 1, len(users), stats)

        await asyncio.sleep(random.uniform(delay_min, delay_max))

    stats["accounts_used"] = len(stats["accounts_used"])
    return stats
