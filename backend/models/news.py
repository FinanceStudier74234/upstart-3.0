"""News / event / sentiment models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class NewsItem(Base, TimestampMixin, DataQualityMixin):
    """News articles and event items."""
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str | None] = mapped_column(String(10), index=True)  # NULL = macro/market-level
    published_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50))
    # Categories: earnings | funding | origination | macro | fed | credit |
    #   fintech | regulatory | world | peer | general

    sentiment_score: Mapped[float | None] = mapped_column(Float)  # -1..+1
    sentiment_label: Mapped[str | None] = mapped_column(String(20))  # very_bearish..very_bullish
    relevance_score: Mapped[float | None] = mapped_column(Float)  # 0..1
    policy_risk_flag: Mapped[bool] = mapped_column(default=False)
    world_risk_flag: Mapped[bool] = mapped_column(default=False)
    funding_flag: Mapped[bool] = mapped_column(default=False)
    earnings_flag: Mapped[bool] = mapped_column(default=False)

    # Second-order transmission estimate
    upst_transmission_score: Mapped[float | None] = mapped_column(Float)  # -1..+1
    transmission_reasoning: Mapped[str | None] = mapped_column(Text)
