"""Inline keyboard builders for bot screens and interactive actions."""

from typing import List, Sequence
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    NavigationCallback,
    ReminderConfirmCallback,
    ReminderActionCallback,
    ClarifyTimeCallback,
    SettingsCallback
)
from app.db.models import Reminder, UserSettings

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


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


def get_reminders_list_keyboard(reminders: Sequence[Reminder], page: int = 0, per_page: int = 5, nav_target: str = "list") -> InlineKeyboardMarkup:
    """Build selection grid allowing user to choose WHICH reminder to manage."""
    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    page_reminders = reminders[start_idx:start_idx + per_page]

    # Item selection buttons [ 1️⃣ ] [ 2️⃣ ] [ 3️⃣ ]
    row_buttons = []
    for idx, r in enumerate(page_reminders):
        icon = NUMBER_EMOJIS[idx] if idx < len(NUMBER_EMOJIS) else f"[{idx + 1}]"
        builder.button(
            text=f"{icon}",
            callback_data=ReminderActionCallback(action="view_detail", reminder_id=r.id)
        )
        row_buttons.append(1)

    builder.adjust(*row_buttons)

    # Pagination controls if items > per_page
    total_pages = (len(reminders) + per_page - 1) // per_page
    if total_pages > 1:
        pag_builder = InlineKeyboardBuilder()
        if page > 0:
            pag_builder.button(text="⬅️ Назад", callback_data=NavigationCallback(target=nav_target, page=page - 1))
        pag_builder.button(text=f"Стр. {page + 1}/{total_pages}", callback_data=NavigationCallback(target="none"))
        if page < total_pages - 1:
            pag_builder.button(text="Вперёд ➡️", callback_data=NavigationCallback(target=nav_target, page=page + 1))
        pag_builder.adjust(3)
        builder.attach(pag_builder)

    # Main menu button
    menu_builder = InlineKeyboardBuilder()
    menu_builder.button(text="🏠 Главное меню", callback_data=NavigationCallback(target="main_menu"))
    builder.attach(menu_builder)

    return builder.as_markup()


def get_single_reminder_detail_keyboard(reminder_id: int, is_recurring: bool = False, is_paused: bool = False, back_target: str = "list") -> InlineKeyboardMarkup:
    """Build management card for a SPECIFIC selected reminder."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить текст", callback_data=ReminderActionCallback(action="edit_text", reminder_id=reminder_id))

    if is_recurring:
        toggle_text = "▶️ Возобновить" if is_paused else "⏸ Приостановить"
        builder.button(text=toggle_text, callback_data=ReminderActionCallback(action="toggle_pause", reminder_id=reminder_id))
    else:
        builder.button(text="⏰ Перенести время", callback_data=ReminderActionCallback(action="reschedule", reminder_id=reminder_id))

    builder.button(text="🗑 Удалить", callback_data=ReminderActionCallback(action="delete", reminder_id=reminder_id))
    builder.button(text="⬅️ К списку", callback_data=NavigationCallback(target=back_target))
    builder.adjust(2, 1, 1)
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
