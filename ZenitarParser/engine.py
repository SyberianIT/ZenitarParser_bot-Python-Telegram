"""
Core Pyrogram operations: account check, parsing, inviting, DM sending.
All long operations accept a stop_event and an optional async progress_cb.
"""
import asyncio
import logging
import os
from typing import Callable, Awaitable

from pyrogram import Client
from pyrogram.raw.functions.contacts import Search
from pyrogram.errors import (
    FloodWait, ChatAdminRequired, UsernameInvalid, UserPrivacyRestricted,
    InputUserDeactivated, UserNotMutualContact, PeerFlood, UserBannedInChannel,
    UserChannelsTooMuch,
)
from config import API_ID, API_HASH

log = logging.getLogger(__name__)

ProgressCB = Callable[..., Awaitable[None]]


def _client(session_name: str) -> Client:
    return Client(session_name, API_ID, API_HASH, workdir="sessions")


async def _flood_sleep(e: FloodWait, cb: ProgressCB | None, msg: str):
    wait = e.value + 2
    log.warning(f"FloodWait {wait}s — {msg}")
    if cb:
        try:
            await cb(flood_wait=wait)
        except Exception:
            pass
    await asyncio.sleep(wait)


# ── Account ───────────────────────────────────────────────────────────────────

async def check_account(session_name: str) -> dict | None:
    try:
        async with _client(session_name) as c:
            me = await c.get_me()
            return {
                "first_name": me.first_name or "",
                "username": me.username or "",
                "tg_id": me.id,
                "phone": me.phone_number or "",
                "dc_id": me.dc_id,
            }
    except Exception as e:
        log.error(f"check_account '{session_name}': {e}")
        return None


# ── Parsers ───────────────────────────────────────────────────────────────────

async def parse_keywords(
    session_name: str,
    keywords: list[str],
    stop: asyncio.Event,
    cb: ProgressCB | None = None,
) -> list[dict]:
    results: list[dict] = []
    async with _client(session_name) as c:
        for i, kw in enumerate(keywords):
            if stop.is_set():
                break
            if cb:
                try:
                    await cb(i=i, total=len(keywords), current=kw, found=len(results))
                except Exception:
                    pass
            for attempt in range(2):
                try:
                    r = await c.invoke(Search(q=kw, limit=100))
                    for chat in r.chats:
                        uname = getattr(chat, "username", None)
                        if uname:
                            results.append({
                                "id": chat.id,
                                "username": uname,
                                "first_name": getattr(chat, "title", None) or getattr(chat, "first_name", ""),
                                "last_name": None,
                                "is_bot": False,
                            })
                    log.info(f"keyword '{kw}': {len(r.chats)} hits")
                    break
                except FloodWait as e:
                    await _flood_sleep(e, cb, f"keyword '{kw}'")
                except Exception as e:
                    log.error(f"keyword '{kw}': {e}")
                    break
            await asyncio.sleep(0.5)
    return results


async def parse_group_members(
    session_name: str,
    group: str,
    stop: asyncio.Event,
    cb: ProgressCB | None = None,
    filter_bots: bool = True,
    filter_no_username: bool = False,
) -> list[dict]:
    results: list[dict] = []
    async with _client(session_name) as c:
        try:
            chat = await c.get_chat(group)
            offset = 0
            limit = 200
            while not stop.is_set():
                try:
                    chunk = await c.get_chat_members(chat.id, offset=offset, limit=limit)
                    if not chunk:
                        break
                    for m in chunk:
                        u = m.user
                        if not u or u.is_deleted:
                            continue
                        if filter_bots and u.is_bot:
                            continue
                        if filter_no_username and not u.username:
                            continue
                        results.append({
                            "id": u.id,
                            "username": u.username or "",
                            "first_name": u.first_name or "",
                            "last_name": u.last_name or "",
                            "is_bot": u.is_bot,
                        })
                    offset += len(chunk)
                    if cb:
                        try:
                            await cb(offset=offset, found=len(results), group=group)
                        except Exception:
                            pass
                    if len(chunk) < limit:
                        break
                    await asyncio.sleep(1.2)
                except FloodWait as e:
                    await _flood_sleep(e, cb, "get_chat_members")
        except Exception as e:
            log.error(f"parse_group '{group}': {e}")
            raise
    return results


