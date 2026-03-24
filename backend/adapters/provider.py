"""Unified data provider that routes to the best available adapter with fallback."""

from __future__ import annotations

import datetime as dt
import logging

from backend.adapters.base import (
    BaseMarketAdapter, BaseMacroAdapter, BaseShortAdapter,
    BaseNewsAdapter, BaseFundamentalAdapter, DataEnvelope,
)

try:
    from backend.adapters.polygon_adapter import PolygonMarketAdapter
except ImportError:
    PolygonMarketAdapter = None

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
try:
    from backend.adapters.news_intelligence_adapter import NewsIntelligenceAdapter
except ImportError:
    NewsIntelligenceAdapter = None

try:
    from backend.adapters.sec_edgar_adapter import SECEdgarAdapter
except ImportError:
    SECEdgarAdapter = None

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class DataProvider:
    """
    Central data provider. Selects the best available adapter based on
    configured API keys and falls back to mock when needed.

    Priority chains (highest to lowest):
      Market:  Polygon → Yahoo → Mock
      Macro:   FRED → Mock
      Short:   Mock (ORTEX/Fintel adapters can be added)
      News:    NewsIntelligence → Mock
      Fundamentals: Yahoo → Mock
      Filings: SEC EDGAR (optional)
    """

    def __init__(self):
        self._mock_mode = settings.mock_mode

        # Market data chain: Polygon → Yahoo → Mock
        self._market_adapters: list[BaseMarketAdapter] = []
        if not self._mock_mode:
            if PolygonMarketAdapter is not None and settings.has_polygon():
                self._market_adapters.append(PolygonMarketAdapter())
                logger.info("Polygon adapter enabled (plan=%s)", settings.polygon_plan)
            if YahooMarketAdapter is not None:
                self._market_adapters.append(YahooMarketAdapter())
        self._market_adapters.append(MockMarketAdapter())

        # SEC EDGAR (optional, non-chain)
        self._sec_adapter = None
        if not self._mock_mode and SECEdgarAdapter is not None:
            self._sec_adapter = SECEdgarAdapter()

        # Macro chain: FRED → Mock
        self._macro_adapters: list[BaseMacroAdapter] = []
        if not self._mock_mode and FREDAdapter is not None and settings.has_fred():
            self._macro_adapters.append(FREDAdapter())
        self._macro_adapters.append(MockMacroAdapter())

        # Short chain: ORTEX → Fintel → Mock
        self._short_adapters: list[BaseShortAdapter] = [MockShortAdapter()]

        # News chain: NewsIntelligence → Mock
        self._news_adapters: list[BaseNewsAdapter] = []
        if not self._mock_mode and NewsIntelligenceAdapter is not None:
            self._news_adapters.append(NewsIntelligenceAdapter())
        self._news_adapters.append(MockNewsAdapter())

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

    async def get_filings(self, ticker: str, filing_types: list[str] | None = None) -> DataEnvelope:
        if self._sec_adapter:
            try:
                return await self._sec_adapter.get_filings(ticker, filing_types)
            except Exception as e:
                logger.warning("SEC EDGAR filings failed: %s", e)
        return DataEnvelope(data=[], source="none", quality_score=0.0,
                            warnings=["No SEC EDGAR adapter available"])

    async def get_insider_transactions(self, ticker: str) -> DataEnvelope:
        if self._sec_adapter:
            try:
                return await self._sec_adapter.get_insider_transactions(ticker)
            except Exception as e:
                logger.warning("SEC EDGAR insider transactions failed: %s", e)
        return DataEnvelope(data=[], source="none", quality_score=0.0,
                            warnings=["No SEC EDGAR adapter available"])

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
            data=None, source="none", source_label="unavailable", quality_score=0.0,
            warnings=["All data adapters failed — results may be unreliable"],
        )


    def get_data_quality_summary(self) -> dict:
        """Return summary of which data sources are active vs mock."""
        return {
            "market": self._market_adapters[0].__class__.__name__ if self._market_adapters else "none",
            "macro": self._macro_adapters[0].__class__.__name__ if self._macro_adapters else "none",
            "short": self._short_adapters[0].__class__.__name__ if self._short_adapters else "none",
            "news": self._news_adapters[0].__class__.__name__ if self._news_adapters else "none",
            "fundamentals": self._fundamental_adapters[0].__class__.__name__ if self._fundamental_adapters else "none",
            "mock_mode": self._mock_mode,
            "has_polygon": bool(PolygonMarketAdapter is not None and any(isinstance(a, PolygonMarketAdapter) for a in self._market_adapters)) if PolygonMarketAdapter else False,
            "has_yahoo": bool(YahooMarketAdapter is not None and any(isinstance(a, YahooMarketAdapter) for a in self._market_adapters)) if YahooMarketAdapter else False,
            "has_fred": bool(FREDAdapter is not None and any(isinstance(a, FREDAdapter) for a in self._macro_adapters)) if FREDAdapter else False,
        }


# Lazy singleton — deferred to first use so import-time side effects are avoided
_data_provider: DataProvider | None = None


def get_data_provider() -> DataProvider:
    """Return the singleton DataProvider, creating it on first call."""
    global _data_provider
    if _data_provider is None:
        _data_provider = DataProvider()
    return _data_provider


# Backwards-compatible alias for existing imports
data_provider = None  # type: ignore[assignment]


class _LazyProxy:
    """Transparent proxy that defers DataProvider creation to first attribute access."""

    def __getattr__(self, name: str):
        return getattr(get_data_provider(), name)


data_provider = _LazyProxy()  # type: ignore[assignment]
