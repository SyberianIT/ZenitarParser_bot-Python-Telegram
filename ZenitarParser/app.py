import os
import csv
import asyncio
from pyrogram import Client
from pyrogram.raw.functions.contacts import Search
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, FSInputFile
from aiogram import F
from aiogram.client.default import DefaultBotProperties
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID

# Инициализация
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
parsing_flag = False

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_session_name():
    sessions_dir = "sessions"
    if not os.path.exists(sessions_dir):
        return None
    for file in os.listdir(sessions_dir):
        if file.endswith(".session"):
            return file[:-8]  # убираем .session
    return None

@dp.message(Command("start"))
async def start_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Доступ запрещён.")
        return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Парсер", callback_data="parser")],
        [InlineKeyboardButton(text="✅ Проверить сессию", callback_data="check_session")]
    ])
    await message.reply("<b>🔐 Панель управления</b>", reply_markup=markup)

@dp.callback_query(F.data == "check_session")
async def check_session(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    
    session_name = get_session_name()
    if not session_name:
        text = "<b>❌ Ошибка:</b> Сессия не найдена в папке sessions"
    else:
        try:
            async with Client(session_name, API_ID, API_HASH, workdir="sessions") as client:
                me = await client.get_me()
                text = f"<b>✅ Сессия активна</b>\n👤 Пользователь: {me.first_name}"
        except Exception as e:
            text = f"<b>❌ Ошибка проверки сессии:</b> {str(e)}"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Парсер", callback_data="parser")],
        [InlineKeyboardButton(text="✅ Проверить сессию", callback_data="check_session")]
    ])
    await callback.message.edit_text("<b>🔐 Панель управления</b>", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "parser")
async def parser_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(
        "<b>📝 Введите список тегов</b>\nКаждый тег с новой строки:", 
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(F.data == "stop_parsing")
async def stop_parsing(callback: CallbackQuery):
    global parsing_flag
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    
    parsing_flag = False
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text("<b>⏹️ Парсинг остановлен</b>", reply_markup=markup)
    await callback.answer()

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_tags(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # Получаем теги
    tags = message.text.strip().split('\n')
    tags = [tag.strip() for tag in tags if tag.strip()]
    
    if not tags:
        await message.reply("❌ Нет тегов для поиска")
        return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ Остановить", callback_data="stop_parsing")]
    ])
    await message.reply(f"<b>🔄 Начинаю парсинг {len(tags)} тегов...</b>", reply_markup=markup)
    
    global parsing_flag
    parsing_flag = True
    all_chats = []
    session_name = get_session_name()
    
    if not session_name:
        await message.reply("<b>❌ Ошибка:</b> Сессия не найдена в папке sessions")
        return
    
    try:
        async with Client(session_name, API_ID, API_HASH, workdir="sessions") as client:
            for i, tag in enumerate(tags, 1):
                if not parsing_flag:
                    await message.reply("⏹️ Парсинг остановлен")
                    break
                
                await message.reply(f"🔍 [{i}/{len(tags)}] Ищем: <b>{tag}</b>")
                
                try:
                    # Поиск через raw API
                    result = await client.invoke(Search(q=tag, limit=100))
                    
                    tag_chats = []
                    for chat in result.chats:
                        if not parsing_flag:
                            break
                        if hasattr(chat, 'username') and chat.username:
                            tag_chats.append(f"@{chat.username}")
                    
                    if tag_chats:
                        all_chats.extend(tag_chats)
                        await message.reply(f"   ✅ Найдено: {len(tag_chats)} чатов")
                    else:
                        await message.reply(f"   ❌ Ничего не найдено")
                        
                except Exception as e:
                    await message.reply(f"   ❌ Ошибка: {str(e)[:50]}")
                    continue
        
        if all_chats and parsing_flag:
            # Удаляем дубликаты
            unique_chats = list(set(all_chats))
            
            # Создаем CSV файл
            filename = f"chats_{message.from_user.id}.csv"
            with open(filename, 'w', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Username"])
                for chat in unique_chats:
                    writer.writerow([chat])
            
            # Отправляем файл
            document = FSInputFile(filename)
            await bot.send_document(
                message.from_user.id, 
                document, 
                caption=f"<b>✅ Готово!</b>\n📊 Найдено всего: {len(unique_chats)} чатов"
            )
            
            # Удаляем временный файл
            os.remove(filename)
        elif parsing_flag:
            await message.reply("<b>❌ Ничего не найдено</b>")
            
    except Exception as e:
        await message.reply(f"<b>❌ Ошибка:</b> {str(e)}")

async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())