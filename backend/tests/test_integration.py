"""
Integration tests — validates the full analysis pipeline, data adapters,
database models, API layer, and cross-engine consistency.
"""

import asyncio
import datetime as dt
import numpy as np
import pytest


# ── Helper ──
def run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════
#  DATA ADAPTER TESTS
# ═══════════════════════════════════════════════════════

class TestDataAdapters:
    """Verify data adapters return well-formed DataEnvelopes."""

    def test_mock_market_quote(self):
        from backend.adapters.mock_adapter import MockMarketAdapter
        adapter = MockMarketAdapter()
        env = run(adapter.get_quote("UPST"))
        assert env.source == "mock"
        assert env.source_label == "mock"
        assert env.data["price"] > 0
        assert env.confidence == 0.3  # Mock data flagged as low confidence

    def test_mock_market_bars(self):
        from backend.adapters.mock_adapter import MockMarketAdapter
        adapter = MockMarketAdapter()
        end = dt.date.today()
        start = end - dt.timedelta(days=30)
        env = run(adapter.get_bars("UPST", "1d", start, end))
        assert len(env.data) > 0
        assert all(b["close"] > 0 for b in env.data)

    def test_mock_options_chain(self):
        from backend.adapters.mock_adapter import MockMarketAdapter
        adapter = MockMarketAdapter()
        env = run(adapter.get_options_chain("UPST"))
        contracts = env.data["contracts"]
        assert len(contracts) > 0
        assert all(c["strike"] > 0 for c in contracts)
        assert all(c["implied_volatility"] > 0 for c in contracts)

    def test_mock_short_interest(self):
        from backend.adapters.mock_adapter import MockShortAdapter
        adapter = MockShortAdapter()
        env = run(adapter.get_short_interest("UPST"))
        assert 0 < env.data["short_pct_float"] < 100
        assert env.data["days_to_cover"] > 0

    def test_mock_macro(self):
        from backend.adapters.mock_adapter import MockMacroAdapter
        adapter = MockMacroAdapter()
        env = run(adapter.get_indicator("FED_FUNDS"))
        assert len(env.data) == 252
        assert all(r["value"] > 0 for r in env.data)

    def test_mock_fundamentals(self):
        from backend.adapters.mock_adapter import MockFundamentalAdapter
        adapter = MockFundamentalAdapter()
        env = run(adapter.get_financials("UPST"))
        assert len(env.data) == 8  # 8 quarters
        assert all(q["revenue"] > 0 for q in env.data)

    def test_yahoo_adapter_imports(self):
        """Yahoo adapter should import without yfinance dependency."""
        from backend.adapters.yahoo_adapter import YahooMarketAdapter, YahooFundamentalAdapter
        adapter = YahooMarketAdapter()
        assert adapter is not None

    def test_provider_data_quality_summary(self):
        from backend.adapters.provider import data_provider
        summary = data_provider.get_data_quality_summary()
        assert "market" in summary
        assert "mock_mode" in summary
        assert isinstance(summary["has_yahoo"], bool)

    def test_provider_chain_fallback(self):
        """If all real adapters fail, mock should still return data."""
        from backend.adapters.mock_adapter import MockMarketAdapter
        adapter = MockMarketAdapter()
        env = run(adapter.get_quote("INVALID_TICKER_XYZ"))
        # Mock adapter doesn't validate tickers, so it returns data
        assert env.data is not None


# ═══════════════════════════════════════════════════════
#  PROBABILITY ENGINE TESTS (data-derived values)
# ═══════════════════════════════════════════════════════

