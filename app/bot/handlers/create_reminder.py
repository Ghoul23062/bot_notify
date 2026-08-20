"""Handlers for natural language reminder creation, confirmation, clarification, and context modifications."""

import datetime
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User
from app.utils.datetime_utils import utc_now, to_local, to_utc, format_russian_datetime
from app.services.parser import parse_reminder_input
from app.services.reminder_service import create_new_reminder, reschedule_last_context_reminder
from app.bot.keyboards.inline import (
    get_confirmation_keyboard,
    get_clarification_keyboard,
    get_main_menu_keyboard,
    get_back_to_menu_keyboard
)
from app.bot.keyboards.callbacks import ReminderConfirmCallback, ClarifyTimeCallback
from app.bot.states import CreateReminderStates, SnoozeStates

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("remind"))
async def cmd_remind(message: Message, state: FSMContext, user: User, user_tz: str):
    """Handle /remind text command."""
    text = message.text.partition(" ")[2].strip()
    if not text:
        await state.set_state(CreateReminderStates.waiting_for_text)
        await message.answer("✍️ Напишите, о чём и когда вас напомнить:", reply_markup=get_back_to_menu_keyboard())
        return

    await process_reminder_text(message, text, state, user, user_tz)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_freeform_text(message: Message, state: FSMContext, user: User, user_tz: str, session: AsyncSession):
    """Handle freeform natural language text input and active FSM states."""
    current_state = await state.get_state()
    text = message.text.strip()

    # 1. State: Editing text of an existing reminder or creation draft
    if current_state == CreateReminderStates.waiting_for_edit_text.state:
        data = await state.get_data()
        edit_reminder_id = data.get("edit_reminder_id")

        if edit_reminder_id:
            updated_rem = await crud.update_reminder_text(session, edit_reminder_id, text)
            await state.clear()
            if updated_rem:
                await message.answer(
                    f"✅ <b>Текст напоминания изменён!</b>\n\n📌 <b>{updated_rem.text}</b>",
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                await message.answer("⚠️ Напоминание не найдено.", reply_markup=get_main_menu_keyboard())
            return
        else:
            data["text"] = text
            await state.update_data(data)
            await show_confirmation_screen(message, data, user_tz)
            return

    # 2. State: Editing/rescheduling time of an existing reminder or creation draft
    if current_state == CreateReminderStates.waiting_for_edit_time.state:
        now_local = to_local(utc_now(), user_tz)
        parsed = await parse_reminder_input(text, now_local, user_tz)
        if not parsed.target_datetime:
            parsed = await parse_reminder_input(f"сегодня {text}", now_local, user_tz)

        if parsed.target_datetime:
            data = await state.get_data()
            edit_reminder_id = data.get("edit_reminder_id")

            if edit_reminder_id:
                new_due_utc = to_utc(parsed.target_datetime, user_tz)
                updated_rem = await crud.update_reminder_due_at(session, edit_reminder_id, new_due_utc, status="ACTIVE")
                await state.clear()
                if updated_rem:
                    formatted_dt = format_russian_datetime(parsed.target_datetime, now_local)
                    await message.answer(
                        f"⏰ Время напоминания <b>«{updated_rem.text}»</b> успешно перенесено на <b>{formatted_dt}</b>.",
                        parse_mode="HTML",
                        reply_markup=get_main_menu_keyboard()
                    )
                else:
                    await message.answer("⚠️ Напоминание не найдено.", reply_markup=get_main_menu_keyboard())
                return
            else:
                data["target_dt_local"] = parsed.target_datetime.isoformat()
                if parsed.is_recurring:
                    data["is_recurring"] = True
                    data["recurrence_rule"] = parsed.recurrence_rule
                await state.update_data(data)
                await show_confirmation_screen(message, data, user_tz)
                return
        else:
            await message.answer("⚠️ Не удалось распознать дату и время. Попробуйте написать, например: <i>«Завтра в 15:00»</i> или <i>«через 30 минут»</i>", parse_mode="HTML")
            return

    # 3. State: Custom Snooze input
    if current_state == SnoozeStates.waiting_for_custom_snooze_time.state:
        now_local = to_local(utc_now(), user_tz)
        parsed = await parse_reminder_input(text, now_local, user_tz)
        if not parsed.target_datetime:
            parsed = await parse_reminder_input(f"сегодня {text}", now_local, user_tz)

        if parsed.target_datetime:
            data = await state.get_data()
            snooze_reminder_id = data.get("snooze_reminder_id")
            new_due_utc = to_utc(parsed.target_datetime, user_tz)
            updated_rem = await crud.update_reminder_due_at(session, snooze_reminder_id, new_due_utc, status="SNOOZED")
            await state.clear()
            if updated_rem:
                formatted_dt = format_russian_datetime(parsed.target_datetime, now_local)
                await message.answer(
                    f"⏰ <b>Отложено!</b>\n\n📌 <b>{updated_rem.text}</b>\nНапомню: {formatted_dt}.",
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                await message.answer("⚠️ Напоминание не найдено.", reply_markup=get_main_menu_keyboard())
            return
        else:
            await message.answer("⚠️ Не удалось распознать время. Попробуйте написать: <i>«через 45 минут»</i> или <i>«завтра в 10:00»</i>", parse_mode="HTML")
            return

    # 4. Context phrases like "перенеси на завтра", "перенеси на 18:00"
    if text.lower().startswith(("перенеси на ", "отложи на ", "перенести на ")):
        now_local = to_local(utc_now(), user_tz)
        time_part = text[11:].strip()
        parsed_context = await parse_reminder_input(f"сегодня {time_part}", now_local, user_tz)
        if not parsed_context.target_datetime:
            parsed_context = await parse_reminder_input(time_part, now_local, user_tz)
        
        if parsed_context.target_datetime:
            updated = await reschedule_last_context_reminder(session, user.id, user_tz, parsed_context.target_datetime)
            if updated:
                formatted_dt = format_russian_datetime(parsed_context.target_datetime, now_local)
                await message.answer(f"⏰ Перенёс ваше последнее напоминание (<b>{updated.text}</b>) на {formatted_dt}.", parse_mode="HTML", reply_markup=get_main_menu_keyboard())
                return
            else:
                await message.answer("⚠️ У вас нет активных напоминаний для переноса.")
                return

    # 5. Default flow: parse text as new reminder
    await process_reminder_text(message, text, state, user, user_tz)


async def process_reminder_text(message: Message, text: str, state: FSMContext, user: User, user_tz: str):
    """Parse text and either show confirmation or ask for clarification."""
    now_local = to_local(utc_now(), user_tz)
    parsed = await parse_reminder_input(text, now_local, user_tz)

    if parsed.target_datetime:
        draft_data = {
            "text": parsed.text,
            "target_dt_local": parsed.target_datetime.isoformat(),
            "is_recurring": parsed.is_recurring,
            "recurrence_rule": parsed.recurrence_rule,
            "time_slot_used": parsed.time_slot_used
        }
        await state.set_state(CreateReminderStates.waiting_for_confirmation)
        await state.set_data(draft_data)
        await show_confirmation_screen(message, draft_data, user_tz)
    else:
        # Ambiguous time -> Save text draft and ask clarification
        await state.set_state(CreateReminderStates.waiting_for_time_clarification)
        await state.set_data({"text": parsed.text})
        question = parsed.clarification_question or "Когда напомнить?"
        msg = (
            f"❓ <b>{question}</b>\n\n"
            f"Напоминание: <b>{parsed.text}</b>\n\n"
            f"Выберите вариант ниже или напишите время в ответ:"
        )
        await message.answer(msg, parse_mode="HTML", reply_markup=get_clarification_keyboard())


async def show_confirmation_screen(target_msg, draft_data: dict, user_tz: str):
    """Format and send the reminder confirmation card."""
    now_local = to_local(utc_now(), user_tz)
    target_dt_local = datetime.datetime.fromisoformat(draft_data["target_dt_local"])
    formatted_dt = format_russian_datetime(target_dt_local, now_local)

    slot_info = f"\nℹ️ <i>Выбрано время: {draft_data['time_slot_used']}</i>" if draft_data.get("time_slot_used") else ""
    rec_info = "\n🔁 <i>Повторяющееся напоминание</i>" if draft_data.get("is_recurring") else ""

    text = (
        f"🔔 <b>Напомню {formatted_dt}:</b>\n\n"
        f"<b>{draft_data['text']}</b>"
        f"{slot_info}{rec_info}\n\n"
        f"Всё верно?"
    )

    if isinstance(target_msg, Message):
        await target_msg.answer(text, parse_mode="HTML", reply_markup=get_confirmation_keyboard())
    elif isinstance(target_msg, CallbackQuery):
        await target_msg.message.edit_text(text, parse_mode="HTML", reply_markup=get_confirmation_keyboard())


@router.callback_query(ReminderConfirmCallback.filter(F.action == "confirm"))
async def callback_confirm_create(call: CallbackQuery, state: FSMContext, user: User, user_tz: str, session: AsyncSession):
    """Save confirmed reminder draft to DB."""
    data = await state.get_data()
    if not data or "text" not in data or "target_dt_local" not in data:
        await call.answer("⚠️ Сессия истекла. Создайте напоминание заново.", show_alert=True)
        await state.clear()
        return

    target_dt_local = datetime.datetime.fromisoformat(data["target_dt_local"])
    reminder = await create_new_reminder(
        session=session,
        user=user,
        text=data["text"],
        target_dt_local=target_dt_local,
        is_recurring=data.get("is_recurring", False),
        recurrence_rule=data.get("recurrence_rule")
    )

    await state.clear()
    now_local = to_local(utc_now(), user_tz)
    formatted_dt = format_russian_datetime(target_dt_local, now_local)

    success_msg = (
        f"✅ <b>Напоминание создано!</b>\n\n"
        f"📌 <b>{reminder.text}</b>\n"
        f"⏰ {formatted_dt}"
    )
    await call.message.edit_text(success_msg, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    await call.answer()


@router.callback_query(ReminderConfirmCallback.filter(F.action == "edit"))
async def callback_edit_draft(call: CallbackQuery, state: FSMContext):
    """Prompt user to edit text or time of the draft."""
    await state.set_state(CreateReminderStates.waiting_for_edit_text)
    await call.message.edit_text("✏️ Напишите новый текст для напоминания:", reply_markup=get_back_to_menu_keyboard())
    await call.answer()


@router.callback_query(ReminderConfirmCallback.filter(F.action == "cancel"))
async def callback_cancel_draft(call: CallbackQuery, state: FSMContext):
    """Cancel creation draft."""
    await state.clear()
    await call.message.edit_text("❌ Действие отменено.", reply_markup=get_main_menu_keyboard())
    await call.answer()


@router.callback_query(ClarifyTimeCallback.filter())
async def callback_clarify_time(call: CallbackQuery, callback_data: ClarifyTimeCallback, state: FSMContext, user: User, user_tz: str):
    """Handle preset time buttons from clarification screen."""
    data = await state.get_data()
    text = data.get("text", "Напоминание")
    now_local = to_local(utc_now(), user_tz)

    preset = callback_data.preset
    target_dt_local = None

    if preset == "15m":
        target_dt_local = now_local + datetime.timedelta(minutes=15)
    elif preset == "1h":
        target_dt_local = now_local + datetime.timedelta(hours=1)
    elif preset == "tonight":
        target_dt_local = now_local.replace(hour=19, minute=0, second=0, microsecond=0)
        if target_dt_local <= now_local:
            target_dt_local += datetime.timedelta(days=1)
    elif preset == "tmr_9am":
        target_dt_local = (now_local + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    elif preset == "custom":
        await state.set_state(CreateReminderStates.waiting_for_edit_time)
        await call.message.edit_text("✍️ Напишите время (например: <i>«завтра в 18:00»</i>):", parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())
        await call.answer()
        return

    if target_dt_local:
        data["target_dt_local"] = target_dt_local.isoformat()
        data["is_recurring"] = False
        data["recurrence_rule"] = None
        await state.set_state(CreateReminderStates.waiting_for_confirmation)
        await state.update_data(data)
        await show_confirmation_screen(call, data, user_tz)

    await call.answer()
