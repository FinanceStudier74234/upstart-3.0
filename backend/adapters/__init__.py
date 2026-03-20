"""Data provider adapters — each adapter implements a common interface with fallback/mock support."""

from backend.adapters.base import (
    DataEnvelope,
    BaseMarketAdapter,
    BaseMacroAdapter,
    BaseShortAdapter,
    BaseNewsAdapter,
    BaseFundamentalAdapter,
)
from backend.adapters.yahoo_adapter import YahooMarketAdapter, YahooFundamentalAdapter
from backend.adapters.fred_adapter import FREDAdapter
from backend.adapters.mock_adapter import (
    MockMarketAdapter,
    MockMacroAdapter,
    MockShortAdapter,
    MockNewsAdapter,
    MockFundamentalAdapter,
)
from backend.adapters.provider import DataProvider, data_provider

__all__ = [
    "DataEnvelope",
    "BaseMarketAdapter", "BaseMacroAdapter", "BaseShortAdapter",
    "BaseNewsAdapter", "BaseFundamentalAdapter",
    "YahooMarketAdapter", "YahooFundamentalAdapter",
    "FREDAdapter",
    "MockMarketAdapter", "MockMacroAdapter", "MockShortAdapter",
    "MockNewsAdapter", "MockFundamentalAdapter",
    "DataProvider", "data_provider",
]
