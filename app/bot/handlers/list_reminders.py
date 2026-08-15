"""Handlers for viewing active reminders list (/list) and today's schedule (/today)."""

import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User
from app.utils.datetime_utils import utc_now, to_local
from app.bot.keyboards.inline import (
    get_reminder_item_keyboard,
    get_back_to_menu_keyboard,
    get_main_menu_keyboard
)
from app.bot.keyboards.callbacks import NavigationCallback, ReminderActionCallback

router = Router()


@router.message(Command("list"))
async def cmd_list(message: Message, user: User, user_tz: str, session: AsyncSession):
    """Handle /list command."""
    await show_reminders_list(message, user.id, user_tz, session)


@router.message(Command("today"))
async def cmd_today(message: Message, user: User, user_tz: str, session: AsyncSession):
    """Handle /today command."""
    await show_today_reminders(message, user.id, user_tz, session)


@router.callback_query(NavigationCallback.filter(F.target == "list"))
async def nav_list(call: CallbackQuery, user: User, user_tz: str, session: AsyncSession):
    """Show active reminders via callback navigation."""
    await show_reminders_list(call, user.id, user_tz, session)
    await call.answer()


@router.callback_query(NavigationCallback.filter(F.target == "today"))
async def nav_today(call: CallbackQuery, user: User, user_tz: str, session: AsyncSession):
    """Show today's reminders via callback navigation."""
    await show_today_reminders(call, user.id, user_tz, session)
    await call.answer()


async def show_reminders_list(target, user_id: int, user_tz: str, session: AsyncSession):
    """Format and send active reminders list."""
    reminders = await crud.get_active_reminders_for_user(session, user_id)

    if not reminders:
        msg_text = "📋 <b>У вас нет активных напоминаний.</b>\n\nЧтобы создать новое, просто напишите мне!"
        if isinstance(target, Message):
            await target.answer(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        else:
            await target.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    now_local = to_local(utc_now(), user_tz)
    today_date = now_local.date()
    tmr_date = today_date + datetime.timedelta(days=1)

    today_items = []
    tmr_items = []
    later_items = []

    for r in reminders:
        due_local = to_local(r.due_at, user_tz)
        r_date = due_local.date()
        time_str = due_local.strftime("%H:%M")
        item_str = f"🔔 {time_str} — {r.text}"

        if r_date == today_date:
            today_items.append((r, item_str))
        elif r_date == tmr_date:
            tmr_items.append((r, item_str))
        else:
            date_str = due_local.strftime("%d.%m")
            later_items.append((r, f"🔔 {date_str} {time_str} — {r.text}"))

    lines = ["📋 <b>МОИ НАПОМИНАНИЯ</b>\n"]

    if today_items:
        lines.append("<b>Сегодня:</b>")
        for r, item_str in today_items:
            lines.append(item_str)
        lines.append("")

    if tmr_items:
        lines.append("<b>Завтра:</b>")
        for r, item_str in tmr_items:
            lines.append(item_str)
        lines.append("")

    if later_items:
        lines.append("<b>Позже:</b>")
        for r, item_str in later_items:
            lines.append(item_str)
        lines.append("")

    lines.append("<i>Для управления нажмите /list или выберите действие под уведомлением.</i>")
    full_text = "\n".join(lines)

    # For the first item, provide action buttons for quick interaction
    first_rem_id = reminders[0].id
    reply_markup = get_reminder_item_keyboard(first_rem_id)

    if isinstance(target, Message):
        await target.answer(full_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.message.edit_text(full_text, parse_mode="HTML", reply_markup=reply_markup)


async def show_today_reminders(target, user_id: int, user_tz: str, session: AsyncSession):
    """Format and send today's reminders."""
    reminders = await crud.get_today_reminders_for_user(session, user_id, user_tz)

    if not reminders:
        msg_text = "📅 <b>На сегодня напоминаний нет!</b>\n\nОтличный повод отдохнуть или запланировать новое."
        if isinstance(target, Message):
            await target.answer(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        else:
            await target.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    lines = ["📅 <b>НАПОМИНАНИЯ НА СЕГОДНЯ:</b>\n"]
    for r in reminders:
        due_local = to_local(r.due_at, user_tz)
        time_str = due_local.strftime("%H:%M")
        lines.append(f"🔔 <b>{time_str}</b> — {r.text}")

    full_text = "\n".join(lines)
    reply_markup = get_reminder_item_keyboard(reminders[0].id)

    if isinstance(target, Message):
        await target.answer(full_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.message.edit_text(full_text, parse_mode="HTML", reply_markup=reply_markup)
