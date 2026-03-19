"""Origination / business model data."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class OriginationData(Base, TimestampMixin, DataQualityMixin):
    """Monthly/quarterly origination volumes and metrics."""
    __tablename__ = "origination_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    period: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)  # monthly | quarterly | annual
    product_type: Mapped[str] = mapped_column(String(50), default="total")  # total | personal | auto | heloc

    origination_volume: Mapped[float | None] = mapped_column(Float)  # USD
    loan_count: Mapped[int | None] = mapped_column(Integer)
    avg_loan_size: Mapped[float | None] = mapped_column(Float)
    conversion_rate: Mapped[float | None] = mapped_column(Float)
    approval_rate: Mapped[float | None] = mapped_column(Float)
    avg_apr: Mapped[float | None] = mapped_column(Float)
    avg_model_score: Mapped[float | None] = mapped_column(Float)

    # Growth metrics (computed)
    yoy_growth: Mapped[float | None] = mapped_column(Float)
    qoq_growth: Mapped[float | None] = mapped_column(Float)
    mom_growth: Mapped[float | None] = mapped_column(Float)

    # Revenue contribution
    fee_revenue_from_origination: Mapped[float | None] = mapped_column(Float)
    take_rate: Mapped[float | None] = mapped_column(Float)  # fee / volume
