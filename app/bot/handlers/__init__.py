"""Router registry for all Telegram bot handler modules."""

from aiogram import Router

from app.bot.handlers.start import router as start_router
from app.bot.handlers.create_reminder import router as create_router
from app.bot.handlers.list_reminders import router as list_router
from app.bot.handlers.recurring import router as recurring_router
from app.bot.handlers.settings import router as settings_router
from app.bot.handlers.reminder_actions import router as actions_router


def setup_routers() -> Router:
    """Combine all routers in priority order."""
    main_router = Router()
    main_router.include_router(start_router)
    main_router.include_router(actions_router)
    main_router.include_router(list_router)
    main_router.include_router(recurring_router)
    main_router.include_router(settings_router)
    main_router.include_router(create_router)  # Freeform fallback text last
    return main_router
