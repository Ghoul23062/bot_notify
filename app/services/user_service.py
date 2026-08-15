"""User service for registration, profile, and user settings management."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User, UserSettings
from app.utils.datetime_utils import get_tz


async def get_or_register_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None
) -> User:
    """Ensure user exists in DB and return User object with settings."""
    return await crud.get_or_create_user(session, telegram_id, username, first_name)


async def set_user_timezone(session: AsyncSession, user_id: int, tz_name: str) -> bool:
    """Validate and set user's preferred timezone string."""
    try:
        get_tz(tz_name)
    except Exception:
        return False
    await crud.update_user_settings(session, user_id, timezone=tz_name)
    return True


async def set_user_quiet_hours(
    session: AsyncSession,
    user_id: int,
    enabled: bool,
    start: Optional[str] = "23:00",
    end: Optional[str] = "07:00",
    action: str = "silent"
) -> UserSettings:
    """Configure user quiet hours."""
    return await crud.update_user_settings(
        session,
        user_id,
        quiet_hours_enabled=enabled,
        quiet_start=start,
        quiet_end=end,
        quiet_action=action
    )
