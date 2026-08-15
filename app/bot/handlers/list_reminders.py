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
    get_reminders_list_keyboard,
    get_back_to_menu_keyboard,
    get_main_menu_keyboard,
    NUMBER_EMOJIS
)
from app.bot.keyboards.callbacks import NavigationCallback

router = Router()


@router.message(Command("list"))
async def cmd_list(message: Message, user: User, user_tz: str, session: AsyncSession):
    """Handle /list command."""
    await show_reminders_list(message, user.id, user_tz, session, page=0)


@router.message(Command("today"))
async def cmd_today(message: Message, user: User, user_tz: str, session: AsyncSession):
    """Handle /today command."""
    await show_today_reminders(message, user.id, user_tz, session, page=0)


@router.callback_query(NavigationCallback.filter(F.target == "list"))
async def nav_list(call: CallbackQuery, callback_data: NavigationCallback, user: User, user_tz: str, session: AsyncSession):
    """Show active reminders via callback navigation immediately answering query."""
    await call.answer()
    await show_reminders_list(call, user.id, user_tz, session, page=callback_data.page)


@router.callback_query(NavigationCallback.filter(F.target == "today"))
async def nav_today(call: CallbackQuery, callback_data: NavigationCallback, user: User, user_tz: str, session: AsyncSession):
    """Show today's reminders via callback navigation immediately answering query."""
    await call.answer()
    await show_today_reminders(call, user.id, user_tz, session, page=callback_data.page)


async def show_reminders_list(target, user_id: int, user_tz: str, session: AsyncSession, page: int = 0):
    """Format and send active reminders list with numbered selection buttons."""
    reminders = await crud.get_active_reminders_for_user(session, user_id)

    if not reminders:
        msg_text = "📋 <b>У вас нет активных напоминаний.</b>\n\nЧтобы создать новое, просто напишите мне!"
        if isinstance(target, Message):
            await target.answer(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        else:
            await target.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    per_page = 5
    start_idx = page * per_page
    page_items = reminders[start_idx:start_idx + per_page]

    now_local = to_local(utc_now(), user_tz)

    lines = ["📋 <b>МОИ НАПОМИНАНИЯ</b>\n"]
    for idx, r in enumerate(page_items):
        num_icon = NUMBER_EMOJIS[idx] if idx < len(NUMBER_EMOJIS) else f"{idx + 1}."
        due_local = to_local(r.due_at, user_tz)
        date_diff = (due_local.date() - now_local.date()).days

        if date_diff == 0:
            when_str = f"сегодня в {due_local.strftime('%H:%M')}"
        elif date_diff == 1:
            when_str = f"завтра в {due_local.strftime('%H:%M')}"
        else:
            when_str = due_local.strftime("%d.%m в %H:%M")

        lines.append(f"{num_icon} <b>{r.text}</b>\n⏰ <i>{when_str}</i>\n")

    lines.append("<i>Выберите номер кнопки ниже для управления:</i>")
    full_text = "\n".join(lines)

    reply_markup = get_reminders_list_keyboard(reminders, page=page, per_page=per_page, nav_target="list")

    if isinstance(target, Message):
        await target.answer(full_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.message.edit_text(full_text, parse_mode="HTML", reply_markup=reply_markup)


async def show_today_reminders(target, user_id: int, user_tz: str, session: AsyncSession, page: int = 0):
    """Format and send today's reminders with selection buttons."""
    reminders = await crud.get_today_reminders_for_user(session, user_id, user_tz)

    if not reminders:
        msg_text = "📅 <b>На сегодня напоминаний нет!</b>\n\nОтличный повод отдохнуть или запланировать новое."
        if isinstance(target, Message):
            await target.answer(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        else:
            await target.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    per_page = 5
    start_idx = page * per_page
    page_items = reminders[start_idx:start_idx + per_page]

    lines = ["📅 <b>НАПОМИНАНИЯ НА СЕГОДНЯ:</b>\n"]
    for idx, r in enumerate(page_items):
        num_icon = NUMBER_EMOJIS[idx] if idx < len(NUMBER_EMOJIS) else f"{idx + 1}."
        due_local = to_local(r.due_at, user_tz)
        time_str = due_local.strftime("%H:%M")
        lines.append(f"{num_icon} <b>{time_str}</b> — {r.text}\n")

    lines.append("<i>Выберите номер кнопки ниже для управления:</i>")
    full_text = "\n".join(lines)

    reply_markup = get_reminders_list_keyboard(reminders, page=page, per_page=per_page, nav_target="today")

    if isinstance(target, Message):
        await target.answer(full_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.message.edit_text(full_text, parse_mode="HTML", reply_markup=reply_markup)
