"""Voice transcription service supporting Groq Whisper, OpenAI Whisper, and Gemini Audio."""

import io
import base64
import logging
from typing import Optional
from aiogram import Bot
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def download_voice_file(bot: Bot, file_id: str) -> bytes:
    """Download voice note bytes from Telegram servers."""
    file = await bot.get_file(file_id)
    stream = io.BytesIO()
    await bot.download_file(file.file_path, destination=stream)
    return stream.getvalue()


async def transcribe_voice(audio_bytes: bytes) -> Optional[str]:
    """
    Transcribe audio bytes to Russian text using Groq Whisper, OpenAI Whisper, or Gemini.
    Returns transcribed text string or None if failed / unconfigured.
    """
    # 1. Try Groq Whisper (Super-fast Whisper Large v3)
    groq_key = settings.groq_api_key or (settings.ai_api_key if settings.ai_provider == "groq" else None)
    if groq_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                files = {"file": ("voice.ogg", audio_bytes, "audio/ogg")}
                data = {"model": "whisper-large-v3", "language": "ru", "response_format": "json"}
                res = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    files=files,
                    data=data
                )
                if res.status_code == 200:
                    text = res.json().get("text", "").strip()
                    if text:
                        return text
        except Exception as e:
            logger.warning(f"Groq whisper transcription error: {e}")

    # 2. Try OpenAI Whisper
    if settings.ai_api_key and settings.ai_provider == "openai":
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                files = {"file": ("voice.ogg", audio_bytes, "audio/ogg")}
                data = {"model": "whisper-1", "language": "ru"}
                res = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                    files=files,
                    data=data
                )
                if res.status_code == 200:
                    text = res.json().get("text", "").strip()
                    if text:
                        return text
        except Exception as e:
            logger.warning(f"OpenAI whisper transcription error: {e}")

    # 3. Try Gemini Multimodal Audio (Gemini 1.5 Flash)
    if settings.ai_api_key and settings.ai_provider in ["gemini", "default"]:
        try:
            b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            prompt = "Точно расшифруй аудиозапись на русском языке. Верни ТОЛЬКО текст того, что сказано вслух, без лишних пояснений."
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.ai_api_key}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "audio/ogg", "data": b64_audio}}
                        ]
                    }]
                }
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        return text
        except Exception as e:
            logger.warning(f"Gemini audio transcription error: {e}")

    return None
