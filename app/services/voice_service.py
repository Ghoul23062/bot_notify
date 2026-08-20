"""Voice transcription service supporting Groq Whisper, OpenAI Whisper, Gemini Audio, and Google Free Speech."""

import io
import os
import json
import base64
import logging
import tempfile
import subprocess
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
    Transcribe audio bytes to Russian text.
    Order of priority:
      1. Groq Whisper (Whisper-large-v3, ultra-fast)
      2. OpenAI Whisper
      3. Google Gemini 1.5 Flash (Multimodal Audio)
      4. Google Free Speech API fallback (0 keys needed)
    """
    # 1. Try Groq Whisper (Whisper Large v3)
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

    # 4. Try Google Free Speech API fallback (No API keys needed)
    free_result = await _transcribe_google_free(audio_bytes)
    if free_result:
        return free_result

    return None


async def _transcribe_google_free(audio_bytes: bytes) -> Optional[str]:
    """Free Chromium Web Speech recognition fallback using ffmpeg if available."""
    ogg_path = None
    flac_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_f:
            ogg_f.write(audio_bytes)
            ogg_path = ogg_f.name

        flac_path = ogg_path.replace(".ogg", ".flac")

        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", flac_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        if proc.returncode == 0 and os.path.exists(flac_path):
            with open(flac_path, "rb") as f:
                flac_data = f.read()

            url = "https://www.google.com/speech-api/v2/recognize?client=chromium&lang=ru-RU&maxresults=1"
            headers = {"Content-Type": "audio/x-flac; rate=16000"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, content=flac_data)
                if res.status_code == 200:
                    for line in res.text.strip().split("\n"):
                        if line:
                            data = json.loads(line)
                            result = data.get("result", [])
                            if result and len(result) > 0:
                                alt = result[0].get("alternative", [])
                                if alt and len(alt) > 0:
                                    transcript = alt[0].get("transcript", "").strip()
                                    if transcript:
                                        return transcript
    except Exception as e:
        logger.debug(f"Google free speech fallback error: {e}")
    finally:
        if ogg_path and os.path.exists(ogg_path):
            try:
                os.remove(ogg_path)
            except OSError:
                pass
        if flac_path and os.path.exists(flac_path):
            try:
                os.remove(flac_path)
            except OSError:
                pass
    return None
