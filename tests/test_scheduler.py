"""Unit tests for background scheduler and duplicate notification prevention."""

import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.db import crud
from app.db.models import User
from app.services.reminder_service import create_new_reminder
from app.services.scheduler_service import SchedulerService


@pytest.mark.asyncio
async def test_scheduler_processes_due_reminders(test_db_session: AsyncSession, test_user: User, mock_bot):
    past_dt_local = datetime.datetime(2026, 8, 15, 10, 0, 0)
    reminder = await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Срочная задача",
        target_dt_local=past_dt_local
    )

    scheduler = SchedulerService(bot=mock_bot)
    await scheduler.process_due_reminders(session=test_db_session)

    mock_bot.send_message.assert_called_once()
    
    fetched = await crud.get_reminder_by_id(test_db_session, reminder.id)
    assert fetched.status == "COMPLETED"


@pytest.mark.asyncio
async def test_scheduler_no_duplicate_notifications(test_db_session: AsyncSession, test_user: User, mock_bot):
    past_dt_local = datetime.datetime(2026, 8, 15, 10, 0, 0)
    await create_new_reminder(
        session=test_db_session,
        user=test_user,
        text="Одноразовое сообщение",
        target_dt_local=past_dt_local
    )

    scheduler = SchedulerService(bot=mock_bot)
    
    # First tick processes the reminder
    await scheduler.process_due_reminders(session=test_db_session)
    assert mock_bot.send_message.call_count == 1

    # Second tick immediately afterwards finds 0 due reminders because status is COMPLETED
    await scheduler.process_due_reminders(session=test_db_session)
    assert mock_bot.send_message.call_count == 1  # count remains 1
