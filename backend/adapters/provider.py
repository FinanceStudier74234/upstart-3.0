"""Unified data provider that routes to the best available adapter with fallback."""

from __future__ import annotations

import datetime as dt
import logging

from backend.adapters.base import (
    BaseMarketAdapter, BaseMacroAdapter, BaseShortAdapter,
    BaseNewsAdapter, BaseFundamentalAdapter, DataEnvelope,
)
try:
    from backend.adapters.yahoo_adapter import YahooMarketAdapter, YahooFundamentalAdapter
except ImportError:
    YahooMarketAdapter = None
    YahooFundamentalAdapter = None

try:
    from backend.adapters.fred_adapter import FREDAdapter
except ImportError:
    FREDAdapter = None

from backend.adapters.mock_adapter import (
    MockMarketAdapter, MockMacroAdapter, MockShortAdapter,
    MockNewsAdapter, MockFundamentalAdapter,
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class DataProvider:
    """
    Central data provider. Selects the best available adapter based on
    configured API keys and falls back to mock when needed.
    """

    def __init__(self):
        self._mock_mode = settings.mock_mode

        # Market data chain: Polygon → Yahoo → Mock
        self._market_adapters: list[BaseMarketAdapter] = []
        if not self._mock_mode and YahooMarketAdapter is not None:
            self._market_adapters.append(YahooMarketAdapter())
        self._market_adapters.append(MockMarketAdapter())

        # Macro chain: FRED → Mock
        self._macro_adapters: list[BaseMacroAdapter] = []
        if not self._mock_mode and FREDAdapter is not None and settings.has_fred():
            self._macro_adapters.append(FREDAdapter())
        self._macro_adapters.append(MockMacroAdapter())

        # Short chain: ORTEX → Fintel → Mock
        self._short_adapters: list[BaseShortAdapter] = [MockShortAdapter()]

        # News chain: Finnhub → NewsAPI → Mock
        self._news_adapters: list[BaseNewsAdapter] = [MockNewsAdapter()]

        # Fundamentals chain: Yahoo → Mock
        self._fundamental_adapters: list[BaseFundamentalAdapter] = []
        if not self._mock_mode and YahooFundamentalAdapter is not None:
            self._fundamental_adapters.append(YahooFundamentalAdapter())
        self._fundamental_adapters.append(MockFundamentalAdapter())

    async def get_quote(self, ticker: str) -> DataEnvelope:
        return await self._try_chain(self._market_adapters, "get_quote", ticker)

    async def get_bars(
        self, ticker: str, timeframe: str = "1d",
        start: dt.date | None = None, end: dt.date | None = None,
    ) -> DataEnvelope:
        if end is None:
            end = dt.date.today()
        if start is None:
            start = end - dt.timedelta(days=365)
        return await self._try_chain(
            self._market_adapters, "get_bars", ticker, timeframe, start, end,
        )

    async def get_options_chain(self, ticker: str) -> DataEnvelope:
        return await self._try_chain(self._market_adapters, "get_options_chain", ticker)

    async def get_macro(self, indicator: str) -> DataEnvelope:
        return await self._try_chain(self._macro_adapters, "get_indicator", indicator)

    async def get_short_interest(self, ticker: str) -> DataEnvelope:
        return await self._try_chain(self._short_adapters, "get_short_interest", ticker)

    async def get_stock_loan(self, ticker: str) -> DataEnvelope:
        return await self._try_chain(self._short_adapters, "get_stock_loan", ticker)

    async def get_news(self, ticker: str, limit: int = 50) -> DataEnvelope:
        return await self._try_chain(self._news_adapters, "get_news", ticker, limit)

    async def get_financials(self, ticker: str) -> DataEnvelope:
        return await self._try_chain(self._fundamental_adapters, "get_financials", ticker)

    async def get_earnings(self, ticker: str) -> DataEnvelope:
        return await self._try_chain(self._fundamental_adapters, "get_earnings", ticker)

    async def _try_chain(self, adapters: list, method: str, *args) -> DataEnvelope:
        """Try each adapter in priority order; return first success."""
        for adapter in adapters:
            try:
                result: DataEnvelope = await getattr(adapter, method)(*args)
                if result.data is not None and result.quality_score > 0:
                    return result
            except Exception as e:
                logger.warning(
                    "Adapter %s.%s failed: %s", type(adapter).__name__, method, e
                )
                continue
        return DataEnvelope(
            data=None, source="none", quality_score=0.0,
            warnings=["All adapters failed"],
        )


# Singleton
data_provider = DataProvider()
