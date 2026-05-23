"""Database session factory for async SQLAlchemy.

Provides the async engine, session maker, and dependency injection helpers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agentos.config import DatabaseConfig

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(db_config: DatabaseConfig) -> AsyncEngine:
    """Initialize the async SQLAlchemy engine."""
    global _engine, _session_factory

    _engine = create_async_engine(
        db_config.url,
        pool_size=db_config.pool_size,
        max_overflow=db_config.max_overflow,
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    logger.info("Database engine initialized: %s", db_config.url.split("@")[-1])  # Log without credentials
    return _engine


def get_engine() -> AsyncEngine:
    """Get the current async engine."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory."""
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized. Call init_engine() first.")
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session (context manager).

    Usage:
        async with get_session() as session:
            result = await session.execute(select(AgentModel))
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables (for development/testing)."""
    from agentos.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def drop_tables() -> None:
    """Drop all tables (for testing only)."""
    from agentos.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_engine() -> None:
    """Close the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed")
