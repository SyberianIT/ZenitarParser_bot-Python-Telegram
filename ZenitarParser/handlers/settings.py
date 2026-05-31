from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database
from utils.keyboards import back_kb
from handlers.start import admin

router = Router()


class SettingsState(StatesGroup):
    wait_bot_token = State()
    wait_delay = State()


def _bots_kb(bots: list):
    kb = InlineKeyboardBuilder()
    for b in bots:
        icon = "✅" if b["status"] == "active" else "❌"
        kb.button(text=f"{icon} @{b['username']}", callback_data=f"bview_{b['id']}")
    kb.button(text="➕ Добавить бота", callback_data="bot_add")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


# ── Bots ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bots_menu")
async def cb_bots_menu(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    bots = await database.get_all_bot_tokens()
    await cb.message.edit_text(
        f"🤖 *Боты для рассылки* ({len(bots)})\n\n"
        "Боты используются в рассыльщике (режим «через бота»).\n"
        "Пользователь должен предварительно запустить бота.",
        reply_markup=_bots_kb(bots), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data == "bot_add")
async def cb_bot_add(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(SettingsState.wait_bot_token)
    await cb.message.edit_text(
        "🤖 Введите токен бота от @BotFather:",
        reply_markup=back_kb("bots_menu"),
    )
    await cb.answer()


@router.message(SettingsState.wait_bot_token)
async def handle_bot_token(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    token = message.text.strip()
    try:
        b = Bot(token=token)
        me = await b.get_me()
        await b.session.close()
        await database.add_bot_token(token, me.username)
        await state.clear()
        await message.answer(f"✅ Бот @{me.username} добавлен!", reply_markup=back_kb("bots_menu"))
    except Exception as e:
        await message.answer(f"❌ Неверный токен: `{e}`", parse_mode="Markdown")
        await state.clear()


@router.callback_query(F.data.startswith("bview_"))
async def cb_bot_view(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    bot_id = int(cb.data[6:])
    bots = await database.get_all_bot_tokens()
    b = next((x for x in bots if x["id"] == bot_id), None)
    if not b:
        await cb.answer("Не найдено", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Удалить бота", callback_data=f"bdel_{bot_id}")
    kb.button(text="◀️ Назад", callback_data="bots_menu")
    kb.adjust(1)

    await cb.message.edit_text(
        f"🤖 *@{b['username']}*\n\n"
        f"📅 Добавлен: {b['created_at']}\n"
        f"🔗 Статус: {'✅ Активен' if b['status'] == 'active' else '❌ Отключён'}",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("bdel_"))
async def cb_bot_delete(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    bot_id = int(cb.data[5:])
    await database.delete_bot_token(bot_id)
    await cb.answer("Бот удалён")
    bots = await database.get_all_bot_tokens()
    await cb.message.edit_text(
        f"🤖 *Боты для рассылки* ({len(bots)})",
        reply_markup=_bots_kb(bots), parse_mode="Markdown",
    )


# ── Settings ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_menu")
async def cb_settings_menu(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    delay_invite = await database.get_setting("delay_invite", "5-15")
    delay_send = await database.get_setting("delay_send", "3-10")

    kb = InlineKeyboardBuilder()
    kb.button(text=f"⏱ Инвайтинг: {delay_invite} сек", callback_data="set_delay_invite")
    kb.button(text=f"⏱ Рассылка: {delay_send} сек", callback_data="set_delay_send")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)

    await cb.message.edit_text(
        f"⚙️ *Настройки*\n\n"
        f"⏱ Задержка инвайтинга: `{delay_invite}` сек\n"
        f"⏱ Задержка рассылки: `{delay_send}` сек\n\n"
        "_Формат: мин-макс, например `5-15`_",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.in_({"set_delay_invite", "set_delay_send"}))
async def cb_set_delay(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    key = "delay_invite" if cb.data == "set_delay_invite" else "delay_send"
    await state.set_state(SettingsState.wait_delay)
    await state.update_data(delay_key=key)
    label = "инвайтинга" if key == "delay_invite" else "рассылки"
    await cb.message.edit_text(
        f"Введите задержку {label} в формате `мин-макс`\nПример: `5-15`",
        parse_mode="Markdown", reply_markup=back_kb("settings_menu"),
    )
    await cb.answer()


@router.message(SettingsState.wait_delay)
async def handle_delay(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    val = message.text.strip()
    try:
        parts = val.split("-")
        assert len(parts) == 2
        float(parts[0])
        float(parts[1])
    except Exception:
        await message.answer("❌ Неверный формат. Пример: `5-15`", parse_mode="Markdown")
        return

    data = await state.get_data()
    await database.set_setting(data["delay_key"], val)
    await state.clear()
    await message.answer(f"✅ Сохранено: `{val}` сек", parse_mode="Markdown", reply_markup=back_kb("settings_menu"))
