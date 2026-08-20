"""Callback query handlers for interactive buttons attached to reminder cards."""

import datetime
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.services.reminder_service import mark_reminder_completed, snooze_reminder
from app.utils.datetime_utils import format_russian_datetime, utc_now, to_local
from app.bot.keyboards.inline import (
    get_snooze_options_keyboard,
    get_single_reminder_detail_keyboard,
    get_main_menu_keyboard
)
from app.bot.keyboards.callbacks import ReminderActionCallback
from app.bot.states import SnoozeStates, CreateReminderStates
from app.bot.handlers.recurring import format_rrule_description

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(ReminderActionCallback.filter(F.action == "view_detail"))
async def callback_view_detail(call: CallbackQuery, callback_data: ReminderActionCallback, user_tz: str, session: AsyncSession):
    """Display dedicated detail control card for a SPECIFIC chosen reminder."""
    await call.answer()
    reminder_id = callback_data.reminder_id
    reminder = await crud.get_reminder_by_id(session, reminder_id)
    if not reminder:
        await call.message.edit_text("⚠️ Напоминание не найдено.", reply_markup=get_main_menu_keyboard())
        return

    now_local = to_local(utc_now(), user_tz)
    due_local = to_local(reminder.due_at, user_tz)
    formatted_dt = format_russian_datetime(due_local, now_local)

    rec_info = f"\n🔁 <i>{format_rrule_description(reminder.recurrence_rule, due_local.strftime('%H:%M'))}</i>" if reminder.is_recurring else ""

    text = (
        f"📌 <b>НАПОМИНАНИЕ</b>\n\n"
        f"<b>{reminder.text}</b>\n"
        f"⏰ {formatted_dt}"
        f"{rec_info}\n\n"
        f"<i>Выберите действие ниже:</i>"
    )

    back_target = "recurring" if reminder.is_recurring else "list"
    reply_markup = get_single_reminder_detail_keyboard(
        reminder_id=reminder.id,
        is_recurring=reminder.is_recurring,
        is_paused=(reminder.status == "PAUSED"),
        back_target=back_target
    )

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)


@router.callback_query(ReminderActionCallback.filter(F.action == "complete"))
async def callback_complete_reminder(call: CallbackQuery, callback_data: ReminderActionCallback, user_tz: str, session: AsyncSession):
    """Mark reminder as completed (or schedule next occurrence if recurring)."""
    await call.answer("Выполнено! 🎉")
    reminder_id = callback_data.reminder_id
    reminder = await crud.get_reminder_by_id(session, reminder_id)
    if not reminder:
        return

    updated = await mark_reminder_completed(session, reminder_id, user_tz)

    if updated and updated.status == "ACTIVE":
        now_local = to_local(utc_now(), user_tz)
        due_local = to_local(updated.due_at, user_tz)
        formatted_dt = format_russian_datetime(due_local, now_local)
        await call.message.edit_text(
            f"✅ <b>Выполнено!</b>\n\n🔁 Следующее напоминание запланировано на <b>{formatted_dt}</b>.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await call.message.edit_text(
            f"✅ <b>Отлично! Напоминание выполнено:</b>\n<s>{reminder.text}</s>",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(ReminderActionCallback.filter(F.action == "snooze_menu"))
async def callback_snooze_menu(call: CallbackQuery, callback_data: ReminderActionCallback):
    """Display quick snooze choices immediately."""
    await call.answer()
    reminder_id = callback_data.reminder_id
    text = "⏰ <b>На сколько отложить напоминание?</b>"
    reply_markup = get_snooze_options_keyboard(reminder_id)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)


@router.callback_query(ReminderActionCallback.filter(F.action == "snooze"))
async def callback_snooze_execute(call: CallbackQuery, callback_data: ReminderActionCallback, state: FSMContext, user_tz: str, session: AsyncSession):
    """Execute snooze preset or prompt custom input."""
    await call.answer("Отложено!")
    reminder_id = callback_data.reminder_id
    preset = callback_data.value

    if preset == "custom":
        await state.set_state(SnoozeStates.waiting_for_custom_snooze_time)
        await state.update_data({"snooze_reminder_id": reminder_id})
        await call.message.edit_text("✍️ Укажите, через сколько или на когда отложить (например: <i>«через 45 минут»</i>):", parse_mode="HTML")
        return

    res = await snooze_reminder(session, reminder_id, preset, user_tz)
    if res:
        updated, new_due_local = res
        now_local = to_local(utc_now(), user_tz)
        formatted_dt = format_russian_datetime(new_due_local, now_local)
        await call.message.edit_text(
            f"⏰ <b>Отложено!</b>\n\n📌 <b>{updated.text}</b>\nНапомню: {formatted_dt}.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(ReminderActionCallback.filter(F.action == "delete"))
async def callback_delete_reminder(call: CallbackQuery, callback_data: ReminderActionCallback, session: AsyncSession):
    """Delete reminder from database."""
    await call.answer("Удалено!")
    reminder_id = callback_data.reminder_id
    await crud.delete_reminder(session, reminder_id)
    await call.message.edit_text("🗑 <b>Напоминание удалено.</b>", parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.callback_query(ReminderActionCallback.filter(F.action == "edit_text"))
async def callback_edit_reminder_text(call: CallbackQuery, callback_data: ReminderActionCallback, state: FSMContext):
    """Prompt user for updated text of existing reminder."""
    await call.answer()
    await state.set_state(CreateReminderStates.waiting_for_edit_text)
    await state.update_data({"edit_reminder_id": callback_data.reminder_id})
    await call.message.edit_text("✏️ Введите новый текст для напоминания:", reply_markup=get_back_to_menu_keyboard())


@router.callback_query(ReminderActionCallback.filter(F.action == "reschedule"))
async def callback_reschedule_reminder(call: CallbackQuery, callback_data: ReminderActionCallback, state: FSMContext):
    """Prompt user for new date/time of existing reminder."""
    await call.answer()
    await state.set_state(CreateReminderStates.waiting_for_edit_time)
    await state.update_data({"edit_reminder_id": callback_data.reminder_id})
    await call.message.edit_text("⏰ Напишите новое время (например: <i>«завтра в 19:00»</i>):", parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())
