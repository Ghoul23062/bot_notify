"""Pytest fixtures for database, mock bot, and test objects."""

import pytest
import datetime
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, MagicMock

from app.db.database import Base
from app.db import crud
from app.db.models import User
from app.utils.datetime_utils import utc_now


@pytest.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an in-memory SQLite async database session for isolated tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(test_db_session: AsyncSession) -> User:
    """Create a sample user fixture."""
    return await crud.get_or_create_user(
        session=test_db_session,
        telegram_id=123456789,
        username="test_user",
        first_name="Тест",
        default_tz="Europe/Moscow"
    )


@pytest.fixture
def mock_bot():
    """Mock aiogram Bot instance."""
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=True)
    return bot
