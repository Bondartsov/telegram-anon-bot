"""
M-MAIN: Bot Main Entry Point
=============================
PURPOSE: Application entry point, initialize and run bot
SCOPE: Bot initialization, handler registration, polling
DEPENDS: M-CONFIG, M-DB, M-HANDLER-PRIVATE, M-HANDLER-GROUP, M-HANDLER-CALLBACK
"""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config, setup_logging
from src.database import init_db
from src.handlers.callback import router as callback_router
from src.handlers.callback import show_delete_keyboard
from src.handlers.group import router as group_router
from src.handlers.private import router as private_router
from src.services.rate_limiter import get_rate_limiter

logger = setup_logging(config.LOG_LEVEL)

db = None


def create_bot() -> Bot:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )
    logger.info("[M-MAIN][create_bot][CREATE] Bot instance created")
    return bot


def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(private_router)
    dp.include_router(group_router)
    dp.include_router(callback_router)
    logger.info("[M-MAIN][setup_dispatcher][SETUP] All routers registered")
    return dp


async def db_middleware(handler, event, data):
    data["db"] = db
    return await handler(event, data)


def setup_middleware(dp: Dispatcher) -> None:
    dp.update.middleware(db_middleware)
    logger.info("[M-MAIN][setup_middleware][SETUP] Database middleware configured")


async def shutdown(bot: Bot, dp: Dispatcher) -> None:
    logger.info("[M-MAIN][shutdown][SHUTDOWN] Shutting down...")
    global db
    if db:
        await db.close()
        logger.info("[M-MAIN][shutdown][DB] Database connection closed")
    await bot.session.close()
    logger.info("[M-MAIN][shutdown][BOT] Bot session closed")


async def main() -> None:
    global db

    logger.info("=" * 60)
    logger.info("Telegram Anonymous Questions Bot")
    logger.info("=" * 60)
    logger.info(f"[M-MAIN][main][CONFIG] Rate limit: {config.RATE_LIMIT}/hour")
    logger.info(f"[M-MAIN][main][CONFIG] Log level: {config.LOG_LEVEL}")

    try:
        get_rate_limiter()
        logger.info("[M-MAIN][main][INIT] Rate limiter initialized")

        db = await init_db(config.DB_PATH)
        logger.info("[M-MAIN][main][INIT] Database initialized")

        bot = create_bot()
        dp = setup_dispatcher()
        setup_middleware(dp)

        me = await bot.get_me()
        logger.info(f"[M-MAIN][main][START] Bot started: @{me.username}")

        logger.info("[M-MAIN][main][POLLING] Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except KeyboardInterrupt:
        logger.info("[M-MAIN][main][INTERRUPT] Keyboard interrupt received")

    except Exception as e:
        logger.error(f"[M-MAIN][main][ERROR] Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await shutdown(bot, dp)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")
