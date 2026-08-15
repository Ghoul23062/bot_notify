"""Unit tests for timezone conversion, Russian date formatting, and quiet hours calculation."""

import pytest
import datetime
from app.utils.datetime_utils import (
    to_utc,
    to_local,
    format_russian_datetime,
    is_in_quiet_hours,
    adjust_for_quiet_hours
)


def test_timezone_conversion_moscow():
    local_dt = datetime.datetime(2026, 8, 15, 15, 0, 0)
    utc_dt = to_utc(local_dt, "Europe/Moscow")
    # Moscow is UTC+3 -> 15:00 local is 12:00 UTC
    assert utc_dt == datetime.datetime(2026, 8, 15, 12, 0, 0)

    back_local = to_local(utc_dt, "Europe/Moscow")
    assert back_local.hour == 15


def test_russian_date_formatting():
    now_local = datetime.datetime(2026, 8, 15, 10, 0, 0)
    dt_today = datetime.datetime(2026, 8, 15, 15, 30, 0)
    dt_tmr = datetime.datetime(2026, 8, 16, 9, 0, 0)
    dt_after_tmr = datetime.datetime(2026, 8, 17, 14, 0, 0)

    assert format_russian_datetime(dt_today, now_local) == "сегодня в 15:30"
    assert format_russian_datetime(dt_tmr, now_local) == "завтра, 16 августа, в 09:00"
    assert format_russian_datetime(dt_after_tmr, now_local) == "послезавтра, 17 августа, в 14:00"


def test_quiet_hours_check():
    # Quiet hours 23:00 to 07:00
    dt_night = datetime.datetime(2026, 8, 15, 1, 30, 0)
    dt_day = datetime.datetime(2026, 8, 15, 14, 0, 0)

    assert is_in_quiet_hours(dt_night, "23:00", "07:00") is True
    assert is_in_quiet_hours(dt_day, "23:00", "07:00") is False


def test_adjust_for_quiet_hours():
    dt_night = datetime.datetime(2026, 8, 15, 1, 30, 0)
    adjusted = adjust_for_quiet_hours(dt_night, "07:00")
    assert adjusted.hour == 7
    assert adjusted.minute == 0
