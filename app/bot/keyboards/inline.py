"""Inline keyboard builders for bot screens and interactive actions."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    NavigationCallback,
    ReminderConfirmCallback,
    ReminderActionCallback,
    ClarifyTimeCallback,
    SettingsCallback
)
from app.db.models import UserSettings


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main menu inline keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать", callback_data=NavigationCallback(target="create"))
    builder.button(text="📋 Мои напоминания", callback_data=NavigationCallback(target="list"))
    builder.button(text="📅 Сегодня", callback_data=NavigationCallback(target="today"))
    builder.button(text="🔁 Повторяющиеся", callback_data=NavigationCallback(target="recurring"))
    builder.button(text="⚙️ Настройки", callback_data=NavigationCallback(target="settings"))
    builder.button(text="❓ Помощь", callback_data=NavigationCallback(target="help"))
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Build reminder creation confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, создать", callback_data=ReminderConfirmCallback(action="confirm"))
    builder.button(text="✏️ Изменить", callback_data=ReminderConfirmCallback(action="edit"))
    builder.button(text="❌ Отмена", callback_data=ReminderConfirmCallback(action="cancel"))
    builder.adjust(1, 2)
    return builder.as_markup()


def get_notification_actions_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Build actions attached to a due reminder notification."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено", callback_data=ReminderActionCallback(action="complete", reminder_id=reminder_id))
    builder.button(text="⏰ Отложить", callback_data=ReminderActionCallback(action="snooze_menu", reminder_id=reminder_id))
    builder.button(text="✏️ Изменить", callback_data=ReminderActionCallback(action="edit_text", reminder_id=reminder_id))
    builder.button(text="🗑 Удалить", callback_data=ReminderActionCallback(action="delete", reminder_id=reminder_id))
    builder.adjust(2, 2)
    return builder.as_markup()


def get_snooze_options_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Build quick snooze time choices."""
    builder = InlineKeyboardBuilder()
    builder.button(text="+5 минут", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="+5m"))
    builder.button(text="+15 минут", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="+15m"))
    builder.button(text="+30 минут", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="+30m"))
    builder.button(text="+1 час", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="+1h"))
    builder.button(text="+3 часа", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="+3h"))
    builder.button(text="Завтра в 09:00", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="tomorrow"))
    builder.button(text="✍️ Своё время", callback_data=ReminderActionCallback(action="snooze", reminder_id=reminder_id, value="custom"))
    builder.button(text="⬅️ Назад", callback_data=NavigationCallback(target="main_menu"))
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()


def get_clarification_keyboard() -> InlineKeyboardMarkup:
    """Build quick time presets when time was ambiguous in user query."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ через 15 мин", callback_data=ClarifyTimeCallback(preset="15m"))
    builder.button(text="⏱ через 1 час", callback_data=ClarifyTimeCallback(preset="1h"))
    builder.button(text="🌙 сегодня вечером (19:00)", callback_data=ClarifyTimeCallback(preset="tonight"))
    builder.button(text="🌅 завтра в 09:00", callback_data=ClarifyTimeCallback(preset="tmr_9am"))
    builder.button(text="✍️ Указать своё время", callback_data=ClarifyTimeCallback(preset="custom"))
    builder.button(text="❌ Отмена", callback_data=ReminderConfirmCallback(action="cancel"))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_reminder_item_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Build options for a single item in list view."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить", callback_data=ReminderActionCallback(action="edit_text", reminder_id=reminder_id))
    builder.button(text="⏰ Перенести", callback_data=ReminderActionCallback(action="reschedule", reminder_id=reminder_id))
    builder.button(text="🗑 Удалить", callback_data=ReminderActionCallback(action="delete", reminder_id=reminder_id))
    builder.adjust(3)
    return builder.as_markup()


def get_recurring_item_keyboard(reminder_id: int, is_paused: bool) -> InlineKeyboardMarkup:
    """Build options for a recurring reminder in list view."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить", callback_data=ReminderActionCallback(action="edit_text", reminder_id=reminder_id))
    toggle_text = "▶️ Возобновить" if is_paused else "⏸ Приостановить"
    builder.button(text=toggle_text, callback_data=ReminderActionCallback(action="toggle_pause", reminder_id=reminder_id))
    builder.button(text="🗑 Удалить", callback_data=ReminderActionCallback(action="delete", reminder_id=reminder_id))
    builder.adjust(3)
    return builder.as_markup()


def get_settings_keyboard(settings: UserSettings) -> InlineKeyboardMarkup:
    """Build settings main screen inline keyboard."""
    builder = InlineKeyboardBuilder()
    
    tz_text = f"🌍 Часовой пояс ({settings.timezone})"
    builder.button(text=tz_text, callback_data=SettingsCallback(action="tz"))

    quiet_status = "Вкл" if settings.quiet_hours_enabled else "Выкл"
    quiet_text = f"⏰ Время тишины ({quiet_status})"
    builder.button(text=quiet_text, callback_data=SettingsCallback(action="quiet"))

    fmt_text = f"🕐 Формат времени ({settings.time_format})"
    builder.button(text=fmt_text, callback_data=SettingsCallback(action="time_fmt"))

    notif_status = "Вкл" if settings.notifications_enabled else "Выкл"
    notif_text = f"🔔 Уведомления ({notif_status})"
    builder.button(text=notif_text, callback_data=SettingsCallback(action="notifications_toggle"))

    builder.button(text="🌐 Язык (Русский)", callback_data=SettingsCallback(action="lang"))
    
    fd_str = "Понедельник" if settings.first_day_of_week == 0 else "Воскресенье"
    builder.button(text=f"📅 Первый день ({fd_str})", callback_data=SettingsCallback(action="first_day"))

    builder.button(text="⬅️ Главное меню", callback_data=NavigationCallback(target="main_menu"))
    builder.adjust(1, 2, 2, 1, 1)
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Simple back button."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Главное меню", callback_data=NavigationCallback(target="main_menu"))
    return builder.as_markup()
