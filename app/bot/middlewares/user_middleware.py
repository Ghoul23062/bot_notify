"""Middleware for resolving Telegram user into database User entity and settings."""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.config import settings


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user: TelegramUser = data.get("event_from_user")
        session: AsyncSession = data.get("session")

        if event_user and session:
            user = await crud.get_or_create_user(
                session=session,
                telegram_id=event_user.id,
                username=event_user.username,
                first_name=event_user.first_name,
                default_tz=settings.default_timezone
            )
            data["user"] = user
            data["user_tz"] = user.settings.timezone if (user and user.settings) else settings.default_timezone

        return await handler(event, data)
