"""Alert model."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class Alert(Base, TimestampMixin):
    """System-generated alert."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str | None] = mapped_column(String(10), index=True)
    alert_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # Categories: funding | origination | earnings | guidance | options_flow |
    #   iv_spike | breakout | breakdown | short_spike | squeeze | borrow_cost |
    #   valuation | macro | world_news | spy_divergence | beta_shift |
    #   model_drift | forecast_collapse | signal_conflict | no_edge
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # info | warning | critical
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    data_json: Mapped[str | None] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
