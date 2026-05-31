import logging
import time
from typing import Optional

from pyrogram import Client

import config
import database
from modules.session_manager import SessionManager

logger = logging.getLogger(__name__)


class AccountPool:
    """Rotates work across multiple Telegram accounts while respecting
    per-account daily limits and flood cooldowns — the core anti-ban engine."""

    def __init__(self, session_manager: SessionManager):
        self.sm = session_manager
        self._rr = 0  # round-robin pointer

    async def sync(self):
        """Ensure every loaded session has a row in the accounts table and
        reset daily counters on day change."""
        for name in self.sm.clients:
            await database.upsert_account(name)
        await database.reset_daily_if_needed()

    async def _is_available(self, acc: dict, action: str) -> bool:
        if acc["status"] in ("banned", "disabled"):
            return False
        if acc["flood_until"] and acc["flood_until"] > time.time():
            return False
        if action == "invite" and acc["invites_today"] >= config.MAX_INVITES_PER_DAY:
            return False
        if action == "send" and acc["messages_today"] >= config.MAX_MESSAGES_PER_DAY:
            return False
        return self.sm.get_client(acc["name"]) is not None

    async def available(self, action: str) -> list[dict]:
        await database.reset_daily_if_needed()
        accounts = await database.get_accounts()
        return [a for a in accounts if await self._is_available(a, action)]

    async def acquire(self, action: str) -> Optional[tuple[str, Client]]:
        """Round-robin pick of the next healthy account for an action."""
        accounts = await self.available(action)
        if not accounts:
            return None
        acc = accounts[self._rr % len(accounts)]
        self._rr += 1
        client = self.sm.get_client(acc["name"])
        return (acc["name"], client) if client else None

    async def report_success(self, name: str, action: str):
        acc = await database.get_account(name)
        if not acc:
            return
        if action == "invite":
            await database.update_account(name, invites_today=acc["invites_today"] + 1)
        elif action == "send":
            await database.update_account(name, messages_today=acc["messages_today"] + 1)

    async def mark_flood(self, name: str, seconds: int = None):
        seconds = seconds or config.FLOOD_COOLDOWN
        until = int(time.time()) + seconds
        await database.update_account(name, status="flood", flood_until=until)
        logger.warning("Account %s on flood cooldown for %ds", name, seconds)

    async def mark_banned(self, name: str):
        await database.update_account(name, status="banned")
        logger.warning("Account %s marked banned", name)

    async def count_available(self, action: str) -> int:
        return len(await self.available(action))