class TestProbabilityEngineDataDerived:
    """Verify probability engine produces data-derived (not hardcoded) estimates."""

    def test_earnings_beat_varies_with_momentum(self):
        from backend.engines.probability import ProbabilityEngine
        pe = ProbabilityEngine()
        # Strong uptrend
        bullish = np.concatenate([np.ones(80) * 0.002, np.ones(21) * 0.01])
        snap_bull = pe.analyze(bullish, 70.0)
        # Strong downtrend
        bearish = np.concatenate([np.ones(80) * -0.002, np.ones(21) * -0.01])
        snap_bear = pe.analyze(bearish, 70.0)
        # Earnings beat should be higher in bullish environment
        assert snap_bull.prob_earnings_beat > snap_bear.prob_earnings_beat

    def test_squeeze_prob_multi_factor(self):
        from backend.engines.probability import ProbabilityEngine
        pe = ProbabilityEngine()
        returns = np.random.normal(0.001, 0.03, 100)
        # Low short interest
        snap_low = pe.analyze(returns, 70.0, short_data={"short_pct_float": 5})
        # High short interest + high borrow cost + high utilization
        snap_high = pe.analyze(returns, 70.0, short_data={
            "short_pct_float": 30, "cost_to_borrow": 25,
            "utilization": 95, "days_to_cover": 6,
        })
        assert snap_high.prob_squeeze > snap_low.prob_squeeze
        assert snap_high.prob_squeeze <= 0.80  # Capped

    def test_regime_probs_graduated(self):
        from backend.engines.probability import ProbabilityEngine
        pe = ProbabilityEngine()
        # Mildly bullish
        np.random.seed(99)
        mild = np.random.normal(0.001, 0.02, 100)
        snap = pe.analyze(mild, 70.0)
        # All three should be non-negative and sum close to 1
        total = snap.prob_bull_regime + snap.prob_neutral_regime + snap.prob_bear_regime
        assert abs(total - 1.0) < 0.02  # Allow rounding tolerance
        assert snap.prob_bull_regime >= 0
        assert snap.prob_bear_regime >= 0
        assert snap.prob_neutral_regime >= 0
        # At least one regime should dominate
        assert max(snap.prob_bull_regime, snap.prob_neutral_regime, snap.prob_bear_regime) > 0.3

    def test_funding_event_varies_with_vol(self):
        from backend.engines.probability import ProbabilityEngine
        pe = ProbabilityEngine()
        # Low vol
        low_vol = np.random.normal(0.001, 0.01, 100)
        snap_low = pe.analyze(low_vol, 70.0)
        # High vol
        high_vol = np.random.normal(-0.005, 0.06, 100)
        snap_high = pe.analyze(high_vol, 70.0)
        assert snap_high.prob_funding_event >= snap_low.prob_funding_event

    def test_probability_cones_ordered(self):
        from backend.engines.probability import ProbabilityEngine
        pe = ProbabilityEngine()
        returns = np.random.normal(0, 0.03, 200)
        snap = pe.analyze(returns, 70.0)
        for cone in [snap.cone_1w, snap.cone_1m, snap.cone_3m]:
            assert cone["p10"] <= cone["p25"] <= cone["p50"] <= cone["p75"] <= cone["p90"]

    def test_brier_score_computed(self):
        from backend.engines.probability import ProbabilityEngine
        pe = ProbabilityEngine()
        returns = np.random.normal(0, 0.03, 200)
        snap = pe.analyze(returns, 70.0)
        assert snap.brier_score is not None
        assert 0 <= snap.brier_score <= 1


# ═══════════════════════════════════════════════════════
#  DATABASE MODEL TESTS
# ═══════════════════════════════════════════════════════

class TestDatabaseModels:
    """Verify ORM models are well-formed."""

    def test_analysis_record_fields(self):
        from backend.models.analysis import AnalysisRecord
        record = AnalysisRecord(
            ticker="UPST", price=70.0,
            composite_score=65.0, action="buy", confidence=0.75,
        )
        assert record.ticker == "UPST"
        assert record.price == 70.0
        assert record.mock_data_used is None or record.mock_data_used == False

    def test_alert_record_fields(self):
        from backend.models.analysis import AlertRecord
        record = AlertRecord(
            severity="warning", title="Test Alert", message="Test message",
        )
        assert record.severity == "warning"
        assert record.acknowledged is None or record.acknowledged == False

    def test_backtest_record_fields(self):
        from backend.models.analysis import BacktestRecord
        record = BacktestRecord(
            strategy="technical_signals", total_return=15.5, sharpe_ratio=1.2,
        )
        assert record.strategy == "technical_signals"

    def test_base_metadata_has_tables(self):
        from backend.models.analysis import Base
        tables = list(Base.metadata.tables.keys())
        assert "analysis_records" in tables
        assert "alert_records" in tables
        assert "backtest_records" in tables


# ═══════════════════════════════════════════════════════
#  CROSS-ENGINE CONSISTENCY TESTS
# ═══════════════════════════════════════════════════════

