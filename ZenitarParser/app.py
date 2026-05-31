import os
import csv
import asyncio
import logging
from datetime import datetime
from pyrogram import Client
from pyrogram.raw.functions.contacts import Search
from pyrogram.errors import FloodWait
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Message, FSInputFile
)
from aiogram import F
from aiogram.client.default import DefaultBotProperties
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Per-user runtime state  {user_id: {"running": bool, "stop": bool}}
user_states: dict[int, dict] = {}

# In-memory search history
search_history: list[dict] = []
MAX_HISTORY = 10


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_session_name() -> str | None:
    sessions_dir = "sessions"
    if not os.path.exists(sessions_dir):
        return None
    for f in os.listdir(sessions_dir):
        if f.endswith(".session"):
            return f[:-8]
    return None


def progress_bar(current: int, total: int, width: int = 12) -> str:
    if total == 0:
        return "▱" * width
    filled = round(width * current / total)
    return "▰" * filled + "▱" * (width - filled)


def main_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Запустить парсер", callback_data="parser")],
        [
            InlineKeyboardButton(text="✅ Проверить сессию", callback_data="check_session"),
            InlineKeyboardButton(text="📜 История", callback_data="history"),
        ],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
    ])


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])


# ── /start ────────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Доступ запрещён.")
        return
    log.info("Admin opened panel")
    await message.reply(
        "<b>⚙️ ZenitarParser — Панель управления</b>\n\nВыберите действие:",
        reply_markup=main_markup(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.reply(
        "<b>📖 ZenitarParser — Справка</b>\n\n"
        "<b>Команды:</b>\n"
        "• /start — открыть панель управления\n"
        "• /help — эта справка\n\n"
        "<b>Как парсить:</b>\n"
        "1. Нажмите <i>Запустить парсер</i>\n"
        "2. Отправьте ключевые слова (каждое с новой строки)\n"
        "3. Дождитесь CSV-файла или нажмите ⛔ Остановить\n\n"
        "<b>Результат:</b> Excel-совместимый CSV со списком @username",
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "back_to_start")
async def cb_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "<b>⚙️ ZenitarParser — Панель управления</b>\n\nВыберите действие:",
        reply_markup=main_markup(),
    )


@dp.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "<b>📖 ZenitarParser — Справка</b>\n\n"
        "<b>Как парсить:</b>\n"
        "1. Нажмите <i>Запустить парсер</i>\n"
        "2. Отправьте ключевые слова — каждое с новой строки\n"
        "3. Дождитесь CSV-файла или нажмите ⛔ Остановить\n\n"
        "<b>Результат:</b> Excel-совместимый CSV со списком @username\n\n"
        "<b>Примечание:</b> при FloodWait бот автоматически делает паузу и продолжает.",
        reply_markup=back_markup(),
    )


