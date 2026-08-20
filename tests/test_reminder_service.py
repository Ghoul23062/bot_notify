"""Unit and integration tests for reminder business logic (CRUD, snooze, completion, context)."""

import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User
from app.services.reminder_service import (
    create_new_reminder,
    mark_reminder_completed,
    snooze_reminder,
    reschedule_last_context_reminder
)
from app.utils.datetime_utils import utc_now, to_utc


@pytest.mark.asyncio
async def test_create_and_fetch_reminder(test_db_session: AsyncSession, test_user: User):
    target_dt_local = datetime.datetime(2026, 8, 16, 15, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Позвонить маме",
        target_dt_local=target_dt_local
    )

    assert reminder.id is not None
    assert reminder.text == "Позвонить маме"
    assert reminder.status == "ACTIVE"
    assert reminder.is_last_context is True

    fetched = await crud.get_reminder_by_id(test_db_session, reminder.id)
    assert fetched is not None
    assert fetched.text == "Позвонить маме"


@pytest.mark.asyncio
async def test_update_reminder_text_and_reschedule(test_db_session: AsyncSession, test_user: User):
    target_dt_local = datetime.datetime(2026, 8, 16, 15, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Старый текст",
        target_dt_local=target_dt_local
    )

    # Update text
    updated_text = await crud.update_reminder_text(test_db_session, reminder.id, "Напомни отключить подписку глово")
    assert updated_text.text == "Напомни отключить подписку глово"

    # Reschedule
    new_due_utc = to_utc(datetime.datetime(2026, 8, 17, 19, 0, 0), "Europe/Moscow")
    updated_due = await crud.update_reminder_due_at(test_db_session, reminder.id, new_due_utc, status="ACTIVE")
    assert updated_due.due_at == new_due_utc


@pytest.mark.asyncio
async def test_snooze_reminder_presets(test_db_session: AsyncSession, test_user: User):
    target_dt_local = datetime.datetime(2026, 8, 16, 15, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Проверить почту",
        target_dt_local=target_dt_local
    )

    # Snooze +15m
    res = await snooze_reminder(test_db_session, reminder.id, "+15m", "Europe/Moscow")
    assert res is not None
    updated, new_local = res
    assert updated.status == "SNOOZED"


@pytest.mark.asyncio
async def test_complete_non_recurring_reminder(test_db_session: AsyncSession, test_user: User):
    target_dt_local = datetime.datetime(2026, 8, 16, 15, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Купить продукты",
        target_dt_local=target_dt_local
    )

    updated = await mark_reminder_completed(test_db_session, reminder.id, "Europe/Moscow")
    assert updated.status == "COMPLETED"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_reschedule_last_context(test_db_session: AsyncSession, test_user: User):
    target_dt_local = datetime.datetime(2026, 8, 16, 15, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Встреча с клиентом",
        target_dt_local=target_dt_local
    )

    new_dt_local = datetime.datetime(2026, 8, 17, 18, 0, 0)
    rescheduled = await reschedule_last_context_reminder(test_db_session, test_user.id, "Europe/Moscow", new_dt_local)

    assert rescheduled is not None
    assert rescheduled.id == reminder.id