async def parse_channel_admins(
    session_name: str,
    group: str,
    stop: asyncio.Event,
    cb: ProgressCB | None = None,
) -> list[dict]:
    results: list[dict] = []
    async with _client(session_name) as c:
        try:
            async for m in c.get_chat_members(group, filter="administrators"):
                if stop.is_set():
                    break
                u = m.user
                if u and not u.is_deleted:
                    results.append({
                        "id": u.id,
                        "username": u.username or "",
                        "first_name": u.first_name or "",
                        "last_name": u.last_name or "",
                        "is_bot": u.is_bot,
                    })
        except Exception as e:
            log.error(f"parse_admins '{group}': {e}")
            raise
    return results


# ── Inviter ───────────────────────────────────────────────────────────────────

async def invite_users(
    session_name: str,
    target_group: str,
    identifiers: list[str | int],  # usernames or tg_ids
    delay: float,
    stop: asyncio.Event,
    cb: ProgressCB | None = None,
) -> tuple[int, int]:
    invited = failed = 0
    async with _client(session_name) as c:
        for i, ident in enumerate(identifiers):
            if stop.is_set():
                break
            try:
                await c.add_chat_members(target_group, ident)
                invited += 1
                log.info(f"Invited {ident}")
            except FloodWait as e:
                await _flood_sleep(e, cb, f"invite {ident}")
                try:
                    await c.add_chat_members(target_group, ident)
                    invited += 1
                except Exception:
                    failed += 1
            except (
                UserPrivacyRestricted, InputUserDeactivated,
                UserNotMutualContact, PeerFlood,
                UserBannedInChannel, UserChannelsTooMuch,
            ) as e:
                failed += 1
                log.warning(f"Can't invite {ident}: {type(e).__name__}")
            except Exception as e:
                failed += 1
                log.error(f"invite {ident}: {e}")
            if cb:
                try:
                    await cb(i=i + 1, total=len(identifiers), invited=invited, failed=failed)
                except Exception:
                    pass
            await asyncio.sleep(delay)
    return invited, failed


# ── DM sender ─────────────────────────────────────────────────────────────────

async def send_dms(
    session_name: str,
    targets: list[int | str],   # tg_ids or usernames
    text: str,
    media_path: str | None,
    media_type: str | None,
    delay: float,
    stop: asyncio.Event,
    cb: ProgressCB | None = None,
) -> tuple[int, int]:
    sent = failed = 0
    async with _client(session_name) as c:
        for i, target in enumerate(targets):
            if stop.is_set():
                break
            for attempt in range(2):
                try:
                    if media_path and os.path.exists(media_path):
                        if media_type == "photo":
                            await c.send_photo(target, media_path, caption=text)
                        elif media_type == "video":
                            await c.send_video(target, media_path, caption=text)
                        elif media_type == "document":
                            await c.send_document(target, media_path, caption=text)
                        else:
                            await c.send_message(target, text)
                    else:
                        await c.send_message(target, text)
                    sent += 1
                    break
                except FloodWait as e:
                    await _flood_sleep(e, cb, f"DM {target}")
                except Exception as e:
                    if attempt == 0:
                        continue
                    failed += 1
                    log.warning(f"DM {target}: {e}")
                    break
            if cb:
                try:
                    await cb(i=i + 1, total=len(targets), sent=sent, failed=failed)
                except Exception:
                    pass
            await asyncio.sleep(delay)
    return sent, failed


# ── Utilities ─────────────────────────────────────────────────────────────────

def scan_sessions(sessions_dir="sessions") -> list[str]:
    if not os.path.exists(sessions_dir):
        os.makedirs(sessions_dir)
        return []
    return [f[:-8] for f in os.listdir(sessions_dir) if f.endswith(".session")]
