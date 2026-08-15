"""Deterministic Russian natural language parser for dates, times, relative intervals, and recurrences."""

import re
import datetime
from dataclasses import dataclass
from typing import Optional, Tuple
from dateutil.relativedelta import relativedelta

from app.utils.datetime_utils import get_tz


@dataclass
class ParsedReminder:
    text: str
    target_datetime: Optional[datetime.datetime] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    recurrence_end_at: Optional[datetime.datetime] = None
    time_slot_used: Optional[str] = None
    confidence: float = 1.0
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


# Default time slots for vague time words
DEFAULT_TIME_SLOTS = {
    "утром": (9, 0, "утро (09:00)"),
    "утро": (9, 0, "утро (09:00)"),
    "днем": (14, 0, "день (14:00)"),
    "днём": (14, 0, "день (14:00)"),
    "вечером": (19, 0, "вечер (19:00)"),
    "вечер": (19, 0, "вечер (19:00)"),
    "ночью": (22, 0, "ночь (22:00)"),
    "ночь": (22, 0, "ночь (22:00)"),
}

WEEKDAYS_MAP = {
    "понедельник": 0, "пн": 0, "понедельникам": 0,
    "вторник": 1, "вт": 1, "вторникам": 1,
    "среду": 2, "среда": 2, "ср": 2, "средам": 2,
    "четверг": 3, "чт": 3, "четвергам": 3,
    "пятницу": 4, "пятница": 4, "пт": 4, "пятницам": 4,
    "субботу": 5, "суббота": 5, "сб": 5, "субботам": 5,
    "воскресенье": 6, "вс": 6, "воскресеньям": 6
}

RRULE_DAY_CODES = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}

MONTH_MAP = {
    "января": 1, "январь": 1,
    "февраля": 2, "февраль": 2,
    "марта": 3, "март": 3,
    "апреля": 4, "апрель": 4,
    "мая": 5, "май": 5,
    "июня": 6, "июнь": 6,
    "июля": 7, "июль": 7,
    "августа": 8, "август": 8,
    "сентября": 9, "сентябрь": 9,
    "октября": 10, "октябрь": 10,
    "ноября": 11, "ноябрь": 11,
    "декабря": 12, "декабрь": 12
}


def clean_reminder_text(text: str) -> str:
    """Strip prefix phrases like 'напомни', 'напомнить мне', 'не забудь'."""
    text = re.sub(r'^(напомни(ть)?|пожалуйста|не забудь(те)?|поставь напоминание|напоминалка)\s+(мне\s+)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+(напомни(ть)?|не забудь(те)?)$', '', text, flags=re.IGNORECASE)
    return text.strip()


def parse_deterministic(text: str, now_local: datetime.datetime) -> ParsedReminder:
    """
    Main deterministic parsing function for Russian text queries.
    """
    original_input = text.strip()
    cleaned = clean_reminder_text(original_input)
    lower_text = cleaned.lower()

    # 1. Check for Recurring Rules first
    recurring_res = _try_parse_recurring(lower_text, now_local)
    if recurring_res:
        rem_text = _extract_rem_text(cleaned, recurring_res.get("matched_span"))
        return ParsedReminder(
            text=rem_text or cleaned,
            target_datetime=recurring_res["target_datetime"],
            is_recurring=True,
            recurrence_rule=recurring_res["rrule"],
            time_slot_used=recurring_res.get("time_slot")
        )

    # 2. Relative offset (e.g. "через 15 минут", "через 2 часа", "через полчаса", "через 3 дня")
    rel_res = _try_parse_relative(lower_text, now_local)
    if rel_res:
        rem_text = _extract_rem_text(cleaned, rel_res["matched_span"])
        return ParsedReminder(
            text=rem_text or cleaned,
            target_datetime=rel_res["target_datetime"]
        )

    # 3. Absolute or relative date + time (e.g. "завтра в 15:00", "сегодня вечером", "в понедельник в 19:30", "16 августа в 10:00")
    dt_res = _try_parse_datetime(lower_text, now_local)
    if dt_res:
        rem_text = _extract_rem_text(cleaned, dt_res["matched_span"])
        return ParsedReminder(
            text=rem_text or cleaned,
            target_datetime=dt_res["target_datetime"],
            time_slot_used=dt_res.get("time_slot")
        )

    # If no date/time found at all, return clarification required
    return ParsedReminder(
        text=cleaned,
        target_datetime=None,
        confidence=0.3,
        clarification_needed=True,
        clarification_question="Когда напомнить?"
    )


def _extract_rem_text(full_text: str, matched_span: Optional[Tuple[int, int]]) -> str:
    """Remove matched date/time substring from the user query safely."""
    if not matched_span:
        return full_text.strip()
    start, end = matched_span

    # Check if there is a leading preposition preceding start (e.g. "в 15:00", "в понедельник")
    prefix = full_text[:start]
    m_prep = re.search(r'\b(в|во|на|к|около)\s+$', prefix, flags=re.IGNORECASE)
    if m_prep:
        start = m_prep.start()

    result = full_text[:start] + " " + full_text[end:]
    result = re.sub(r'\s+', ' ', result).strip()
    return result or full_text.strip()


