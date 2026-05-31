import os
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

import config
import database
from modules.session_manager import SessionManager
from modules.account_pool import AccountPool
from utils.keyboards import back_kb
from handlers.start import admin

router = Router()

# Live Pyrogram clients during auth — keyed by admin user_id: (client, created_ts)
_pending: dict[int, tuple] = {}
_PENDING_TTL = 600  # seconds


class AccountState(StatesGroup):
    wait_phone = State()
    wait_code = State()
    wait_2fa = State()
    wait_proxy = State()


async def _cleanup_pending(user_id: int):
    entry = _pending.pop(user_id, None)
    if entry:
        client, _ = entry
        try:
            await client.disconnect()
        except Exception:
            pass


async def _gc_pending():
    now = time.time()
    for uid in list(_pending.keys()):
        _, ts = _pending[uid]
        if now - ts > _PENDING_TTL:
            await _cleanup_pending(uid)


def _accounts_kb(sessions: list, health: dict):
    kb = InlineKeyboardBuilder()
    for s in sessions:
        acc = health.get(s["name"], {})
        if acc.get("status") == "banned":
            icon = "🚫"
        elif acc.get("status") == "flood" or (acc.get("flood_until", 0) > time.time()):
            icon = "🌊"
        elif s.get("connected"):
            icon = "✅"
        else:
            icon = "❌"
        uname = s.get("username") or s.get("first_name") or s.get("name", "?")
        label = f"{icon} @{uname}" if s.get("username") else f"{icon} {uname}"
        kb.button(text=label, callback_data=f"acv_{s['name']}")
    kb.button(text="➕ Добавить аккаунт", callback_data="acc_add")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "accounts_menu")