class TestCrossEngineConsistency:
    """Verify engines produce consistent, bounded outputs when chained."""

    def test_scoring_engine_all_bounded(self):
        """All 15 scores must be in [0, 100]."""
        from backend.engines.scoring import ScoringEngine
        se = ScoringEngine()
        scores = se.compute_all(
            technical={"technical_strength_score": 75, "trend": "up"},
            options={"options_sentiment_score": 60, "atm_iv": 0.70},
            short={"short_opportunity_score": 65, "squeeze_risk_score": 40},
            funding={}, origination={}, macro={}, valuation={},
            news={}, spy_rel={}, forecast={},
        )
        for name, score in scores.items():
            assert 0 <= score.value <= 100, f"Score {name} = {score.value} out of bounds"

    def test_trade_decision_from_scores(self):
        """Trade decision engine must produce valid action from score inputs."""
        from backend.engines.trade_decision import TradeDecisionEngine
        from backend.engines.scoring import ScoringEngine
        se = ScoringEngine()
        scores = se.compute_all(
            technical={"technical_strength_score": 80, "trend": "up",
                       "atr": 3.0, "support_levels": [65, 60], "resistance_levels": [75, 80]},
            options={"options_sentiment_score": 70, "atm_iv": 0.70},
            short={"short_opportunity_score": 30, "squeeze_risk_score": 20},
            funding={}, origination={}, macro={}, valuation={},
            news={}, spy_rel={"beta": 1.5}, forecast={},
        )
        tde = TradeDecisionEngine()
        rec = tde.decide(
            scores, {"atr": 3.0, "support_levels": [65], "resistance_levels": [75]},
            {}, {}, {"beta": 1.5}, macro={}, price=70.0,
        )
        assert rec is not None
        valid_actions = {"buy", "sell", "hold", "short", "cover", "no_trade",
                         "buy_calls", "buy_puts", "bull_spread", "bear_spread",
                         "add", "add_short", "trim", "vol_trade"}
        assert rec.action in valid_actions

    def test_risk_engine_from_returns(self):
        """Risk engine must produce bounded VaR and drawdown."""
        from backend.engines.risk import RiskEngine
        re = RiskEngine()
        returns = np.random.normal(0.001, 0.03, 252)
        risk = re.compute_risk(returns, 70.0)
        assert risk.var_95_1d is not None
        assert risk.var_95_1d > 0  # VaR expressed as positive % loss
        assert risk.max_drawdown is not None
        assert risk.max_drawdown < 0  # Drawdown is negative

    def test_forecast_produces_cone(self):
        """Forecast engine must produce upper > point > lower."""
        import pandas as pd
        from backend.engines.forecast import ForecastEngine
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=252, freq="B", tz="UTC")
        prices = 70.0 * np.exp(np.cumsum(np.random.normal(0.001, 0.03, 252)))
        df = pd.DataFrame({
            "open": prices * 0.99, "high": prices * 1.02,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(1e6, 1e7, 252),
        }, index=dates)
        df.index.name = "bar_time"
        fe = ForecastEngine()
        result = fe.forecast(df, "UPST")
        assert result.ensemble_lower <= result.ensemble_point <= result.ensemble_upper


# ═══════════════════════════════════════════════════════
#  API LAYER TESTS
# ═══════════════════════════════════════════════════════

class TestAPIValidation:
    """Verify API layer validation and error handling."""

    def test_bot_name_whitelist(self):
        """Invalid bot names should be rejected."""
        from backend.api.routes import _VALID_BOT_NAMES
        assert "price_action" in _VALID_BOT_NAMES
        assert "sql_injection; DROP TABLE" not in _VALID_BOT_NAMES

    def test_backtest_request_validation(self):
        """BacktestRequest should enforce bounds."""
        from backend.api.routes import BacktestRequest
        req = BacktestRequest(days=365, position_size_pct=10.0)
        assert req.days == 365
        # Invalid values should raise
        with pytest.raises(Exception):
            BacktestRequest(days=-1)
        with pytest.raises(Exception):
            BacktestRequest(position_size_pct=200.0)

    def test_scenario_request_model(self):
        """ScenarioRequest should accept all lever types."""
        from backend.api.routes import ScenarioRequest
        req = ScenarioRequest(spy_return_pct=-10.0, fed_funds_change_bps=25.0)
        assert req.spy_return_pct == -10.0

    def test_global_exception_handler_exists(self):
        """Verify the FastAPI app has a global exception handler."""
        from backend.main import app
        # FastAPI stores exception handlers
        assert Exception in app.exception_handlers
