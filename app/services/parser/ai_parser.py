"""Optional AI/LLM integration adapter for parsing complex ambiguous queries."""

import json
import datetime
import logging
from typing import Optional
import httpx

from app.config import settings
from app.services.parser.deterministic import ParsedReminder

logger = logging.getLogger(__name__)


async def parse_with_ai(text: str, now_local: datetime.datetime, user_tz: str) -> Optional[ParsedReminder]:
    """
    Query LLM API if AI_API_KEY is configured.
    Returns structured ParsedReminder or None if disabled/failed.
    """
    if not settings.ai_api_key:
        return None

    prompt = f"""
System: You are an expert natural language parser for a Telegram Reminder Bot.
User local time: {now_local.isoformat()} (Timezone: {user_tz}).
User input: "{text}"

Extract the reminder details into strict JSON:
{{
    "reminder_text": "cleaned reminder text without date/time words",
    "iso_datetime": "YYYY-MM-DDTHH:MM:SS or null if missing",
    "is_recurring": true/false,
    "recurrence_rule": "rrule string or null (e.g. DAILY, WEEKLY;BYDAY=MO, MONTHLY;BYMONTHDAY=1, INTERVAL;HOURS=2)",
    "confidence": 0.0 to 1.0,
    "clarification_needed": true/false,
    "clarification_question": "short question if time is missing or text is ambiguous, else null"
}}
Return ONLY valid JSON.
"""

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            if settings.ai_provider == "openai":
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    }
                )
                data = response.json()
                content = data["choices"][0]["message"]["content"]
            else:  # Gemini REST API default (gemini-flash-latest)
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={settings.ai_api_key}"
                response = await client.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"}
                    }
                )
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]

            parsed_json = json.loads(content)
            target_dt = None
            if parsed_json.get("iso_datetime"):
                target_dt = datetime.datetime.fromisoformat(parsed_json["iso_datetime"])

            return ParsedReminder(
                text=parsed_json.get("reminder_text", text),
                target_datetime=target_dt,
                is_recurring=parsed_json.get("is_recurring", False),
                recurrence_rule=parsed_json.get("recurrence_rule"),
                confidence=float(parsed_json.get("confidence", 0.9)),
                clarification_needed=parsed_json.get("clarification_needed", False),
                clarification_question=parsed_json.get("clarification_question")
            )
    except Exception as e:
        logger.warning(f"AI parser fallback triggered due to error: {e}")
        return None
