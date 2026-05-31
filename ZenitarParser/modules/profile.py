"""Account profile tools — operate on a single Pyrogram client (one account):
rename, bio, username, avatar, join/leave chat, spam-block check."""
import asyncio
import logging

from pyrogram import Client
from pyrogram.errors import FloodWait, UsernameOccupied, UsernameInvalid

logger = logging.getLogger(__name__)


async def set_name(client: Client, first_name: str, last_name: str = "") -> str:
    await client.update_profile(first_name=first_name, last_name=last_name)
    return "✅ Имя обновлено"


async def set_bio(client: Client, bio: str) -> str:
    await client.update_profile(bio=bio)
    return "✅ Описание (bio) обновлено"


async def set_username(client: Client, username: str) -> str:
    username = username.lstrip("@").strip()
    try:
        await client.set_username(username or None)
        return "✅ Username обновлён" if username else "✅ Username удалён"
    except UsernameOccupied:
        return "❌ Этот username уже занят"
    except UsernameInvalid:
        return "❌ Некорректный username"


async def set_avatar(client: Client, photo_path: str) -> str:
    await client.set_profile_photo(photo=photo_path)
    return "✅ Аватар обновлён"


async def join(client: Client, link: str) -> str:
    try:
        chat = await client.join_chat(link)
        return f"✅ Вступил: {getattr(chat, 'title', link)}"
    except FloodWait as e:
        return f"🌊 FloodWait {e.value}с — попробуйте позже"
    except Exception as e:
        return f"❌ Не удалось вступить: {str(e)[:120]}"


async def leave(client: Client, chat: str) -> str:
    try:
        await client.leave_chat(chat)
        return "✅ Вышел из чата"
    except Exception as e:
        return f"❌ Не удалось выйти: {str(e)[:120]}"


async def check_spam(client: Client) -> str:
    """Ask @SpamBot about the account's current restriction status."""
    try:
        await client.send_message("SpamBot", "/start")
        await asyncio.sleep(2.5)
        async for msg in client.get_chat_history("SpamBot", limit=1):
            text = msg.text or msg.caption or ""
            return f"🤖 @SpamBot:\n\n{text[:600]}" if text else "🤖 @SpamBot не ответил"
        return "🤖 @SpamBot не ответил"
    except FloodWait as e:
        return f"🌊 FloodWait {e.value}с"
    except Exception as e:
        return f"❌ Ошибка проверки: {str(e)[:120]}"
