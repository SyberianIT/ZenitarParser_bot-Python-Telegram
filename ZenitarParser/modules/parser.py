import asyncio
import logging
import re
from typing import Callable, List, Optional

from pyrogram import Client
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import (
    FloodWait, ChatAdminRequired, ChannelPrivate, UserNotParticipant,
)

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
    # "all" → iterate without a search filter (RECENT yields the full member
    # list for groups the account can fully enumerate)
    fmap = {
        "all":    ChatMembersFilter.RECENT,
        "recent": ChatMembersFilter.RECENT,
        "admins": ChatMembersFilter.ADMINISTRATORS,
        "bots":   ChatMembersFilter.BOTS,
    }
    pf = fmap.get(filter_type, ChatMembersFilter.RECENT)
    result: list[dict] = []
    seen: set[int] = set()

    try:
        chat = await client.get_chat(group)
        total = chat.members_count or 0

        async for member in client.get_chat_members(chat.id, filter=pf):
            if stop and stop.is_set():
                break
            if not member.user or member.user.id in seen:
                continue
            seen.add(member.user.id)
            result.append(_u(member.user))
            n = len(result)
            if n >= limit:
                break
            if n % 100 == 0 and on_progress:
                await on_progress(n, total, f"⏳ Участников: {n}/{total or '?'}")
            if n % 500 == 0:
                await asyncio.sleep(1)

    except FloodWait as e:
        logger.warning("FloodWait %ds", e.value)
        await asyncio.sleep(e.value)
    except (ChatAdminRequired, ChannelPrivate, UserNotParticipant) as e:
        logger.warning("members access: %s", e)
        raise
    except Exception as e:
        logger.error("members error: %s", e)
        raise

    return result


async def active_users(
    client: Client,
    group: str,
    messages_limit: int = 2000,
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
        raise
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
                        "username": uname,
                        "id": ch.id,
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


_POST_RE = re.compile(r"t\.me/([\w\d_]+)/(\d+)", re.IGNORECASE)


async def comments(
    client: Client,
    post_link: str,
    limit: int = 5000,
    on_progress: Prog = None,
    stop: Optional[asyncio.Event] = None,
) -> List[dict]:
    """Parse users who commented under a channel post (its discussion thread)."""
    m = _POST_RE.search(post_link)
    if not m:
        raise ValueError("Неверная ссылка. Нужен пост вида https://t.me/channel/123")
    chat_slug, msg_id = m.group(1), int(m.group(2))

    seen: dict[int, dict] = {}
    try:
        async for reply in client.get_discussion_replies(chat_slug, msg_id):
            if stop and stop.is_set():
                break
            if reply.from_user and reply.from_user.id not in seen:
                seen[reply.from_user.id] = _u(reply.from_user)
                if len(seen) % 100 == 0 and on_progress:
                    await on_progress(len(seen), 0, f"⏳ Комментаторов: {len(seen)}")
            if len(seen) >= limit:
                break
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except ValueError:
        raise
    except Exception as e:
        logger.error("comments error: %s", e)
        raise
    return list(seen.values())


async def reactions(
    client: Client,
    post_link: str,
    on_progress: Prog = None,
    stop: Optional[asyncio.Event] = None,
) -> List[dict]:
    from pyrogram.raw.functions.messages import GetMessageReactionsList

    m = _POST_RE.search(post_link)
    if not m:
        raise ValueError(
            "Неверная ссылка. Нужен публичный пост вида https://t.me/channel/123"
        )
    chat_slug, msg_id = m.group(1), int(m.group(2))

    users: dict[int, dict] = {}
    try:
        peer = await client.resolve_peer(chat_slug)
        offset = ""
        while True:
            if stop and stop.is_set():
                break
            r = await client.invoke(
                GetMessageReactionsList(peer=peer, id=msg_id, limit=100, offset=offset)
            )
            for u in r.users:
                users[u.id] = _u(u)
            total = getattr(r, "count", len(users))
            if on_progress:
                await on_progress(len(users), total, f"⏳ Реакции: {len(users)}/{total}")
            next_off = getattr(r, "next_offset", None)
            if not next_off or len(users) >= total:
                break
            offset = next_off
            await asyncio.sleep(1)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except ValueError:
        raise
    except Exception as e:
        logger.error("reactions error: %s", e)
        raise
    return list(users.values())
