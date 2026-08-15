"""Main application entrypoint initializing Bot, DB, Middlewares, and Background Scheduler."""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.utils.logging import setup_logging
from app.db.database import init_db
from app.bot.middlewares.db_middleware import DbSessionMiddleware
from app.bot.middlewares.user_middleware import UserMiddleware
from app.bot.handlers import setup_routers
from app.services.scheduler_service import SchedulerService

logger = logging.getLogger("app.main")


async def main():
    """Application async entrypoint."""
    setup_logging()
    logger.info("Initializing bot_notify application...")

    # Initialize Database tables if not existing
    await init_db()
    logger.info("Database initialized.")

    # Initialize Bot and Dispatcher
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Register Middlewares
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserMiddleware())

    # Include Routers
    main_router = setup_routers()
    dp.include_router(main_router)

    # Initialize and start background scheduler service
    scheduler = SchedulerService(bot=bot)
    await scheduler.start()

    try:
        # Clear webhook and old updates queue
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting Telegram Bot long polling loop...")
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down bot_notify application...")
        await scheduler.stop()
        await bot.session.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution interrupted by user.")
