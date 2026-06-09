import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent, BotCommand

import config
import database
from utils.logger import setup_logging
from modules.session_manager import SessionManager
from modules.account_pool import AccountPool
from modules.scheduler import start_scheduler, stop_scheduler
from handlers import start, parser, audience, inviter, sender, accounts, profile, settings, blacklist, scheduler

logger = logging.getLogger(__name__)


def _build_storage():
    if config.REDIS_URL:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            logger.info("Using RedisStorage for FSM")
            return RedisStorage.from_url(config.REDIS_URL)
        except Exception as e:
            logger.warning("Redis unavailable (%s), falling back to MemoryStorage", e)
    return MemoryStorage()


async def main():
    setup_logging()

    problems = config.validate()
    if problems:
        logger.error("Configuration errors:\n  - %s", "\n  - ".join(problems))
        logger.error("Заполните .env файл и перезапустите. См. README.md")
        sys.exit(1)

    for d in (config.SESSIONS_DIR, config.EXPORTS_DIR, config.UPLOADS_DIR, config.LOGS_DIR):
        os.makedirs(d, exist_ok=True)

    await database.init_db()
    logger.info("Database ready: %s", config.DB_PATH)

    sm = SessionManager()
    await sm.load_sessions()
    pool = AccountPool(sm)
    await pool.sync()
    logger.info("Sessions loaded: %d active", len(sm.clients))

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )
    dp = Dispatcher(storage=_build_storage())

    # Dependency injection into all handlers
    dp["session_manager"] = sm
    dp["account_pool"] = pool

    dp.include_router(start.router)
    dp.include_router(parser.router)
    dp.include_router(audience.router)
    dp.include_router(inviter.router)
    dp.include_router(sender.router)
    dp.include_router(accounts.router)
    dp.include_router(profile.router)
    dp.include_router(settings.router)
    dp.include_router(blacklist.router)
    dp.include_router(scheduler.router)

    @dp.error()
    async def on_error(event: ErrorEvent):
        logger.exception("Unhandled error: %s", event.exception)
        return True

    await bot.set_my_commands([
        BotCommand(command="menu", description="🚀 Панель управления"),
        BotCommand(command="cancel", description="✖️ Отменить действие"),
        BotCommand(command="help", description="ℹ️ Помощь"),
    ])

    me = await bot.get_me()
    logger.info("Bot @%s started. Admins: %s", me.username, config.ADMIN_IDS)

    start_scheduler(pool, bot)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        stop_scheduler()
        await sm.stop_all()
        await bot.session.close()
        logger.info("Bot stopped gracefully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
