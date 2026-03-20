"""Data provider adapters — each adapter implements a common interface with fallback/mock support."""

from backend.adapters.base import (
    DataEnvelope,
    BaseMarketAdapter,
    BaseMacroAdapter,
    BaseShortAdapter,
    BaseNewsAdapter,
    BaseFundamentalAdapter,
)
try:
    from backend.adapters.yahoo_adapter import YahooMarketAdapter, YahooFundamentalAdapter
except ImportError:
    YahooMarketAdapter = None  # type: ignore[assignment,misc]
    YahooFundamentalAdapter = None  # type: ignore[assignment,misc]

try:
    from backend.adapters.fred_adapter import FREDAdapter
except ImportError:
    FREDAdapter = None  # type: ignore[assignment,misc]
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
