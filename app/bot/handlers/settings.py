"""Settings handlers for user timezone, quiet hours, time format, and preferences."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import User
from app.services.user_service import set_user_timezone, set_user_quiet_hours
from app.bot.keyboards.inline import get_settings_keyboard, get_back_to_menu_keyboard
from app.bot.keyboards.callbacks import NavigationCallback, SettingsCallback
from app.bot.states import SettingsStates

router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: Message, user: User):
    """Handle /settings command."""
    await show_settings_screen(message, user)


@router.callback_query(NavigationCallback.filter(F.target == "settings"))
async def nav_settings(call: CallbackQuery, user: User):
    """Show settings main screen via callback immediately answering query."""
    await call.answer()
    await show_settings_screen(call, user)


async def show_settings_screen(target, user: User):
    """Render settings card with inline buttons."""
    s = user.settings
    quiet_info = f"{s.quiet_start}–{s.quiet_end}" if s.quiet_hours_enabled else "Выключено"

    text = (
        f"⚙️ <b>НАСТРОЙКИ</b>\n\n"
        f"🌍 <b>Часовой пояс:</b> {s.timezone}\n"
        f"⏰ <b>Тихие часы:</b> {quiet_info}\n"
        f"🕐 <b>Формат времени:</b> {s.time_format}\n"
        f"🔔 <b>Уведомления:</b> {'Включены' if s.notifications_enabled else 'Выключены'}\n"
        f"🌐 <b>Язык:</b> Русский (ru)\n"
        f"📅 <b>Первый день недели:</b> {'Понедельник' if s.first_day_of_week == 0 else 'Воскресенье'}\n\n"
        f"<i>Выберите пункт для изменения:</i>"
    )
    reply_markup = get_settings_keyboard(s)

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)


@router.callback_query(SettingsCallback.filter(F.action == "tz"))
async def callback_tz_prompt(call: CallbackQuery, state: FSMContext):
    """Prompt user for timezone input immediately answering query."""
    await call.answer()
    await state.set_state(SettingsStates.waiting_for_timezone_input)
    text = (
        "🌍 <b>Укажите ваш часовой пояс:</b>\n\n"
        "Отправьте название города или часового пояса, например:\n"
        "• <code>Europe/Moscow</code> (Москва, МСК)\n"
        "• <code>Asia/Yekaterinburg</code> (Екатеринбург)\n"
        "• <code>Asia/Almaty</code> (Алматы)\n"
        "• <code>Europe/Kiev</code> (Киев)\n"
        "• <code>UTC</code>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())


@router.message(SettingsStates.waiting_for_timezone_input)
async def process_tz_input(message: Message, state: FSMContext, user: User, session: AsyncSession):
    """Validate and update user timezone."""
    tz_input = message.text.strip()
    city_map = {
        "москва": "Europe/Moscow", "мск": "Europe/Moscow", "питер": "Europe/Moscow", "санкт-петербург": "Europe/Moscow",
        "екатеринбург": "Asia/Yekaterinburg", "новосибирск": "Asia/Novosibirsk", "красноярск": "Asia/Krasnoyarsk",
        "владивосток": "Asia/Vladivostok", "калининград": "Europe/Kaliningrad", "алматы": "Asia/Almaty",
        "минск": "Europe/Minsk", "киев": "Europe/Kiev", "ташкент": "Asia/Tashkent"
    }

    tz_name = city_map.get(tz_input.lower(), tz_input)

    success = await set_user_timezone(session, user.id, tz_name)
    if success:
        await state.clear()
        user.settings.timezone = tz_name
        await message.answer(f"✅ Часовой пояс успешно изменён на <b>{tz_name}</b>!", parse_mode="HTML")
        await show_settings_screen(message, user)
    else:
        await message.answer("⚠️ Некорректный часовой пояс. Попробуйте написать, например: <code>Europe/Moscow</code>", parse_mode="HTML")


@router.callback_query(SettingsCallback.filter(F.action == "quiet"))
async def callback_quiet_hours_menu(call: CallbackQuery, user: User, session: AsyncSession):
    """Toggle quiet hours or prompt configuration."""
    s = user.settings
    new_enabled = not s.quiet_hours_enabled
    await set_user_quiet_hours(session, user.id, enabled=new_enabled, start=s.quiet_start or "23:00", end=s.quiet_end or "07:00")
    user.settings.quiet_hours_enabled = new_enabled
    status_str = "включены" if new_enabled else "выключены"
    await call.answer(f"Тихие часы {status_str}!")
    await show_settings_screen(call, user)


@router.callback_query(SettingsCallback.filter(F.action == "time_fmt"))
async def callback_time_fmt_toggle(call: CallbackQuery, user: User, session: AsyncSession):
    """Toggle 24h / 12h time format."""
    new_fmt = "12h" if user.settings.time_format == "24h" else "24h"
    await crud.update_user_settings(session, user.id, time_format=new_fmt)
    user.settings.time_format = new_fmt
    await call.answer(f"Формат изменён на {new_fmt}!")
    await show_settings_screen(call, user)


@router.callback_query(SettingsCallback.filter(F.action == "notifications_toggle"))
async def callback_notifications_toggle(call: CallbackQuery, user: User, session: AsyncSession):
    """Toggle global notifications enabled/disabled."""
    new_val = not user.settings.notifications_enabled
    await crud.update_user_settings(session, user.id, notifications_enabled=new_val)
    user.settings.notifications_enabled = new_val
    status_str = "включены" if new_val else "выключены"
    await call.answer(f"Уведомления {status_str}!")
    await show_settings_screen(call, user)


@router.callback_query(SettingsCallback.filter(F.action == "first_day"))
async def callback_first_day_toggle(call: CallbackQuery, user: User, session: AsyncSession):
    """Toggle first day of week (Monday vs Sunday)."""
    new_fd = 6 if user.settings.first_day_of_week == 0 else 0
    await crud.update_user_settings(session, user.id, first_day_of_week=new_fd)
    user.settings.first_day_of_week = new_fd
    name = "Понедельник" if new_fd == 0 else "Воскресенье"
    await call.answer(f"Первый день недели: {name}!")
    await show_settings_screen(call, user)
