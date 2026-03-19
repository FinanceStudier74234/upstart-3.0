"""Score snapshot models — all 15 mandatory scores."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class ScoreSnapshot(Base, TimestampMixin, DataQualityMixin):
    """Point-in-time snapshot of a composite or component score."""
    __tablename__ = "score_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    snapshot_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # Score names:
    #   funding_strength, origination_momentum, macro_pressure, credit_stress,
    #   valuation_attractiveness, technical_strength, options_sentiment,
    #   short_opportunity, squeeze_risk, news_regime, forecast_confidence,
    #   relative_strength_spy, trade_quality, positioning_fragility,
    #   composite_opportunity

    value: Mapped[float] = mapped_column(Float, nullable=False)  # 0..100
    components_json: Mapped[str | None] = mapped_column(Text)  # JSON breakdown
    weights_json: Mapped[str | None] = mapped_column(Text)  # JSON weights used
    inputs_freshness_json: Mapped[str | None] = mapped_column(Text)  # JSON freshness flags
    explanation: Mapped[str | None] = mapped_column(Text)
