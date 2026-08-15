"""Unit tests for Russian natural language parsing logic."""

import pytest
import datetime
from app.services.parser.deterministic import parse_deterministic


@pytest.fixture
def now_local():
    # Saturday, 15 August 2026, 12:00
    return datetime.datetime(2026, 8, 15, 12, 0, 0)


def test_parse_tomorrow_specific_time(now_local):
    res = parse_deterministic("напомни завтра в 15:00 позвонить маме", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 16, 15, 0)
    assert "позвонить маме" in res.text
    assert not res.is_recurring


def test_parse_relative_hours(now_local):
    res = parse_deterministic("напомни через 2 часа проверить почту", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 15, 14, 0)
    assert "проверить почту" in res.text


def test_parse_relative_half_hour(now_local):
    res = parse_deterministic("через полчаса позвони клиенту", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 15, 12, 30)
    assert "позвони клиенту" in res.text


def test_parse_relative_minutes(now_local):
    res = parse_deterministic("через 30 минут выключить духовку", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 15, 12, 30)
    assert "выключить духовку" in res.text


def test_parse_weekday(now_local):
    # now_local is Saturday 15th Aug. Next Monday is 17th Aug.
    res = parse_deterministic("напомни в понедельник в 9:00 сходить в спортзал", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 17, 9, 0)
    assert "сходить в спортзал" in res.text


def test_parse_daily_recurring(now_local):
    res = parse_deterministic("каждый день в 20:00 принимать витамины", now_local)
    assert res.is_recurring
    assert res.recurrence_rule == "DAILY"
    assert res.target_datetime == datetime.datetime(2026, 8, 15, 20, 0)
    assert "принимать витамины" in res.text


def test_parse_weekly_recurring(now_local):
    res = parse_deterministic("каждую пятницу в 18:30 проверить отчёт", now_local)
    assert res.is_recurring
    assert res.recurrence_rule == "WEEKLY;BYDAY=FR"
    # Next Friday is 21st Aug
    assert res.target_datetime == datetime.datetime(2026, 8, 21, 18, 30)
    assert "проверить отчёт" in res.text


def test_parse_workdays_recurring(now_local):
    res = parse_deterministic("по будням в 8:30 вставать", now_local)
    assert res.is_recurring
    assert res.recurrence_rule == "WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    # Saturday -> Next Monday is 17th Aug
    assert res.target_datetime == datetime.datetime(2026, 8, 17, 8, 30)
    assert "вставать" in res.text


def test_parse_vague_morning(now_local):
    res = parse_deterministic("напомни завтра утром купить молоко", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 16, 9, 0)
    assert res.time_slot_used is not None
    assert "купить молоко" in res.text


def test_parse_fast_creation(now_local):
    res = parse_deterministic("молоко завтра 18", now_local)
    assert res.target_datetime == datetime.datetime(2026, 8, 16, 18, 0)
    assert "молоко" in res.text


def test_parse_interval_hours(now_local):
    res = parse_deterministic("каждые 2 часа пить воду", now_local)
    assert res.is_recurring
    assert res.recurrence_rule == "INTERVAL;HOURS=2"
    assert res.target_datetime == datetime.datetime(2026, 8, 15, 14, 0)


def test_parse_monthly_day(now_local):
    res = parse_deterministic("каждое 1 число месяца в 10:00 оплатить подписки", now_local)
    assert res.is_recurring
    assert res.recurrence_rule == "MONTHLY;BYMONTHDAY=1"
    # Next 1st of month is 1st September
    assert res.target_datetime == datetime.datetime(2026, 9, 1, 10, 0)
