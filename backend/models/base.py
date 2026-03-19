"""SQLAlchemy async base and mixins."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class TimestampMixin:
    """created_at / updated_at columns."""
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DataQualityMixin:
    """Standard data-governance columns attached to every data row."""
    source: Mapped[str] = mapped_column(default="unknown")
    source_label: Mapped[str] = mapped_column(default="official")  # official | estimated | proxy
    confidence: Mapped[float] = mapped_column(default=1.0)  # 0..1
    freshness_seconds: Mapped[int | None] = mapped_column(default=None)
    quality_score: Mapped[float] = mapped_column(default=1.0)  # 0..1
    is_stale: Mapped[bool] = mapped_column(default=False)
