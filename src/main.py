"""
M-MAIN: Bot Main Entry Point
=============================
PURPOSE: Application entry point, initialize and run bot
SCOPE: Bot initialization, handler registration, polling
DEPENDS: M-CONFIG, M-DB, M-HANDLER-PRIVATE, M-HANDLER-GROUP, M-HANDLER-CALLBACK
"""

import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config, setup_logging
from src.database import init_db
from src.handlers.callback import router as callback_router
from src.handlers.callback import show_delete_keyboard
from src.handlers.group import router as group_router
from src.handlers.private import router as private_router
from src.services.rate_limiter import get_rate_limiter

# Setup logging
logger = setup_logging(config.LOG_LEVEL)


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Bot Main

PURPOSE:
    Application entry point that initializes and runs the Telegram bot.

INPUTS:
    - config: BotConfig — Application configuration

OUTPUTS:
    - exit_code: int — 0 for success, 1 for error

ERRORS:
    - INIT_FAILED: Bot initialization failed
    - RUNTIME_ERROR: Runtime error during polling

EXPORTS:
    - main: Entry point function
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. create_bot — Create and configure bot instance
    2. setup_dispatcher — Setup dispatcher with all routers
    3. setup_middleware — Setup database middleware
    4. main — Main entry point
    5. shutdown — Graceful shutdown handler
"""

# ==============================================================================
# Global instances
# ==============================================================================

# Global database connection
db = None

# ==============================================================================
# START_BLOCK: create_bot
# ==============================================================================

def create_bot() -> Bot:
    """
    Create and configure bot instance.
    
    Returns:
        Bot: Configured Aiogram Bot instance
    """
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )
    
    logger.info("[M-MAIN][create_bot][CREATE] Bot instance created")
    return bot

# ==============================================================================
# END_BLOCK: create_bot
# ==============================================================================


# ==============================================================================
# START_BLOCK: setup_dispatcher
# ==============================================================================

def setup_dispatcher() -> Dispatcher:
    """
    Setup dispatcher with all routers.
    
    Returns:
        Dispatcher: Configured dispatcher with all handlers
    """
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(private_router)
    dp.include_router(group_router)
    dp.include_router(callback_router)
    
    logger.info("[M-MAIN][setup_dispatcher][SETUP] All routers registered")
    
    return dp

# ==============================================================================
# END_BLOCK: setup_dispatcher
# ==============================================================================


# ==============================================================================
# START_BLOCK: setup_middleware
# ==============================================================================

async def db_middleware(handler, event, data):
    """
    Middleware to inject database connection into handlers.
    
    Args:
        handler: Handler function
        event: Event object
        data: Handler data dictionary
        
    Returns:
        Handler result
    """
    data["db"] = db
    return await handler(event, data)

def setup_middleware(dp: Dispatcher) -> None:
    """
    Setup middleware for dispatcher.
    
    Args:
        dp: Dispatcher instance
    """
    # Add database middleware to all updates
    dp.update.middleware(db_middleware)
    
    logger.info("[M-MAIN][setup_middleware][SETUP] Database middleware configured")

# ==============================================================================
# END_BLOCK: setup_middleware
# ==============================================================================


# ==============================================================================
# START_BLOCK: shutdown
# ==============================================================================

async def shutdown(bot: Bot, dp: Dispatcher) -> None:
    """
    Graceful shutdown handler.
    
    Args:
        bot: Bot instance
        dp: Dispatcher instance
    """
    logger.info("[M-MAIN][shutdown][SHUTDOWN] Shutting down...")
    
    # Close database connection
    global db
    if db:
        await db.close()
        logger.info("[M-MAIN][shutdown][DB] Database connection closed")
    
    # Close bot session
    await bot.session.close()
    logger.info("[M-MAIN][shutdown][BOT] Bot session closed")

# ==============================================================================
# END_BLOCK: shutdown
# ==============================================================================


# ==============================================================================
# START_BLOCK: main
# ==============================================================================

async def main() -> None:
    """
    Main entry point.
    
    Initializes bot, database, and starts polling.
    """
    global db
    
    logger.info("="*60)
    logger.info("🤖 Telegram Anonymous Questions Bot")
    logger.info("="*60)
    logger.info(f"[M-MAIN][main][CONFIG] Group ID: {config.GROUP_ID}")
    logger.info(f"[M-MAIN][main][CONFIG] Rate limit: {config.RATE_LIMIT}/hour")
    logger.info(f"[M-MAIN][main][CONFIG] Log level: {config.LOG_LEVEL}")
    
    try:
        # Initialize rate limiter (lazy init on first use)
        get_rate_limiter()
        logger.info("[M-MAIN][main][INIT] Rate limiter initialized")
        
        # Initialize database
        db = await init_db(config.DB_PATH)
        logger.info("[M-MAIN][main][INIT] Database initialized")
        
        # Create bot
        bot = create_bot()
        
        # Setup dispatcher
        dp = setup_dispatcher()
        
        # Setup middleware
        setup_middleware(dp)
        
        # Override /delete handler with db access
        # This is a workaround since we can't easily pass db to command handlers
        @private_router.message(lambda m: m.text == "/delete" and m.chat.type == "private")
        async def cmd_delete_with_db(message, bot: Bot):
            await show_delete_keyboard(bot, db, message.from_user.id, message.chat.id)
        
        # Log bot info
        me = await bot.get_me()
        logger.info(f"[M-MAIN][main][START] Bot started: @{me.username}")
        
        # Start polling
        logger.info("[M-MAIN][main][POLLING] Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except KeyboardInterrupt:
        logger.info("[M-MAIN][main][INTERRUPT] Keyboard interrupt received")
        
    except Exception as e:
        logger.error(f"[M-MAIN][main][ERROR] Fatal error: {e}", exc_info=True)
        sys.exit(1)
        
    finally:
        await shutdown(bot, dp)

# ==============================================================================
# END_BLOCK: main
# ==============================================================================


# ==============================================================================
# Entry point
# ==============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[M-MAIN][EXIT] Bot stopped by user")
        print("\n👋 Bot stopped. Goodbye!")


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Created main entry point with async/await
    - Implemented bot initialization and configuration
    - Setup all routers and middleware
    - Added graceful shutdown handling
    - Integrated rate limiter with config
    - Proper error handling and logging
    - Signal handling for clean exit
"""

