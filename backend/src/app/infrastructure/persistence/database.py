from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import PostgresConfig

logger = logging.getLogger(__name__)


def create_engine(config: PostgresConfig) -> AsyncEngine:
    return create_async_engine(
        config.url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        connect_args={"connect_timeout": config.connect_timeout_seconds},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


class DatabaseReadinessProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            logger.exception("postgres_readiness_check_failed")
            return False
        return True