def _extract_time(text: str) -> Tuple[Optional[int], Optional[int], Optional[Tuple[int, int]]]:
    """Extract HH:MM or 'в HH' or standalone hour from string."""
    # Pattern 1: 15:00, 15-00, 15.00
    m = re.search(r'\b(в\s+)?([0-1]?[0-9]|2[0-3])[:.-]([0-5][0-9])\b', text)
    if m:
        return int(m.group(2)), int(m.group(3)), (m.start(), m.end())

    # Pattern 2: в 15, в 8 (hour after 'в' or 'во')
    m2 = re.search(r'\b(в|во)\s+([0-1]?[0-9]|2[0-3])\b', text)
    if m2:
        return int(m2.group(2)), 0, (m2.start(), m2.end())

    # Pattern 3: standalone hour after relative date word (e.g. "завтра 18", "сегодня 9")
    m3 = re.search(r'\b(сегодня|завтра|послезавтра)\s+([0-1]?[0-9]|2[0-3])\b', text)
    if m3:
        return int(m3.group(2)), 0, (m3.start(2), m3.end(2))

    return None, None, None


def _try_parse_relative(text: str, now: datetime.datetime) -> Optional[dict]:
    """Parse relative expressions: через X минут/часов/дней/недель/полчаса."""
    m_half = re.search(r'\bчерез\s+полчаса\b', text)
    if m_half:
        return {
            "target_datetime": now + datetime.timedelta(minutes=30),
            "matched_span": (m_half.start(), m_half.end())
        }

    m = re.search(r'\bчерез\s+(\d+)\s*(мин|минут|минуты|час|часа|часов|дней|дня|день|недель|неделю|недели)\b', text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        target = now
        if unit.startswith("мин"):
            target += datetime.timedelta(minutes=num)
        elif unit.startswith("час"):
            target += datetime.timedelta(hours=num)
        elif unit.startswith("дн") or unit.startswith("ден"):
            target += datetime.timedelta(days=num)
        elif unit.startswith("недел"):
            target += datetime.timedelta(weeks=num)
        return {
            "target_datetime": target,
            "matched_span": (m.start(), m.end())
        }

    return None


def _try_parse_recurring(text: str, now: datetime.datetime) -> Optional[dict]:
    """Parse recurring expressions: каждый день, по будням, каждую пятницу, каждые 2 часа, etc."""
    time_slot = None
    h, m, time_span = _extract_time(text)
    
    if h is None:
        for slot_key, (sh, sm, slot_label) in DEFAULT_TIME_SLOTS.items():
            if slot_key in text:
                h, m = sh, sm
                time_slot = slot_label
                break
    
    if h is None:
        h, m = 9, 0

    # 1. "каждые X часа / 3 дня"
    m_int = re.search(r'\bкаждые\s+(\d+)\s*(час|часа|часов|дней|дня|день)\b', text)
    if m_int:
        val = int(m_int.group(1))
        unit = m_int.group(2)
        if unit.startswith("час"):
            rrule = f"INTERVAL;HOURS={val}"
            target = now + datetime.timedelta(hours=val)
        else:
            rrule = f"INTERVAL;DAYS={val}"
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=val)
        return {
            "rrule": rrule,
            "target_datetime": target,
            "time_slot": time_slot,
            "matched_span": (m_int.start(), time_span[1] if time_span else m_int.end())
        }

    # 2. "каждый будний день", "по будням", "каждый рабочий день"
    m_workdays = re.search(r'\b(каждый\s+будний\s+день|по\s+будням|каждый\s+рабочий\s+день|по\s+рабочим\s+дням)\b', text)
    if m_workdays:
        rrule = "WEEKLY;BYDAY=MO,TU,WE,TH,FR"
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        while target.weekday() >= 5 or target <= now:
            target += datetime.timedelta(days=1)
        return {
            "rrule": rrule,
            "target_datetime": target,
            "time_slot": time_slot,
            "matched_span": (m_workdays.start(), time_span[1] if time_span else m_workdays.end())
        }

    # 3. "каждый день", "ежедневно", "каждый вечер"
    m_daily = re.search(r'\b(каждый\s+день|ежедневно|каждое\s+утро|каждый\s+вечер)\b', text)
    if m_daily:
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return {
            "rrule": "DAILY",
            "target_datetime": target,
            "time_slot": time_slot,
            "matched_span": (m_daily.start(), time_span[1] if time_span else m_daily.end())
        }

    # 4. "каждую субботу", "каждый понедельник", "по понедельникам и пятницам"
    m_weekly_days = re.findall(r'\b(каждую|каждый|по)\s+([а-яa-z]+)\b', text)
    found_days = []
    for prefix, day_word in m_weekly_days:
        if prefix in ("каждую", "каждый", "по") and day_word in WEEKDAYS_MAP:
            found_days.append(WEEKDAYS_MAP[day_word])
    if found_days:
        day_codes = ",".join(RRULE_DAY_CODES[d] for d in sorted(set(found_days)))
        rrule = f"WEEKLY;BYDAY={day_codes}"
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        while target.weekday() not in found_days or target <= now:
            target += datetime.timedelta(days=1)
        return {
            "rrule": rrule,
            "target_datetime": target,
            "time_slot": time_slot,
            "matched_span": (0, time_span[1] if time_span else len(text))
        }

    # 5. "каждое 1 число месяца", "каждый месяц 15 числа"
    m_monthly = re.search(r'\bкаждое\s+(\d+)\s+число\b|\bкаждый\s+месяц\s+(\d+)\s+числа\b', text)
    if m_monthly:
        dom = int(m_monthly.group(1) or m_monthly.group(2))
        rrule = f"MONTHLY;BYMONTHDAY={dom}"
        target = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += relativedelta(months=1)
        return {
            "rrule": rrule,
            "target_datetime": target,
            "time_slot": time_slot,
            "matched_span": (m_monthly.start(), time_span[1] if time_span else m_monthly.end())
        }

    return None


