"""Tests for adapter layer: mock adapters, DataEnvelope, and DataProvider fallback logic."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

from backend.adapters.base import (
    DataEnvelope,
    BaseMarketAdapter,
)
from backend.adapters.mock_adapter import (
    MockMarketAdapter,
    MockMacroAdapter,
    MockShortAdapter,
    MockNewsAdapter,
    MockFundamentalAdapter,
)


# ---------------------------------------------------------------------------
# DataEnvelope unit tests
# ---------------------------------------------------------------------------


class TestDataEnvelope:

    def test_default_values(self):
        env = DataEnvelope(data={"x": 1}, source="test")
        assert env.source_label == "official"
        assert env.confidence == 1.0
        assert env.quality_score == 1.0
        assert env.is_stale is False
        assert env.warnings == []
        assert env.freshness_seconds is None
        assert isinstance(env.fetched_at, dt.datetime)

    def test_fetched_at_is_utc(self):
        env = DataEnvelope(data=None, source="test")
        assert env.fetched_at.tzinfo == dt.timezone.utc

    def test_mark_stale_when_fresh(self):
        env = DataEnvelope(data={}, source="test", freshness_seconds=10)
        env.mark_stale(threshold_seconds=60)
        assert env.is_stale is False
        assert env.quality_score == 1.0
        assert len(env.warnings) == 0

    def test_mark_stale_when_stale(self):
        env = DataEnvelope(data={}, source="test", freshness_seconds=120)
        env.mark_stale(threshold_seconds=60)
        assert env.is_stale is True
        assert env.quality_score == pytest.approx(0.7, abs=1e-9)
        assert len(env.warnings) == 1
        assert "120s > 60s" in env.warnings[0]

    def test_mark_stale_no_freshness(self):
        """When freshness_seconds is None, mark_stale should be a no-op."""
        env = DataEnvelope(data={}, source="test")
        env.mark_stale(threshold_seconds=10)
        assert env.is_stale is False

    def test_mark_stale_quality_floor(self):
        """Quality score should not drop below 0.0 after repeated stale marks."""
        env = DataEnvelope(data={}, source="test", freshness_seconds=999, quality_score=0.1)
        env.mark_stale(threshold_seconds=1)
        assert env.quality_score == 0.0

    def test_mark_stale_accumulates_warnings(self):
        """Calling mark_stale multiple times should accumulate warnings."""
        env = DataEnvelope(data={}, source="test", freshness_seconds=100, quality_score=1.0)
        env.mark_stale(threshold_seconds=50)
        env.mark_stale(threshold_seconds=50)
        assert len(env.warnings) == 2
        assert env.quality_score == pytest.approx(0.4, abs=1e-9)

    def test_custom_source_label(self):
        env = DataEnvelope(data={}, source="polygon", source_label="proxy", confidence=0.8)
        assert env.source_label == "proxy"
        assert env.confidence == 0.8

    def test_warnings_list_independent_between_instances(self):
        """Ensure the default mutable list is not shared between instances."""
        e1 = DataEnvelope(data={}, source="a")
        e2 = DataEnvelope(data={}, source="b")
        e1.warnings.append("w1")
        assert len(e2.warnings) == 0


# ---------------------------------------------------------------------------
# MockMarketAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockMarketAdapter:

    async def test_get_quote_returns_envelope(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        assert isinstance(env, DataEnvelope)
        assert env.source == "mock"
        assert env.data["ticker"] == "UPST"

    async def test_get_quote_contains_expected_fields(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        data = env.data
        for f in ("ticker", "price", "previous_close", "market_cap", "volume"):
            assert f in data, f"Missing field: {f}"
        assert isinstance(data["price"], float)
        assert isinstance(data["volume"], int)

    async def test_get_quote_spy_has_no_market_cap(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("SPY")
        assert env.data["market_cap"] is None

    async def test_get_quote_has_mock_warning(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        assert any("Mock" in w for w in env.warnings)

    async def test_get_quote_confidence_below_one(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        assert env.confidence == 0.5

    async def test_get_bars_returns_list_of_records(self):
        adapter = MockMarketAdapter()
        start = dt.date(2024, 1, 1)
        end = dt.date(2024, 1, 31)
        env = await adapter.get_bars("UPST", "1d", start, end)
        assert isinstance(env, DataEnvelope)
        assert isinstance(env.data, list)
        assert len(env.data) > 0
        record = env.data[0]
        for f in ("ticker", "open", "high", "low", "close", "volume", "vwap"):
            assert f in record, f"Missing bar field: {f}"

    async def test_get_bars_skips_weekends(self):
        adapter = MockMarketAdapter()
        start = dt.date(2024, 1, 1)
        end = dt.date(2024, 1, 14)
        env = await adapter.get_bars("UPST", "1d", start, end)
        for record in env.data:
            assert record["bar_time"].weekday() < 5

    async def test_get_bars_zero_day_range_defaults(self):
        """When start == end (0-day range), adapter should still return data."""
        adapter = MockMarketAdapter()
        d = dt.date(2024, 6, 1)
        env = await adapter.get_bars("UPST", "1d", d, d)
        assert isinstance(env.data, list)
        # days <= 0 defaults to 30 days of GBM path
        assert len(env.data) > 0

    async def test_get_options_chain_structure(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_options_chain("UPST")
        assert isinstance(env, DataEnvelope)
        data = env.data
        assert data["ticker"] == "UPST"
        assert "contracts" in data
        assert len(data["contracts"]) > 0
        contract = data["contracts"][0]
        for f in ("strike", "expiration", "bid", "ask", "implied_volatility", "delta", "option_type"):
            assert f in contract, f"Missing option field: {f}"

    async def test_get_options_chain_has_calls_and_puts(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_options_chain("UPST")
        types = {c["option_type"] for c in env.data["contracts"]}
        assert types == {"call", "put"}

    async def test_get_options_chain_greeks_present(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_options_chain("UPST")
        contract = env.data["contracts"][0]
        for greek in ("delta", "gamma", "theta", "vega"):
            assert greek in contract
            assert isinstance(contract[greek], float)


# ---------------------------------------------------------------------------
# MockMacroAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockMacroAdapter:

    async def test_get_indicator_known(self):
        adapter = MockMacroAdapter()
        env = await adapter.get_indicator("FED_FUNDS")
        assert isinstance(env, DataEnvelope)
        assert env.source == "mock"
        assert isinstance(env.data, list)
        assert len(env.data) == 252

    async def test_get_indicator_record_fields(self):
        adapter = MockMacroAdapter()
        env = await adapter.get_indicator("TREASURY_10Y")
        record = env.data[0]
        assert record["indicator"] == "TREASURY_10Y"
        assert "observation_date" in record
        assert "value" in record

    async def test_get_indicator_unknown_defaults_to_zero(self):
        adapter = MockMacroAdapter()
        env = await adapter.get_indicator("NONEXISTENT_INDICATOR")
        for record in env.data:
            assert record["value"] == 0.0

    async def test_get_indicator_values_near_base(self):
        """Values should jitter within 3% of the base value."""
        adapter = MockMacroAdapter()
        env = await adapter.get_indicator("VIX")
        base = 18.5
        for record in env.data:
            assert abs(record["value"] - base) <= base * 0.03 + 1e-9

    async def test_get_indicator_multiple_indicators(self):
        """Verify several known indicators return non-empty data."""
        adapter = MockMacroAdapter()
        for indicator in ("FED_FUNDS", "TREASURY_2Y", "UNEMPLOYMENT", "CPI_YOY"):
            env = await adapter.get_indicator(indicator)
            assert len(env.data) == 252
            assert env.data[0]["indicator"] == indicator


# ---------------------------------------------------------------------------
# MockShortAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockShortAdapter:

    async def test_get_short_interest_fields(self):
        adapter = MockShortAdapter()
        env = await adapter.get_short_interest("UPST")
        assert isinstance(env, DataEnvelope)
        data = env.data
        for f in ("ticker", "short_interest", "shares_float", "short_pct_float", "days_to_cover"):
            assert f in data
        assert data["ticker"] == "UPST"
        assert 8 <= data["short_pct_float"] <= 25

    async def test_get_short_interest_consistency(self):
        """short_interest should equal shares_float * short_pct_float / 100."""
        adapter = MockShortAdapter()
        env = await adapter.get_short_interest("UPST")
        data = env.data
        expected_si = int(data["shares_float"] * data["short_pct_float"] / 100)
        assert data["short_interest"] == expected_si

    async def test_get_stock_loan_fields(self):
        adapter = MockShortAdapter()
        env = await adapter.get_stock_loan("UPST")
        data = env.data
        for f in ("ticker", "cost_to_borrow", "utilization", "shares_available", "borrow_fee_trend"):
            assert f in data
        assert data["borrow_fee_trend"] in ("rising", "stable", "falling")

    async def test_get_stock_loan_utilization_range(self):
        adapter = MockShortAdapter()
        env = await adapter.get_stock_loan("UPST")
        assert 40 <= env.data["utilization"] <= 95


# ---------------------------------------------------------------------------
# MockNewsAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockNewsAdapter:

    async def test_get_news_returns_items(self):
        adapter = MockNewsAdapter()
        env = await adapter.get_news("UPST", limit=5)
        assert isinstance(env, DataEnvelope)
        assert isinstance(env.data, list)
        assert len(env.data) == 5

    async def test_get_news_item_fields(self):
        adapter = MockNewsAdapter()
        env = await adapter.get_news("UPST", limit=1)
        item = env.data[0]
        for f in ("ticker", "headline", "summary", "source_name", "sentiment_score", "relevance_score"):
            assert f in item

    async def test_get_news_limit_capped_at_headlines(self):
        adapter = MockNewsAdapter()
        env = await adapter.get_news("UPST", limit=999)
        assert len(env.data) == len(adapter._HEADLINES)

    async def test_get_news_sentiment_range(self):
        adapter = MockNewsAdapter()
        env = await adapter.get_news("UPST", limit=10)
        for item in env.data:
            assert -1.0 <= item["sentiment_score"] <= 1.0
            assert 0.0 <= item["relevance_score"] <= 1.0

    async def test_get_news_ticker_propagated(self):
        adapter = MockNewsAdapter()
        env = await adapter.get_news("AAPL", limit=2)
        for item in env.data:
            assert item["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# MockFundamentalAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockFundamentalAdapter:

    async def test_get_financials_returns_quarters(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_financials("UPST")
        assert isinstance(env, DataEnvelope)
        assert isinstance(env.data, list)
        assert len(env.data) == 8

    async def test_get_financials_record_fields(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_financials("UPST")
        record = env.data[0]
        for f in ("ticker", "revenue", "gross_margin", "operating_margin", "eps_diluted", "shares_outstanding"):
            assert f in record

    async def test_get_financials_revenue_positive(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_financials("UPST")
        for q in env.data:
            assert q["revenue"] > 0

    async def test_get_earnings_returns_releases(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_earnings("UPST")
        assert isinstance(env.data, list)
        assert len(env.data) == 8
        release = env.data[0]
        for f in ("ticker", "report_date", "eps_estimate", "eps_actual", "implied_move", "realized_move"):
            assert f in release

    async def test_get_earnings_implied_move_positive(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_earnings("UPST")
        for r in env.data:
            assert r["implied_move"] >= 0
            assert r["realized_move"] >= 0


# ---------------------------------------------------------------------------
# DataProvider fallback chain tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDataProvider:

    async def _make_provider(self):
        """Create a DataProvider with mock_mode forced on."""
        with patch("backend.adapters.provider.settings") as mock_settings:
            mock_settings.mock_mode = True
            mock_settings.has_fred.return_value = False
            from backend.adapters.provider import DataProvider
            return DataProvider()

    async def test_provider_falls_back_to_mock(self):
        provider = await self._make_provider()
        env = await provider.get_quote("UPST")
        assert isinstance(env, DataEnvelope)
        assert env.source == "mock"

    async def test_try_chain_returns_first_success(self):
        provider = await self._make_provider()
        env = await provider.get_quote("UPST")
        assert env.data is not None
        assert env.quality_score > 0

    async def test_try_chain_skips_failed_adapter(self):
        provider = await self._make_provider()
        broken = AsyncMock(spec=BaseMarketAdapter)
        broken.get_quote.side_effect = RuntimeError("connection failed")
        provider._market_adapters.insert(0, broken)

        env = await provider.get_quote("UPST")
        assert env.source == "mock"
        assert env.data is not None

    async def test_try_chain_all_fail_returns_none_envelope(self):
        provider = await self._make_provider()
        broken = AsyncMock(spec=BaseMarketAdapter)
        broken.get_quote.side_effect = RuntimeError("down")
        provider._market_adapters = [broken]

        env = await provider.get_quote("UPST")
        assert env.data is None
        assert env.source == "none"
        assert env.quality_score == 0.0
        assert "All adapters failed" in env.warnings

    async def test_try_chain_skips_zero_quality(self):
        provider = await self._make_provider()
        bad_quality = AsyncMock(spec=BaseMarketAdapter)
        bad_quality.get_quote.return_value = DataEnvelope(
            data={"ticker": "UPST"}, source="bad", quality_score=0.0,
        )
        provider._market_adapters = [bad_quality, MockMarketAdapter()]

        env = await provider.get_quote("UPST")
        assert env.source == "mock"

    async def test_try_chain_skips_none_data(self):
        """Adapter returning data=None should be skipped."""
        provider = await self._make_provider()
        null_adapter = AsyncMock(spec=BaseMarketAdapter)
        null_adapter.get_quote.return_value = DataEnvelope(
            data=None, source="null_source", quality_score=1.0,
        )
        provider._market_adapters = [null_adapter, MockMarketAdapter()]

        env = await provider.get_quote("UPST")
        assert env.source == "mock"

    async def test_provider_get_macro(self):
        provider = await self._make_provider()
        env = await provider.get_macro("VIX")
        assert isinstance(env, DataEnvelope)
        assert env.data[0]["indicator"] == "VIX"

    async def test_provider_get_news(self):
        provider = await self._make_provider()
        env = await provider.get_news("UPST", limit=3)
        assert isinstance(env.data, list)
        assert len(env.data) == 3

    async def test_provider_get_bars_default_dates(self):
        """get_bars with no start/end should default to 1-year range."""
        provider = await self._make_provider()
        env = await provider.get_bars("UPST")
        assert isinstance(env, DataEnvelope)
        assert isinstance(env.data, list)
        assert len(env.data) > 200  # ~252 trading days in a year

    async def test_provider_get_short_interest(self):
        provider = await self._make_provider()
        env = await provider.get_short_interest("UPST")
        assert isinstance(env, DataEnvelope)
        assert env.data["ticker"] == "UPST"

    async def test_provider_get_stock_loan(self):
        provider = await self._make_provider()
        env = await provider.get_stock_loan("UPST")
        assert isinstance(env, DataEnvelope)
        assert "cost_to_borrow" in env.data

    async def test_provider_get_financials(self):
        provider = await self._make_provider()
        env = await provider.get_financials("UPST")
        assert isinstance(env, DataEnvelope)
        assert len(env.data) == 8

    async def test_provider_get_earnings(self):
        provider = await self._make_provider()
        env = await provider.get_earnings("UPST")
        assert isinstance(env, DataEnvelope)
        assert len(env.data) == 8

    async def test_provider_get_options_chain(self):
        provider = await self._make_provider()
        env = await provider.get_options_chain("UPST")
        assert isinstance(env, DataEnvelope)
        assert len(env.data["contracts"]) > 0
