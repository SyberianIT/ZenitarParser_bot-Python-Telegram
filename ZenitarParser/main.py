import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database
from modules.session_manager import SessionManager
from handlers import start, parser, inviter, sender, accounts, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    os.makedirs(config.SESSIONS_DIR, exist_ok=True)
    os.makedirs(config.EXPORTS_DIR, exist_ok=True)

    await database.init_db()
    logger.info("Database ready: %s", config.DB_PATH)

    sm = SessionManager()
    await sm.load_sessions()
    logger.info("Sessions loaded: %d active", len(sm.clients))

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Inject session_manager into all handlers via workflow_data
    dp["session_manager"] = sm

    dp.include_router(start.router)
    dp.include_router(parser.router)
    dp.include_router(inviter.router)
    dp.include_router(sender.router)
    dp.include_router(accounts.router)
    dp.include_router(settings.router)

    logger.info("Bot started. Admin IDs: %s", config.ADMIN_IDS)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await sm.stop_all()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
