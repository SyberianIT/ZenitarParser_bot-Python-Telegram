import os
import time
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database
from utils.keyboards import back_kb
from utils.export import load_csv, latest_export
from handlers.start import admin

router = Router()


class SchedulerState(StatesGroup):
    wait_csv = State()
    wait_message = State()
    wait_photo = State()
    wait_button = State()
    wait_datetime = State()


_STATUS_ICON = {"pending": "⏰", "running": "🔄", "done": "✅", "failed": "❌"}


def _jobs_kb(jobs: list):
    kb = InlineKeyboardBuilder()
    for j in jobs:
        ts = datetime.fromtimestamp(j["run_at"], tz=timezone.utc).strftime("%d.%m %H:%M")
        icon = _STATUS_ICON.get(j["status"], "•")
        kb.button(text=f"{icon} #{j['id']} {ts} [{j['mode']}]", callback_data=f"jview_{j['id']}")
    kb.button(text="➕ Новая задача", callback_data="job_new")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "scheduler_menu")
async def cb_scheduler_menu(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.clear()
    jobs = await database.job_get_all()
    await cb.message.edit_text(
        f"⏰ *Планировщик* ({len(jobs)} задач)\n\n"
        "Запустите рассылку в нужное время.\n"
        "Задача выполнится автоматически даже без вашего участия.",
        reply_markup=_jobs_kb(jobs), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("jview_"))
async def cb_job_view(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    job_id = int(cb.data[6:])
    jobs = await database.job_get_all()
    j = next((x for x in jobs if x["id"] == job_id), None)
    if not j:
        await cb.answer("Не найдено", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    if j["status"] == "pending":
        kb.button(text="🗑 Отменить задачу", callback_data=f"jdel_{job_id}")
    kb.button(text="◀️ Назад", callback_data="scheduler_menu")
    kb.adjust(1)

    ts = datetime.fromtimestamp(j["run_at"], tz=timezone.utc).strftime("%d.%m.%Y %H:%M")
    status_text = {
        "pending": "⏰ Ожидает",
        "running": "🔄 Выполняется",
        "done": "✅ Выполнено",
        "failed": "❌ Ошибка",
    }.get(j["status"], j["status"])
    tmpl_prev = j["template"][:80] + "…" if len(j["template"]) > 80 else j["template"]
    extras = ""
    if j.get("photo_path"):
        extras += "🖼 Фото: ✅\n"
    if j.get("button"):
        extras += f"🔗 Кнопка: `{j['button']}`\n"
    await cb.message.edit_text(
        f"⏰ *Задача #{j['id']}*\n\n"
        f"📅 Запуск: `{ts}` UTC\n"
        f"📤 Режим: `{j['mode']}`\n"
        f"📊 Статус: {status_text}\n"
        f"📄 CSV: `{os.path.basename(j['csv_path'])}`\n"
        f"✉️ Шаблон: `{tmpl_prev}`\n"
        + extras,
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("jdel_"))
async def cb_job_delete(cb: CallbackQuery):
    if not admin(cb.from_user.id): return
    job_id = int(cb.data[5:])
    await database.job_delete(job_id)
    await cb.answer("Задача отменена")
    jobs = await database.job_get_all()
    await cb.message.edit_text(
        f"⏰ *Планировщик* ({len(jobs)} задач)",
        reply_markup=_jobs_kb(jobs), parse_mode="Markdown",
    )


@router.callback_query(F.data == "job_new")
async def cb_job_new(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Юзербот (Pyrogram)", callback_data="jmode_userbot")
    kb.button(text="🤖 Через бота (Bot API)", callback_data="jmode_bot")
    kb.button(text="◀️ Отмена", callback_data="scheduler_menu")
    kb.adjust(2, 1)
    await state.set_state(SchedulerState.wait_csv)
    await state.update_data(mode="userbot")
    await cb.message.edit_text(
        "⏰ *Новая плановая рассылка*\n\nВыберите режим:",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.in_({"jmode_userbot", "jmode_bot"}))
async def cb_job_mode(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    mode = "userbot" if cb.data == "jmode_userbot" else "bot"
    await state.update_data(mode=mode)
    await state.set_state(SchedulerState.wait_csv)
    await cb.message.edit_text(
        "📁 Отправьте CSV с получателями\nили напишите `last` — для последнего экспорта.",
        parse_mode="Markdown", reply_markup=back_kb("scheduler_menu"),
    )
    await cb.answer()


@router.message(SchedulerState.wait_csv)
async def handle_job_csv(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    csv_path = None
    if message.document and message.document.file_name.endswith(".csv"):
        os.makedirs(config.UPLOADS_DIR, exist_ok=True)
        csv_path = os.path.join(config.UPLOADS_DIR, f"job_{message.from_user.id}_{int(time.time())}.csv")
        await message.bot.download(message.document, csv_path)
    elif message.text and message.text.strip().lower() == "last":
        csv_path = latest_export()
    if not csv_path:
        await message.answer("❌ Отправьте CSV или напишите `last`.", parse_mode="Markdown")
        return
    await state.update_data(csv_path=csv_path)
    await state.set_state(SchedulerState.wait_message)
    await message.answer(
        "✉️ Введите текст сообщения.\n"
        "Переменные: `{name}` `{username}` `{full_name}`",
        parse_mode="Markdown",
    )


@router.message(SchedulerState.wait_message, F.text)
async def handle_job_text(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.update_data(template=message.text)
    await state.set_state(SchedulerState.wait_photo)
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без фото", callback_data="jskip_photo")
    await message.answer(
        "🖼 Отправьте фото (медиа-рассылка) или пропустите:",
        reply_markup=kb.as_markup(),
    )


@router.message(SchedulerState.wait_photo, F.photo)
async def handle_job_photo(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    photo_path = os.path.join(config.UPLOADS_DIR, f"job_photo_{message.from_user.id}_{int(time.time())}.jpg")
    await message.bot.download(message.photo[-1], photo_path)
    await state.update_data(photo_path=photo_path)
    await _ask_button(message, state)


@router.callback_query(SchedulerState.wait_photo, F.data == "jskip_photo")
async def cb_skip_photo(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.update_data(photo_path="")
    await _ask_button(cb.message, state)
    await cb.answer()


async def _ask_button(msg, state: FSMContext):
    await state.set_state(SchedulerState.wait_button)
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без кнопки", callback_data="jskip_button")
    await msg.answer(
        "🔗 Добавить инлайн-кнопку? Формат: `Текст кнопки|https://url.com`\n"
        "Или пропустите:",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )


@router.message(SchedulerState.wait_button, F.text)
async def handle_job_button(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    button = message.text.strip()
    if "|" not in button:
        await message.answer("❌ Формат: `Текст|https://url.com`", parse_mode="Markdown")
        return
    await state.update_data(button=button)
    await _ask_datetime(message, state)


@router.callback_query(SchedulerState.wait_button, F.data == "jskip_button")
async def cb_skip_button(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.update_data(button="")
    await _ask_datetime(cb.message, state)
    await cb.answer()


async def _ask_datetime(msg, state: FSMContext):
    await state.set_state(SchedulerState.wait_datetime)
    now_utc = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    await msg.answer(
        "📅 Введите дату и время запуска (UTC):\n"
        f"Формат: `ДД.ММ.ГГГГ ЧЧ:ММ`\n\n"
        f"Сейчас UTC: `{now_utc}`",
        parse_mode="Markdown",
    )


@router.message(SchedulerState.wait_datetime, F.text)
async def handle_job_datetime(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        run_at = int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: `25.12.2025 14:30`", parse_mode="Markdown")
        return
    if run_at <= int(time.time()):
        await message.answer("❌ Это время уже прошло. Введите время в будущем.")
        return

    data = await state.get_data()
    await state.clear()
    job_id = await database.job_add(
        run_at=run_at,
        mode=data.get("mode", "userbot"),
        csv_path=data.get("csv_path", ""),
        template=data.get("template", ""),
        photo_path=data.get("photo_path", ""),
        button=data.get("button", ""),
    )
    ts = dt.strftime("%d.%m.%Y %H:%M")
    await message.answer(
        f"✅ *Задача #{job_id} создана!*\n\n"
        f"📅 Запуск: `{ts}` UTC\n"
        f"📤 Режим: `{data.get('mode', 'userbot')}`",
        parse_mode="Markdown", reply_markup=back_kb("scheduler_menu"),
    )
