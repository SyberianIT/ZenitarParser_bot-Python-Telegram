import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
from modules.session_manager import SessionManager
from modules import inviter as I
from utils.keyboards import inviter_menu, stop_kb, back_kb
from utils.export import load_csv, latest_export
from utils import tasks
from handlers.start import admin
import database

router = Router()


class InviterState(StatesGroup):
    wait_file = State()
    wait_group = State()


@router.callback_query(F.data == "inviter_menu")
async def cb_inviter_menu(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    await cb.message.edit_text(
        "📨 *Инвайтер*\n\n"
        "Массовое добавление пользователей из CSV в группу.\n\n"
        "💡 CSV должен содержать колонки `id` или `username`.",
        reply_markup=inviter_menu(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data == "invite_load")
async def cb_invite_load(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(InviterState.wait_file)
    await cb.message.edit_text(
        "📥 Отправьте CSV файл с пользователями:",
        reply_markup=back_kb("inviter_menu"),
    )
    await cb.answer()


@router.callback_query(F.data == "invite_last")
async def cb_invite_last(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    path = latest_export()
    if not path:
        await cb.answer("❌ Нет ни одного экспорта.", show_alert=True)
        return
    users = load_csv(path)
    await state.update_data(users=users)
    await state.set_state(InviterState.wait_group)
    await cb.message.edit_text(
        f"✅ Загружено *{len(users)}* из последнего экспорта.\n\n"
        "Введите @username или ссылку на *целевую группу*:",
        parse_mode="Markdown", reply_markup=back_kb("inviter_menu"),
    )
    await cb.answer()


@router.message(InviterState.wait_file, F.document)
async def handle_invite_file(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    if not message.document.file_name.endswith(".csv"):
        await message.answer("❌ Нужен CSV файл.")
        return
    os.makedirs(config.EXPORTS_DIR, exist_ok=True)
    path = os.path.join(config.EXPORTS_DIR, f"inv_{message.from_user.id}.csv")
    await message.bot.download(message.document, path)
    users = load_csv(path)
    await state.update_data(users=users)
    await state.set_state(InviterState.wait_group)
    await message.answer(
        f"✅ Загружено *{len(users)}* пользователей.\n\n"
        "Введите @username или ссылку на *целевую группу*:",
        parse_mode="Markdown",
    )


@router.message(InviterState.wait_file)
async def handle_invite_file_wrong(message: Message):
    if not admin(message.from_user.id): return
    await message.answer("❌ Ожидаю CSV файл.")


@router.message(InviterState.wait_group)
async def handle_invite_group(message: Message, state: FSMContext, session_manager: SessionManager):
    if not admin(message.from_user.id): return

    data = await state.get_data()
    users = data.get("users", [])
    group = message.text.strip()
    await state.clear()

    if not users:
        await message.answer("❌ Список пуст. Начните заново.")
        return

    client = session_manager.get_client()
    if not client:
        await message.answer("❌ Нет активных аккаунтов. Добавьте в разделе 👥 Аккаунты.")
        return

    delay_raw = await database.get_setting("delay_invite", "5-15")
    try:
        dmin, dmax = (float(x) for x in delay_raw.split("-"))
    except Exception:
        dmin, dmax = 5.0, 15.0

    stop = tasks.new_task()
    msg = await message.answer(
        f"📨 Инвайчу *{len(users)}* пользователей → `{group}`...",
        reply_markup=stop_kb(id(stop)), parse_mode="Markdown",
    )

    async def prog(cur, tot, s):
        try:
            await msg.edit_text(
                f"📨 Прогресс: {cur}/{tot}\n"
                f"✅ Успешно: {s['success']}\n"
                f"⛔ Приватность: {s['privacy']}\n"
                f"🔁 Уже в группе: {s['skip']}\n"
                f"🌊 Флуд: {s['flood']}\n"
                f"❌ Ошибок: {s['error']}",
                reply_markup=stop_kb(id(stop)),
            )
        except Exception:
            pass

    try:
        stats = await I.invite(client, group, users, dmin, dmax, on_progress=prog, stop=stop)
    finally:
        tasks.done_task(stop)

    await msg.edit_text(
        f"📨 *Инвайтинг завершён*\n\n"
        f"✅ Успешно: {stats['success']}\n"
        f"⛔ Приватность: {stats['privacy']}\n"
        f"🔁 Уже в группе: {stats['skip']}\n"
        f"🌊 Флуд/лимит: {stats['flood']}\n"
        f"❌ Ошибок: {stats['error']}\n"
        f"📊 Всего: {stats['total']}",
        parse_mode="Markdown", reply_markup=back_kb("inviter_menu"),
    )
