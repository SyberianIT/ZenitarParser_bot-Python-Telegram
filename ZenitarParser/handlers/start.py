from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import config
from utils.keyboards import main_menu

router = Router()


def admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.message(Command("start"))
async def cmd_start(message: Message):
    if not admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        "🚀 *ZenitarParser Pro*\n\n"
        "Профессиональный инструмент для парсинга,\n"
        "инвайтинга и рассылки в Telegram.\n\n"
        "Выберите раздел:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main(cb: CallbackQuery):
    if not admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "🚀 *ZenitarParser Pro*\n\nВыберите раздел:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    await cb.answer()
