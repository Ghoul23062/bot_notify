"""Unit tests for recurring rules calculation and lifecycle."""

import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User
from app.services.reminder_service import (
    calculate_next_occurrence,
    create_new_reminder,
    mark_reminder_completed
)
from app.services.scheduler_service import SchedulerService
from app.utils.datetime_utils import to_utc, to_local, utc_now


def test_calculate_next_occurrence_daily():
    due_utc = datetime.datetime(2026, 8, 15, 12, 0, 0)
    next_utc = calculate_next_occurrence(due_utc, "DAILY", "Europe/Moscow")
    assert next_utc == datetime.datetime(2026, 8, 16, 12, 0, 0)


def test_calculate_next_occurrence_interval_hours():
    due_utc = datetime.datetime(2026, 8, 15, 12, 0, 0)
    next_utc = calculate_next_occurrence(due_utc, "INTERVAL;HOURS=2", "Europe/Moscow")
    assert next_utc == datetime.datetime(2026, 8, 15, 14, 0, 0)


def test_calculate_next_occurrence_workdays():
    # Saturday 15th Aug 2026 -> Next occurrence is Monday 17th Aug 2026
    due_utc = to_utc(datetime.datetime(2026, 8, 15, 8, 30, 0), "Europe/Moscow")
    next_utc = calculate_next_occurrence(due_utc, "WEEKLY;BYDAY=MO,TU,WE,TH,FR", "Europe/Moscow")
    expected_utc = to_utc(datetime.datetime(2026, 8, 17, 8, 30, 0), "Europe/Moscow")
    assert next_utc == expected_utc


@pytest.mark.asyncio
async def test_recurring_completion_advances_date_when_due(test_db_session: AsyncSession, test_user: User):
    # Past due reminder (due now)
    past_due_local = to_local(utc_now(), "Europe/Moscow") - datetime.timedelta(hours=2)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Принимать витамины",
        target_dt_local=past_due_local,
        is_recurring=True,
        recurrence_rule="DAILY"
    )

    old_due_at = reminder.due_at
    updated = await mark_reminder_completed(test_db_session, reminder.id, "Europe/Moscow")
    assert updated.status == "ACTIVE"
    assert updated.due_at > old_due_at


@pytest.mark.asyncio
async def test_daily_reminder_no_double_skip_after_notification(test_db_session: AsyncSession, test_user: User, mock_bot):
    """Verify daily reminder does NOT skip a day when user clicks 'Выполнено' after receiving notification."""
    now_local = to_local(utc_now(), "Europe/Moscow")
    just_due_local = now_local - datetime.timedelta(minutes=1)
    
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Ежедневное дело",
        target_dt_local=just_due_local,
        is_recurring=True,
        recurrence_rule="DAILY"
    )

    # 1. Scheduler runs and sends notification
    scheduler = SchedulerService(bot=mock_bot)
    await scheduler.process_due_reminders(session=test_db_session)
    mock_bot.send_message.assert_called_once()

    # After notification, scheduler scheduled it for tomorrow
    refreshed = await crud.get_reminder_by_id(test_db_session, reminder.id)
    expected_tomorrow_local = just_due_local + datetime.timedelta(days=1)
    expected_tomorrow_utc = to_utc(expected_tomorrow_local, "Europe/Moscow")
    assert refreshed.due_at == expected_tomorrow_utc
    assert refreshed.status == "ACTIVE"

    # 2. User taps "Выполнено" in Telegram
    completed_reminder = await mark_reminder_completed(test_db_session, reminder.id, "Europe/Moscow")
    
    # It must STILL be scheduled for tomorrow, NOT skipped by 2 days!
    assert completed_reminder.due_at == expected_tomorrow_utc
    assert completed_reminder.status == "ACTIVE"