@dp.callback_query(F.data == "check_session")
async def cb_check_session(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text("⏳ Проверяю сессию...")

    session_name = get_session_name()
    if not session_name:
        text = (
            "<b>❌ Сессия не найдена</b>\n\n"
            "Поместите <code>.session</code> файл в папку <code>sessions/</code>"
        )
    else:
        try:
            async with Client(session_name, API_ID, API_HASH, workdir="sessions") as client:
                me = await client.get_me()
                name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                phone = me.phone_number or "скрыт"
                text = (
                    "<b>✅ Сессия активна</b>\n\n"
                    f"👤 Имя: <b>{name}</b>\n"
                    f"📱 Телефон: <code>+{phone}</code>\n"
                    f"🆔 User ID: <code>{me.id}</code>\n"
                    f"📡 DC: {me.dc_id}"
                )
        except Exception as e:
            log.error(f"Session check failed: {e}")
            text = f"<b>❌ Ошибка проверки сессии</b>\n\n<code>{str(e)[:300]}</code>"

    await callback.message.edit_text(text, reply_markup=back_markup())


@dp.callback_query(F.data == "history")
async def cb_history(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.answer()

    if not search_history:
        text = "<b>📜 История поисков</b>\n\n<i>Поиски ещё не выполнялись</i>"
    else:
        lines = ["<b>📜 История поисков</b>"]
        for entry in reversed(search_history):
            kw = ", ".join(entry["keywords"][:3])
            if len(entry["keywords"]) > 3:
                kw += f" +{len(entry['keywords']) - 3}"
            lines.append(
                f"\n🕐 {entry['date']}\n"
                f"   🔑 {kw}\n"
                f"   📊 {entry['total']} уникальных"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=back_markup())


@dp.callback_query(F.data == "parser")
async def cb_parser(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "<b>📝 Введите ключевые слова</b>\n\n"
        "Каждое слово или фраза — с новой строки.\n\n"
        "<i>Пример:</i>\n<code>новости\nкрипто\nтехнологии</code>",
        reply_markup=back_markup(),
    )


@dp.callback_query(F.data == "stop_parsing")
async def cb_stop(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    user_id = callback.from_user.id
    if user_id in user_states:
        user_states[user_id]["stop"] = True
    await callback.answer("⛔ Остановка запрошена…", show_alert=True)


# ── Main parsing handler ───────────────────────────────────────────────────────

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_keywords(message: Message):
    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    if user_states.get(user_id, {}).get("running"):
        await message.reply("⚠️ Парсинг уже запущен. Дождитесь завершения или нажмите ⛔ Остановить.")
        return

    tags = [t.strip() for t in message.text.strip().splitlines() if t.strip()]
    if not tags:
        await message.reply("❌ Введите хотя бы одно ключевое слово.")
        return

    session_name = get_session_name()
    if not session_name:
        await message.reply(
            "<b>❌ Сессия не найдена</b>\n\n"
            "Поместите <code>.session</code> файл в папку <code>sessions/</code>"
        )
        return

    user_states[user_id] = {"running": True, "stop": False}

    stop_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ Остановить", callback_data="stop_parsing")]
    ])

    progress_msg = await message.reply(
        f"<b>🚀 Запускаю парсинг</b>\n\n"
        f"📋 Тегов: <b>{len(tags)}</b>\n"
        f"⏳ Инициализация…",
        reply_markup=stop_markup,
    )

    log.info(f"Parse started: {len(tags)} tags")

    all_chats: list[str] = []
    per_tag: dict[str, int] = {}

    async def update_progress(idx: int, current_tag: str):
        bar = progress_bar(idx, len(tags))
        await progress_msg.edit_text(
            f"<b>🔍 Парсинг…</b>\n\n"
            f"{bar} {idx}/{len(tags)}\n\n"
            f"▶️ Сейчас: <b>{current_tag}</b>\n"
            f"📦 Собрано: {len(all_chats)} чатов",
            reply_markup=stop_markup,
        )

    try:
        async with Client(session_name, API_ID, API_HASH, workdir="sessions") as client:
            for i, tag in enumerate(tags, 1):
                if user_states[user_id]["stop"]:
                    break

                try:
                    await update_progress(i - 1, tag)
                except Exception:
                    pass

                for attempt in range(2):
                    try:
                        result = await client.invoke(Search(q=tag, limit=100))
                        found = [
                            f"@{chat.username}"
                            for chat in result.chats
                            if getattr(chat, "username", None)
                        ]
                        per_tag[tag] = len(found)
                        all_chats.extend(found)
                        log.info(f"[{i}/{len(tags)}] '{tag}' → {len(found)}")
                        break

                    except FloodWait as e:
                        wait = e.value + 2
                        log.warning(f"FloodWait {wait}s on '{tag}'")
                        try:
                            await progress_msg.edit_text(
                                f"<b>⏳ FloodWait — жду {wait}с</b>\n\nПродолжу автоматически…",
                                reply_markup=stop_markup,
                            )
                        except Exception:
                            pass
                        await asyncio.sleep(wait)

                    except Exception as e:
                        per_tag[tag] = 0
                        log.error(f"Error on '{tag}': {e}")
                        break

                await asyncio.sleep(0.4)  # gentle rate limiting

        stopped_early = user_states[user_id]["stop"]
        unique = sorted(set(all_chats))

        if unique:
            top = sorted(per_tag.items(), key=lambda x: x[1], reverse=True)[:5]
            top_str = "\n".join(f"  • {k}: {v}" for k, v in top if v > 0) or "  —"

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chats_{user_id}_{ts}.csv"
            with open(filename, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Username"])
                for chat in unique:
                    writer.writerow([chat])

            status_icon = "⛔" if stopped_early else "✅"
            status_label = "Остановлен" if stopped_early else "Готово"
            caption = (
                f"<b>{status_icon} {status_label}</b>\n\n"
                f"📊 Уникальных чатов: <b>{len(unique)}</b>\n"
                f"📋 Обработано тегов: {len(per_tag)}/{len(tags)}\n\n"
                f"<b>Топ тегов по результатам:</b>\n{top_str}"
            )

            await progress_msg.edit_text(f"{status_icon} Отправляю файл…", reply_markup=None)
            await bot.send_document(user_id, FSInputFile(filename), caption=caption)
            os.remove(filename)

            search_history.append({
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "keywords": tags,
                "total": len(unique),
            })
            if len(search_history) > MAX_HISTORY:
                search_history.pop(0)

        else:
            status = "⛔ Остановлен" if stopped_early else "❌ Ничего не найдено"
            await progress_msg.edit_text(
                f"<b>{status}</b>\n\nПо указанным ключевым словам чаты не найдены.",
                reply_markup=back_markup(),
            )

        log.info(f"Parse done: {len(unique)} unique chats")

    except Exception as e:
        log.error(f"Critical error: {e}", exc_info=True)
        await progress_msg.edit_text(
            f"<b>❌ Критическая ошибка</b>\n\n<code>{str(e)[:400]}</code>",
            reply_markup=back_markup(),
        )
    finally:
        user_states.pop(user_id, None)


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    log.info("ZenitarParser starting…")
    if API_ID == 123 or not API_HASH.strip() or not BOT_TOKEN.strip():
        log.error("config.py не заполнен! Укажи API_ID, API_HASH, BOT_TOKEN и ADMIN_ID.")
        return
    log.info(f"Admin: {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
