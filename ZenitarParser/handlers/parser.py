import asyncio
import os
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from modules.session_manager import SessionManager
from modules import parser as P
from utils.keyboards import parser_menu, member_filter_menu, stop_kb, back_kb
from utils.export import to_csv, list_exports
from utils import tasks
from handlers.start import admin

router = Router()


class ParserState(StatesGroup):
    wait_group = State()
    wait_filter_group = State()
    wait_keywords = State()
    wait_post = State()


# ── Menu ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parser_menu")
async def cb_parser_menu(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    await cb.message.edit_text(
        "🔍 *Парсер*\n\nВыберите тип парсинга:",
        reply_markup=parser_menu(), parse_mode="Markdown",
    )
    await cb.answer()


# ── Members ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parse_members")
async def cb_parse_members(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(ParserState.wait_filter_group)
    await cb.message.edit_text(
        "👥 *Парсинг участников*\n\nВведите @username или ссылку на группу/канал:",
        parse_mode="Markdown", reply_markup=back_kb("parser_menu"),
    )
    await cb.answer()


@router.message(ParserState.wait_filter_group)
async def handle_members_group(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.update_data(group=message.text.strip())
    await state.set_state(ParserState.wait_group)
    await message.answer("Выберите фильтр участников:", reply_markup=member_filter_menu())


@router.callback_query(F.data.startswith("mf_"))
async def cb_member_filter(cb: CallbackQuery, state: FSMContext, session_manager: SessionManager):
    if not admin(cb.from_user.id): return
    ftype = cb.data[3:]  # all / recent / admins / bots
    data = await state.get_data()
    group = data.get("group", "")
    await state.clear()

    client = session_manager.get_client()
    if not client:
        await cb.message.edit_text("❌ Нет активных аккаунтов.", reply_markup=back_kb("parser_menu"))
        await cb.answer()
        return

    stop = tasks.new_task()
    await cb.message.edit_text("⏳ Запускаю парсинг участников...", reply_markup=stop_kb(id(stop)))
    await cb.answer()

    async def prog(cur, tot, text):
        try:
            await cb.message.edit_text(text, reply_markup=stop_kb(id(stop)))
        except Exception:
            pass

    try:
        users = await P.members(client, group, filter_type=ftype, on_progress=prog, stop=stop)
        await _finish(cb.message, users, f"members_{ftype}", stop, send_to=cb.from_user.id)
    finally:
        tasks.done_task(stop)


# ── Active users ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parse_active")
async def cb_parse_active(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(ParserState.wait_group)
    await state.update_data(parse_type="active")
    await cb.message.edit_text(
        "✍️ *Активные пользователи*\n\n"
        "Введите @username или ссылку на группу/канал:",
        parse_mode="Markdown", reply_markup=back_kb("parser_menu"),
    )
    await cb.answer()


@router.message(ParserState.wait_group)
async def handle_group(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return

    data = await state.get_data()
    parse_type = data.get("parse_type", "active")
    group = message.text.strip()
    await state.clear()

    client = session_manager.get_client()
    if not client:
        await message.answer("❌ Нет активных аккаунтов. Добавьте в разделе 👥 Аккаунты.")
        return

    stop = tasks.new_task()
    msg = await message.answer("⏳ Запускаю...", reply_markup=stop_kb(id(stop)))

    async def prog(cur, tot, text):
        try:
            await msg.edit_text(text, reply_markup=stop_kb(id(stop)))
        except Exception:
            pass

    try:
        users = await P.active_users(client, group, on_progress=prog, stop=stop)
        await _finish(msg, users, parse_type, stop, orig_chat=message.chat.id)
    finally:
        tasks.done_task(stop)


# ── Keywords ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parse_keyword")
async def cb_parse_keyword(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(ParserState.wait_keywords)
    await cb.message.edit_text(
        "🔎 *Поиск по ключевым словам*\n\n"
        "Введите ключевые слова — каждое с новой строки:",
        parse_mode="Markdown", reply_markup=back_kb("parser_menu"),
    )
    await cb.answer()


@router.message(ParserState.wait_keywords)
async def handle_keywords(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    await state.clear()

    kws = [k.strip() for k in message.text.strip().splitlines() if k.strip()]
    client = session_manager.get_client()
    if not client:
        await message.answer("❌ Нет активных аккаунтов.")
        return

    stop = tasks.new_task()
    msg = await message.answer(f"⏳ Ищу по {len(kws)} словам...", reply_markup=stop_kb(id(stop)))

    async def prog(cur, tot, text):
        try:
            await msg.edit_text(text, reply_markup=stop_kb(id(stop)))
        except Exception:
            pass

    try:
        chats = await P.by_keyword(client, kws, on_progress=prog, stop=stop)
        if not chats:
            await msg.edit_text("❌ Ничего не найдено.", reply_markup=back_kb("parser_menu"))
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = await to_csv(chats, f"chats_kw_{ts}.csv")
        await msg.edit_text(f"✅ Найдено *{len(chats)}* чатов", parse_mode="Markdown")
        await message.answer_document(
            FSInputFile(path),
            caption=f"🔍 По ключевым словам | {len(chats)} чатов",
        )
    finally:
        tasks.done_task(stop)


# ── Reactions ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parse_reactions")
async def cb_parse_reactions(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(ParserState.wait_post)
    await cb.message.edit_text(
        "❤️ *Парсинг реакций*\n\n"
        "Введите ссылку на пост:\n"
        "Пример: `https://t.me/channel/123`",
        parse_mode="Markdown", reply_markup=back_kb("parser_menu"),
    )
    await cb.answer()


@router.message(ParserState.wait_post)
async def handle_post(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return
    await state.clear()

    link = message.text.strip()
    client = session_manager.get_client()
    if not client:
        await message.answer("❌ Нет активных аккаунтов.")
        return

    stop = tasks.new_task()
    msg = await message.answer("⏳ Парсю реакции...", reply_markup=stop_kb(id(stop)))

    async def prog(cur, tot, text):
        try:
            await msg.edit_text(text, reply_markup=stop_kb(id(stop)))
        except Exception:
            pass

    try:
        users = await P.reactions(client, link, on_progress=prog, stop=stop)
        await _finish(msg, users, "reactions", stop, orig_chat=message.chat.id)
    finally:
        tasks.done_task(stop)


# ── Exports list ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parse_exports")
async def cb_exports(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    files = list_exports(10)
    if not files:
        await cb.message.edit_text("📂 Экспортов нет.", reply_markup=back_kb("parser_menu"))
        await cb.answer()
        return

    kb = InlineKeyboardBuilder()
    for f in files:
        kb.button(text=f"📄 {f}", callback_data=f"dlexp_{f}")
    kb.button(text="◀️ Назад", callback_data="parser_menu")
    kb.adjust(1)
    await cb.message.edit_text("📂 *Последние экспорты:*", reply_markup=kb.as_markup(), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("dlexp_"))
async def cb_dl_export(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    fname = cb.data[6:]
    path = os.path.join(config.EXPORTS_DIR, fname)
    if os.path.exists(path):
        await cb.message.answer_document(FSInputFile(path), caption=f"📄 {fname}")
    await cb.answer()


# ── Global stop handler (used by all task modules) ────────────────────────────

@router.callback_query(F.data.startswith("stop_"))
async def cb_stop(cb: CallbackQuery):
    try:
        task_id = int(cb.data[5:])
        stopped = tasks.stop_task(task_id)
        await cb.answer("🛑 Остановка..." if stopped else "Задача уже завершена")
    except Exception:
        await cb.answer()


# ── Helper ────────────────────────────────────────────────────────────────────

async def _finish(
    status_msg,
    users: list,
    label: str,
    stop,
    orig_chat: int = None,
    send_to: int = None,
):
    if not users:
        await status_msg.edit_text("❌ Ничего не найдено.", reply_markup=back_kb("parser_menu"))
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = await to_csv(users, f"{label}_{ts}.csv")
    await status_msg.edit_text(
        f"✅ *Готово!* Спаршено: *{len(users)}* записей",
        parse_mode="Markdown",
    )
    chat_id = send_to or orig_chat or status_msg.chat.id
    await status_msg.bot.send_document(
        chat_id,
        FSInputFile(path),
        caption=f"📊 {label} | {len(users)} записей",
    )
