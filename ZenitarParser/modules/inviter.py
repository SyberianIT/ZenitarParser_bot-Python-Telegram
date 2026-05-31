import asyncio
import random
import logging
from typing import Callable, List, Optional

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, InputUserDeactivated,
    PeerFlood, UserBannedInChannel, UserNotMutualContact,
    UserAlreadyParticipant,
)

logger = logging.getLogger(__name__)


async def invite(
    client: Client,
    group: str,
    users: List[dict],
    delay_min: float = 5,
    delay_max: float = 15,
    on_progress: Optional[Callable] = None,
    stop: Optional[asyncio.Event] = None,
) -> dict:
    stats = {"success": 0, "privacy": 0, "flood": 0, "error": 0, "skip": 0, "total": len(users)}

    try:
        chat = await client.get_chat(group)
    except Exception as e:
        logger.error("Can't resolve group '%s': %s", group, e)
        stats["error"] = len(users)
        return stats

    for i, u in enumerate(users):
        if stop and stop.is_set():
            break

        uid = u.get("username") or u.get("id")
        if not uid:
            stats["skip"] += 1
            continue

        try:
            await client.add_chat_members(chat.id, uid)
            stats["success"] += 1
        except UserAlreadyParticipant:
            stats["skip"] += 1
        except UserPrivacyRestricted:
            stats["privacy"] += 1
        except PeerFlood:
            stats["flood"] += 1
            logger.warning("PeerFlood — account limited, stopping invites")
            break
        except FloodWait as e:
            await asyncio.sleep(e.value)
            stats["flood"] += 1
        except (InputUserDeactivated, UserBannedInChannel, UserNotMutualContact):
            stats["error"] += 1
        except Exception as e:
            stats["error"] += 1
            logger.error("invite %s: %s", uid, e)

        if on_progress and (i + 1) % 5 == 0:
            await on_progress(i + 1, len(users), stats)

        await asyncio.sleep(random.uniform(delay_min, delay_max))

    return stats
