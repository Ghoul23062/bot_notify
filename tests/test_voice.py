"""Unit tests for voice note transcription."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.voice_service import transcribe_voice


@pytest.mark.asyncio
async def test_transcribe_voice_groq():
    fake_audio = b"fake_ogg_bytes"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "напомни завтра в 15:00 позвонить маме"}

    with patch("app.config.settings.groq_api_key", "fake_groq_key"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        
        mock_post.return_value = mock_response

        text = await transcribe_voice(fake_audio)
        assert text == "напомни завтра в 15:00 позвонить маме"


@pytest.mark.asyncio
async def test_transcribe_voice_no_keys():
    fake_audio = b"fake_ogg_bytes"
    with patch("app.config.settings.groq_api_key", None), \
         patch("app.config.settings.ai_api_key", None):
        text = await transcribe_voice(fake_audio)
        assert text is None
