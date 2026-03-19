"""
Database Connection Service — Async SQLAlchemy engine and session management.
Falls back gracefully when no database is available.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None
_db_available = False


async def init_db():
    """Initialize database connection. Fails gracefully if unavailable."""
    global _engine, _session_factory, _db_available

    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from backend.config.settings import settings

        _engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_size=settings.database_pool_size,
            pool_pre_ping=True,
        )

        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        _db_available = True
        logger.info("Database connection established")
    except Exception as e:
        logger.warning("Database not available, running in stateless mode: %s", e)
        _db_available = False


async def close_db():
    """Close database connection."""
    global _engine, _db_available
    if _engine:
        await _engine.dispose()
        _db_available = False
        logger.info("Database connection closed")


@asynccontextmanager
async def get_session():
    """Get an async database session."""
    if not _db_available or not _session_factory:
        yield None
        return

    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def is_available() -> bool:
    """Check if database is connected."""
    return _db_available
