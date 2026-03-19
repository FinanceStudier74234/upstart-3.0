"""Backtesting models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class BacktestRun(Base, TimestampMixin):
    """Metadata for a backtest run."""
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), default="daily")

    # Performance metrics
    total_return: Mapped[float | None] = mapped_column(Float)
    annualized_return: Mapped[float | None] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    sortino_ratio: Mapped[float | None] = mapped_column(Float)
    calmar_ratio: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    avg_win: Mapped[float | None] = mapped_column(Float)
    avg_loss: Mapped[float | None] = mapped_column(Float)
    payoff_ratio: Mapped[float | None] = mapped_column(Float)
    expectancy: Mapped[float | None] = mapped_column(Float)
    total_trades: Mapped[int | None] = mapped_column(Integer)
    profit_factor: Mapped[float | None] = mapped_column(Float)

    # Beta decomposition
    alpha_vs_spy: Mapped[float | None] = mapped_column(Float)
    beta_vs_spy: Mapped[float | None] = mapped_column(Float)

    # Regime breakdown
    performance_by_regime_json: Mapped[str | None] = mapped_column(Text)

    # Parameters
    parameters_json: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class BacktestTrade(Base, TimestampMixin):
    """Individual trade within a backtest run."""
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    trade_number: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # long | short
    vehicle: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[dt.date | None] = mapped_column(Date)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float)
    position_size: Mapped[float | None] = mapped_column(Float)
    pnl: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    holding_days: Mapped[int | None] = mapped_column(Integer)
    exit_reason: Mapped[str | None] = mapped_column(String(50))  # target | stop | signal | time
    regime_at_entry: Mapped[str | None] = mapped_column(String(50))
