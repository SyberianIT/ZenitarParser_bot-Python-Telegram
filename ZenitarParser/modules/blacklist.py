import logging

import database

logger = logging.getLogger(__name__)


def idents_for_user(user: dict) -> list[str]:
    result = []
    uid = user.get("id")
    if uid:
        result.append(f"id:{uid}")
    uname = user.get("username")
    if uname:
        result.append(f"un:{str(uname).lstrip('@').lower()}")
    return result


async def is_blacklisted(user: dict) -> bool:
    try:
        for ident in idents_for_user(user):
            if await database.blacklist_check(ident):
                return True
    except Exception as e:
        logger.warning("Blacklist check failed: %s", e)
    return False


async def add_user(user: dict):
    for ident in idents_for_user(user):
        await database.blacklist_add(ident)


async def add_ident(ident: str):
    await database.blacklist_add(ident)


async def remove_ident(ident: str):
    await database.blacklist_remove(ident)


def parse_ident(text: str) -> str | None:
    """Convert 'id:123', '@username', 'username', or '123456' → normalised ident."""
    t = text.strip().lstrip("@")
    if not t:
        return None
    if t.lstrip("-").isdigit():
        return f"id:{t}"
    return f"un:{t.lower()}"
