"""Unit tests for recurring rules calculation and lifecycle."""

import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.reminder_service import (
    calculate_next_occurrence,
    create_new_reminder,
    mark_reminder_completed
)
from app.utils.datetime_utils import to_utc


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
async def test_recurring_completion_advances_date(test_db_session: AsyncSession, test_user: User):
    target_dt_local = datetime.datetime(2026, 8, 15, 20, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Принимать витамины",
        target_dt_local=target_dt_local,
        is_recurring=True,
        recurrence_rule="DAILY"
    )

    old_due_at = reminder.due_at
    updated = await mark_reminder_completed(test_db_session, reminder.id, "Europe/Moscow")
    assert updated.status == "ACTIVE"
    assert updated.due_at > old_due_at
