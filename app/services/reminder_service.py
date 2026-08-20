"""Reminder business logic: creation, completion, snooze, context resolution, and recurrence handling."""

import datetime
from typing import Optional, Tuple
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import Reminder, User
from app.utils.datetime_utils import utc_now, to_utc, to_local


def calculate_next_occurrence(
    current_due_utc: datetime.datetime,
    recurrence_rule: str,
    user_tz: str
) -> Optional[datetime.datetime]:
    """
    Calculate the next occurrence UTC datetime for a recurring rule string.
    Supported formats:
      - DAILY
      - WEEKLY;BYDAY=MO,TU,WE,TH,FR
      - MONTHLY;BYMONTHDAY=1
      - INTERVAL;HOURS=2
      - INTERVAL;DAYS=3
    """
    current_due_local = to_local(current_due_utc, user_tz)

    if recurrence_rule == "DAILY":
        next_local = current_due_local + datetime.timedelta(days=1)
        return to_utc(next_local, user_tz)

    if recurrence_rule.startswith("INTERVAL;HOURS="):
        hours = int(recurrence_rule.split("=")[1])
        next_local = current_due_local + datetime.timedelta(hours=hours)
        return to_utc(next_local, user_tz)

    if recurrence_rule.startswith("INTERVAL;DAYS="):
        days = int(recurrence_rule.split("=")[1])
        next_local = current_due_local + datetime.timedelta(days=days)
        return to_utc(next_local, user_tz)

    if recurrence_rule.startswith("MONTHLY;BYMONTHDAY="):
        dom = int(recurrence_rule.split("=")[1])
        next_local = current_due_local + relativedelta(months=1)
        try:
            next_local = next_local.replace(day=dom)
        except ValueError:
            pass  # Fall back to end of month
        return to_utc(next_local, user_tz)

    if recurrence_rule.startswith("WEEKLY;BYDAY="):
        days_str = recurrence_rule.split("=")[1]
        day_codes = days_str.split(",")
        code_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        target_weekdays = [code_map[c] for c in day_codes if c in code_map]

        if not target_weekdays:
            next_local = current_due_local + datetime.timedelta(days=1)
            return to_utc(next_local, user_tz)

        next_local = current_due_local + datetime.timedelta(days=1)
        while next_local.weekday() not in target_weekdays:
            next_local += datetime.timedelta(days=1)

        return to_utc(next_local, user_tz)

    # Fallback to +1 day if unknown rule
    return to_utc(current_due_local + datetime.timedelta(days=1), user_tz)


async def create_new_reminder(
    session: AsyncSession,
    user: User,
    text: str,
    target_dt_local: datetime.datetime,
    is_recurring: bool = False,
    recurrence_rule: Optional[str] = None
) -> Reminder:
    """Convert local target datetime to UTC and insert new Reminder record."""
    tz_name = user.settings.timezone if user.settings else "Europe/Moscow"
    due_at_utc = to_utc(target_dt_local, tz_name)

    return await crud.create_reminder(
        session=session,
        user_id=user.id,
        text=text,
        due_at=due_at_utc,
        timezone=tz_name,
        is_recurring=is_recurring,
        recurrence_rule=recurrence_rule
    )


async def mark_reminder_completed(session: AsyncSession, reminder_id: int, user_tz: str) -> Optional[Reminder]:
    """
    Mark reminder completed. If recurring, ensure next occurrence is scheduled.
    Avoids double-advancing if scheduler already advanced due_at upon delivery.
    """
    reminder = await crud.get_reminder_by_id(session, reminder_id)
    if not reminder:
        return None

    now_utc = utc_now()

    if reminder.is_recurring and reminder.recurrence_rule:
        # If due_at is already in the future and active (i.e. scheduler already advanced it upon sending notification)
        if reminder.due_at > now_utc and reminder.status == "ACTIVE":
            reminder.completed_at = now_utc
            await session.commit()
            return reminder

        # If due_at is in the past, currently due, or snoozed, advance to next occurrence
        next_due_utc = calculate_next_occurrence(reminder.due_at, reminder.recurrence_rule, user_tz)
        if next_due_utc:
            # Check if recurrence end date reached
            if reminder.recurrence_end_at and next_due_utc > reminder.recurrence_end_at:
                return await crud.update_reminder_status(session, reminder_id, "COMPLETED")
            else:
                return await crud.update_reminder_due_at(session, reminder_id, next_due_utc, status="ACTIVE")

    return await crud.update_reminder_status(session, reminder_id, "COMPLETED")


async def snooze_reminder(
    session: AsyncSession,
    reminder_id: int,
    preset: str,
    user_tz: str
) -> Optional[Tuple[Reminder, datetime.datetime]]:
    """
    Snooze reminder by preset ('+5m', '+15m', '+30m', '+1h', '+3h', 'tomorrow') or return None.
    Returns (updated_reminder, new_due_local).
    """
    reminder = await crud.get_reminder_by_id(session, reminder_id)
    if not reminder:
        return None

    now_utc = utc_now()
    now_local = to_local(now_utc, user_tz)

    delta = None
    if preset == "+5m":
        delta = datetime.timedelta(minutes=5)
    elif preset == "+15m":
        delta = datetime.timedelta(minutes=15)
    elif preset == "+30m":
        delta = datetime.timedelta(minutes=30)
    elif preset == "+1h":
        delta = datetime.timedelta(hours=1)
    elif preset == "+3h":
        delta = datetime.timedelta(hours=3)
    elif preset == "tomorrow":
        # Tomorrow at same hour/minute or 09:00 if past
        tmr = now_local + datetime.timedelta(days=1)
        new_due_local = tmr.replace(hour=9, minute=0, second=0, microsecond=0)
        new_due_utc = to_utc(new_due_local, user_tz)
        updated = await crud.update_reminder_due_at(session, reminder_id, new_due_utc, status="SNOOZED")
        return updated, new_due_local

    if delta:
        new_due_local = now_local + delta
        new_due_utc = to_utc(new_due_local, user_tz)
        updated = await crud.update_reminder_due_at(session, reminder_id, new_due_utc, status="SNOOZED")
        return updated, new_due_local

    return None


async def reschedule_last_context_reminder(
    session: AsyncSession,
    user_id: int,
    user_tz: str,
    new_dt_local: datetime.datetime
) -> Optional[Reminder]:
    """Reschedule the latest active reminder in user context ('перенеси на завтра')."""
    last_rem = await crud.get_last_context_reminder(session, user_id)
    if not last_rem:
        return None

    new_due_utc = to_utc(new_dt_local, user_tz)
    return await crud.update_reminder_due_at(session, last_rem.id, new_due_utc, status="ACTIVE")
