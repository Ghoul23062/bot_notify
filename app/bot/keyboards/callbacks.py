"""Typed CallbackData schemas for inline keyboards."""

from typing import Optional
from aiogram.filters.callback_data import CallbackData


class ReminderActionCallback(CallbackData, prefix="rem_act"):
    action: str  # "view_detail", "complete", "snooze_menu", "snooze", "edit_text", "reschedule", "delete", "toggle_pause"
    reminder_id: int
    value: Optional[str] = None


class ReminderConfirmCallback(CallbackData, prefix="rem_cfg"):
    action: str  # "confirm", "edit", "cancel"


class ClarifyTimeCallback(CallbackData, prefix="rem_clr"):
    preset: str  # "15m", "1h", "tonight", "tmr_9am", "custom"


class NavigationCallback(CallbackData, prefix="nav"):
    target: str  # "main_menu", "list", "today", "recurring", "settings", "help", "create"
    page: int = 0


class SettingsCallback(CallbackData, prefix="set"):
    action: str  # "tz", "quiet", "quiet_toggle", "quiet_action", "time_fmt", "lang", "first_day", "notifications_toggle"
    value: Optional[str] = None
