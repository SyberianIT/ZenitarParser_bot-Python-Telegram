import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from modules.session_manager import SessionManager, _parse_proxy
from modules import profile as PR
from handlers.start import admin

router = Router()


class ProfileState(StatesGroup):
    wait_name = State()
    wait_bio = State()
    wait_username = State()
    wait_avatar = State()
    wait_join = State()
    wait_leave = State()
    wait_proxy = State()


def _profile_kb(name: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Имя", callback_data="prof_name")
    kb.button(text="📝 Bio", callback_data="prof_bio")
    kb.button(text="🔗 Username", callback_data="prof_username")
    kb.button(text="🖼 Аватар", callback_data="prof_avatar")
    kb.button(text="➕ Вступить в чат", callback_data="prof_join")
    kb.button(text="➖ Выйти из чата", callback_data="prof_leave")
    kb.button(text="🌐 Изменить прокси", callback_data="prof_proxy")
    kb.button(text="🛡 Проверить спам-статус", callback_data="prof_spam")
    kb.button(text="◀️ Назад", callback_data=f"acv_{name}")
    kb.adjust(2, 2, 2, 1, 1, 1)
    return kb.as_markup()


async def _client_or_warn(cb_or_msg, name: str, session_manager: SessionManager):
    client = session_manager.get_client(name)
    if not client:
        target = cb_or_msg.message if isinstance(cb_or_msg, CallbackQuery) else cb_or_msg
        await target.answer("❌ Аккаунт не подключён.")
        return None
    return client


@router.callback_query(F.data.startswith("prof_open_"))
async def cb_profile_open(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    name = cb.data[len("prof_open_"):]
    await state.set_data({"prof_account": name})
    await cb.message.edit_text(
        f"🛠 *Профильные инструменты*\n`{name}`\n\n"
        "Изменяйте профиль аккаунта, управляйте прокси и членством в чатах, "
        "проверяйте спам-блок.",
        reply_markup=_profile_kb(name), parse_mode="Markdown",
    )
    await cb.answer()


# ── prompts ──────────────────────────────────────────────────────────────────

_PROMPTS = {
    "prof_name":     (ProfileState.wait_name,     "✏️ Введите имя (можно `Имя Фамилия`):"),
    "prof_bio":      (ProfileState.wait_bio,      "📝 Введите новое описание (bio):"),
    "prof_username": (ProfileState.wait_username, "🔗 Введите новый username (без @), или `-` чтобы удалить:"),
    "prof_avatar":   (ProfileState.wait_avatar,   "🖼 Отправьте фото для аватара:"),
    "prof_join":     (ProfileState.wait_join,     "➕ Ссылка/@username чата для вступления:"),
    "prof_leave":    (ProfileState.wait_leave,    "➖ Ссылка/@username чата для выхода:"),
    "prof_proxy":    (ProfileState.wait_proxy,    "🌐 Прокси `socks5://user:pass@host:port` или `host:port`, или `-` чтобы убрать:"),
}


@router.callback_query(F.data.in_(set(_PROMPTS)))
async def cb_profile_action(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    st, prompt = _PROMPTS[cb.data]
    await state.set_state(st)
    await cb.message.answer(prompt, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "prof_spam")
async def cb_profile_spam(cb: CallbackQuery, state: FSMContext, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    data = await state.get_data()
    name = data.get("prof_account")
    client = session_manager.get_client(name) if name else None
    if not client:
        await cb.answer("❌ Аккаунт не подключён.", show_alert=True)
        return
    await cb.answer("Проверяю...")
    result = await PR.check_spam(client)
    await cb.message.answer(result, parse_mode=None)


# ── input handlers ─────────────────────────────────────────────────────────────

def _back_kb(name: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ К профилю", callback_data=f"prof_open_{name}")
    return kb.as_markup()


@router.message(ProfileState.wait_name, F.text)
async def do_name(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    client = await _client_or_warn(message, name, session_manager)
    if not client: return await state.clear()
    parts = message.text.strip().split(maxsplit=1)
    first, last = parts[0], (parts[1] if len(parts) > 1 else "")
    res = await PR.set_name(client, first, last)
    await state.clear()
    await message.answer(res, reply_markup=_back_kb(name))


@router.message(ProfileState.wait_bio, F.text)
async def do_bio(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    client = await _client_or_warn(message, name, session_manager)
    if not client: return await state.clear()
    res = await PR.set_bio(client, message.text.strip())
    await state.clear()
    await message.answer(res, reply_markup=_back_kb(name))


@router.message(ProfileState.wait_username, F.text)
async def do_username(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    client = await _client_or_warn(message, name, session_manager)
    if not client: return await state.clear()
    val = message.text.strip()
    res = await PR.set_username(client, "" if val == "-" else val)
    await state.clear()
    await message.answer(res, reply_markup=_back_kb(name))


@router.message(ProfileState.wait_avatar, F.photo)
async def do_avatar(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    client = await _client_or_warn(message, name, session_manager)
    if not client: return await state.clear()
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    path = os.path.join(config.UPLOADS_DIR, f"avatar_{name}.jpg")
    await message.bot.download(message.photo[-1], path)
    try:
        res = await PR.set_avatar(client, path)
    except Exception as e:
        res = f"❌ Ошибка: {str(e)[:120]}"
    await state.clear()
    await message.answer(res, reply_markup=_back_kb(name))


@router.message(ProfileState.wait_avatar)
async def do_avatar_wrong(message: Message):
    if not admin(message.from_user.id): return
    await message.answer("❌ Отправьте именно фото (изображение).")


@router.message(ProfileState.wait_join, F.text)
async def do_join(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    client = await _client_or_warn(message, name, session_manager)
    if not client: return await state.clear()
    res = await PR.join(client, message.text.strip())
    await state.clear()
    await message.answer(res, reply_markup=_back_kb(name), parse_mode=None)


@router.message(ProfileState.wait_leave, F.text)
async def do_leave(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    client = await _client_or_warn(message, name, session_manager)
    if not client: return await state.clear()
    res = await PR.leave(client, message.text.strip())
    await state.clear()
    await message.answer(res, reply_markup=_back_kb(name), parse_mode=None)


@router.message(ProfileState.wait_proxy, F.text)
async def do_proxy(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    data = await state.get_data(); name = data.get("prof_account")
    await state.clear()
    proxy = message.text.strip()
    if proxy == "-":
        proxy = ""
    elif proxy and _parse_proxy(proxy) is None:
        await message.answer("❌ Не удалось разобрать прокси. Формат: `socks5://user:pass@host:port`", parse_mode="Markdown")
        return
    await message.answer("⏳ Переподключаю аккаунт с новым прокси...")
    ok = await session_manager.reconnect(name, proxy)
    await message.answer(
        "✅ Прокси применён, аккаунт переподключён." if ok
        else "❌ Не удалось переподключиться. Проверьте прокси.",
        reply_markup=_back_kb(name),
    )