def _try_parse_datetime(text: str, now: datetime.datetime) -> Optional[dict]:
    """Parse absolute/relative dates with or without specific time."""
    time_slot = None
    h, m, time_span = _extract_time(text)

    if h is None:
        for slot_key, (sh, sm, slot_label) in DEFAULT_TIME_SLOTS.items():
            if slot_key in text:
                h, m = sh, sm
                time_slot = slot_label
                break

    target_date = None
    span_start, span_end = (time_span[0], time_span[1]) if time_span else (0, 0)

    # "сегодня"
    m_today = re.search(r'\bсегодня\b', text)
    if m_today:
        target_date = now.date()
        span_start = min(span_start, m_today.start()) if time_span else m_today.start()
        span_end = max(span_end, m_today.end()) if time_span else m_today.end()

    # "завтра"
    m_tmr = re.search(r'\bзавтра\b', text)
    if m_tmr and not target_date:
        target_date = now.date() + datetime.timedelta(days=1)
        span_start = min(span_start, m_tmr.start()) if time_span else m_tmr.start()
        span_end = max(span_end, m_tmr.end()) if time_span else m_tmr.end()

    # "послезавтра"
    m_dat = re.search(r'\bпослезавтра\b', text)
    if m_dat and not target_date:
        target_date = now.date() + datetime.timedelta(days=2)
        span_start = min(span_start, m_dat.start()) if time_span else m_dat.start()
        span_end = max(span_end, m_dat.end()) if time_span else m_dat.end()

    # Specific weekday: "в понедельник", "в пятницу", "в сб"
    if not target_date:
        m_wd = re.search(r'\b(в|во)?\s*(понедельник|пн|вторник|вт|среду|ср|четверг|чт|пятницу|пт|субботу|сб|воскресенье|вс)\b', text)
        if m_wd:
            day_word = m_wd.group(2)
            target_w = WEEKDAYS_MAP.get(day_word)
            if target_w is not None:
                days_ahead = target_w - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now.date() + datetime.timedelta(days=days_ahead)
                span_start = min(span_start, m_wd.start()) if time_span else m_wd.start()
                span_end = max(span_end, m_wd.end()) if time_span else m_wd.end()

    # Explicit day + month: "16 августа", "15 мая"
    if not target_date:
        m_dm = re.search(r'\b(\d{1,2})\s+([а-я]+)\b', text)
        if m_dm:
            day_num = int(m_dm.group(1))
            month_word = m_dm.group(2)
            month_num = MONTH_MAP.get(month_word)
            if month_num:
                year = now.year
                try:
                    candidate = datetime.date(year, month_num, day_num)
                    if candidate < now.date():
                        candidate = datetime.date(year + 1, month_num, day_num)
                    target_date = candidate
                    span_start = min(span_start, m_dm.start()) if time_span else m_dm.start()
                    span_end = max(span_end, m_dm.end()) if time_span else m_dm.end()
                except ValueError:
                    pass

    if not target_date and h is not None:
        target_date = now.date()
        candidate_dt = datetime.datetime.combine(target_date, datetime.time(h, m))
        if candidate_dt <= now:
            target_date += datetime.timedelta(days=1)
        span_start = span_start or (time_span[0] if time_span else 0)
        span_end = span_end or (time_span[1] if time_span else len(text))

    if target_date and h is not None:
        final_dt = datetime.datetime.combine(target_date, datetime.time(h, m))
        return {
            "target_datetime": final_dt,
            "time_slot": time_slot,
            "matched_span": (span_start, span_end)
        }
    elif target_date and h is None:
        final_dt = datetime.datetime.combine(target_date, datetime.time(9, 0))
        return {
            "target_datetime": final_dt,
            "time_slot": "утро по умолчанию (09:00)",
            "matched_span": (span_start, span_end)
        }

    return None