async def cb_accounts_menu(cb: CallbackQuery, state: FSMContext, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    await state.clear()
    sessions = await session_manager.status()
    health = {a["name"]: a for a in await database.get_accounts()}
    await cb.message.edit_text(
        f"👥 *Аккаунты* ({len(sessions)})\n\n"
        "✅ активен · 🌊 кулдаун · 🚫 бан · ❌ отключён\n\n"
        "Аккаунты используются для парсинга, инвайтинга и рассылки.\n"
        "Добавьте хотя бы один.",
        reply_markup=_accounts_kb(sessions, health), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("acv_"))
async def cb_acc_view(cb: CallbackQuery, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    name = cb.data[4:]
    sessions = await session_manager.status()
    s = next((x for x in sessions if x["name"] == name), None)
    if not s:
        await cb.answer("Не найдено", show_alert=True)
        return
    acc = await database.get_account(name) or {}

    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Удалить аккаунт", callback_data=f"acd_{name}")
    kb.button(text="◀️ Назад", callback_data="accounts_menu")
    kb.adjust(1)

    uname = f"@{s['username']}" if s.get("username") else "—"
    proxy = s.get("proxy") or "—"
    await cb.message.edit_text(
        f"👤 *{s.get('first_name', '')} {uname}*\n\n"
        f"📱 Телефон: `{s.get('phone', '—') or '—'}`\n"
        f"💎 Premium: {'Да' if s.get('is_premium') else 'Нет'}\n"
        f"🌐 Прокси: `{proxy}`\n"
        f"🔗 Статус: {'✅ Активен' if s.get('connected') else '❌ Неактивен'}\n"
        f"📨 Инвайтов сегодня: {acc.get('invites_today', 0)}/{config.MAX_INVITES_PER_DAY}\n"
        f"📢 Сообщений сегодня: {acc.get('messages_today', 0)}/{config.MAX_MESSAGES_PER_DAY}",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("acd_"))
async def cb_acc_delete(cb: CallbackQuery, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    name = cb.data[4:]
    await session_manager.remove_session(name)
    await database.delete_account(name)
    await cb.answer("Аккаунт удалён")
    sessions = await session_manager.status()
    health = {a["name"]: a for a in await database.get_accounts()}
    await cb.message.edit_text(
        f"👥 *Аккаунты* ({len(sessions)})",
        reply_markup=_accounts_kb(sessions, health), parse_mode="Markdown",
    )


@router.callback_query(F.data == "acc_add")
async def cb_acc_add(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await _gc_pending()
    await state.set_state(AccountState.wait_proxy)
    await cb.message.edit_text(
        "🌐 *Прокси (опционально)*\n\n"
        "Отправьте прокси в формате\n"
        "`socks5://user:pass@host:port` или `host:port`\n\n"
        "Или напишите `нет` чтобы без прокси.",
        parse_mode="Markdown", reply_markup=back_kb("accounts_menu"),
    )
    await cb.answer()


@router.message(AccountState.wait_proxy, F.text)
async def handle_proxy(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    proxy = message.text.strip()
    if proxy.lower() in ("нет", "no", "-", "skip"):
        proxy = ""
    await state.update_data(proxy=proxy)
    await state.set_state(AccountState.wait_phone)
    await message.answer(
        "📱 *Добавление аккаунта*\n\n"
        "Введите номер телефона с кодом страны:\n"
        "Пример: `+79001234567`",
        parse_mode="Markdown",
    )


@router.message(AccountState.wait_phone, F.text)
async def handle_phone(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Введите номер с `+` (пример: `+79001234567`)", parse_mode="Markdown")
        return

    data = await state.get_data()
    proxy = data.get("proxy", "")
    session_name = phone.replace("+", "").replace(" ", "")
    os.makedirs(config.SESSIONS_DIR, exist_ok=True)
    session_path = os.path.join(config.SESSIONS_DIR, session_name)

    from modules.session_manager import _parse_proxy
    client = Client(
        session_path, api_id=config.API_ID, api_hash=config.API_HASH,
        no_updates=True, proxy=_parse_proxy(proxy),
    )
    try:
        await client.connect()
        sent = await client.send_code(phone)
        _pending[message.from_user.id] = (client, time.time())
        await state.update_data(phone=phone, session_name=session_name, pch=sent.phone_code_hash)
        await state.set_state(AccountState.wait_code)
        await message.answer(
            "📨 Код отправлен в Telegram.\n\n"
            "Введите код *с пробелами или дефисами* (например: `1 2 3 4 5`):",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке кода: `{e}`", parse_mode="Markdown")
        try:
            await client.disconnect()
        except Exception:
            pass
        await state.clear()


@router.message(AccountState.wait_code, F.text)
async def handle_code(message: Message, state: FSMContext,
                      session_manager: SessionManager, account_pool: AccountPool):
    if not admin(message.from_user.id): return
    code = message.text.strip().replace(" ", "").replace("-", "")
    data = await state.get_data()
    entry = _pending.get(message.from_user.id)

    if not entry:
        await message.answer("❌ Сессия истекла. Начните заново — /start")
        await state.clear()
        return
    client, _ = entry

    try:
        await client.sign_in(data["phone"], data["pch"], code)
        await client.disconnect()
        _pending.pop(message.from_user.id, None)
        await session_manager.add_session(data["session_name"], data.get("proxy", ""))
        await database.upsert_account(data["session_name"], data.get("proxy", ""))
        await account_pool.sync()
        await state.clear()
        await message.answer("✅ Аккаунт успешно добавлен!", reply_markup=back_kb("accounts_menu"))
    except SessionPasswordNeeded:
        await state.set_state(AccountState.wait_2fa)
        await message.answer("🔐 Включена 2FA. Введите облачный пароль:")
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await message.answer("❌ Код неверный или просрочен. Начните заново — /start")
        await _cleanup_pending(message.from_user.id)
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")
        await _cleanup_pending(message.from_user.id)
        await state.clear()


@router.message(AccountState.wait_2fa, F.text)
async def handle_2fa(message: Message, state: FSMContext,
                     session_manager: SessionManager, account_pool: AccountPool):
    if not admin(message.from_user.id): return
    data = await state.get_data()
    entry = _pending.get(message.from_user.id)

    if not entry:
        await message.answer("❌ Сессия истекла. Начните заново — /start")
        await state.clear()
        return
    client, _ = entry

    try:
        await client.check_password(message.text.strip())
        await client.disconnect()
        _pending.pop(message.from_user.id, None)
        await session_manager.add_session(data["session_name"], data.get("proxy", ""))
        await database.upsert_account(data["session_name"], data.get("proxy", ""))
        await account_pool.sync()
        await state.clear()
        await message.answer("✅ Аккаунт с 2FA успешно добавлен!", reply_markup=back_kb("accounts_menu"))
    except Exception as e:
        await message.answer(f"❌ Неверный пароль: `{e}`\nПопробуйте ещё раз:", parse_mode="Markdown")
