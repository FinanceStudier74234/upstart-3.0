"""SQLAlchemy models for analysis persistence."""

from __future__ import annotations

import datetime as dt
from sqlalchemy import Column, String, Float, DateTime, Integer, JSON, Boolean, Text, Index
from backend.models.base import Base


class AnalysisRecord(Base):
    """Persists each full analysis run."""
    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, default="UPST")
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc))
    price = Column(Float)

    # Core scores (denormalized for fast queries)
    composite_score = Column(Float)
    technical_strength = Column(Float)
    options_sentiment = Column(Float)
    short_opportunity = Column(Float)
    squeeze_risk = Column(Float)
    funding_strength = Column(Float)
    macro_pressure = Column(Float)
    valuation_attractiveness = Column(Float)

    # Trade decision
    action = Column(String(30))
    confidence = Column(Float)
    target_price = Column(Float)
    stop_price = Column(Float)

    # Forecast
    forecast_point = Column(Float)
    forecast_lower = Column(Float)
    forecast_upper = Column(Float)

    # Risk
    var_95 = Column(Float)
    max_drawdown = Column(Float)

    # Full JSON blob (for detailed lookups)
    full_analysis = Column(JSON)

    # Data quality
    data_sources = Column(JSON)
    warnings_count = Column(Integer, default=0)
    mock_data_used = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_analysis_ticker_ts", "ticker", "timestamp"),
    )


class AlertRecord(Base):
    """Persists alerts for audit trail."""
    __tablename__ = "alert_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, default="UPST")
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc))
    severity = Column(String(20), nullable=False)  # info, warning, critical, urgent
    title = Column(String(200), nullable=False)
    message = Column(Text)
    category = Column(String(50))
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True))


class BacktestRecord(Base):
    """Persists backtest results."""
    __tablename__ = "backtest_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc))
    strategy = Column(String(100), nullable=False)
    params = Column(JSON)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    results = Column(JSON)
