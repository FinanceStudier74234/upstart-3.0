"""Fundamental data models — financials, earnings, filings, insiders, institutions."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class FinancialStatement(Base, TimestampMixin, DataQualityMixin):
    """Quarterly and annual financial statements."""
    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint("ticker", "period", "period_type", name="uq_financial"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    period: Mapped[dt.date] = mapped_column(Date, nullable=False)  # quarter-end or year-end
    period_type: Mapped[str] = mapped_column(String(4), nullable=False)  # Q1-Q4 | FY
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Income statement
    revenue: Mapped[float | None] = mapped_column(Float)
    fee_revenue: Mapped[float | None] = mapped_column(Float)
    cost_of_revenue: Mapped[float | None] = mapped_column(Float)
    gross_profit: Mapped[float | None] = mapped_column(Float)
    gross_margin: Mapped[float | None] = mapped_column(Float)
    operating_expense: Mapped[float | None] = mapped_column(Float)
    operating_income: Mapped[float | None] = mapped_column(Float)
    operating_margin: Mapped[float | None] = mapped_column(Float)
    ebitda: Mapped[float | None] = mapped_column(Float)
    adjusted_ebitda: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[float | None] = mapped_column(Float)
    net_margin: Mapped[float | None] = mapped_column(Float)
    eps_basic: Mapped[float | None] = mapped_column(Float)
    eps_diluted: Mapped[float | None] = mapped_column(Float)

    # Balance sheet
    cash_and_equivalents: Mapped[float | None] = mapped_column(Float)
    total_debt: Mapped[float | None] = mapped_column(Float)
    total_assets: Mapped[float | None] = mapped_column(Float)
    total_liabilities: Mapped[float | None] = mapped_column(Float)
    shareholders_equity: Mapped[float | None] = mapped_column(Float)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    shares_diluted: Mapped[int | None] = mapped_column(BigInteger)

    # Cash flow
    operating_cash_flow: Mapped[float | None] = mapped_column(Float)
    capex: Mapped[float | None] = mapped_column(Float)
    free_cash_flow: Mapped[float | None] = mapped_column(Float)

    # UPST-specific
    contribution_profit: Mapped[float | None] = mapped_column(Float)
    contribution_margin: Mapped[float | None] = mapped_column(Float)

    # Guidance
    revenue_guidance_low: Mapped[float | None] = mapped_column(Float)
    revenue_guidance_high: Mapped[float | None] = mapped_column(Float)
    ebitda_guidance_low: Mapped[float | None] = mapped_column(Float)
    ebitda_guidance_high: Mapped[float | None] = mapped_column(Float)

    # Metadata
    management_commentary: Mapped[str | None] = mapped_column(Text)


class EarningsRelease(Base, TimestampMixin, DataQualityMixin):
    """Earnings event data."""
    __tablename__ = "earnings_releases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    report_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    report_time: Mapped[str | None] = mapped_column(String(10))  # BMO | AMC
    eps_estimate: Mapped[float | None] = mapped_column(Float)
    eps_actual: Mapped[float | None] = mapped_column(Float)
    eps_surprise: Mapped[float | None] = mapped_column(Float)
    revenue_estimate: Mapped[float | None] = mapped_column(Float)
    revenue_actual: Mapped[float | None] = mapped_column(Float)
    revenue_surprise: Mapped[float | None] = mapped_column(Float)
    pre_earnings_iv: Mapped[float | None] = mapped_column(Float)
    post_earnings_iv: Mapped[float | None] = mapped_column(Float)
    implied_move: Mapped[float | None] = mapped_column(Float)
    realized_move: Mapped[float | None] = mapped_column(Float)
    post_earnings_drift_5d: Mapped[float | None] = mapped_column(Float)
    post_earnings_drift_20d: Mapped[float | None] = mapped_column(Float)


class SECFiling(Base, TimestampMixin, DataQualityMixin):
    """SEC EDGAR filing metadata."""
    __tablename__ = "sec_filings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 10-K, 10-Q, 8-K, etc.
    filed_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_of_report: Mapped[dt.date | None] = mapped_column(Date)
    accession_number: Mapped[str] = mapped_column(String(30), unique=True)
    filing_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    has_funding_info: Mapped[bool] = mapped_column(default=False)
    has_covenant_info: Mapped[bool] = mapped_column(default=False)


class InsiderTransaction(Base, TimestampMixin, DataQualityMixin):
    """Insider buy/sell transactions."""
    __tablename__ = "insider_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    filing_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    trade_date: Mapped[dt.date | None] = mapped_column(Date)
    insider_name: Mapped[str | None] = mapped_column(String(200))
    insider_title: Mapped[str | None] = mapped_column(String(200))
    transaction_type: Mapped[str | None] = mapped_column(String(50))  # Purchase | Sale | Option Exercise
    shares: Mapped[int | None] = mapped_column(BigInteger)
    price: Mapped[float | None] = mapped_column(Float)
    value: Mapped[float | None] = mapped_column(Float)
    shares_owned_after: Mapped[int | None] = mapped_column(BigInteger)


class InstitutionalOwnership(Base, TimestampMixin, DataQualityMixin):
    """13F institutional ownership snapshots."""
    __tablename__ = "institutional_ownership"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    report_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    institution_name: Mapped[str] = mapped_column(String(300), nullable=False)
    shares_held: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[float | None] = mapped_column(Float)
    pct_of_portfolio: Mapped[float | None] = mapped_column(Float)
    change_shares: Mapped[int | None] = mapped_column(BigInteger)
    change_pct: Mapped[float | None] = mapped_column(Float)
