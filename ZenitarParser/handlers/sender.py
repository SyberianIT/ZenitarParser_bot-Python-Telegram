import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database
from modules.account_pool import AccountPool
from modules import sender as S
from utils.keyboards import sender_menu, stop_kb, back_kb
from utils.export import load_csv, latest_export
from utils import tasks
from modules.sender import _fmt
from handlers.start import admin

router = Router()


class SenderState(StatesGroup):
    wait_input = State()
    wait_message = State()
    wait_photo = State()
    wait_button = State()
    wait_confirm = State()


@router.callback_query(F.data == "sender_menu")
async def cb_sender_menu(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.clear()
    await cb.message.edit_text(
        "📢 *Рассыльщик*\n\n"
        "• *Юзербот* — от имени ваших аккаунтов (ротация)\n"
        "• *Бот* — через Bot API (быстрее, нужен старт бота)\n\n"
        "💡 Переменные: `{name}` `{username}` `{last_name}` `{full_name}`\n"
        "🖼 Поддержка фото и инлайн-кнопок",
        reply_markup=sender_menu(), parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.in_({"send_userbot", "send_bot"}))
async def cb_send_mode(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    mode = "userbot" if cb.data == "send_userbot" else "bot"
    await state.set_state(SenderState.wait_input)
    await state.update_data(mode=mode)
    label = "юзербот (Pyrogram)" if mode == "userbot" else "ботов (Bot API)"
    await cb.message.edit_text(
        f"📤 *Рассылка через {label}*\n\n"
        "Отправьте CSV файл с получателями\n"
        "или напишите `last` — для последнего экспорта.",
        parse_mode="Markdown", reply_markup=back_kb("sender_menu"),
    )
    await cb.answer()


@router.message(SenderState.wait_input)
async def handle_sender_input(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return

    users = None
    if message.document and message.document.file_name.endswith(".csv"):
        os.makedirs(config.UPLOADS_DIR, exist_ok=True)
        path = os.path.join(config.UPLOADS_DIR, f"snd_{message.from_user.id}.csv")
        await message.bot.download(message.document, path)
        try:
            users = await load_csv(path)
        except Exception as e:
            await message.answer(f"❌ Не удалось прочитать CSV: {str(e)[:100]}")
            return
    elif message.text and message.text.strip().lower() == "last":
        path = latest_export()
        if not path:
            await message.answer("❌ Нет ни одного экспорта.")
            return
        users = await load_csv(path)
    else:
        await message.answer("❌ Отправьте CSV файл или напишите `last`.", parse_mode="Markdown")
        return

    await state.update_data(users=users)
    await state.set_state(SenderState.wait_message)
    await message.answer(
        f"✅ Загружено *{len(users)}* получателей.\n\n"
        "Введите *текст сообщения*.\n"
        "Переменные: `{name}` `{username}` `{last_name}` `{full_name}`",
        parse_mode="Markdown",
    )


@router.message(SenderState.wait_message, F.text)
async def handle_sender_text(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.update_data(template=message.text)
    await state.set_state(SenderState.wait_photo)
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без фото", callback_data="snd_skip_photo")
    await message.answer(
        "🖼 Отправьте фото для медиа-сообщения или пропустите:",
        reply_markup=kb.as_markup(),
    )


@router.message(SenderState.wait_photo, F.photo)
async def handle_sender_photo(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    photo_path = os.path.join(config.UPLOADS_DIR, f"snd_photo_{message.from_user.id}.jpg")
    await message.bot.download(message.photo[-1], photo_path)
    await state.update_data(photo_path=photo_path)
    await _ask_button(message, state)


@router.callback_query(SenderState.wait_photo, F.data == "snd_skip_photo")
async def cb_skip_photo(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.update_data(photo_path="")
    await _ask_button(cb.message, state)
    await cb.answer()


async def _ask_button(msg, state: FSMContext):
    await state.set_state(SenderState.wait_button)
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без кнопки", callback_data="snd_skip_button")
    await msg.answer(
        "🔗 Добавить инлайн-кнопку к сообщению?\n"
        "Формат: `Текст кнопки|https://url.com`\n"
        "Или пропустите:",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )


@router.message(SenderState.wait_button, F.text)
async def handle_sender_button(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    button = message.text.strip()
    if "|" not in button:
        await message.answer("❌ Формат: `Текст|https://url.com`", parse_mode="Markdown")
        return
    await state.update_data(button=button)
    await _show_preview(message, state)


@router.callback_query(SenderState.wait_button, F.data == "snd_skip_button")
async def cb_skip_button(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.update_data(button="")
    await _show_preview(cb.message, state)
    await cb.answer()


async def _show_preview(msg, state: FSMContext):
    await state.set_state(SenderState.wait_confirm)
    data = await state.get_data()
    users = data.get("users", [])
    template = data.get("template", "")
    photo_path = data.get("photo_path", "")
    button = data.get("button", "")

    sample = users[0] if users else {"first_name": "Имя", "username": "username"}
    preview = _fmt(template, sample)

    extras = ""
    if photo_path:
        extras += "🖼 Фото: ✅\n"
    if button:
        extras += f"🔗 Кнопка: `{button}`\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="🧪 Тест себе", callback_data="send_test")
    kb.button(text="🚀 Запустить", callback_data="send_confirm")
    kb.button(text="✖️ Отмена", callback_data="sender_menu")
    kb.adjust(2, 1)

    await msg.answer(
        f"👀 *Превью* (на примере первого получателя):\n"
        f"━━━━━━━━━━━━━━━━━━━━\n{preview}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        + extras +
        f"📊 Получателей: *{len(users)}*",
        reply_markup=kb.as_markup(), parse_mode="Markdown",
    )


@router.callback_query(SenderState.wait_confirm, F.data == "send_test")
async def cb_send_test(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    data = await state.get_data()
    users = data.get("users", [])
    template = data.get("template", "")
    photo_path = data.get("photo_path", "")
    sample = users[0] if users else {"first_name": cb.from_user.first_name}
    text = _fmt(template, sample)
    try:
        if photo_path and os.path.exists(photo_path):
            from aiogram.types import FSInputFile
            await cb.message.answer_photo(FSInputFile(photo_path), caption=text)
        else:
            await cb.message.answer(f"🧪 *Тест:*\n\n{text}", parse_mode="Markdown")
        await cb.answer("Тест отправлен")
    except Exception:
        await cb.message.answer(f"🧪 Тест:\n\n{text}", parse_mode=None)
        await cb.answer()


@router.callback_query(SenderState.wait_confirm, F.data == "send_confirm")
async def cb_send_confirm(cb: CallbackQuery, state: FSMContext, account_pool: AccountPool):
    if not admin(cb.from_user.id): return

    data = await state.get_data()
    users = data.get("users", [])
    mode = data.get("mode", "userbot")
    template = data.get("template", "")
    photo_path = data.get("photo_path", "") or None
    button = data.get("button", "") or None
    await state.clear()
    await cb.answer()

    message = cb.message
    if not users:
        await message.edit_text("❌ Список пуст.", reply_markup=back_kb("sender_menu"))
        return

    delay_raw = await database.get_setting("delay_send", config.DEFAULT_DELAY_SEND)
    try:
        dmin, dmax = (float(x) for x in delay_raw.split("-"))
    except Exception:
        dmin, dmax = 15.0, 40.0

    task_id, stop = tasks.new_task()
    msg = await message.answer(
        f"📢 Запускаю рассылку для *{len(users)}* получателей...",
        reply_markup=stop_kb(task_id), parse_mode="Markdown",
    )

    async def prog(cur, tot, s):
        try:
            await msg.edit_text(
                f"📢 Рассылка: {cur}/{tot}\n"
                f"✅ Отправлено: {s['success']}\n"
                f"🚫 Заблокировано: {s.get('blocked', 0)}\n"
                f"🚫 Пропущено (ЧС): {s.get('skip', 0)}\n"
                f"🌊 Флуд: {s.get('flood', 0)}\n"
                f"❌ Ошибок: {s['error']}",
                reply_markup=stop_kb(task_id),
            )
        except Exception:
            pass

    try:
        if mode == "userbot":
            if await account_pool.count_available("send") == 0:
                await msg.edit_text(
                    "❌ Нет доступных аккаунтов. Добавьте в 👥 Аккаунты.",
                    reply_markup=back_kb("sender_menu"),
                )
                return
            stats = await S.via_userbot(
                account_pool, users, template, dmin, dmax,
                photo_path=photo_path, button=button,
                on_progress=prog, stop=stop,
            )
        else:
            bots = await database.get_bot_tokens()
            if not bots:
                await msg.edit_text(
                    "❌ Нет активных ботов. Добавьте в разделе 🤖 Боты.",
                    reply_markup=back_kb("sender_menu"),
                )
                return
            tokens = [b["token"] for b in bots]
            stats = await S.via_bot(
                tokens, users, template, 0.05, 0.3,
                photo_path=photo_path, button=button,
                on_progress=prog, stop=stop,
            )
        await database.log_stat("send", mode, stats["success"])
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка рассылки: {str(e)[:200]}",
            reply_markup=back_kb("sender_menu"), parse_mode=None,
        )
        return
    finally:
        tasks.done_task(task_id)

    note = "\n\n⚠️ Аккаунты закончились (флуд/лимиты)." if stats.get("no_accounts") else ""
    used = f"\n👥 Аккаунтов: {stats['accounts_used']}" if "accounts_used" in stats else ""
    await msg.edit_text(
        f"📢 *Рассылка завершена*\n\n"
        f"✅ Отправлено: {stats['success']}\n"
        f"🚫 Заблокировано: {stats.get('blocked', 0)}\n"
        f"🚫 Пропущено (ЧС): {stats.get('skip', 0)}\n"
        f"🌊 Флуд/лимит: {stats.get('flood', 0)}\n"
        f"❌ Ошибок: {stats['error']}{used}\n"
        f"📊 Всего: {stats['total']}{note}",
        parse_mode="Markdown", reply_markup=back_kb("sender_menu"),
    )
