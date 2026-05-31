import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

import config
from modules.session_manager import SessionManager
from utils.keyboards import back_kb
from handlers.start import admin

router = Router()

# Live Pyrogram clients during auth — keyed by admin user_id
_pending: dict[int, Client] = {}


class AccountState(StatesGroup):
    wait_phone = State()
    wait_code = State()
    wait_2fa = State()


def _accounts_kb(sessions: list):
    kb = InlineKeyboardBuilder()
    for s in sessions:
        icon = "✅" if s.get("connected") else "❌"
        uname = s.get("username") or s.get("first_name") or s.get("name", "?")
        label = f"{icon} @{uname}" if s.get("username") else f"{icon} {uname}"
        kb.button(text=label, callback_data=f"acv_{s['name']}")
    kb.button(text="➕ Добавить аккаунт", callback_data="acc_add")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "accounts_menu")
async def cb_accounts_menu(cb: CallbackQuery, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    sessions = await session_manager.status()
    await cb.message.edit_text(
        f"👥 *Аккаунты* ({len(sessions)})\n\n"
        "Аккаунты используются для парсинга, инвайтинга и рассылки.\n"
        "Добавьте хотя бы один аккаунт.",
        reply_markup=_accounts_kb(sessions), parse_mode="Markdown",
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

    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Удалить аккаунт", callback_data=f"acd_{name}")
    kb.button(text="◀️ Назад", callback_data="accounts_menu")
    kb.adjust(1)

    uname = f"@{s['username']}" if s.get("username") else "—"
    await cb.message.edit_text(
        f"👤 *{s.get('first_name', '')} {uname}*\n\n"
        f"📱 Телефон: `{s.get('phone', '—')}`\n"
        f"💎 Premium: {'Да' if s.get('is_premium') else 'Нет'}\n"
        f"🔗 Статус: {'✅ Активен' if s.get('connected') else '❌ Неактивен'}",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("acd_"))
async def cb_acc_delete(cb: CallbackQuery, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    name = cb.data[4:]
    await session_manager.remove_session(name)
    await cb.answer(f"Аккаунт удалён")
    sessions = await session_manager.status()
    await cb.message.edit_text(
        f"👥 *Аккаунты* ({len(sessions)})",
        reply_markup=_accounts_kb(sessions), parse_mode="Markdown",
    )


@router.callback_query(F.data == "acc_add")
async def cb_acc_add(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(AccountState.wait_phone)
    await cb.message.edit_text(
        "📱 *Добавление аккаунта*\n\n"
        "Введите номер телефона с кодом страны:\n"
        "Пример: `+79001234567`",
        parse_mode="Markdown", reply_markup=back_kb("accounts_menu"),
    )
    await cb.answer()


@router.message(AccountState.wait_phone)
async def handle_phone(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Введите номер с `+` (пример: `+79001234567`)", parse_mode="Markdown")
        return

    session_name = phone.replace("+", "").replace(" ", "")
    os.makedirs(config.SESSIONS_DIR, exist_ok=True)
    session_path = os.path.join(config.SESSIONS_DIR, session_name)

    client = Client(session_path, api_id=config.API_ID, api_hash=config.API_HASH, no_updates=True)
    try:
        await client.connect()
        sent = await client.send_code(phone)
        _pending[message.from_user.id] = client
        await state.update_data(phone=phone, session_name=session_name, pch=sent.phone_code_hash)
        await state.set_state(AccountState.wait_code)
        await message.answer(
            "📨 Код отправлен в Telegram.\n\n"
            "Введите код *без пробелов* (например: `12345`):",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке кода: `{e}`", parse_mode="Markdown")
        try:
            await client.disconnect()
        except Exception:
            pass
        await state.clear()


@router.message(AccountState.wait_code)
async def handle_code(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    client = _pending.get(message.from_user.id)

    if not client:
        await message.answer("❌ Сессия истекла. Начните заново — /start")
        await state.clear()
        return

    try:
        await client.sign_in(data["phone"], data["pch"], code)
        await client.disconnect()
        _pending.pop(message.from_user.id, None)
        await session_manager.add_session(data["session_name"])
        await state.clear()
        await message.answer("✅ Аккаунт успешно добавлен!", reply_markup=back_kb("accounts_menu"))
    except SessionPasswordNeeded:
        await state.set_state(AccountState.wait_2fa)
        await message.answer(
            "🔐 На аккаунте включена двухфакторная аутентификация.\n\n"
            "Введите облачный пароль:"
        )
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await message.answer("❌ Код неверный или просрочен. Начните заново — /start")
        try:
            await client.disconnect()
        except Exception:
            pass
        _pending.pop(message.from_user.id, None)
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")
        try:
            await client.disconnect()
        except Exception:
            pass
        _pending.pop(message.from_user.id, None)
        await state.clear()


@router.message(AccountState.wait_2fa)
async def handle_2fa(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data()
    client = _pending.get(message.from_user.id)

    if not client:
        await message.answer("❌ Сессия истекла. Начните заново — /start")
        await state.clear()
        return

    try:
        await client.check_password(message.text.strip())
        await client.disconnect()
        _pending.pop(message.from_user.id, None)
        await session_manager.add_session(data["session_name"])
        await state.clear()
        await message.answer("✅ Аккаунт с 2FA успешно добавлен!", reply_markup=back_kb("accounts_menu"))
    except Exception as e:
        await message.answer(f"❌ Неверный пароль: `{e}`\nПопробуйте ещё раз:", parse_mode="Markdown")
