import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database
from modules import blacklist as BL
from utils.export import load_csv
from utils.keyboards import back_kb
from handlers.start import admin

router = Router()


class BlacklistState(StatesGroup):
    wait_add = State()
    wait_csv = State()


def _bl_kb(count: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить вручную", callback_data="bl_add")
    kb.button(text="📥 Импорт из CSV", callback_data="bl_csv")
    if count:
        kb.button(text="🗑 Очистить весь список", callback_data="bl_clear")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(2, 1, 1) if count else kb.adjust(2, 1)
    return kb.as_markup()


@router.callback_query(F.data == "blacklist_menu")
async def cb_blacklist_menu(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.clear()
    idents = await database.blacklist_get_all()
    preview = "\n".join(idents[:15])
    more = f"\n_...и ещё {len(idents) - 15}_" if len(idents) > 15 else ""
    body = (f"```\n{preview}\n```{more}" if idents else "_Список пуст_")
    await cb.message.edit_text(
        f"🚫 *Чёрный список* ({len(idents)} записей)\n\n"
        "Пользователи из списка пропускаются при инвайтинге и рассылке.\n\n"
        + body,
        reply_markup=_bl_kb(len(idents)), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data == "bl_add")
async def cb_bl_add(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(BlacklistState.wait_add)
    await cb.message.edit_text(
        "🚫 Введите username-ы или ID для добавления.\n"
        "Можно несколько — через запятую или с новой строки.\n\n"
        "Примеры: `@username1, 123456789, username2`",
        parse_mode="Markdown", reply_markup=back_kb("blacklist_menu"),
    )
    await cb.answer()


@router.message(BlacklistState.wait_add, F.text)
async def handle_bl_add(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    raw = message.text.replace(",", "\n").replace(";", "\n")
    added, failed = 0, []
    for line in raw.splitlines():
        ident = BL.parse_ident(line.strip())
        if ident:
            await database.blacklist_add(ident)
            added += 1
        elif line.strip():
            failed.append(line.strip())
    await state.clear()
    text = f"✅ Добавлено в чёрный список: {added}"
    if failed:
        text += f"\n❌ Не распознано: {', '.join(failed[:5])}"
    await message.answer(text, reply_markup=back_kb("blacklist_menu"))


@router.callback_query(F.data == "bl_csv")
async def cb_bl_csv(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(BlacklistState.wait_csv)
    await cb.message.edit_text(
        "📥 Отправьте CSV с пользователями для чёрного списка.\n"
        "Нужны колонки `id` и/или `username`.",
        parse_mode="Markdown", reply_markup=back_kb("blacklist_menu"),
    )
    await cb.answer()


@router.message(BlacklistState.wait_csv)
async def handle_bl_csv(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    if not (message.document and message.document.file_name.endswith(".csv")):
        await message.answer("❌ Отправьте CSV файл.")
        return
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    path = os.path.join(config.UPLOADS_DIR, f"bl_{message.from_user.id}.csv")
    await message.bot.download(message.document, path)
    try:
        users = await load_csv(path)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode=None)
        await state.clear()
        return
    added = 0
    for u in users:
        for ident in BL.idents_for_user(u):
            await database.blacklist_add(ident)
            added += 1
    await state.clear()
    await message.answer(f"✅ Добавлено записей: {added}", reply_markup=back_kb("blacklist_menu"))


@router.callback_query(F.data == "bl_clear")
async def cb_bl_clear(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    await database.blacklist_clear()
    await cb.answer("Чёрный список очищен", show_alert=True)
    await cb.message.edit_text(
        "🚫 *Чёрный список* (0 записей)\n\n_Список пуст_",
        reply_markup=_bl_kb(0), parse_mode="Markdown",
    )
