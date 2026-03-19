"""Macro / credit / rates data models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Date, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class MacroIndicator(Base, TimestampMixin, DataQualityMixin):
    """Time-series macro/credit indicators from FRED and other sources."""
    __tablename__ = "macro_indicators"
    __table_args__ = (
        UniqueConstraint("indicator", "observation_date", name="uq_macro"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Supported indicators:
    #   FED_FUNDS, TREASURY_2Y, TREASURY_10Y, YIELD_CURVE_2_10,
    #   CPI_YOY, PCE_YOY, UNEMPLOYMENT, INITIAL_CLAIMS,
    #   HY_SPREAD, IG_SPREAD, CONSUMER_CREDIT,
    #   CONSUMER_DELINQUENCY, ABS_SPREAD,
    #   VIX, MOVE_INDEX, FINANCIAL_CONDITIONS,
    #   RECESSION_PROB, LENDING_STANDARDS
    observation_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    prior_value: Mapped[float | None] = mapped_column(Float)
    change: Mapped[float | None] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float)  # vs rolling history
    percentile: Mapped[float | None] = mapped_column(Float)  # vs full history
    unit: Mapped[str | None] = mapped_column(String(30))
    frequency: Mapped[str | None] = mapped_column(String(20))  # daily | weekly | monthly | quarterly
    description: Mapped[str | None] = mapped_column(Text)
