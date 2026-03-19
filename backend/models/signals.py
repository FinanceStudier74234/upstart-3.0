"""Signal and trade-decision models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class Signal(Base, TimestampMixin, DataQualityMixin):
    """Individual analytical signal from any engine."""
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    signal_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    engine: Mapped[str] = mapped_column(String(60), nullable=False)
    # Engines: technical, options, short, funding, origination, macro, valuation,
    #   news, factor, behavioral, execution, ensemble
    signal_name: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # bullish | bearish | neutral
    strength: Mapped[float] = mapped_column(Float, nullable=False)  # 0..1
    timeframe: Mapped[str] = mapped_column(String(16), default="daily")
    explanation: Mapped[str | None] = mapped_column(Text)
    data_inputs_json: Mapped[str | None] = mapped_column(Text)


class TradeDecision(Base, TimestampMixin, DataQualityMixin):
    """Aggregated trade decision from the decision engine."""
    __tablename__ = "trade_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    decision_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)

    # Decision
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    # Actions: buy | add | hold | trim | sell | short | add_short | cover |
    #   buy_calls | buy_puts | bull_spread | bear_spread | vol_trade | no_trade
    vehicle: Mapped[str] = mapped_column(String(30), nullable=False)
    # Vehicles: common_stock | call_option | put_option | call_spread | put_spread |
    #   short_stock | no_vehicle

    # Levels
    entry_price: Mapped[float | None] = mapped_column(Float)
    target_price: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    invalidation_price: Mapped[float | None] = mapped_column(Float)
    reward_risk_ratio: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)

    # Sizing
    suggested_position_pct: Mapped[float | None] = mapped_column(Float)
    max_loss_pct: Mapped[float | None] = mapped_column(Float)

    # Scoring
    trade_quality_score: Mapped[float | None] = mapped_column(Float)  # 0..100
    signal_agreement_pct: Mapped[float | None] = mapped_column(Float)  # % of signals agreeing
    fragility_score: Mapped[float | None] = mapped_column(Float)

    # Explanation
    dominant_factors_json: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    what_would_change: Mapped[str | None] = mapped_column(Text)
    risk_factors: Mapped[str | None] = mapped_column(Text)
