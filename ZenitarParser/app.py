import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

import db
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from handlers.common import router as common_router
from handlers.accounts import router as accounts_router
from handlers.parser import router as parser_router
from handlers.results import router as results_router
from handlers.inviter import router as inviter_router
from handlers.mailer import router as mailer_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("zenitar.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

dp.include_routers(
    common_router,
    accounts_router,
    parser_router,
    results_router,
    inviter_router,
    mailer_router,
)


async def main():
    log.info("ZenitarParser Pro starting…")
    if API_ID == 123 or not API_HASH.strip() or not BOT_TOKEN.strip():
        log.error("Заполни config.py: API_ID, API_HASH, BOT_TOKEN, ADMIN_ID")
        return
    log.info(f"Admin ID: {ADMIN_ID}")
    await db.init()
    log.info("Database initialised")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
