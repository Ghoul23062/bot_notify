"""Finite State Machine (FSM) states for user interaction flows."""

from aiogram.fsm.state import State, StatesGroup


class CreateReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_confirmation = State()
    waiting_for_time_clarification = State()
    waiting_for_edit_text = State()
    waiting_for_edit_time = State()


class SettingsStates(StatesGroup):
    waiting_for_timezone_input = State()
    waiting_for_quiet_hours_start = State()
    waiting_for_quiet_hours_end = State()


class SnoozeStates(StatesGroup):
    waiting_for_custom_snooze_time = State()
