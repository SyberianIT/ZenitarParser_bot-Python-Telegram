from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID

print("=== ПРОВЕРКА КОНФИГА ===")
print(f"API_ID: {API_ID}")
print(f"API_HASH: {API_HASH[:10]}...")
print(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"ADMIN_ID: {ADMIN_ID}")
print("========================\n")

import asyncio
from pyrogram import Client

async def test_connection():
    print("🔍 Проверяем подключение к Telegram...")
    
    # Проверяем наличие папки sessions
    import os
    if not os.path.exists("sessions"):
        os.makedirs("sessions")
        print("📁 Создана папка sessions")
    
    # Проверяем наличие файла сессии
    session_files = [f for f in os.listdir("sessions") if f.endswith(".session")]
    if not session_files:
        print("❌ Нет файла сессии! Нужно создать:")
        print("   python create_session.py")
        return
    
    session_name = session_files[0][:-8]  # убираем .session
    print(f"📁 Найден файл сессии: {session_name}.session")
    
    try:
        # Пробуем подключиться
        async with Client(session_name, API_ID, API_HASH, workdir="sessions") as app:
            me = await app.get_me()
            print(f"✅ Успешное подключение!")
            print(f"👤 Аккаунт: {me.first_name}")
            print(f"📱 Телефон: {me.phone_number}")
            
            # Проверяем поиск
            print("\n🔍 Тест поиска (ищем 'новости'):")
            try:
                from pyrogram.raw.functions.contacts import Search
                result = await app.invoke(Search(q="новости", limit=5))
                print(f"📊 Найдено чатов: {len(result.chats)}")
                
                if result.chats:
                    for chat in result.chats[:3]:
                        if chat.username:
                            print(f"   - @{chat.username}")
                else:
                    print("   Ничего не найдено")
                    
            except Exception as e:
                print(f"❌ Ошибка поиска: {e}")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())