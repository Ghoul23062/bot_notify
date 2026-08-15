"""Date and time utilities for timezone conversions, formatting, and calculations."""

import datetime
from typing import Optional, Tuple
import zoneinfo
from dateutil import tz


MONTH_NAMES_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

WEEKDAY_NAMES_RU = {
    0: "понедельник", 1: "вторник", 2: "среду", 3: "четверг",
    4: "пятницу", 5: "субботу", 6: "воскресенье"
}


def get_tz(tz_str: str) -> datetime.tzinfo:
    """Get zoneinfo tzinfo object safely fallback to UTC if invalid."""
    try:
        return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        try:
            return tz.gettz(tz_str) or datetime.timezone.utc
        except Exception:
            return datetime.timezone.utc


def utc_now() -> datetime.datetime:
    """Get current UTC datetime (naive in UTC representation for DB simplicity)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def to_utc(dt: datetime.datetime, tz_str: str) -> datetime.datetime:
    """
    Convert a timezone-naive or tz-aware local datetime into a naive UTC datetime.
    If dt is naive, assumes it is in timezone `tz_str`.
    """
    user_tz = get_tz(tz_str)
    if dt.tzinfo is None:
        localized = dt.replace(tzinfo=user_tz)
    else:
        localized = dt.astimezone(user_tz)
    utc_dt = localized.astimezone(datetime.timezone.utc)
    return utc_dt.replace(tzinfo=None)


def to_local(utc_dt: datetime.datetime, tz_str: str) -> datetime.datetime:
    """
    Convert a naive UTC datetime into a localized datetime for timezone `tz_str`.
    """
    if utc_dt.tzinfo is None:
        utc_aware = utc_dt.replace(tzinfo=datetime.timezone.utc)
    else:
        utc_aware = utc_dt.astimezone(datetime.timezone.utc)
    user_tz = get_tz(tz_str)
    return utc_aware.astimezone(user_tz)


def format_russian_datetime(dt_local: datetime.datetime, now_local: Optional[datetime.datetime] = None) -> str:
    """
    Format local datetime into a user-friendly Russian string.
    Examples:
      - "сегодня в 15:00"
      - "завтра, 16 августа, в 10:00"
      - "понедельник, 18 августа, в 09:30"
    """
    if now_local is None:
        now_local = datetime.datetime.now()

    date_diff = (dt_local.date() - now_local.date()).days
    time_str = dt_local.strftime("%H:%M")
    day_month = f"{dt_local.day} {MONTH_NAMES_RU.get(dt_local.month, '')}"

    if date_diff == 0:
        return f"сегодня в {time_str}"
    elif date_diff == 1:
        return f"завтра, {day_month}, в {time_str}"
    elif date_diff == 2:
        return f"послезавтра, {day_month}, в {time_str}"
    elif 0 < date_diff < 7:
        weekday = WEEKDAY_NAMES_RU.get(dt_local.weekday(), "")
        return f"{weekday}, {day_month}, в {time_str}"
    else:
        return f"{day_month} {dt_local.year} г. в {time_str}"


def is_in_quiet_hours(
    dt_local: datetime.datetime,
    quiet_start: Optional[str],
    quiet_end: Optional[str]
) -> bool:
    """
    Check if a given local datetime falls inside quiet hours.
    quiet_start and quiet_end are formatted as "HH:MM" (e.g., "23:00" and "07:00").
    """
    if not quiet_start or not quiet_end:
        return False
    try:
        sh, sm = map(int, quiet_start.split(":"))
        eh, em = map(int, quiet_end.split(":"))
    except ValueError:
        return False

    current_minutes = dt_local.hour * 60 + dt_local.minute
    start_minutes = sh * 60 + sm
    end_minutes = eh * 60 + em

    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    else:  # Overnight range, e.g. 23:00 to 07:00
        return current_minutes >= start_minutes or current_minutes < end_minutes


def adjust_for_quiet_hours(
    dt_local: datetime.datetime,
    quiet_end: str
) -> datetime.datetime:
    """
    If a notification falls in quiet hours, shift it to quiet_end time on the same or next day.
    """
    try:
        eh, em = map(int, quiet_end.split(":"))
    except ValueError:
        return dt_local

    adjusted = dt_local.replace(hour=eh, minute=em, second=0, microsecond=0)
    if adjusted <= dt_local:
        adjusted += datetime.timedelta(days=1)
    return adjusted
