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
    get_main_menu_keyboard
)
from app.bot.keyboards.callbacks import ReminderActionCallback
from app.bot.states import SnoozeStates, CreateReminderStates

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(ReminderActionCallback.filter(F.action == "complete"))
async def callback_complete_reminder(call: CallbackQuery, callback_data: ReminderActionCallback, user_tz: str, session: AsyncSession):
    """Mark reminder as completed (or schedule next occurrence if recurring)."""
    reminder_id = callback_data.reminder_id
    reminder = await crud.get_reminder_by_id(session, reminder_id)
    if not reminder:
        await call.answer("⚠️ Напоминание уже было удалено.", show_alert=True)
        return

    updated = await mark_reminder_completed(session, reminder_id, user_tz)

    if updated and updated.status == "ACTIVE":
        # Recurring reminder moved to next occurrence
        now_local = to_local(utc_now(), user_tz)
        due_local = to_local(updated.due_at, user_tz)
        formatted_dt = format_russian_datetime(due_local, now_local)
        await call.message.edit_text(
            f"✅ <b>Выполнено!</b>\n\n🔁 Следующее напоминание запланировано на <b>{formatted_dt}</b>.",
            parse_mode="HTML"
        )
    else:
        await call.message.edit_text(
            f"✅ <b>Отлично! Напоминание выполнено:</b>\n<s>{reminder.text}</s>",
            parse_mode="HTML"
        )

    await call.answer("Выполнено! 🎉")


@router.callback_query(ReminderActionCallback.filter(F.action == "snooze_menu"))
async def callback_snooze_menu(call: CallbackQuery, callback_data: ReminderActionCallback):
    """Display quick snooze choices."""
    reminder_id = callback_data.reminder_id
    text = "⏰ <b>На сколько отложить напоминание?</b>"
    reply_markup = get_snooze_options_keyboard(reminder_id)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    await call.answer()


@router.callback_query(ReminderActionCallback.filter(F.action == "snooze"))
async def callback_snooze_execute(call: CallbackQuery, callback_data: ReminderActionCallback, state: FSMContext, user_tz: str, session: AsyncSession):
    """Execute snooze preset or prompt custom input."""
    reminder_id = callback_data.reminder_id
    preset = callback_data.value

    if preset == "custom":
        await state.set_state(SnoozeStates.waiting_for_custom_snooze_time)
        await state.update_data({"snooze_reminder_id": reminder_id})
        await call.message.edit_text("✍️ Укажите, через сколько или на когда отложить (например: <i>«через 45 минут»</i>):", parse_mode="HTML")
        await call.answer()
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
        await call.answer("Отложено!")
    else:
        await call.answer("⚠️ Не удалось отложить напоминание.", show_alert=True)


@router.callback_query(ReminderActionCallback.filter(F.action == "delete"))
async def callback_delete_reminder(call: CallbackQuery, callback_data: ReminderActionCallback, session: AsyncSession):
    """Delete reminder from database."""
    reminder_id = callback_data.reminder_id
    success = await crud.delete_reminder(session, reminder_id)
    if success:
        await call.message.edit_text("🗑 <b>Напоминание удалено.</b>", parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        await call.answer("Удалено!")
    else:
        await call.answer("⚠️ Напоминание не найдено.", show_alert=True)


@router.callback_query(ReminderActionCallback.filter(F.action == "edit_text"))
async def callback_edit_reminder_text(call: CallbackQuery, callback_data: ReminderActionCallback, state: FSMContext):
    """Prompt user for updated text of existing reminder."""
    await state.set_state(CreateReminderStates.waiting_for_edit_text)
    await state.update_data({"edit_reminder_id": callback_data.reminder_id})
    await call.message.edit_text("✏️ Введите новый текст для напоминания:", reply_markup=get_main_menu_keyboard())
    await call.answer()


@router.callback_query(ReminderActionCallback.filter(F.action == "reschedule"))
async def callback_reschedule_reminder(call: CallbackQuery, callback_data: ReminderActionCallback, state: FSMContext):
    """Prompt user for new date/time of existing reminder."""
    await state.set_state(CreateReminderStates.waiting_for_edit_time)
    await state.update_data({"edit_reminder_id": callback_data.reminder_id})
    await call.message.edit_text("⏰ Напишите новое время (например: <i>«завтра в 19:00»</i>):", parse_mode="HTML")
    await call.answer()
