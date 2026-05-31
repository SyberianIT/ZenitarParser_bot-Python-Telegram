from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import config
import database
from modules.account_pool import AccountPool
from utils.keyboards import main_menu

router = Router()


def admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def _dashboard_text(account_pool: AccountPool) -> str:
    d = await account_pool.dashboard()
    bots = await database.get_bot_tokens()
    summary = await database.stats_summary()

    if d["total"] == 0:
        acc_line = "👥 Аккаунты: _нет_ — добавьте в разделе 👥 Аккаунты"
    else:
        parts = [f"✅ {d['connected']}"]
        if d["flood"]:
            parts.append(f"🌊 {d['flood']}")
        if d["banned"]:
            parts.append(f"🚫 {d['banned']}")
        acc_line = f"👥 Аккаунты: {' · '.join(parts)} из {d['total']}"

    return (
        "🚀 *ZenitarParser Pro* — панель управления\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{acc_line}\n"
        f"🤖 Боты для рассылки: {len(bots)}\n"
        f"\n"
        f"📦 *Запас на сегодня*\n"
        f"  📨 инвайтов: {d['invites_left']}  ·  📢 сообщений: {d['messages_left']}\n"
        f"📊 *Сегодня израсходовано*\n"
        f"  📨 {d['invites_used']}  ·  📢 {d['messages_used']}\n"
        f"\n"
        f"📈 *Всего:* 🔍 {summary['parse']['total']} спаршено · "
        f"📨 {summary['invite']['total']} · 📢 {summary['send']['total']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выберите раздел:"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, account_pool: AccountPool):
    if not admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await state.clear()
    await message.answer(
        await _dashboard_text(account_pool),
        reply_markup=main_menu(), parse_mode="Markdown",
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, account_pool: AccountPool):
    await cmd_start(message, state, account_pool)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("✖️ Действие отменено. /menu — открыть панель")


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not admin(message.from_user.id):
        return
    await message.answer(
        "ℹ️ *Как пользоваться*\n\n"
        "1️⃣ 👥 *Аккаунты* — добавьте один или несколько аккаунтов\n"
        "2️⃣ 🔍 *Парсер* — соберите аудиторию в CSV\n"
        "3️⃣ 📨 *Инвайтер* — добавьте людей в свою группу\n"
        "4️⃣ 📢 *Рассыльщик* — разошлите сообщения\n\n"
        "Чем больше аккаунтов — тем выше лимиты и устойчивость к флуду.\n\n"
        "*Команды:* /menu · /cancel · /help",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main(cb: CallbackQuery, state: FSMContext, account_pool: AccountPool):
    if not admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.clear()
    try:
        await cb.message.edit_text(
            await _dashboard_text(account_pool),
            reply_markup=main_menu(), parse_mode="Markdown",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "refresh")
async def cb_refresh(cb: CallbackQuery, account_pool: AccountPool):
    if not admin(cb.from_user.id):
        await cb.answer()
        return
    try:
        await cb.message.edit_text(
            await _dashboard_text(account_pool),
            reply_markup=main_menu(), parse_mode="Markdown",
        )
        await cb.answer("🔄 Обновлено")
    except Exception:
        await cb.answer("Актуально")
