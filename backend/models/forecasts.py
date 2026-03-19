"""Forecast and forecast-validation models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class Forecast(Base, TimestampMixin, DataQualityMixin):
    """Point-in-time price / metric forecast."""
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    forecast_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    target_variable: Mapped[str] = mapped_column(String(50), nullable=False)
    # Target variables: price, return, iv, origination_volume, revenue, etc.

    model_name: Mapped[str] = mapped_column(String(60), nullable=False)
    point_estimate: Mapped[float | None] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float)
    upper_bound: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.80)
    probability_up: Mapped[float | None] = mapped_column(Float)
    probability_down: Mapped[float | None] = mapped_column(Float)
    probability_flat: Mapped[float | None] = mapped_column(Float)

    regime_context: Mapped[str | None] = mapped_column(String(50))
    assumptions_json: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)


class ForecastValidation(Base, TimestampMixin):
    """Post-hoc validation of a forecast once the horizon has passed."""
    __tablename__ = "forecast_validations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    forecast_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    error: Mapped[float] = mapped_column(Float, nullable=False)
    abs_error: Mapped[float] = mapped_column(Float, nullable=False)
    pct_error: Mapped[float | None] = mapped_column(Float)
    within_interval: Mapped[bool | None] = mapped_column()
    brier_score: Mapped[float | None] = mapped_column(Float)
    direction_correct: Mapped[bool | None] = mapped_column()
