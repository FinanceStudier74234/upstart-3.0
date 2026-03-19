"""Funding / capital markets models — facilities, securitizations, partners."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class FundingFacility(Base, TimestampMixin, DataQualityMixin):
    """Warehouse / credit facility tracking."""
    __tablename__ = "funding_facilities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    facility_name: Mapped[str] = mapped_column(String(200), nullable=False)
    partner_name: Mapped[str | None] = mapped_column(String(200))
    facility_type: Mapped[str] = mapped_column(String(50))  # warehouse | revolving | term
    committed: Mapped[bool] = mapped_column(Boolean, default=False)
    facility_size: Mapped[float | None] = mapped_column(Float)  # USD millions
    drawn_amount: Mapped[float | None] = mapped_column(Float)
    available_amount: Mapped[float | None] = mapped_column(Float)
    maturity_date: Mapped[dt.date | None] = mapped_column(Date)
    revolving_period_end: Mapped[dt.date | None] = mapped_column(Date)
    interest_rate_type: Mapped[str | None] = mapped_column(String(50))  # fixed | floating
    spread_bps: Mapped[float | None] = mapped_column(Float)
    advance_rate: Mapped[float | None] = mapped_column(Float)
    has_covenant: Mapped[bool] = mapped_column(Boolean, default=False)
    covenant_details: Mapped[str | None] = mapped_column(Text)
    has_waiver: Mapped[bool] = mapped_column(Boolean, default=False)
    waiver_details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | expired | renewed
    renewal_probability: Mapped[float | None] = mapped_column(Float)  # 0..1 model estimate
    filing_source: Mapped[str | None] = mapped_column(Text)
    last_updated_from_filing: Mapped[dt.date | None] = mapped_column(Date)


class Securitization(Base, TimestampMixin, DataQualityMixin):
    """ABS / securitization deal tracking."""
    __tablename__ = "securitizations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    deal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuance_date: Mapped[dt.date | None] = mapped_column(Date)
    deal_size: Mapped[float | None] = mapped_column(Float)  # USD millions
    collateral_type: Mapped[str | None] = mapped_column(String(100))  # personal | auto | mixed
    weighted_avg_coupon: Mapped[float | None] = mapped_column(Float)
    weighted_avg_life: Mapped[float | None] = mapped_column(Float)
    subordination_pct: Mapped[float | None] = mapped_column(Float)
    initial_cnl_estimate: Mapped[float | None] = mapped_column(Float)  # Cumulative Net Loss
    current_cnl: Mapped[float | None] = mapped_column(Float)
    delinquency_30d: Mapped[float | None] = mapped_column(Float)
    delinquency_60d: Mapped[float | None] = mapped_column(Float)
    delinquency_90d: Mapped[float | None] = mapped_column(Float)
    cumulative_default_rate: Mapped[float | None] = mapped_column(Float)
    deal_status: Mapped[str] = mapped_column(String(20), default="active")
    rating_agency: Mapped[str | None] = mapped_column(String(50))
    senior_tranche_rating: Mapped[str | None] = mapped_column(String(10))


class FundingPartner(Base, TimestampMixin, DataQualityMixin):
    """Bank / institutional funding partner tracking."""
    __tablename__ = "funding_partners"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    partner_name: Mapped[str] = mapped_column(String(200), nullable=False)
    partner_type: Mapped[str | None] = mapped_column(String(50))  # bank | credit_union | institutional
    relationship_start: Mapped[dt.date | None] = mapped_column(Date)
    is_forward_flow: Mapped[bool] = mapped_column(Boolean, default=False)
    forward_flow_commitment: Mapped[float | None] = mapped_column(Float)
    products_covered: Mapped[str | None] = mapped_column(Text)  # JSON list of product types
    status: Mapped[str] = mapped_column(String(20), default="active")
    concentration_pct: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
