import os
import logging
from typing import Optional

from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered, UserDeactivated

import config

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self):
        self.clients: dict[str, Client] = {}

    async def load_sessions(self):
        os.makedirs(config.SESSIONS_DIR, exist_ok=True)
        names = [f[:-8] for f in os.listdir(config.SESSIONS_DIR) if f.endswith(".session")]
        for name in names:
            await self._start(name)

    async def _start(self, name: str) -> Optional[Client]:
        path = os.path.join(config.SESSIONS_DIR, name)
        client = Client(path, api_id=config.API_ID, api_hash=config.API_HASH)
        try:
            await client.start()
            me = await client.get_me()
            self.clients[name] = client
            logger.info("Session %s → %s", name, me.username or me.first_name)
            return client
        except (AuthKeyUnregistered, UserDeactivated) as e:
            logger.warning("Session %s invalid: %s", name, e)
        except Exception as e:
            logger.error("Session %s start failed: %s", name, e)
        return None

    async def add_session(self, name: str) -> Optional[Client]:
        return await self._start(name)

    async def remove_session(self, name: str):
        client = self.clients.pop(name, None)
        if client:
            try:
                await client.stop()
            except Exception:
                pass
        path = os.path.join(config.SESSIONS_DIR, f"{name}.session")
        if os.path.exists(path):
            os.remove(path)

    def get_client(self, name: str = None) -> Optional[Client]:
        if name:
            return self.clients.get(name)
        for c in self.clients.values():
            if c.is_connected:
                return c
        return None

    def all_clients(self) -> list[Client]:
        return [c for c in self.clients.values() if c.is_connected]

    async def status(self) -> list[dict]:
        result = []
        for name, client in self.clients.items():
            try:
                me = await client.get_me()
                result.append({
                    "name": name,
                    "username": me.username or "",
                    "first_name": me.first_name or "",
                    "phone": me.phone_number or "",
                    "is_premium": bool(getattr(me, "is_premium", False)),
                    "connected": client.is_connected,
                })
            except Exception:
                result.append({
                    "name": name, "connected": False,
                    "username": "", "first_name": "", "phone": "", "is_premium": False,
                })
        return result

    async def stop_all(self):
        for c in list(self.clients.values()):
            try:
                await c.stop()
            except Exception:
                pass
        self.clients.clear()
