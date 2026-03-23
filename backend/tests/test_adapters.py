"""Tests for adapter layer: mock adapters, DataEnvelope, and DataProvider fallback logic."""

from __future__ import annotations

import asyncio
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
import backend.adapters.mock_adapter as _mock_mod


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

    def test_data_envelope_repr_or_str(self):
        """repr/str on DataEnvelope should not crash and should contain source."""
        env = DataEnvelope(data={"x": 1}, source="test_src", quality_score=0.8)
        r = repr(env)
        assert isinstance(r, str)
        assert len(r) > 0
        # dataclass repr includes field names
        assert "test_src" in r
        s = str(env)
        assert isinstance(s, str)


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
        assert env.quality_score > 0
        assert env.fetched_at is not None
        assert isinstance(env.fetched_at, dt.datetime)
        assert env.source_label == "mock"

    async def test_get_quote_contains_expected_fields(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        data = env.data
        for f in ("ticker", "price", "previous_close", "market_cap", "volume"):
            assert f in data, f"Missing field: {f}"
        assert isinstance(data["price"], float)
        assert isinstance(data["volume"], int)
        assert data["price"] > 0
        assert data["volume"] > 0
        assert data["previous_close"] > 0
        assert isinstance(data["market_cap"], (int, float)) or data["market_cap"] is None
        # For UPST specifically, market_cap should be set
        assert data["market_cap"] is not None
        assert data["market_cap"] > 0

    async def test_get_quote_spy_has_no_market_cap(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("SPY")
        assert env.data["market_cap"] is None

    async def test_get_quote_has_mock_warning(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        assert len(env.warnings) >= 1
        assert any("Mock" in w for w in env.warnings)
        assert isinstance(env.warnings[0], str)

    async def test_get_quote_confidence_below_one(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_quote("UPST")
        assert env.confidence == 0.3
        assert 0 < env.confidence < 1.0

    async def test_get_bars_returns_list_of_records(self):
        adapter = MockMarketAdapter()
        start = dt.date(2024, 1, 1)
        end = dt.date(2024, 1, 31)
        env = await adapter.get_bars("UPST", "1d", start, end)
        assert isinstance(env, DataEnvelope)
        assert isinstance(env.data, list)
        assert 0 < len(env.data) < 500
        record = env.data[0]
        for f in ("ticker", "open", "high", "low", "close", "volume", "vwap"):
            assert f in record, f"Missing bar field: {f}"
        assert record["open"] > 0
        assert record["high"] >= record["low"]
        assert record["close"] > 0
        assert record["volume"] > 0

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
        # Verify bars have valid OHLCV structure
        for bar in env.data:
            assert bar["open"] > 0
            assert bar["high"] >= bar["low"]
            assert bar["close"] > 0
            assert bar["volume"] > 0
            assert "vwap" in bar

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
        # Validate value ranges
        assert contract["strike"] > 0
        assert contract["bid"] >= 0
        assert contract["ask"] >= contract["bid"]
        assert 0 < contract["implied_volatility"] < 5

    async def test_get_options_chain_has_calls_and_puts(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_options_chain("UPST")
        types = {c["option_type"] for c in env.data["contracts"]}
        assert types == {"call", "put"}
        # Verify there are multiple of each type
        calls = [c for c in env.data["contracts"] if c["option_type"] == "call"]
        puts = [c for c in env.data["contracts"] if c["option_type"] == "put"]
        assert len(calls) > 1
        assert len(puts) > 1
        assert len(calls) + len(puts) == len(env.data["contracts"])

    async def test_get_options_chain_greeks_present(self):
        adapter = MockMarketAdapter()
        env = await adapter.get_options_chain("UPST")
        for contract in env.data["contracts"]:
            for greek in ("delta", "gamma", "theta", "vega"):
                assert greek in contract
                assert isinstance(contract[greek], float)
            assert -1 <= contract["delta"] <= 1
            assert contract["gamma"] >= 0
            assert contract["theta"] <= 0
            assert contract["vega"] >= 0

    async def test_mock_market_adapter_deterministic_with_seed(self):
        """Resetting module RNGs to the same seed produces identical quotes."""
        import random
        import numpy as np

        adapter = MockMarketAdapter()

        # Save state, reset, call, capture
        _mock_mod._rng = random.Random(99)
        _mock_mod._np_rng = np.random.RandomState(99)
        env1 = await adapter.get_quote("UPST")

        _mock_mod._rng = random.Random(99)
        _mock_mod._np_rng = np.random.RandomState(99)
        env2 = await adapter.get_quote("UPST")

        assert env1.data["price"] == env2.data["price"]
        assert env1.data["volume"] == env2.data["volume"]
        assert env1.data["previous_close"] == env2.data["previous_close"]

        # Restore default seed so other tests aren't affected
        _mock_mod._rng = random.Random(42)
        _mock_mod._np_rng = np.random.RandomState(42)

    async def test_mock_bars_high_always_gte_low(self):
        """OHLC invariant: high >= low for every bar across a long range."""
        adapter = MockMarketAdapter()
        start = dt.date(2023, 1, 1)
        end = dt.date(2024, 1, 1)
        env = await adapter.get_bars("UPST", "1d", start, end)
        assert len(env.data) > 100
        for bar in env.data:
            assert bar["high"] >= bar["low"], (
                f"OHLC invariant violated: high={bar['high']} < low={bar['low']}"
            )
            assert bar["high"] >= bar["close"]
            assert bar["low"] <= bar["close"]
            assert bar["high"] >= bar["open"]
            assert bar["low"] <= bar["open"]


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
        assert env.quality_score > 0
        # Records should have observation dates
        for rec in env.data[:5]:
            assert "observation_date" in rec
            assert isinstance(rec["observation_date"], str)

    async def test_get_indicator_record_fields(self):
        adapter = MockMacroAdapter()
        env = await adapter.get_indicator("TREASURY_10Y")
        record = env.data[0]
        assert record["indicator"] == "TREASURY_10Y"
        assert "observation_date" in record
        assert "value" in record
        assert isinstance(record["value"], float)
        assert isinstance(record["observation_date"], str)
        # observation_date should be a valid ISO date
        dt.date.fromisoformat(record["observation_date"])

    async def test_get_indicator_unknown_defaults_to_zero(self):
        adapter = MockMacroAdapter()
        env = await adapter.get_indicator("NONEXISTENT_INDICATOR")
        assert len(env.data) == 252
        for record in env.data:
            assert record["value"] == 0.0
            assert record["indicator"] == "NONEXISTENT_INDICATOR"

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
        assert data["short_interest"] > 0
        assert data["shares_float"] > 0
        assert data["days_to_cover"] > 0

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
        assert data["cost_to_borrow"] > 0
        assert data["shares_available"] > 0
        assert isinstance(data["cost_to_borrow"], float)
        assert isinstance(data["shares_available"], int)

    async def test_get_stock_loan_utilization_range(self):
        adapter = MockShortAdapter()
        env = await adapter.get_stock_loan("UPST")
        assert 40 <= env.data["utilization"] <= 95
        assert isinstance(env.data["utilization"], (int, float))
        assert env.data["ticker"] == "UPST"
        assert env.source == "mock"
        assert isinstance(env, DataEnvelope)
        # Utilization should be consistent with shares available
        assert env.data["shares_available"] > 0


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
        # Each item should be a dict with expected fields
        for item in env.data:
            assert isinstance(item, dict)
            assert "headline" in item
            assert "sentiment_score" in item

    async def test_get_news_item_fields(self):
        adapter = MockNewsAdapter()
        env = await adapter.get_news("UPST", limit=1)
        item = env.data[0]
        for f in ("ticker", "headline", "summary", "source_name", "sentiment_score", "relevance_score"):
            assert f in item
        # Type checks
        assert isinstance(item["headline"], str)
        assert len(item["headline"]) > 0
        assert isinstance(item["sentiment_score"], float)
        assert isinstance(item["relevance_score"], float)
        assert isinstance(item["summary"], str)

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
            # Verify other fields are present and valid
            assert "headline" in item
            assert isinstance(item["headline"], str)
            assert len(item["headline"]) > 0
            assert "published_at" in item
            assert isinstance(item["published_at"], str)


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
        assert env.quality_score > 0
        # Each quarter should be a dict with expected fields
        for q in env.data:
            assert isinstance(q, dict)
            assert "revenue" in q
            assert "ticker" in q

    async def test_get_financials_record_fields(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_financials("UPST")
        record = env.data[0]
        for f in ("ticker", "revenue", "gross_margin", "operating_margin", "eps_diluted", "shares_outstanding"):
            assert f in record
        # Type checks
        assert isinstance(record["revenue"], (int, float))
        assert record["revenue"] > 0
        assert isinstance(record["gross_margin"], float)
        assert 0 <= record["gross_margin"] <= 1.0
        assert isinstance(record["eps_diluted"], float)

    async def test_get_financials_revenue_positive(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_financials("UPST")
        for q in env.data:
            assert q["revenue"] > 0
            assert isinstance(q["revenue"], (int, float))
            assert q["ticker"] == "UPST"
            assert 0 <= q["gross_margin"] <= 1.0
            assert isinstance(q["eps_diluted"], float)

    async def test_get_earnings_returns_releases(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_earnings("UPST")
        assert isinstance(env.data, list)
        assert len(env.data) == 8
        assert env.quality_score > 0
        release = env.data[0]
        for f in ("ticker", "report_date", "eps_estimate", "eps_actual", "implied_move", "realized_move"):
            assert f in release
        # Validate report_date is a valid ISO date string
        for r in env.data:
            dt.date.fromisoformat(r["report_date"])

    async def test_get_earnings_implied_move_positive(self):
        adapter = MockFundamentalAdapter()
        env = await adapter.get_earnings("UPST")
        for r in env.data:
            assert r["implied_move"] >= 0
            assert r["realized_move"] >= 0
            # eps values should be numeric
            assert isinstance(r["eps_estimate"], (int, float))
            assert isinstance(r["eps_actual"], (int, float))


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
        assert env.data is not None
        assert env.quality_score > 0

    async def test_try_chain_returns_first_success(self):
        provider = await self._make_provider()
        env = await provider.get_quote("UPST")
        assert env.data is not None
        assert env.quality_score > 0
        assert env.data["ticker"] == "UPST"
        assert "price" in env.data

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
        assert any("adapters failed" in w.lower() for w in env.warnings)

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
        assert len(env.data) > 0
        # Data has expected structure
        for rec in env.data[:3]:
            assert "value" in rec
            assert "observation_date" in rec
            assert isinstance(rec["value"], float)

    async def test_provider_get_news(self):
        provider = await self._make_provider()
        env = await provider.get_news("UPST", limit=3)
        assert isinstance(env.data, list)
        assert len(env.data) == 3
        for item in env.data:
            assert "headline" in item
            assert "sentiment_score" in item
            assert isinstance(item["headline"], str)
            assert isinstance(item["sentiment_score"], float)

    async def test_provider_get_bars_default_dates(self):
        """get_bars with no start/end should default to 1-year range."""
        provider = await self._make_provider()
        env = await provider.get_bars("UPST")
        assert isinstance(env, DataEnvelope)
        assert isinstance(env.data, list)
        assert len(env.data) > 200  # ~252 trading days in a year
        assert env.quality_score > 0
        # Bars should have OHLCV structure
        bar = env.data[0]
        for f in ("open", "high", "low", "close", "volume"):
            assert f in bar
        assert bar["high"] >= bar["low"]
        assert bar["close"] > 0

    async def test_provider_get_short_interest(self):
        provider = await self._make_provider()
        env = await provider.get_short_interest("UPST")
        assert isinstance(env, DataEnvelope)
        assert env.data["ticker"] == "UPST"
        assert isinstance(env.data["short_interest"], int)
        assert env.data["short_interest"] > 0
        assert env.data["shares_float"] > 0

    async def test_provider_get_stock_loan(self):
        provider = await self._make_provider()
        env = await provider.get_stock_loan("UPST")
        assert isinstance(env, DataEnvelope)
        assert "cost_to_borrow" in env.data
        assert isinstance(env.data["cost_to_borrow"], float)
        assert env.data["cost_to_borrow"] > 0
        assert env.data["shares_available"] > 0

    async def test_provider_get_financials(self):
        provider = await self._make_provider()
        env = await provider.get_financials("UPST")
        assert isinstance(env, DataEnvelope)
        assert len(env.data) == 8
        for q in env.data:
            assert isinstance(q["revenue"], (int, float))
            assert q["revenue"] > 0
            assert "gross_margin" in q

    async def test_provider_get_earnings(self):
        provider = await self._make_provider()
        env = await provider.get_earnings("UPST")
        assert isinstance(env, DataEnvelope)
        assert len(env.data) == 8
        for r in env.data:
            assert "eps_estimate" in r
            assert "eps_actual" in r
            assert isinstance(r["eps_estimate"], (int, float))
            assert isinstance(r["eps_actual"], (int, float))

    async def test_provider_get_options_chain(self):
        provider = await self._make_provider()
        env = await provider.get_options_chain("UPST")
        assert isinstance(env, DataEnvelope)
        assert len(env.data["contracts"]) > 0
        contract = env.data["contracts"][0]
        assert contract["strike"] > 0
        assert contract["bid"] >= 0
        assert "implied_volatility" in contract
        types = {c["option_type"] for c in env.data["contracts"]}
        assert types == {"call", "put"}

    async def test_provider_concurrent_calls(self):
        """Calling get_quote and get_bars concurrently should both succeed."""
        provider = await self._make_provider()
        quote_env, bars_env = await asyncio.gather(
            provider.get_quote("UPST"),
            provider.get_bars("UPST"),
        )
        assert isinstance(quote_env, DataEnvelope)
        assert isinstance(bars_env, DataEnvelope)
        assert quote_env.data is not None
        assert bars_env.data is not None
        assert quote_env.data["ticker"] == "UPST"
        assert len(bars_env.data) > 0
        assert quote_env.source == "mock"
        assert bars_env.source == "mock"
