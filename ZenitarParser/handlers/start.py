from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import config
from utils.keyboards import main_menu

router = Router()


def admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


_WELCOME = (
    "🚀 *ZenitarParser Pro*\n\n"
    "Профессиональный инструмент для парсинга,\n"
    "инвайтинга и рассылки в Telegram.\n\n"
    "Выберите раздел:"
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await state.clear()
    await message.answer(_WELCOME, reply_markup=main_menu(), parse_mode="Markdown")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("✖️ Отменено.", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not admin(message.from_user.id):
        return
    await message.answer(
        "ℹ️ *Помощь*\n\n"
        "1. 👥 Аккаунты → добавьте аккаунт(ы)\n"
        "2. 🔍 Парсер → соберите аудиторию в CSV\n"
        "3. 📨 Инвайтер → добавьте людей в группу\n"
        "4. 📢 Рассыльщик → разошлите сообщения\n\n"
        "Команды: /start /cancel /help",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text(_WELCOME, reply_markup=main_menu(), parse_mode="Markdown")
    await cb.answer()
