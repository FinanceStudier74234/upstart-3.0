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

        # Create tables if they don't exist
        from backend.models.analysis import Base
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created")
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


async def save_analysis(analysis_dict: dict) -> bool:
    """Persist an analysis record to the database."""
    if not _db_available:
        return False
    try:
        from backend.models.analysis import AnalysisRecord
        async with get_session() as session:
            if session is None:
                return False
            scores = analysis_dict.get("scores", {})
            decision = analysis_dict.get("trade_decision", {})
            forecast = analysis_dict.get("forecast", {})
            risk = analysis_dict.get("risk", {})
            sources = analysis_dict.get("data_sources", {})

            record = AnalysisRecord(
                ticker=analysis_dict.get("ticker", "UPST"),
                price=analysis_dict.get("price"),
                composite_score=scores.get("composite_opportunity", {}).get("value"),
                technical_strength=scores.get("technical_strength", {}).get("value"),
                options_sentiment=scores.get("options_sentiment", {}).get("value"),
                short_opportunity=scores.get("short_opportunity", {}).get("value"),
                squeeze_risk=scores.get("squeeze_risk", {}).get("value"),
                funding_strength=scores.get("funding_strength", {}).get("value"),
                macro_pressure=scores.get("macro_pressure", {}).get("value"),
                valuation_attractiveness=scores.get("valuation_attractiveness", {}).get("value"),
                action=decision.get("action"),
                confidence=decision.get("confidence"),
                target_price=decision.get("target_price"),
                stop_price=decision.get("stop_price"),
                forecast_point=forecast.get("ensemble_point"),
                forecast_lower=forecast.get("ensemble_lower"),
                forecast_upper=forecast.get("ensemble_upper"),
                var_95=risk.get("var_95_pct"),
                max_drawdown=risk.get("max_drawdown_pct"),
                full_analysis=analysis_dict,
                data_sources=sources,
                warnings_count=len(analysis_dict.get("warnings", [])),
                mock_data_used=any(v == "mock" for v in sources.values()),
            )
            session.add(record)
        return True
    except Exception as e:
        logger.warning("Failed to save analysis: %s", e)
        return False
