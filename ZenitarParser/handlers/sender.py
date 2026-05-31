import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database
from modules.account_pool import AccountPool
from modules import sender as S
from utils.keyboards import sender_menu, stop_kb, back_kb
from utils.export import load_csv, latest_export
from utils import tasks
from handlers.start import admin

router = Router()


class SenderState(StatesGroup):
    wait_input = State()
    wait_message = State()


@router.callback_query(F.data == "sender_menu")
async def cb_sender_menu(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.clear()
    await cb.message.edit_text(
        "📢 *Рассыльщик*\n\n"
        "• *Юзербот* — пишет от имени ваших аккаунтов (ротация по пулу)\n"
        "• *Бот* — пишет от имени добавленных ботов (Bot API)\n\n"
        "💡 Переменные: `{name}` `{username}` `{last_name}` `{full_name}`",
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
        "Теперь введите *текст сообщения*.\n"
        "Переменные: `{name}` `{username}` `{last_name}` `{full_name}`",
        parse_mode="Markdown",
    )


@router.message(SenderState.wait_message, F.text)
async def handle_sender_text(message: Message, state: FSMContext, account_pool: AccountPool):
    if not admin(message.from_user.id): return

    data = await state.get_data()
    users = data.get("users", [])
    mode = data.get("mode", "userbot")
    template = message.text
    await state.clear()

    if not users:
        await message.answer("❌ Список пуст.")
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
                    "❌ Нет доступных аккаунтов (кулдаун/лимит/нет активных). "
                    "Добавьте в 👥 Аккаунты.",
                    reply_markup=back_kb("sender_menu"),
                )
                return
            stats = await S.via_userbot(account_pool, users, template, dmin, dmax, on_progress=prog, stop=stop)
        else:
            bots = await database.get_bot_tokens()
            if not bots:
                await msg.edit_text(
                    "❌ Нет активных ботов. Добавьте токен в разделе 🤖 Боты.",
                    reply_markup=back_kb("sender_menu"),
                )
                return
            tokens = [b["token"] for b in bots]
            # Bot API rate-limit is generous; userbot delays would be far too slow.
            sdmin, sdmax = (0.05, 0.3) if mode == "bot" else (dmin, dmax)
            stats = await S.via_bot(tokens, users, template, sdmin, sdmax, on_progress=prog, stop=stop)
        await database.log_stat("send", mode, stats["success"])
    finally:
        tasks.done_task(task_id)

    note = "\n\n⚠️ Аккаунты закончились (флуд/лимиты)." if stats.get("no_accounts") else ""
    used = f"\n👥 Аккаунтов задействовано: {stats['accounts_used']}" if "accounts_used" in stats else ""
    await msg.edit_text(
        f"📢 *Рассылка завершена*\n\n"
        f"✅ Отправлено: {stats['success']}\n"
        f"🚫 Заблокировано: {stats.get('blocked', 0)}\n"
        f"🌊 Флуд/лимит: {stats.get('flood', 0)}\n"
        f"❌ Ошибок: {stats['error']}{used}\n"
        f"📊 Всего: {stats['total']}{note}",
        parse_mode="Markdown", reply_markup=back_kb("sender_menu"),
    )
