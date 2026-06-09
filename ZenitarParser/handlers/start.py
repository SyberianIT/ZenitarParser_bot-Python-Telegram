from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database
from modules.account_pool import AccountPool
from utils.keyboards import main_menu

router = Router()

_TOS_TEXT = (
    "⚠️ *Пользовательское соглашение*\n\n"
    "Перед использованием ознакомьтесь с условиями:\n\n"
    "1️⃣ Инструмент предоставляется *«как есть»* исключительно для законного маркетинга "
    "с собственной аудиторией и собственными данными.\n\n"
    "2️⃣ *Запрещается* использовать для:\n"
    "   • рассылки незапрошенных сообщений (спама)\n"
    "   • инвайтинга без согласия пользователей\n"
    "   • любых действий, нарушающих [Условия использования Telegram](https://telegram.org/tos)\n"
    "   • сбора персональных данных без правового основания\n\n"
    "3️⃣ *Вся ответственность* за использование лежит исключительно на операторе "
    "(лице, применяющем данное ПО). Разработчик не несёт никакой ответственности "
    "за последствия использования.\n\n"
    "4️⃣ Нажимая «Принимаю», вы подтверждаете, что ознакомились с условиями, "
    "понимаете ограничения и берёте на себя полную ответственность.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "_Продолжение использования = согласие с условиями._"
)


def admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def _check_tos() -> bool:
    return bool(await database.get_setting("tos_accepted", ""))


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

    bl_count = len(await database.blacklist_get_all())
    pending_jobs = len(await database.job_get_pending())

    return (
        "🚀 *ZenitarParser Pro* — панель управления\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{acc_line}\n"
        f"🤖 Боты для рассылки: {len(bots)}\n"
        f"🚫 Чёрный список: {bl_count}\n"
        f"⏰ Плановых задач: {pending_jobs}\n"
        f"\n"
        f"📦 *Запас на сегодня*\n"
        f"  📨 инвайтов: {d['invites_left']}  ·  📢 сообщений: {d['messages_left']}\n"
        f"📊 *Сегодня израсходовано*\n"
        f"  📨 {d['invites_used']}  ·  📢 {d['messages_used']}\n"
        f"\n"
        f"📈 *Всего:* 🔍 {summary['parse']['total']} · "
        f"📨 {summary['invite']['total']} · 📢 {summary['send']['total']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выберите раздел:"
    )


def _tos_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принимаю ответственность", callback_data="tos_accept")
    return kb.as_markup()


async def _show_tos(target):
    """Send the ToS screen. target is a Message or CallbackQuery."""
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(_TOS_TEXT, reply_markup=_tos_kb(), parse_mode="Markdown")
        await target.answer()
    else:
        await target.answer(_TOS_TEXT, reply_markup=_tos_kb(), parse_mode="Markdown")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, account_pool: AccountPool):
    if not admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await state.clear()
    if not await _check_tos():
        await _show_tos(message)
        return
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
        "3️⃣ 🎯 *Аудитория* — дедупликация, объединение, фильтры\n"
        "4️⃣ 📨 *Инвайтер* — добавьте людей в свою группу\n"
        "5️⃣ 📢 *Рассыльщик* — разошлите сообщения (фото + кнопки)\n"
        "6️⃣ ⏰ *Планировщик* — запустите рассылку по расписанию\n"
        "7️⃣ 🚫 *Чёрный список* — исключите пользователей\n\n"
        "Чем больше аккаунтов — тем выше лимиты.\n\n"
        "*Команды:* /menu · /cancel · /help",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "tos_accept")
async def cb_tos_accept(cb: CallbackQuery, account_pool: AccountPool):
    if not admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа.", show_alert=True)
        return
    from datetime import datetime
    await database.set_setting("tos_accepted", datetime.utcnow().isoformat())
    await cb.answer("✅ Условия приняты")
    await cb.message.edit_text(
        await _dashboard_text(account_pool),
        reply_markup=main_menu(), parse_mode="Markdown",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main(cb: CallbackQuery, state: FSMContext, account_pool: AccountPool):
    if not admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.clear()
    if not await _check_tos():
        await _show_tos(cb)
        return
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
