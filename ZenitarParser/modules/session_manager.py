import json
import logging
import os
from typing import Optional

from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered, UserDeactivated

import config

logger = logging.getLogger(__name__)


def _parse_proxy(proxy: str) -> Optional[dict]:
    """Accepts 'scheme://user:pass@host:port' or 'host:port' (socks5 default)."""
    if not proxy:
        return None
    try:
        scheme = "socks5"
        rest = proxy
        if "://" in proxy:
            scheme, rest = proxy.split("://", 1)
        username = password = None
        if "@" in rest:
            creds, rest = rest.split("@", 1)
            username, password = creds.split(":", 1)
        host, port = rest.rsplit(":", 1)
        d = {"scheme": scheme, "hostname": host, "port": int(port)}
        if username:
            d["username"] = username
            d["password"] = password
        return d
    except Exception as e:
        logger.error("Bad proxy '%s': %s", proxy, e)
        return None


class SessionManager:
    def __init__(self):
        self.clients: dict[str, Client] = {}
        self.proxies: dict[str, str] = {}
        self._load_proxies()

    def _proxy_file(self) -> str:
        return os.path.join(config.SESSIONS_DIR, "proxies.json")

    def _load_proxies(self):
        path = self._proxy_file()
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.proxies = json.load(f)
            except Exception:
                self.proxies = {}

    def _save_proxies(self):
        os.makedirs(config.SESSIONS_DIR, exist_ok=True)
        with open(self._proxy_file(), "w", encoding="utf-8") as f:
            json.dump(self.proxies, f)

    def set_proxy(self, name: str, proxy: str):
        if proxy:
            self.proxies[name] = proxy
        else:
            self.proxies.pop(name, None)
        self._save_proxies()

    async def load_sessions(self):
        os.makedirs(config.SESSIONS_DIR, exist_ok=True)
        names = [f[:-8] for f in os.listdir(config.SESSIONS_DIR) if f.endswith(".session")]
        for name in names:
            await self._start(name)

    async def _start(self, name: str) -> Optional[Client]:
        path = os.path.join(config.SESSIONS_DIR, name)
        proxy = _parse_proxy(self.proxies.get(name, ""))
        client = Client(path, api_id=config.API_ID, api_hash=config.API_HASH, proxy=proxy)
        try:
            await client.start()
            me = await client.get_me()
            self.clients[name] = client
            logger.info("Session %s → @%s (%s)", name, me.username or "—", me.first_name)
            return client
        except (AuthKeyUnregistered, UserDeactivated) as e:
            logger.warning("Session %s invalid: %s", name, e)
        except Exception as e:
            logger.error("Session %s start failed: %s", name, e)
        return None

    async def add_session(self, name: str, proxy: str = "") -> Optional[Client]:
        if proxy:
            self.set_proxy(name, proxy)
        return await self._start(name)

    async def reconnect(self, name: str, proxy: str = None) -> bool:
        """Restart a session, optionally applying a new proxy."""
        client = self.clients.pop(name, None)
        if client:
            try:
                await client.stop()
            except Exception:
                pass
        if proxy is not None:
            self.set_proxy(name, proxy)
        return await self._start(name) is not None

    async def remove_session(self, name: str):
        client = self.clients.pop(name, None)
        if client:
            try:
                await client.stop()
            except Exception:
                pass
        for ext in (".session", ".session-journal"):
            p = os.path.join(config.SESSIONS_DIR, f"{name}{ext}")
            if os.path.exists(p):
                os.remove(p)
        self.set_proxy(name, "")

    def get_client(self, name: str = None) -> Optional[Client]:
        if name:
            c = self.clients.get(name)
            return c if (c and c.is_connected) else None
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
                    "proxy": self.proxies.get(name, ""),
                })
            except Exception:
                result.append({
                    "name": name, "connected": False, "username": "",
                    "first_name": "", "phone": "", "is_premium": False,
                    "proxy": self.proxies.get(name, ""),
                })
        return result

    async def stop_all(self):
        for c in list(self.clients.values()):
            try:
                await c.stop()
            except Exception:
                pass
        self.clients.clear()
