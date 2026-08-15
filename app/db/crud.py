"""Database CRUD operations for bot_notify."""

import datetime
from typing import Optional, List, Sequence
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User, UserSettings, Reminder, ReminderSchedule, Notification
from app.utils.datetime_utils import utc_now, to_utc, to_local


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    default_tz: str = "Europe/Moscow"
) -> User:
    """Fetch user by Telegram ID or create new user with default settings."""
    stmt = select(User).options(selectinload(User.settings)).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            created_at=utc_now()
        )
        session.add(user)
        await session.flush()

        settings = UserSettings(
            user_id=user.id,
            timezone=default_tz,
            language="ru",
            time_format="24h"
        )
        session.add(settings)
        await session.commit()
        
        # Refresh with settings loaded
        result = await session.execute(stmt)
        user = result.scalar_one()
    else:
        # Update username / first_name if changed
        if user.username != username or user.first_name != first_name:
            user.username = username
            user.first_name = first_name
            await session.commit()

    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Fetch user by Telegram ID with settings loaded."""
    stmt = select(User).options(selectinload(User.settings)).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_settings(session: AsyncSession, user_id: int, **kwargs) -> UserSettings:
    """Update UserSettings fields dynamically."""
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    result = await session.execute(stmt)
    settings = result.scalar_one()

    for key, value in kwargs.items():
        if hasattr(settings, key) and value is not None:
            setattr(settings, key, value)

    await session.commit()
    return settings


async def create_reminder(
    session: AsyncSession,
    user_id: int,
    text: str,
    due_at: datetime.datetime,
    timezone: str = "Europe/Moscow",
    is_recurring: bool = False,
    recurrence_rule: Optional[str] = None,
    recurrence_end_at: Optional[datetime.datetime] = None
) -> Reminder:
    """Create a new reminder and update user's last context marker."""
    # Reset existing context markers for user
    await session.execute(
        update(Reminder)
        .where(Reminder.user_id == user_id)
        .values(is_last_context=False)
    )

    reminder = Reminder(
        user_id=user_id,
        text=text,
        due_at=due_at,
        timezone=timezone,
        status="ACTIVE",
        is_recurring=is_recurring,
        recurrence_rule=recurrence_rule,
        recurrence_end_at=recurrence_end_at,
        is_last_context=True,
        created_at=utc_now(),
        updated_at=utc_now()
    )
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def get_reminder_by_id(session: AsyncSession, reminder_id: int) -> Optional[Reminder]:
    """Get single reminder by ID with user loaded."""
    stmt = select(Reminder).options(selectinload(Reminder.user)).where(Reminder.id == reminder_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_reminders_for_user(
    session: AsyncSession,
    user_id: int,
    limit: int = 50,
    offset: int = 0
) -> Sequence[Reminder]:
    """Get active non-recurring and recurring reminders ordered by due_at."""
    stmt = (
        select(Reminder)
        .where(
            and_(
                Reminder.user_id == user_id,
                Reminder.status.in_(["ACTIVE", "SNOOZED"])
            )
        )
        .order_by(Reminder.due_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_today_reminders_for_user(
    session: AsyncSession,
    user_id: int,
    user_tz: str
) -> Sequence[Reminder]:
    """Get reminders scheduled for user's today."""
    now_utc = utc_now()
    now_local = to_local(now_utc, user_tz)
    
    start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_of_day_utc = to_utc(start_of_day_local, user_tz)
    end_of_day_utc = to_utc(end_of_day_local, user_tz)

    stmt = (
        select(Reminder)
        .where(
            and_(
                Reminder.user_id == user_id,
                Reminder.status.in_(["ACTIVE", "SNOOZED"]),
                Reminder.due_at >= start_of_day_utc,
                Reminder.due_at <= end_of_day_utc
            )
        )
        .order_by(Reminder.due_at.asc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_recurring_reminders_for_user(
    session: AsyncSession,
    user_id: int
) -> Sequence[Reminder]:
    """Get all recurring reminders (active or paused) for user."""
    stmt = (
        select(Reminder)
        .where(
            and_(
                Reminder.user_id == user_id,
                Reminder.is_recurring == True,
                Reminder.status.in_(["ACTIVE", "PAUSED", "SNOOZED"])
            )
        )
        .order_by(Reminder.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_reminder_status(
    session: AsyncSession,
    reminder_id: int,
    status: str
) -> Optional[Reminder]:
    """Update reminder status (COMPLETED, CANCELLED, ACTIVE, PAUSED, etc.)."""
    reminder = await get_reminder_by_id(session, reminder_id)
    if reminder:
        reminder.status = status
        reminder.updated_at = utc_now()
        if status == "COMPLETED":
            reminder.completed_at = utc_now()
        await session.commit()
    return reminder


async def update_reminder_due_at(
    session: AsyncSession,
    reminder_id: int,
    new_due_at: datetime.datetime,
    status: str = "ACTIVE"
) -> Optional[Reminder]:
    """Update reminder's due_at timestamp and reset status."""
    reminder = await get_reminder_by_id(session, reminder_id)
    if reminder:
        reminder.due_at = new_due_at
        reminder.status = status
        reminder.updated_at = utc_now()
        await session.commit()
    return reminder


async def update_reminder_text(
    session: AsyncSession,
    reminder_id: int,
    new_text: str
) -> Optional[Reminder]:
    """Update text of a reminder."""
    reminder = await get_reminder_by_id(session, reminder_id)
    if reminder:
        reminder.text = new_text
        reminder.updated_at = utc_now()
        await session.commit()
    return reminder


async def delete_reminder(session: AsyncSession, reminder_id: int) -> bool:
    """Delete a reminder from DB."""
    stmt = delete(Reminder).where(Reminder.id == reminder_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def get_last_context_reminder(session: AsyncSession, user_id: int) -> Optional[Reminder]:
    """Get the latest reminder referenced or created by user."""
    stmt = (
        select(Reminder)
        .where(
            and_(
                Reminder.user_id == user_id,
                Reminder.is_last_context == True,
                Reminder.status.in_(["ACTIVE", "SNOOZED"])
            )
        )
        .order_by(Reminder.updated_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_last_context_reminder(session: AsyncSession, user_id: int, reminder_id: int):
    """Mark specific reminder as current context target."""
    await session.execute(
        update(Reminder)
        .where(Reminder.user_id == user_id)
        .values(is_last_context=False)
    )
    await session.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(is_last_context=True, updated_at=utc_now())
    )
    await session.commit()


async def get_due_reminders(session: AsyncSession, current_utc_time: datetime.datetime) -> Sequence[Reminder]:
    """
    Find active or snoozed reminders whose due_at is <= current_utc_time.
    Loads associated User and UserSettings.
    """
    stmt = (
        select(Reminder)
        .options(
            selectinload(Reminder.user).selectinload(User.settings)
        )
        .where(
            and_(
                Reminder.status.in_(["ACTIVE", "SNOOZED"]),
                Reminder.due_at <= current_utc_time
            )
        )
        .order_by(Reminder.due_at.asc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_notification_log(
    session: AsyncSession,
    reminder_id: int,
    user_id: int,
    scheduled_at: datetime.datetime,
    status: str,
    error_message: Optional[str] = None
) -> Notification:
    """Record notification delivery log in DB."""
    notification = Notification(
        reminder_id=reminder_id,
        user_id=user_id,
        scheduled_at=scheduled_at,
        sent_at=utc_now() if status == "SENT" else None,
        status=status,
        error_message=error_message
    )
    session.add(notification)
    await session.commit()
    return notification
