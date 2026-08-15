"""Handlers for recurring reminders (/repeat) and pause/resume lifecycle controls."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User
from app.utils.datetime_utils import to_local
from app.bot.keyboards.inline import (
    get_reminders_list_keyboard,
    get_main_menu_keyboard,
    NUMBER_EMOJIS
)
from app.bot.keyboards.callbacks import NavigationCallback, ReminderActionCallback

router = Router()


@router.message(Command("repeat"))
async def cmd_repeat(message: Message, user: User, user_tz: str, session: AsyncSession):
    """Handle /repeat command."""
    await show_recurring_reminders(message, user.id, user_tz, session, page=0)


@router.callback_query(NavigationCallback.filter(F.target == "recurring"))
async def nav_recurring(call: CallbackQuery, callback_data: NavigationCallback, user: User, user_tz: str, session: AsyncSession):
    """Show recurring reminders via callback navigation immediately answering query."""
    await call.answer()
    await show_recurring_reminders(call, user.id, user_tz, session, page=callback_data.page)


async def show_recurring_reminders(target, user_id: int, user_tz: str, session: AsyncSession, page: int = 0):
    """Format and display list of recurring reminders with selection buttons."""
    reminders = await crud.get_recurring_reminders_for_user(session, user_id)

    if not reminders:
        msg_text = "🔁 <b>У вас нет повторяющихся напоминаний.</b>\n\nПример создания:\n<i>«Каждый день в 09:00 принимать витамины»</i>"
        if isinstance(target, Message):
            await target.answer(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        else:
            await target.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    per_page = 5
    start_idx = page * per_page
    page_items = reminders[start_idx:start_idx + per_page]

    lines = ["🔁 <b>ПОВТОРЯЮЩИЕСЯ НАПОМИНАНИЯ</b>\n"]

    for idx, r in enumerate(page_items):
        num_icon = NUMBER_EMOJIS[idx] if idx < len(NUMBER_EMOJIS) else f"{idx + 1}."
        due_local = to_local(r.due_at, user_tz)
        time_str = due_local.strftime("%H:%M")
        status_tag = " [⏸ ПРИОСТАНОВЛЕНО]" if r.status == "PAUSED" else ""
        rule_desc = format_rrule_description(r.recurrence_rule, time_str)

        lines.append(f"{num_icon} <b>{rule_desc}</b>{status_tag}\n📌 {r.text}\n")

    lines.append("<i>Выберите номер кнопки ниже для управления:</i>")
    full_text = "\n".join(lines)

    reply_markup = get_reminders_list_keyboard(reminders, page=page, per_page=per_page, nav_target="recurring")

    if isinstance(target, Message):
        await target.answer(full_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.message.edit_text(full_text, parse_mode="HTML", reply_markup=reply_markup)


def format_rrule_description(rule: str, time_str: str) -> str:
    """Format raw rrule string into Russian description."""
    if not rule:
        return f"Повтор в {time_str}"
    if rule == "DAILY":
        return f"Каждый день в {time_str}"
    if rule == "WEEKLY;BYDAY=MO,TU,WE,TH,FR":
        return f"Каждый будний день в {time_str}"
    if rule.startswith("WEEKLY;BYDAY="):
        return f"Каждую неделю ({rule.split('=')[1]}) в {time_str}"
    if rule.startswith("MONTHLY;BYMONTHDAY="):
        dom = rule.split("=")[1]
        return f"Каждое {dom} число месяца в {time_str}"
    if rule.startswith("INTERVAL;HOURS="):
        hrs = rule.split("=")[1]
        return f"Каждые {hrs} ч."
    if rule.startswith("INTERVAL;DAYS="):
        days = rule.split("=")[1]
        return f"Каждые {days} дн. в {time_str}"
    return f"Повтор ({rule}) в {time_str}"


@router.callback_query(ReminderActionCallback.filter(F.action == "toggle_pause"))
async def callback_toggle_pause(call: CallbackQuery, callback_data: ReminderActionCallback, user_tz: str, session: AsyncSession):
    """Pause or resume a recurring reminder."""
    await call.answer("Статус обновлен!")
    reminder = await crud.get_reminder_by_id(session, callback_data.reminder_id)
    if not reminder:
        return

    new_status = "ACTIVE" if reminder.status == "PAUSED" else "PAUSED"
    await crud.update_reminder_status(session, reminder.id, new_status)
    await show_recurring_reminders(call, reminder.user_id, user_tz, session)
