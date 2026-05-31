import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
import kb
import shared
from config import ADMIN_ID

log = logging.getLogger(__name__)
router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


HELP_TEXT = (
    "<b>📖 ZenitarParser Pro — Справка</b>\n\n"
    "<b>🔍 Парсер</b>\n"
    "• <i>По ключевым словам</i> — найти публичные чаты по запросу\n"
    "• <i>Участники группы</i> — спарсить всех участников группы/канала\n"
    "• <i>Только администраторы</i> — список только администраторов\n\n"
    "<b>👥 Инвайтер</b>\n"
    "Добавляет участников из результата парсинга в вашу группу.\n"
    "Работает только с аккаунтами, у которых есть общий контакт/группа с целевыми пользователями.\n\n"
    "<b>💌 Рассыльщик</b>\n"
    "• <i>DM через аккаунты</i> — личные сообщения пользователям из результата\n"
    "• <i>Бот-рассылка</i> — рассылка по подписчикам бота\n\n"
    "<b>⚡ Аккаунты</b>\n"
    "Помести <code>.session</code> файлы (Pyrogram) в папку <code>sessions/</code> и нажми 🔄 Обновить.\n\n"
    "<b>📊 Результаты</b>\n"
    "Сохранённые результаты парсинга. Экспорт в CSV, запуск инвайтера/рассыльщика.\n\n"
    "<b>⚠️ Важно:</b> Соблюдай задержки между действиями, чтобы не получить бан аккаунта."
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await db.add_bot_sub(message.from_user.id, message.from_user.username, message.from_user.first_name)
        await message.reply("🚫 Доступ запрещён.")
        return
    await state.clear()
    await db.add_bot_sub(message.from_user.id, message.from_user.username, message.from_user.first_name)
    log.info("Admin opened panel")
    await message.reply(
        "<b>⚙️ ZenitarParser Pro</b>\n\nВыберите раздел:",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.reply(HELP_TEXT)


@router.callback_query(F.data == "menu:main")
async def cb_main(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "<b>⚙️ ZenitarParser Pro</b>\n\nВыберите раздел:",
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(HELP_TEXT, reply_markup=kb.back())


@router.callback_query(F.data.in_({"job:stop", "parser:stop"}))
async def cb_stop_any(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    triggered = shared.trigger(callback.from_user.id)
    await callback.answer("⛔ Остановка запрошена…" if triggered else "Нет активного задания", show_alert=True)
