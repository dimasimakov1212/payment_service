from collections.abc import AsyncGenerator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Отдаёт async-сессию SQLAlchemy для обработчика запроса."""

    async for session in get_session():
        yield session


def verify_api_key(
    x_api_key: str = Header(
        alias="X-API-Key",
        description="Статический ключ доступа к API",
    ),
) -> None:
    """Проверяет статический API-ключ из заголовка X-API-Key."""
    
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
