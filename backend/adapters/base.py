"""Base adapter interface and data-envelope types."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataEnvelope:
    """Wraps every piece of fetched data with provenance and quality metadata."""
    data: Any
    source: str  # e.g. "polygon", "yfinance", "mock"
    source_label: str = "official"  # official | estimated | proxy | mock
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    confidence: float = 1.0
    freshness_seconds: int | None = None
    quality_score: float = 1.0
    is_stale: bool = False
    warnings: list[str] = field(default_factory=list)

    def mark_stale(self, threshold_seconds: int) -> None:
        if self.freshness_seconds is not None and self.freshness_seconds > threshold_seconds:
            self.is_stale = True
            self.quality_score = max(0.0, self.quality_score - 0.3)
            self.warnings.append(f"Data stale: {self.freshness_seconds}s > {threshold_seconds}s")


class BaseMarketAdapter(ABC):
    """Interface for equity / price data providers."""

    @abstractmethod
    async def get_quote(self, ticker: str) -> DataEnvelope:
        ...

    @abstractmethod
    async def get_bars(
        self, ticker: str, timeframe: str, start: dt.date, end: dt.date
    ) -> DataEnvelope:
        ...

    @abstractmethod
    async def get_options_chain(self, ticker: str) -> DataEnvelope:
        ...


class BaseMacroAdapter(ABC):
    """Interface for macro / FRED data."""

    @abstractmethod
    async def get_indicator(self, indicator: str) -> DataEnvelope:
        ...


class BaseShortAdapter(ABC):
    """Interface for short-interest / stock-loan data."""

    @abstractmethod
    async def get_short_interest(self, ticker: str) -> DataEnvelope:
        ...

    @abstractmethod
    async def get_stock_loan(self, ticker: str) -> DataEnvelope:
        ...


class BaseNewsAdapter(ABC):
    """Interface for news / filings data."""

    @abstractmethod
    async def get_news(self, ticker: str, limit: int = 50) -> DataEnvelope:
        ...


class BaseFundamentalAdapter(ABC):
    """Interface for financial statement data."""

    @abstractmethod
    async def get_financials(self, ticker: str) -> DataEnvelope:
        ...

    @abstractmethod
    async def get_earnings(self, ticker: str) -> DataEnvelope:
        ...
