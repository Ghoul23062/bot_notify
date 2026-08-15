"""Hybrid parser combining high-speed deterministic parser with optional AI fallback."""

import datetime
from app.services.parser.deterministic import parse_deterministic, ParsedReminder
from app.services.parser.ai_parser import parse_with_ai


async def parse_reminder_input(
    text: str,
    now_local: datetime.datetime,
    user_tz: str = "Europe/Moscow"
) -> ParsedReminder:
    """
    Parse natural language text into a structured ParsedReminder object.
    1. Runs fast deterministic parsing.
    2. Uses AI fallback if deterministic result is ambiguous and AI key is present.
    """
    det_res = parse_deterministic(text, now_local)

    # High confidence or explicit recurrence -> return immediately
    if det_res.target_datetime is not None or det_res.is_recurring:
        return det_res

    # Try AI parser if deterministic parser could not extract a target date/time
    ai_res = await parse_with_ai(text, now_local, user_tz)
    if ai_res and (ai_res.target_datetime or ai_res.is_recurring):
        return ai_res

    # Fallback to deterministic (asks clarification)
    return det_res
