"""Audit trail and data-quality log models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    """Audit trail for data mutations and model runs."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # Event types: data_ingestion | model_run | score_update | forecast_generated |
    #   alert_fired | decision_generated | backtest_run | config_change
    entity: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(Text)
    user_or_system: Mapped[str] = mapped_column(String(50), default="system")


class DataQualityLog(Base, TimestampMixin):
    """Logs data quality issues and staleness events."""
    __tablename__ = "data_quality_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_source: Mapped[str] = mapped_column(String(60), nullable=False)
    table_name: Mapped[str] = mapped_column(String(60), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Issue types: stale | missing | outlier | schema_mismatch | api_error | gap
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    quality_score: Mapped[float | None] = mapped_column(Float)
