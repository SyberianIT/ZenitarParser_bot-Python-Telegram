import asyncio
import logging
from typing import Callable, List, Optional

from pyrogram import Client
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, ChatAdminRequired, ChannelPrivate, UserNotParticipant

logger = logging.getLogger(__name__)

Prog = Optional[Callable]


def _u(user) -> dict:
    return {
        "id": user.id,
        "username": getattr(user, "username", "") or "",
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
        "phone": getattr(user, "phone_number", "") or "",
        "is_bot": bool(getattr(user, "is_bot", False)),
        "is_premium": bool(getattr(user, "is_premium", False)),
        "is_verified": bool(getattr(user, "is_verified", False)),
    }


async def members(
    client: Client,
    group: str,
    filter_type: str = "recent",
    limit: int = 50000,
    on_progress: Prog = None,
    stop: Optional[asyncio.Event] = None,
) -> List[dict]:
    fmap = {
        "all":    ChatMembersFilter.SEARCH,
        "recent": ChatMembersFilter.RECENT,
        "admins": ChatMembersFilter.ADMINISTRATORS,
        "bots":   ChatMembersFilter.BOTS,
    }
    pf = fmap.get(filter_type, ChatMembersFilter.RECENT)
    result: list[dict] = []

    try:
        chat = await client.get_chat(group)
        total = chat.members_count or 0

        async for member in client.get_chat_members(chat.id, filter=pf):
            if stop and stop.is_set():
                break
            result.append(_u(member.user))
            n = len(result)
            if n >= limit:
                break
            if n % 100 == 0 and on_progress:
                await on_progress(n, total, f"⏳ Участников: {n}/{total}")
            if n % 500 == 0:
                await asyncio.sleep(1)

    except FloodWait as e:
        logger.warning("FloodWait %ds", e.value)
        await asyncio.sleep(e.value)
    except (ChatAdminRequired, ChannelPrivate, UserNotParticipant) as e:
        logger.warning("members access: %s", e)
    except Exception as e:
        logger.error("members error: %s", e)

    return result


async def active_users(
    client: Client,
    group: str,
    messages_limit: int = 1000,
    on_progress: Prog = None,
    stop: Optional[asyncio.Event] = None,
) -> List[dict]:
    seen: dict[int, dict] = {}
    try:
        chat = await client.get_chat(group)
        n = 0
        async for msg in client.get_chat_history(chat.id, limit=messages_limit):
            if stop and stop.is_set():
                break
            if msg.from_user and msg.from_user.id not in seen:
                seen[msg.from_user.id] = _u(msg.from_user)
            n += 1
            if n % 100 == 0 and on_progress:
                await on_progress(len(seen), 0, f"⏳ Сообщений: {n} | Юзеров: {len(seen)}")
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error("active_users error: %s", e)
    return list(seen.values())


async def by_keyword(
    client: Client,
    keywords: List[str],
    limit: int = 100,
    on_progress: Prog = None,
    stop: Optional[asyncio.Event] = None,
) -> List[dict]:
    from pyrogram.raw.functions.contacts import Search

    chats: dict[str, dict] = {}
    for i, kw in enumerate(keywords):
        if stop and stop.is_set():
            break
        if on_progress:
            await on_progress(i, len(keywords), f"⏳ Поиск: «{kw}» ({i+1}/{len(keywords)})")
        try:
            r = await client.invoke(Search(q=kw, limit=limit))
            for ch in r.chats:
                uname = getattr(ch, "username", None)
                if uname and uname not in chats:
                    chats[uname] = {
                        "id": ch.id,
                        "username": uname,
                        "title": getattr(ch, "title", ""),
                        "members_count": getattr(ch, "participants_count", 0),
                        "type": ch.__class__.__name__,
                    }
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.error("keyword '%s': %s", kw, e)
        await asyncio.sleep(2)
    return list(chats.values())


async def reactions(
    client: Client,
    post_link: str,
    on_progress: Prog = None,
    stop: Optional[asyncio.Event] = None,
) -> List[dict]:
    from pyrogram.raw.functions.messages import GetMessageReactionsList

    users: list[dict] = []
    try:
        parts = post_link.rstrip("/").split("/")
        chat_slug = parts[-2]
        msg_id = int(parts[-1])
        peer = await client.resolve_peer(chat_slug)
        offset = ""

        while True:
            if stop and stop.is_set():
                break
            r = await client.invoke(
                GetMessageReactionsList(peer=peer, id=msg_id, limit=100, offset=offset)
            )
            for u in r.users:
                users.append(_u(u))
            if on_progress:
                await on_progress(len(users), r.count, f"⏳ Реакции: {len(users)}/{r.count}")
            if not getattr(r, "next_offset", None) or len(users) >= r.count:
                break
            offset = r.next_offset
            await asyncio.sleep(1)
    except Exception as e:
        logger.error("reactions error: %s", e)
    return users
