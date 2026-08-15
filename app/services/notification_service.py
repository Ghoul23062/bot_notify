"""Notification delivery service with quiet hours support and Telegram API handling."""

import logging
import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import Reminder, User
from app.utils.datetime_utils import to_local, is_in_quiet_hours, adjust_for_quiet_hours, utc_now, to_utc
from app.bot.keyboards.inline import get_notification_actions_keyboard

logger = logging.getLogger(__name__)


async def deliver_reminder_notification(
    bot: Bot,
    session: AsyncSession,
    reminder: Reminder,
    user: User
) -> bool:
    """
    Deliver reminder notification to Telegram user.
    Checks quiet hours and handles errors.
    """
    settings = user.settings
    user_tz = settings.timezone if settings else "Europe/Moscow"
    now_utc = utc_now()
    now_local = to_local(now_utc, user_tz)

    # Check quiet hours
    disable_sound = False
    if settings and settings.quiet_hours_enabled:
        if is_in_quiet_hours(now_local, settings.quiet_start, settings.quiet_end):
            if settings.quiet_action == "delay":
                # Shift due_at to end of quiet hours
                shifted_local = adjust_for_quiet_hours(now_local, settings.quiet_end)
                shifted_utc = to_utc(shifted_local, user_tz)
                await crud.update_reminder_due_at(session, reminder.id, shifted_utc, status="ACTIVE")
                logger.info(f"Reminder {reminder.id} shifted to quiet_end: {shifted_local}")
                return True
            else:  # "silent"
                disable_sound = True

    due_local = to_local(reminder.due_at, user_tz)
    time_str = due_local.strftime("%H:%M")

    text_msg = (
        f"🔔 <b>НАПОМИНАНИЕ</b>\n\n"
        f"{reminder.text}\n\n"
        f"⏰ {time_str}"
    )

    reply_markup = get_notification_actions_keyboard(reminder.id)

    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text_msg,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_notification=disable_sound
        )
        # Log successful delivery
        await crud.create_notification_log(
            session=session,
            reminder_id=reminder.id,
            user_id=user.id,
            scheduled_at=reminder.due_at,
            status="SENT"
        )
        return True
    except TelegramAPIError as e:
        logger.error(f"Failed to send Telegram notification for reminder {reminder.id}: {e}")
        await crud.create_notification_log(
            session=session,
            reminder_id=reminder.id,
            user_id=user.id,
            scheduled_at=reminder.due_at,
            status="FAILED",
            error_message=str(e)
        )
        return False
