"""Persistent background scheduler for querying and dispatching due reminders."""

import asyncio
import logging
from typing import Optional
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.db import crud
from app.utils.datetime_utils import utc_now
from app.services.notification_service import deliver_reminder_notification
from app.services.reminder_service import calculate_next_occurrence

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self._task: asyncio.Task = None
        self._running = False

    async def start(self):
        """Start background scheduler polling loop."""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Background reminder scheduler started.")

    async def stop(self):
        """Stop background scheduler cleanly."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background reminder scheduler stopped.")

    async def _poll_loop(self):
        """Periodic loop to fetch and process due reminders from DB."""
        while self._running:
            try:
                await self.process_due_reminders()
            except Exception as e:
                logger.error(f"Error during scheduler processing loop: {e}", exc_info=True)
            await asyncio.sleep(settings.scheduler_poll_interval)

    async def process_due_reminders(self, session: Optional[AsyncSession] = None):
        """Query due items, lock them, send notifications, and handle recurrences."""
        if session is not None:
            await self._process_with_session(session)
        else:
            async with AsyncSessionLocal() as db_session:
                await self._process_with_session(db_session)

    async def _process_with_session(self, session: AsyncSession):
        now_utc = utc_now()
        due_reminders = await crud.get_due_reminders(session, now_utc)

        if not due_reminders:
            return

        logger.info(f"Found {len(due_reminders)} due reminders to process.")

        for reminder in due_reminders:
            user = reminder.user
            user_tz = user.settings.timezone if (user and user.settings) else "Europe/Moscow"

            old_status = reminder.status
            reminder.status = "PROCESSING"
            await session.commit()

            sent_success = await deliver_reminder_notification(
                bot=self.bot,
                session=session,
                reminder=reminder,
                user=user
            )

            if reminder.is_recurring and reminder.recurrence_rule:
                next_due = calculate_next_occurrence(reminder.due_at, reminder.recurrence_rule, user_tz)
                if next_due and (not reminder.recurrence_end_at or next_due <= reminder.recurrence_end_at):
                    await crud.update_reminder_due_at(session, reminder.id, next_due, status="ACTIVE")
                else:
                    await crud.update_reminder_status(session, reminder.id, "COMPLETED")
            else:
                if sent_success:
                    await crud.update_reminder_status(session, reminder.id, "COMPLETED")
                else:
                    await crud.update_reminder_status(session, reminder.id, old_status)
