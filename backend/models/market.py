"""Market data models — price bars, options, short interest, stock-loan."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, DataQualityMixin


class PriceBar(Base, TimestampMixin, DataQualityMixin):
    """OHLCV price bar — intraday through monthly."""
    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint("ticker", "timeframe", "bar_time", name="uq_pricebar"),
        Index("ix_pricebar_ticker_time", "ticker", "bar_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)  # 1m,5m,15m,1h,1d,1w,1M
    bar_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vwap: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int | None] = mapped_column(Integer)


class OptionsChain(Base, TimestampMixin, DataQualityMixin):
    """Snapshot metadata for an options-chain pull."""
    __tablename__ = "options_chains"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    snapshot_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    underlying_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_call_volume: Mapped[int] = mapped_column(Integer, default=0)
    total_put_volume: Mapped[int] = mapped_column(Integer, default=0)
    total_call_oi: Mapped[int] = mapped_column(Integer, default=0)
    total_put_oi: Mapped[int] = mapped_column(Integer, default=0)
    put_call_volume_ratio: Mapped[float | None] = mapped_column(Float)
    put_call_oi_ratio: Mapped[float | None] = mapped_column(Float)
    iv_rank: Mapped[float | None] = mapped_column(Float)
    iv_percentile: Mapped[float | None] = mapped_column(Float)
    expected_move: Mapped[float | None] = mapped_column(Float)
    max_pain: Mapped[float | None] = mapped_column(Float)


class OptionsContract(Base, TimestampMixin, DataQualityMixin):
    """Individual option contract data."""
    __tablename__ = "options_contracts"
    __table_args__ = (
        Index("ix_opt_ticker_exp_strike", "ticker", "expiration", "strike"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    option_type: Mapped[str] = mapped_column(String(4), nullable=False)  # call | put
    strike: Mapped[float] = mapped_column(Float, nullable=False)
    expiration: Mapped[dt.date] = mapped_column(Date, nullable=False)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    mark: Mapped[float | None] = mapped_column(Float)
    last: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    open_interest: Mapped[int] = mapped_column(Integer, default=0)
    implied_volatility: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float)
    gamma: Mapped[float | None] = mapped_column(Float)
    theta: Mapped[float | None] = mapped_column(Float)
    vega: Mapped[float | None] = mapped_column(Float)
    rho: Mapped[float | None] = mapped_column(Float)
    in_the_money: Mapped[bool | None] = mapped_column()
    days_to_expiry: Mapped[int | None] = mapped_column(Integer)


class ShortInterest(Base, TimestampMixin, DataQualityMixin):
    """Short-interest snapshots (bi-monthly FINRA + proxy estimates)."""
    __tablename__ = "short_interest"
    __table_args__ = (
        UniqueConstraint("ticker", "report_date", name="uq_short_interest"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    report_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    short_interest: Mapped[int | None] = mapped_column(BigInteger)
    shares_float: Mapped[int | None] = mapped_column(BigInteger)
    short_pct_float: Mapped[float | None] = mapped_column(Float)
    days_to_cover: Mapped[float | None] = mapped_column(Float)
    avg_volume_30d: Mapped[int | None] = mapped_column(BigInteger)
    short_change_pct: Mapped[float | None] = mapped_column(Float)


class StockLoan(Base, TimestampMixin, DataQualityMixin):
    """Stock-loan / borrow data snapshots."""
    __tablename__ = "stock_loan"
    __table_args__ = (
        UniqueConstraint("ticker", "snapshot_date", name="uq_stock_loan"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    snapshot_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    cost_to_borrow: Mapped[float | None] = mapped_column(Float)
    utilization: Mapped[float | None] = mapped_column(Float)  # 0..100
    shares_available: Mapped[int | None] = mapped_column(BigInteger)
    lendable_shares: Mapped[int | None] = mapped_column(BigInteger)
    borrow_fee_trend: Mapped[str | None] = mapped_column(String(20))  # rising | stable | falling
