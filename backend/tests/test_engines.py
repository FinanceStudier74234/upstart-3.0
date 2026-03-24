"""
Tests for all analytics engines — verifies each engine produces
valid output with correct score ranges and required fields.
"""

import asyncio
import numpy as np
import pandas as pd
import pytest
import datetime as dt


# ── Helpers ──

def make_ohlcv_df(n=252) -> pd.DataFrame:
    """Generate synthetic OHLCV DataFrame."""
    np.random.seed(42)
    dates = pd.date_range("2025-03-20", periods=n, freq="B", tz="UTC")
    price = 70.0
    rows = []
    for d in dates:
        ret = np.random.normal(0.001, 0.04)
        close = price * (1 + ret)
        high = close * (1 + abs(np.random.normal(0, 0.01)))
        low = close * (1 - abs(np.random.normal(0, 0.01)))
        vol = int(np.random.uniform(3e6, 12e6))
        rows.append({"open": price, "high": high, "low": low, "close": close, "volume": vol})
        price = close
    df = pd.DataFrame(rows, index=dates)
    df.index.name = "bar_time"
    return df


# ── Technical Engine ──

class TestTechnicalEngine:
    def test_analyze_returns_snapshot(self):
        from backend.engines.technical import TechnicalEngine
        engine = TechnicalEngine()
        df = make_ohlcv_df()
        snap = engine.analyze(df, "UPST")
        assert snap.ticker == "UPST"
        assert snap.price > 0
        assert 0 <= snap.technical_strength_score <= 100
        assert snap.rsi is not None
        assert 0 <= snap.rsi <= 100
        assert snap.atr is not None and snap.atr > 0
        assert snap.trend_direction in ("up", "down", "neutral")
        assert snap.volatility_regime in ("compressed", "normal", "expanded")
        assert len(snap.sma) > 0
        assert len(snap.ema) > 0
        assert snap.macd_histogram is not None
        assert snap.adx is not None and snap.adx >= 0
        assert snap.stochastic_k is not None and 0 <= snap.stochastic_k <= 100
        assert len(snap.support_levels) >= 0
        assert len(snap.resistance_levels) >= 0
        assert snap.bollinger_pct_b is not None

    def test_empty_df(self):
        from backend.engines.technical import TechnicalEngine
        snap = TechnicalEngine().analyze(pd.DataFrame(), "UPST")
        assert snap.price == 0.0
        assert snap.rsi is None or snap.rsi == 0
        assert snap.technical_strength_score >= 0


# ── Options Engine ──

class TestOptionsEngine:
    def test_analyze_returns_snapshot(self):
        from backend.engines.options import OptionsEngine
        engine = OptionsEngine()
        # Use mock data structure matching engine's expected format
        chain = {
            "contracts": [
                {"strike": 70, "expiration": "2026-04-17", "option_type": "call",
                 "bid": 5.0, "ask": 5.5, "volume": 1000, "open_interest": 5000,
                 "implied_volatility": 0.65},
                {"strike": 70, "expiration": "2026-04-17", "option_type": "put",
                 "bid": 4.0, "ask": 4.5, "volume": 800, "open_interest": 4000,
                 "implied_volatility": 0.70},
                {"strike": 75, "expiration": "2026-04-17", "option_type": "call",
                 "bid": 3.0, "ask": 3.5, "volume": 500, "open_interest": 3000,
                 "implied_volatility": 0.60},
                {"strike": 60, "expiration": "2026-04-17", "option_type": "put",
                 "bid": 1.0, "ask": 1.5, "volume": 200, "open_interest": 1500,
                 "implied_volatility": 0.80},
                {"strike": 80, "expiration": "2026-05-15", "option_type": "call",
                 "bid": 2.0, "ask": 2.5, "volume": 300, "open_interest": 2000,
                 "implied_volatility": 0.55},
                {"strike": 65, "expiration": "2026-05-15", "option_type": "put",
                 "bid": 3.0, "ask": 3.5, "volume": 400, "open_interest": 2500,
                 "implied_volatility": 0.72},
            ],
            "underlying_price": 70.0,
        }
        snap = engine.analyze(chain, "UPST")
        assert 0 <= snap.options_sentiment_score <= 100
        assert snap.atm_iv is not None and snap.atm_iv > 0
        assert snap.iv_rank is not None
        assert snap.put_call_volume_ratio is not None
        assert isinstance(snap.unusual_calls, list)
        assert isinstance(snap.unusual_puts, list)
        assert snap.options_sentiment in ("very_bearish", "bearish", "neutral", "bullish", "very_bullish")


# ── Short Engine ──

class TestShortEngine:
    def test_analyze_returns_snapshot(self):
        from backend.engines.short import ShortEngine
        engine = ShortEngine()
        short_data = {
            "short_interest": 15_000_000, "avg_volume": 8_000_000,
            "float_shares": 80_000_000, "short_pct_float": 18.75,
            "days_to_cover": 1.875,
        }
        loan_data = {"cost_to_borrow": 5.0, "shares_available": 500_000, "utilization": 85}
        snap = engine.analyze(short_data, loan_data, {}, {}, 70.0)
        assert 0 <= snap.squeeze_risk_score <= 100
        assert snap.short_decision is not None
        assert isinstance(snap.do_not_short_flag, bool)
        assert snap.short_pct_float is not None
        assert snap.days_to_cover is not None
        assert snap.short_decision in (
            "short_now", "short_rally", "short_breakdown", "add_short",
            "cover_short", "avoid_short", "use_puts", "use_spreads",
            "no_bearish_trade", "no_action",
        )
        assert snap.crowding_score is not None


# ── SPY Beta Engine ──

class TestSPYBetaEngine:
    def test_analyze_returns_relationship(self):
        from backend.engines.spy_beta import SPYBetaEngine
        engine = SPYBetaEngine()
        upst_df = make_ohlcv_df()
        spy_df = make_ohlcv_df()
        snap = engine.analyze(upst_df, spy_df)
        assert snap.beta is not None
        assert snap.correlation is not None
        assert 0 <= snap.relative_strength_score <= 100
        assert snap.alpha_annualized is not None
        assert snap.pct_market_driven is not None and 0 <= snap.pct_market_driven <= 100
        assert snap.upside_capture is not None
        assert snap.downside_capture is not None


# ── Scoring Engine ──

class TestScoringEngine:
    def test_all_15_scores(self):
        from backend.engines.scoring import ScoringEngine
        engine = ScoringEngine()
        scores = engine.compute_all()
        assert len(scores) == 15
        expected = {
            "funding_strength", "origination_momentum", "macro_pressure",
            "credit_stress", "valuation_attractiveness", "technical_strength",
            "options_sentiment", "short_opportunity", "squeeze_risk",
            "news_regime", "forecast_confidence", "relative_strength_spy",
            "trade_quality", "positioning_fragility", "composite_opportunity",
        }
        assert set(scores.keys()) == expected
        for name, sr in scores.items():
            assert 0 <= sr.value <= 100, f"{name} score {sr.value} out of range"


# ── Trade Decision Engine ──

class TestTradeDecisionEngine:
    def test_decide_returns_recommendation(self):
        from backend.engines.trade_decision import TradeDecisionEngine
        from backend.engines.scoring import ScoringEngine
        scores = ScoringEngine().compute_all()
        engine = TradeDecisionEngine()
        rec = engine.decide(scores, price=70.0)
        assert rec.action is not None
        assert rec.confidence in ("low", "moderate", "high")
        assert rec.explanation != ""
        assert rec.vehicle is not None
        assert rec.entry_price is not None and rec.entry_price > 0
        # target/stop/R:R may be None when confidence is "low" (HOLD)
        if rec.confidence in ("moderate", "high"):
            assert rec.target_price is not None
            assert rec.stop_price is not None
            assert rec.reward_risk_ratio is not None
        assert hasattr(rec, "target_price")
        assert hasattr(rec, "stop_price")
        assert hasattr(rec, "reward_risk_ratio")

    def test_bearish_decision_parity(self):
        """Bearish path must compute EV, use ATR from technical, and have max_loss_pct."""
        from backend.engines.trade_decision import TradeDecisionEngine

        def make_score(v):
            return type("S", (), {"value": float(v), "confidence": 0.8})()

        bullish_scores = {k: make_score(v) for k, v in {
            "composite_opportunity": 75, "technical_strength": 72,
            "options_sentiment": 65, "short_opportunity": 40,
            "squeeze_risk": 25, "trade_quality": 68, "positioning_fragility": 30,
        }.items()}
        bearish_scores = {k: make_score(v) for k, v in {
            "composite_opportunity": 28, "technical_strength": 28,
            "options_sentiment": 30, "short_opportunity": 70,
            "squeeze_risk": 30, "trade_quality": 65, "positioning_fragility": 25,
        }.items()}
        technical = {"atr": 2.5, "rsi": 42.0}

        bull = TradeDecisionEngine().decide(scores=bullish_scores, price=70.0, technical=technical)
        bear = TradeDecisionEngine().decide(scores=bearish_scores, price=70.0, technical=technical)

        # Both must use ATR from technical dict (target = price ± atr*3)
        assert bull.target_price == round(70.0 + 2.5 * 3, 2)
        assert bear.target_price == round(70.0 - 2.5 * 3, 2)

        # Both must compute expected_value
        assert bull.expected_value is not None
        assert bear.expected_value is not None

        # max_loss_pct must be derived from actual stop distance, not hardcoded 2.0
        assert bull.max_loss_pct is not None and bull.max_loss_pct != 2.0
        assert bear.max_loss_pct is not None and bear.max_loss_pct != 2.0

        # Bearish EV should be positive (positive expected return on a valid short)
        assert bear.expected_value > 0


# ── Forecast Engine ──

class TestForecastEngine:
    def test_forecast_returns_ensemble(self):
        from backend.engines.forecast import ForecastEngine
        engine = ForecastEngine()
        df = make_ohlcv_df()
        result = engine.forecast(df, "UPST")
        assert result.ensemble_point > 0
        assert result.ensemble_lower <= result.ensemble_point <= result.ensemble_upper
        assert 0 <= result.confidence_score <= 100
        assert len(result.individual_forecasts) >= 3
        for model in result.individual_forecasts:
            assert model.model_name is not None and model.model_name != ""
            assert model.point_estimate is not None and model.point_estimate > 0


# ── Risk Engine ──

class TestRiskEngine:
    def test_compute_risk(self):
        from backend.engines.risk import RiskEngine
        engine = RiskEngine()
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        rm = engine.compute_risk(returns, 70.0)
        assert rm.var_95_1d is not None and rm.var_95_1d > 0
        assert rm.cvar_95_1d is not None
        assert rm.max_drawdown is not None and rm.max_drawdown <= 0
        assert rm.recommended_size_pct is not None and rm.recommended_size_pct > 0
        assert rm.skewness is not None
        assert rm.kurtosis is not None


# ── Backtest Engine ──

class TestBacktestEngine:
    def test_basic_backtest(self):
        from backend.engines.backtest import BacktestEngine
        engine = BacktestEngine()
        df = make_ohlcv_df(100)
        signals = [{"date": str(df.index[20].date()), "direction": "long", "strength": 0.8}]
        result = engine.run(df, signals, strategy_name="test")
        assert result.strategy_name == "test"
        assert isinstance(result.equity_curve, list)
        assert result.total_return is not None
        assert result.sharpe_ratio is not None
        assert result.max_drawdown is not None and result.max_drawdown <= 0
        assert result.win_rate is not None and 0 <= result.win_rate <= 100
        assert len(result.equity_curve) > 0
        assert result.total_trades >= 0

    def test_slippage_applied_to_fills(self):
        """Entry prices must be worse than close (slippage applied), and exit prices too."""
        from backend.engines.backtest import BacktestEngine
        import pandas as pd
        # Fixed price path to make assertions deterministic
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        prices = [70.0 + i * 0.1 for i in range(50)]  # monotonically rising
        df = pd.DataFrame({
            "open": prices, "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices], "close": prices,
            "volume": [1_000_000] * 50,
        }, index=dates)
        signals = [{"date": str(dates[5].date()), "direction": "long", "strength": 0.8}]
        slip = 0.10  # 0.1% slippage
        result = BacktestEngine().run(df, signals, slippage_pct=slip,
                                      commission_per_trade=2.0,
                                      stop_loss_pct=20.0, take_profit_pct=20.0)
        assert result.total_trades >= 1
        t = result.trades[0]
        close_at_entry = prices[5]
        # Long entry: fill must be higher than close by ~slippage
        assert t["entry_price"] > close_at_entry
        assert abs(t["entry_price"] - close_at_entry * (1 + slip / 100)) < 1e-6


# ── Valuation Engine ──

class TestValuationEngine:
    def test_analyze(self):
        from backend.engines.valuation import ValuationEngine
        snap = ValuationEngine().analyze(price=70.0)
        assert snap.price_to_sales is not None
        assert snap.fair_value_base is not None
        assert snap.fair_value_bull > snap.fair_value_base > snap.fair_value_bear
        assert 0 <= snap.valuation_attractiveness_score <= 100
        assert snap.ev_revenue is not None
        assert snap.fcf_yield is not None
        assert snap.upside_to_fair is not None
        assert len(snap.peer_multiples) > 0


# ── Funding Analysis Engine ──

class TestFundingAnalysisEngine:
    def test_analyze(self):
        from backend.engines.funding_analysis import FundingAnalysisEngine
        snap = FundingAnalysisEngine().analyze()
        assert snap.total_committed > 0
        assert len(snap.facilities) > 0
        assert snap.partner_count > 0
        assert 0 <= snap.funding_strength_score <= 100
        assert snap.utilization_pct is not None
        assert snap.months_coverage is not None
        for fac in snap.facilities:
            assert fac.name is not None and fac.name != ""


# ── Origination Analysis Engine ──

class TestOriginationAnalysisEngine:
    def test_analyze(self):
        from backend.engines.origination_analysis import OriginationAnalysisEngine
        snap = OriginationAnalysisEngine().analyze()
        assert snap.quarterly_volume > 0
        assert snap.product_count > 0
        assert 0 <= snap.origination_momentum_score <= 100
        assert snap.monthly_run_rate is not None
        assert snap.qoq_growth is not None
        assert snap.yoy_growth is not None
        assert snap.personal_pct is not None or snap.auto_pct is not None  # product_mix exists


# ── Factor Engine ──

class TestFactorEngine:
    def test_analyze(self):
        from backend.engines.factor import FactorEngine
        snap = FactorEngine().analyze()
        assert snap.market_beta is not None
        assert snap.style in ("growth", "value", "blend")
        assert snap.systematic_risk_pct is not None
        assert snap.size_loading is not None
        assert snap.value_loading is not None
        assert snap.momentum_loading is not None
        assert snap.size in ("mega", "large", "mid", "small", "micro", "mid_cap")
        assert snap.systematic_risk_pct + snap.idiosyncratic_risk_pct == pytest.approx(100)


# ── Stress Engine ──

class TestStressEngine:
    def test_analyze(self):
        from backend.engines.stress import StressEngine
        snap = StressEngine().analyze()
        assert len(snap.scenarios) > 0
        assert snap.runway_months > 0
        assert 0 <= snap.balance_sheet_health_score <= 100
        for scenario in snap.scenarios:
            assert scenario.name is not None and scenario.name != ""
            assert isinstance(scenario.survives, bool)
        assert snap.cash_and_equivalents is not None and snap.cash_and_equivalents > 0


# ── Reflexivity Engine ──

class TestReflexivityEngine:
    def test_analyze(self):
        from backend.engines.reflexivity import ReflexivityEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        snap = ReflexivityEngine().analyze(returns, price=70.0)
        assert len(snap.feedback_loops) > 0
        assert 0 <= snap.reflexivity_score <= 100
        assert snap.return_autocorrelation is not None
        for loop in snap.feedback_loops:
            assert loop.name is not None and loop.name != ""
        assert snap.herding_score is not None
        assert snap.regime_transition_probability is not None


# ── Execution Engine ──

class TestExecutionEngine:
    def test_analyze(self):
        from backend.engines.execution import ExecutionEngine
        snap = ExecutionEngine().analyze(price=70.0)
        assert snap.bid_ask_spread is not None
        assert snap.est_slippage_100k is not None
        assert 0 <= snap.liquidity_score <= 100
        assert snap.avg_daily_volume is not None and snap.avg_daily_volume > 0
        assert snap.optimal_algo is not None
        assert snap.stop_run_risk is not None
        assert snap.stop_run_risk in ("low", "medium", "high")

    def test_round_number_stop_cluster(self):
        """round_below must always be floor(price), not conditional on fractional part."""
        from backend.engines.execution import ExecutionEngine
        import datetime as dt
        e = ExecutionEngine()
        # Use bars with lows far below price so round number is the closest stop
        bars = [{"bar_time": dt.datetime(2024, 1, 1, 10, i), "open": 75.0,
                 "high": 75.5, "low": 60.0, "close": 75.0, "volume": 100_000}
                for i in range(20)]
        # For price=70.3: round_below=70, distance=(70.3-70)/70.3*100≈0.427%
        # For price=70.7: round_below=70, distance=(70.7-70)/70.7*100≈0.990%
        # Both should produce stop_run_proximity_pct ≈ (price-70)/price*100
        for price in [70.3, 70.7, 70.99]:
            snap = e.analyze(price=price, bars=bars)
            expected_below = int(price)  # floor
            if snap.stop_run_proximity_pct is not None:
                expected_dist = (price - expected_below) / price * 100
                assert abs(snap.stop_run_proximity_pct - expected_dist) < 0.1, (
                    f"price={price}: got {snap.stop_run_proximity_pct:.3f}, "
                    f"expected {expected_dist:.3f} (round_below={expected_below})"
                )


# ── Data Governance Engine ──

class TestDataGovernanceEngine:
    def test_analyze(self):
        from backend.engines.data_governance import DataGovernanceEngine
        snap = DataGovernanceEngine().analyze()
        assert len(snap.sources) > 0
        assert 0 <= snap.data_governance_score <= 100
        for src in snap.sources:
            assert src.name is not None and src.name != ""
            assert src.source is not None
            assert src.freshness in ("live", "stale", "expired", "unknown")
        assert snap.overall_quality_score is not None
        assert snap.overall_coverage_pct is not None
        assert snap.overall_freshness_score is not None


# ── Catalyst Engine ──

class TestCatalystEngine:
    def test_analyze(self):
        from backend.engines.catalyst import CatalystEngine
        snap = CatalystEngine().analyze()
        assert len(snap.upcoming) > 0
        assert snap.next_earnings_date is not None
        assert 0 <= snap.binary_event_risk <= 100
        assert snap.days_to_earnings is not None
        assert snap.catalysts_next_30d >= 0
        for cat in snap.upcoming:
            assert cat.name is not None and cat.name != ""
            assert cat.category in ("earnings", "product", "regulatory", "macro", "funding", "partnership")


# ── Overfitting Engine ──

class TestOverfittingEngine:
    def test_analyze(self):
        from backend.engines.overfitting import OverfittingEngine
        snap = OverfittingEngine().analyze()
        assert snap.risk_level in ("low", "medium", "high", "critical")
        assert 0 <= snap.overfitting_risk_score <= 100
        assert snap.is_sharpe is not None
        assert snap.oos_sharpe is not None
        assert snap.sharpe_decay_pct is not None
        assert snap.pbo is not None


# ── Probability Engine ──

class TestProbabilityEngine:
    def test_analyze(self):
        from backend.engines.probability import ProbabilityEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        snap = ProbabilityEngine().analyze(returns, 70.0, target=80.0, stop=65.0)
        assert snap.prob_up_1w is not None
        assert 0 <= snap.prob_up_1w <= 1
        assert snap.cone_1m is not None and len(snap.cone_1m) > 0
        assert snap.prob_up_1m is not None and 0 <= snap.prob_up_1m <= 1
        assert snap.prob_above_target is not None
        assert snap.prob_below_stop is not None

    def test_analyze_with_precomputed_garch(self):
        """ProbabilityEngine should use a pre-computed GARCH result instead of re-fitting."""
        from backend.engines.probability import ProbabilityEngine
        from unittest.mock import MagicMock

        returns = make_ohlcv_df()["close"].pct_change().dropna().values

        fake_garch = MagicMock()
        fake_garch.garch_converged = True
        fake_garch.conditional_volatility = np.array([0.03] * len(returns))

        snap = ProbabilityEngine().analyze(
            returns, 70.0, target=80.0, stop=65.0, garch_result=fake_garch)
        assert snap.calibration_score == 70.0  # Should be set when GARCH is used
        assert snap.prob_up_1w is not None

    def test_analyze_with_precomputed_hmm(self):
        """ProbabilityEngine should use a pre-computed HMM result for regime probs."""
        from backend.engines.probability import ProbabilityEngine
        from unittest.mock import MagicMock

        returns = make_ohlcv_df()["close"].pct_change().dropna().values

        fake_hmm = MagicMock()
        fake_hmm.current_regime_probabilities = {"bull": 0.6, "neutral": 0.3, "bear": 0.1}

        snap = ProbabilityEngine().analyze(
            returns, 70.0, hmm_result=fake_hmm)
        assert snap.prob_bull_regime == pytest.approx(0.6, abs=0.01)
        assert snap.prob_bear_regime == pytest.approx(0.1, abs=0.01)

    def test_analyze_no_precomputed_still_works(self):
        """Without pre-computed results, engine falls back to internal fitting."""
        from backend.engines.probability import ProbabilityEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        snap = ProbabilityEngine().analyze(returns, 70.0, garch_result=None, hmm_result=None)
        assert snap.prob_up_1w is not None
        assert 0 <= snap.prob_up_1w <= 1


# ── Behavioral Engine ──

class TestBehavioralEngine:
    def test_analyze(self):
        from backend.engines.behavioral import BehavioralEngine
        snap = BehavioralEngine().analyze(
            technical={"rsi": 24, "technical_strength_score": 30, "trend_direction": "down", "volatility_regime": "expanded"},
            options={"options_sentiment_score": 35},
            short={"squeeze_risk_score": 40},
            volume_ratio=2.5,
        )
        assert snap.panic_selling is True
        assert snap.sentiment_extreme == "panic"
        assert 0 <= snap.signal_clarity_score <= 100


# ── News Engine ──

class TestNewsEngine:
    def test_analyze(self):
        from backend.engines.news import NewsEngine
        snap = NewsEngine().analyze()
        assert snap.article_count > 0
        assert -1 <= snap.avg_sentiment <= 1
        assert snap.sentiment_label in ("very_bearish", "bearish", "neutral", "bullish", "very_bullish")
        assert 0 <= snap.news_sentiment_score <= 100
        assert snap.articles is not None and len(snap.articles) > 0
        for article in snap.articles:
            assert article.headline is not None and article.headline != ""
        assert isinstance(snap.policy_risk, bool)
        assert isinstance(snap.regulatory_risk, bool)


# ── Macro Engine ──

class TestMacroEngine:
    def test_analyze(self):
        from backend.engines.macro import MacroEngine
        snap = MacroEngine().analyze({"fed_funds": 5.25, "treasury_2y": 4.5, "treasury_10y": 4.2, "vix": 18, "hy_spread": 350})
        assert snap.yield_curve_inverted is True  # 4.2 - 4.5 = -0.3
        assert snap.rate_regime == "tightening"
        assert snap.macro_stress_regime in ("benign", "normal", "stressed", "crisis")


# ── Learning Engine ──

class TestLearningEngine:
    def test_log_and_validate(self):
        from backend.engines.learning import LearningEngine
        engine = LearningEngine()
        pid = engine.log_prediction("model_a", "price", 5, 75.0)
        assert pid is not None
        engine.validate_prediction(pid, 72.0)
        report = engine.get_report()
        assert report["total_predictions"] == 1
        assert report["validated"] == 1


# ── Scenario Engine ──

class TestScenarioEngine:
    def test_run_scenario_defaults(self):
        from backend.engines.scenario import ScenarioEngine, ScenarioInputs
        engine = ScenarioEngine()
        inputs = ScenarioInputs()
        # Create mock score objects
        base_scores = {}
        for name in ["funding_strength", "origination_momentum", "macro_pressure",
                      "credit_stress", "valuation_attractiveness", "technical_strength",
                      "options_sentiment", "short_opportunity", "squeeze_risk",
                      "news_regime", "forecast_confidence", "relative_strength_spy",
                      "trade_quality", "positioning_fragility", "composite_opportunity"]:
            base_scores[name] = type("Score", (), {"value": 50})()
        result = engine.run_scenario(inputs, 70.0, base_scores, beta=1.5, base_iv=0.65)
        assert result.adjusted_price_target > 0
        assert 0 <= result.probability_up <= 1
        assert 0 <= result.probability_down <= 1
        assert result.confidence > 0
        assert result.adjusted_trade_recommendation is not None
        assert result.fragility is not None
        assert result.probability_up + result.probability_down <= 1.0 + 1e-6

    def test_scenario_with_spy_shock(self):
        from backend.engines.scenario import ScenarioEngine, ScenarioInputs
        engine = ScenarioEngine()
        inputs = ScenarioInputs(spy_return_pct=-20.0)
        base_scores = {}
        for name in ["funding_strength", "origination_momentum", "macro_pressure",
                      "credit_stress", "valuation_attractiveness", "technical_strength",
                      "options_sentiment", "short_opportunity", "squeeze_risk",
                      "news_regime", "forecast_confidence", "relative_strength_spy",
                      "trade_quality", "positioning_fragility", "composite_opportunity"]:
            base_scores[name] = type("Score", (), {"value": 50})()
        result = engine.run_scenario(inputs, 70.0, base_scores, beta=1.5, base_iv=0.65)
        # SPY -20% with beta 1.5 should push target below current price
        assert result.adjusted_price_target < 70.0


# ── Bot Tests ──

class TestPriceActionBot:
    def test_run(self):
        from backend.bots.price_action_bot import PriceActionBot
        from backend.bots.base_bot import BotInput
        bot = PriceActionBot()
        inp = BotInput(ticker="UPST", current_price=70.0, scenario_params={"n_paths": 100, "horizon_days": 21})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert out.bot_name == "price_action_simulation"
        assert out.confidence > 0
        assert out.bot_name is not None
        assert "percentiles" in out.results
        assert len(out.paths) > 0
        assert len(out.results) >= 2


class TestSqueezeBot:
    def test_run(self):
        from backend.bots.squeeze_bot import SqueezeBot
        from backend.bots.base_bot import BotInput
        bot = SqueezeBot()
        inp = BotInput(ticker="UPST", current_price=70.0, scenario_params={"short_pct_float": 25.0})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert "scenarios" in out.results
        assert out.confidence > 0
        assert out.bot_name is not None
        assert "expected_price_with_squeeze_risk" in out.results
        assert len(out.results) >= 2


class TestMacroShockBot:
    def test_run(self):
        from backend.bots.macro_shock_bot import MacroShockBot
        from backend.bots.base_bot import BotInput
        bot = MacroShockBot()
        inp = BotInput(ticker="UPST", current_price=70.0, scenario_params={})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert "scenarios" in out.results
        assert out.results.get("most_likely") is not None
        assert out.confidence > 0
        assert out.bot_name is not None
        assert len(out.results) >= 2


class TestFundingStressBot:
    def test_run(self):
        from backend.bots.funding_stress_bot import FundingStressBot
        from backend.bots.base_bot import BotInput
        bot = FundingStressBot()
        inp = BotInput(ticker="UPST", current_price=70.0, scenario_params={})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert "scenarios" in out.results
        assert len(out.results["scenarios"]) > 0
        assert out.confidence > 0
        assert out.bot_name is not None
        assert "current_capacity_mm" in out.results or "concentration_risk" in out.results


class TestStrategyBot:
    def test_run_bearish(self):
        from backend.bots.strategy_bot import StrategyBot
        from backend.bots.base_bot import BotInput
        bot = StrategyBot()
        inp = BotInput(ticker="UPST", current_price=70.0,
                       scenario_params={"direction": "bearish", "iv": 0.70, "dte": 30})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert "strategies" in out.results
        assert "best_strategy" in out.results
        assert out.confidence > 0
        assert out.bot_name is not None
        assert len(out.results) >= 2


class TestRegimeBot:
    def test_run(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(ticker="UPST", current_price=70.0,
                       scenario_params={"vix": 35, "spy_trend": "down", "credit_spread_bps": 600})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert out.results.get("detected_regime") == "risk_off"
        assert out.confidence > 0
        assert out.bot_name is not None
        assert "transitions" in out.results
        assert len(out.results) >= 2


class TestOptionsReactionBot:
    def test_run(self):
        from backend.bots.options_reaction_bot import OptionsReactionBot
        from backend.bots.base_bot import BotInput
        bot = OptionsReactionBot()
        inp = BotInput(ticker="UPST", current_price=70.0,
                       scenario_params={"price_change_pct": -10, "iv_change_pct": 20})
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert "calls" in out.results
        assert "puts" in out.results
        assert out.confidence > 0
        assert out.bot_name is not None
        assert "greeks_summary" in out.results


class TestTradeDecisionBot:
    def test_run(self):
        from backend.bots.trade_decision_bot import TradeDecisionBot
        from backend.bots.base_bot import BotInput
        bot = TradeDecisionBot()
        # Bot _get_val expects either .value attr or dict with "value" key
        scores = {
            "technical_strength": {"value": 65}, "options_sentiment": {"value": 60},
            "funding_strength": {"value": 70}, "macro_pressure": {"value": 40},
            "short_opportunity": {"value": 30}, "squeeze_risk": {"value": 25},
        }
        inp = BotInput(
            ticker="UPST", current_price=70.0, scenario_params={},
            market_data={
                "scores": scores,
                "technical": {}, "options": {}, "short": {},
            },
        )
        out = asyncio.run(bot.run(inp))
        assert out.is_simulation is True
        assert "action" in out.results
        assert out.confidence > 0
        assert out.bot_name is not None
        assert "trade_quality" in out.results
        assert len(out.results) >= 2


# ═══════════════════════════════════════════════════════════════
# Advanced PhD-Level Engine Tests
# ═══════════════════════════════════════════════════════════════

class TestGARCHEngine:
    def test_fit_basic(self):
        from backend.engines.garch import GARCHEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        result = GARCHEngine().fit(returns)
        assert result.garch_converged is True
        assert result.alpha is not None and result.alpha > 0
        assert result.beta is not None and result.beta > 0
        assert result.persistence is not None and 0 < result.persistence < 1.05
        assert result.forecast_annualized_vol is not None and result.forecast_annualized_vol > 0
        assert result.current_regime in ("low_vol", "normal_vol", "high_vol", "crisis_vol")
        assert result.half_life_days is None or result.half_life_days > 0
        assert result.vol_term_structure is not None and len(result.vol_term_structure) > 0

    def test_insufficient_data(self):
        from backend.engines.garch import GARCHEngine
        result = GARCHEngine().fit(np.array([0.01, -0.02, 0.005]))
        assert result.garch_converged is False


class TestHMMRegimeEngine:
    def test_fit_3_regimes(self):
        from backend.engines.hmm_regime import HMMRegimeEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        result = HMMRegimeEngine().fit(returns)
        assert result.current_regime != ""
        assert result.current_regime_probabilities is not None
        assert len(result.current_regime_probabilities) > 0
        probs = list(result.current_regime_probabilities.values())
        assert abs(sum(probs) - 1.0) < 0.05
        assert result.transition_matrix is not None
        assert result.regime_statistics is not None

    def test_short_data(self):
        from backend.engines.hmm_regime import HMMRegimeEngine
        result = HMMRegimeEngine().fit(np.array([0.01] * 10))
        assert result is not None


class TestMultiFactorEngine:
    def test_single_factor(self):
        from backend.engines.multifactor import MultiFactorEngine
        df = make_ohlcv_df()
        returns = df["close"].pct_change().dropna().values
        spy_returns = returns + np.random.normal(0, 0.005, len(returns))
        result = MultiFactorEngine().analyze(returns, {"market": spy_returns})
        assert result.r_squared is not None and 0 <= result.r_squared <= 1
        assert "market" in result.betas
        assert result.systematic_risk_pct is not None

    def test_empty_factors(self):
        from backend.engines.multifactor import MultiFactorEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        result = MultiFactorEngine().analyze(returns, {})
        assert result.r_squared is None or result.r_squared == 0


class TestKalmanBetaEngine:
    def test_filter(self):
        from backend.engines.kalman_beta import KalmanBetaEngine
        df = make_ohlcv_df()
        upst = df["close"].pct_change().dropna().values
        spy = upst * 0.5 + np.random.normal(0, 0.01, len(upst))
        result = KalmanBetaEngine().filter(upst, spy)
        assert result.current_beta is not None
        assert result.beta_std is not None and result.beta_std >= 0
        assert result.beta_series is not None and len(result.beta_series) > 0

    def test_short_data(self):
        from backend.engines.kalman_beta import KalmanBetaEngine
        result = KalmanBetaEngine().filter(np.array([0.01, 0.02]), np.array([0.005, 0.01]))
        # Should handle gracefully
        assert result is not None


class TestCopulaRiskEngine:
    def test_analyze(self):
        from backend.engines.copula_risk import CopulaRiskEngine
        df = make_ohlcv_df()
        upst = df["close"].pct_change().dropna().values
        spy = upst * 0.4 + np.random.normal(0, 0.01, len(upst))
        result = CopulaRiskEngine().analyze(upst, spy)
        assert result.lambda_lower is not None
        assert result.lambda_upper is not None
        assert result.conditional_var_5pct is not None

    def test_short_data(self):
        from backend.engines.copula_risk import CopulaRiskEngine
        result = CopulaRiskEngine().analyze(np.array([0.01] * 5), np.array([0.005] * 5))
        assert result is not None


class TestARIMAForecastEngine:
    def test_forecast(self):
        from backend.engines.arima_forecast import ARIMAForecastEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        result = ARIMAForecastEngine().forecast(returns, horizon=21, price=70.0)
        assert result.selected_order is not None
        assert result.aic is not None
        assert result.point_forecast is not None or result.selected_order is not None


class TestIntradayEngine:
    def test_analyze(self):
        from backend.engines.intraday import IntradayEngine
        import datetime as dt
        bars = []
        price = 70.0
        base_time = dt.datetime(2026, 3, 22, 9, 30, tzinfo=dt.timezone.utc)
        for i in range(100):
            ret = np.random.normal(0, 0.002)
            price *= (1 + ret)
            bars.append({
                "bar_time": base_time + dt.timedelta(minutes=i),
                "open": round(price * 0.999, 2),
                "high": round(price * 1.005, 2),
                "low": round(price * 0.995, 2),
                "close": round(price, 2),
                "volume": int(np.random.uniform(50000, 200000)),
            })
        result = IntradayEngine().analyze(bars, daily_atr=3.0, prev_close=70.0)
        assert result.vwap is not None and result.vwap > 0
        assert result.orb_15_high is not None
        assert result.intraday_regime in ("trend", "range", "chop")
        assert result.point_of_control is not None
        assert result.n_bars == 100


class TestVolSurfaceEngine:
    def test_fit(self):
        from backend.engines.vol_surface import VolSurfaceEngine
        contracts = []
        spot = 70.0
        for strike in [60, 65, 70, 75, 80]:
            for otype in ["call", "put"]:
                iv = 0.65 + (strike - spot) * 0.005  # Simple skew
                contracts.append({
                    "strike": strike, "option_type": otype,
                    "expiration": "2026-06-19", "implied_volatility": iv,
                    "delta": 0.5 if strike == 70 else 0.3,
                })
        result = VolSurfaceEngine().fit(contracts, spot)
        assert result is not None


class TestMicrostructureEngine:
    def test_analyze(self):
        from backend.engines.microstructure import MicrostructureEngine
        df = make_ohlcv_df()
        bars = []
        for idx, row in df.iterrows():
            bars.append({
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": int(row["volume"]),
            })
        result = MicrostructureEngine().analyze(bars)
        assert np.isfinite(result.kyle_lambda)
        assert np.isfinite(result.amihud_illiquidity)
        assert np.isfinite(result.vpin)
        assert np.isfinite(result.roll_spread) or result.roll_spread == 0.0
        assert 0 <= result.toxicity_score <= 1.0
        assert result.n_bars == len(bars)


class TestCalibrationEngine:
    def test_calibrate(self):
        from backend.engines.calibration import CalibrationEngine, SCORE_NAMES
        rng = np.random.RandomState(42)
        n = 120
        returns = rng.normal(0.0005, 0.02, n)
        scores_history = [
            {name: float(rng.uniform(30, 80)) for name in SCORE_NAMES}
            for _ in range(n)
        ]
        signals_history = [
            {
                "prob_up": float(rng.uniform(0.3, 0.7)),
                "regime": rng.choice(["bull", "neutral", "bear"]),
                "direction": rng.choice(["bullish", "bearish", "neutral"]),
                "forecast_models": {"arima": float(rng.normal(0, 0.01)),
                                    "hmm": float(rng.normal(0, 0.01))},
            }
            for _ in range(n)
        ]
        result = CalibrationEngine().calibrate(returns, scores_history, signals_history)
        assert result.n_observations == n
        assert 0 < result.buy_threshold <= 100
        assert 0 <= result.sell_threshold < result.buy_threshold
        assert 0.0 <= result.brier_score <= 1.0
        assert isinstance(result.signal_decay, dict)
        assert isinstance(result.ensemble_weights, dict)
        assert "all" in result.confusion


# ═══════════════════════════════════════════════════
# COMPREHENSIVE EDGE-CASE TESTS
# ═══════════════════════════════════════════════════

class TestTradeDecisionEdgeCases:
    """Edge cases for trade decision engine."""

    def _make_scores(self, overrides=None):
        defaults = {
            "composite_opportunity": 50, "technical_strength": 50,
            "options_sentiment": 50, "short_opportunity": 50,
            "squeeze_risk": 30, "trade_quality": 55, "positioning_fragility": 30,
            "funding_strength": 50, "macro_pressure": 50,
        }
        if overrides:
            defaults.update(overrides)
        return {k: type("S", (), {"value": float(v), "confidence": 0.8})()
                for k, v in defaults.items()}

    def test_all_neutral_scores(self):
        """All scores at 50 → neutral/hold, no crash."""
        from backend.engines.trade_decision import TradeDecisionEngine
        rec = TradeDecisionEngine().decide(scores=self._make_scores(), price=70.0)
        assert rec.action in ("hold", "no_trade")
        assert rec.confidence == "low"

    def test_neutral_path_has_stops(self):
        """Neutral action should still provide defensive stop/target levels."""
        from backend.engines.trade_decision import TradeDecisionEngine
        rec = TradeDecisionEngine().decide(
            scores=self._make_scores({"composite_opportunity": 55, "trade_quality": 55}),
            price=70.0,
            technical={"atr": 2.5},
        )
        if rec.action == "hold":
            assert rec.stop_price is not None
            assert rec.target_price is not None

    def test_zero_price(self):
        """Zero price must not crash."""
        from backend.engines.trade_decision import TradeDecisionEngine
        rec = TradeDecisionEngine().decide(scores=self._make_scores(), price=0.0)
        assert rec.action is not None
        assert rec.target_price is None or rec.target_price == 0

    def test_regime_aware_sizing(self):
        """Crisis vol regime must produce smaller position than bull regime."""
        from backend.engines.trade_decision import TradeDecisionEngine
        bull_scores = self._make_scores({"composite_opportunity": 80, "technical_strength": 75})
        engine = TradeDecisionEngine()
        bull_rec = engine.decide(scores=bull_scores, price=70.0,
                                  hmm_regime={"current_regime": "bull"},
                                  garch={"vol_regime": "normal"})
        crisis_rec = engine.decide(scores=bull_scores, price=70.0,
                                    hmm_regime={"current_regime": "bear"},
                                    garch={"vol_regime": "crisis_vol"})
        if bull_rec.suggested_position_pct and crisis_rec.suggested_position_pct:
            assert crisis_rec.suggested_position_pct < bull_rec.suggested_position_pct

    def test_win_prob_bounded(self):
        """Win probability must stay within [0.15, 0.85]."""
        from backend.engines.trade_decision import TradeDecisionEngine
        extreme_bull = self._make_scores({
            "composite_opportunity": 100, "technical_strength": 100,
            "trade_quality": 100, "positioning_fragility": 0,
        })
        rec = TradeDecisionEngine().decide(scores=extreme_bull, price=70.0,
                                            technical={"atr": 2.5})
        if rec.expected_value is not None and rec.target_price and rec.stop_price:
            # Back-derive win_prob from EV
            upside = rec.target_price - 70.0
            downside = 70.0 - rec.stop_price
            if upside > 0 and downside > 0:
                wp = (rec.expected_value + downside) / (upside + downside)
                assert 0.14 <= wp <= 0.86

    def test_conflicting_signals(self):
        """Strong bullish + strong bearish → low confidence."""
        from backend.engines.trade_decision import TradeDecisionEngine
        mixed = self._make_scores({
            "composite_opportunity": 50, "technical_strength": 80,
            "options_sentiment": 20, "short_opportunity": 75,
            "funding_strength": 80, "macro_pressure": 80,
        })
        rec = TradeDecisionEngine().decide(scores=mixed, price=70.0)
        assert rec.confidence in ("low", "moderate")


class TestScoringEdgeCases:
    """Edge cases for scoring engine."""

    def test_all_scores_bounded(self):
        """Every score in compute_all must be in [0, 100]."""
        from backend.engines.scoring import ScoringEngine
        result = ScoringEngine().compute_all()
        for name, sr in result.items():
            assert 0 <= sr.value <= 100, f"{name}={sr.value} out of bounds"

    def test_extreme_valuation_inputs(self):
        """Extreme valuation data must not produce unbounded scores."""
        from backend.engines.scoring import ScoringEngine
        engine = ScoringEngine()
        # Simulate extreme inputs
        sr = engine._valuation_attractiveness({
            "price_to_sales": 0.01,  # extremely cheap
            "ps_median_3y": 8.0,
            "ev_revenue": 0.1,
            "growth_rate": 200,  # 200% growth
            "fcf_yield": 0.50,  # 50% FCF yield
            "upside_to_fair": 200,  # 200% upside
        })
        assert 0 <= sr.value <= 100

    def test_zero_ps_no_crash(self):
        """price_to_sales = 0 must not cause division by zero."""
        from backend.engines.scoring import ScoringEngine
        sr = ScoringEngine()._valuation_attractiveness({"price_to_sales": 0})
        assert 0 <= sr.value <= 100


class TestRiskEdgeCases:
    """Edge cases for risk engine."""

    def test_all_positive_returns(self):
        """All-winning returns: VaR should still be valid, tail_ratio not None."""
        from backend.engines.risk import RiskEngine
        returns = np.array([0.01, 0.02, 0.015, 0.005, 0.03] * 10)
        rm = RiskEngine().compute_risk(returns, price=70.0)
        assert rm.var_95_1d is not None
        assert rm.max_drawdown is not None and rm.max_drawdown <= 0

    def test_all_negative_returns(self):
        """All-losing returns: risk metrics still populated, high risk of ruin."""
        from backend.engines.risk import RiskEngine
        returns = np.array([-0.01, -0.02, -0.015, -0.005, -0.03] * 10)
        # Pass negative-expectancy parameters to match the return distribution
        rm = RiskEngine().compute_risk(returns, price=70.0, win_rate=0.2, avg_win=0.01, avg_loss=0.03)
        assert rm.var_95_1d is not None and rm.var_95_1d > 0
        assert rm.risk_of_ruin_pct == 100.0  # truly negative expectancy

    def test_zero_vol_capped_size(self):
        """Zero-vol returns: position sizing must be capped, not 100%."""
        from backend.engines.risk import RiskEngine
        returns = np.array([0.0] * 30)
        rm = RiskEngine().compute_risk(returns, price=70.0)
        assert rm.vol_target_size_pct <= 50.0

    def test_skew_adjusts_max_loss_sizing(self):
        """Highly skewed returns should produce different sizing than normal."""
        from backend.engines.risk import RiskEngine
        # Normal returns
        np.random.seed(42)
        normal_ret = np.random.normal(0, 0.02, 100)
        rm_normal = RiskEngine().compute_risk(normal_ret, price=70.0)
        # Fat-tailed returns (heavy left skew)
        skewed_ret = normal_ret.copy()
        skewed_ret[0] = -0.15  # crash event
        skewed_ret[1] = -0.12
        rm_skewed = RiskEngine().compute_risk(skewed_ret, price=70.0)
        # Skewed should have smaller max_loss_size (more conservative)
        if rm_normal.max_loss_size_pct and rm_skewed.max_loss_size_pct:
            assert rm_skewed.max_loss_size_pct <= rm_normal.max_loss_size_pct


class TestScenarioEdgeCases:
    """Edge cases for scenario engine."""

    def test_probability_sum_equals_one(self):
        """probability_up + probability_down + flat must always sum to ~1.0."""
        from backend.engines.scenario import ScenarioEngine, ScenarioInputs
        engine = ScenarioEngine()
        for impact in [-1.0, -0.5, -0.1, 0.0, 0.1, 0.5, 1.0]:
            inputs = ScenarioInputs(spy_return_pct=impact * 10)
            result = engine.run_scenario(inputs, base_price=70.0, base_scores={})
            total = result.probability_up + result.probability_down + 0.10
            assert 0.95 <= total <= 1.05, (
                f"impact={impact}: prob_up={result.probability_up}, "
                f"prob_down={result.probability_down}, total={total}"
            )

    def test_probabilities_non_negative(self):
        """All probabilities must be >= 0."""
        from backend.engines.scenario import ScenarioEngine, ScenarioInputs
        inputs = ScenarioInputs(spy_return_pct=-30, macro_stress_shock=1.0)
        result = ScenarioEngine().run_scenario(inputs, base_price=70.0, base_scores={})
        assert result.probability_up >= 0
        assert result.probability_down >= 0

    def test_negative_iv_change_clamped(self):
        """IV change of -150% must not produce negative IV."""
        from backend.engines.scenario import ScenarioEngine, ScenarioInputs
        inputs = ScenarioInputs(iv_change_pct=-150)
        result = ScenarioEngine().run_scenario(inputs, base_price=70.0, base_scores={})
        vol = result.adjusted_risk_metrics.get("vol_adjusted", 0)
        assert vol > 0

    def test_ev_based_trade_recommendation(self):
        """Strong upside + high probability should trigger buy."""
        from backend.engines.scenario import ScenarioEngine, ScenarioInputs
        inputs = ScenarioInputs(origination_growth_change_pct=20, funding_capacity_change_pct=30)
        result = ScenarioEngine().run_scenario(inputs, base_price=70.0, base_scores={})
        if result.adjusted_upside_pct > 10:
            assert result.adjusted_trade_recommendation in ("buy", "no_trade")


class TestBacktestEdgeCases:
    """Edge cases for backtest engine."""

    def test_short_signals(self):
        """Backtest with short-only signals must handle shorts correctly."""
        from backend.engines.backtest import BacktestEngine
        df = make_ohlcv_df(100)
        signals = [{"date": str(df.index[10].date()), "direction": "short", "strength": 0.8}]
        result = BacktestEngine().run(df, signals, slippage_pct=0.0, commission_per_trade=0.0)
        assert result.total_trades >= 1
        for t in result.trades:
            assert t["direction"] == "short"

    def test_all_winners_profit_factor(self):
        """All-winning trades should produce high payoff/profit factor, not 0."""
        from backend.engines.backtest import BacktestEngine
        import pandas as pd
        # Steadily rising price guarantees long winners
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        prices = [70.0 + i * 0.5 for i in range(50)]
        df = pd.DataFrame({
            "open": prices, "high": [p + 0.3 for p in prices],
            "low": [p - 0.3 for p in prices], "close": prices,
            "volume": [1_000_000] * 50,
        }, index=dates)
        signals = [{"date": str(dates[5].date()), "direction": "long", "strength": 0.9}]
        result = BacktestEngine().run(df, signals, take_profit_pct=5.0, stop_loss_pct=20.0,
                                       slippage_pct=0.0, commission_per_trade=0.0)
        if result.total_trades > 0 and result.avg_loss == 0:
            assert result.payoff_ratio > 0  # Not 0, should be high
            assert result.profit_factor > 0

    def test_empty_signals(self):
        """Empty signals list → no crash, zero trades."""
        from backend.engines.backtest import BacktestEngine
        df = make_ohlcv_df(50)
        result = BacktestEngine().run(df, [])
        assert result.total_trades == 0

    def test_very_short_backtest_annualization(self):
        """Very short backtest (<20 days) should not inflate annualized returns."""
        from backend.engines.backtest import BacktestEngine
        df = make_ohlcv_df(10)
        signals = [{"date": str(df.index[1].date()), "direction": "long", "strength": 0.8}]
        result = BacktestEngine().run(df, signals, slippage_pct=0.0, commission_per_trade=0.0)
        # Annualized should equal total (not compounded to absurd levels)
        assert result.annualized_return == result.total_return


class TestExecutionEdgeCases:
    """Edge cases for execution engine."""

    def test_zero_depth_imbalance(self):
        """Zero bid + ask depth must produce None imbalance, not 0."""
        from backend.engines.execution import ExecutionEngine
        snap = ExecutionEngine().analyze(price=70.0, volume_data={
            "bid_depth": 0, "ask_depth": 0, "avg_daily_volume": 5_000_000,
        })
        assert snap.depth_imbalance is None

    def test_chop_index_constant_price(self):
        """Constant price bars → chop index = 100 (max chop)."""
        from backend.engines.execution import ExecutionEngine
        bars = [{"open": 70.0, "high": 70.0, "low": 70.0, "close": 70.0,
                 "volume": 100_000} for _ in range(20)]
        snap = ExecutionEngine().analyze(price=70.0, bars=bars)
        # All highs/lows are 0 range → should be "chop" or "unknown"
        assert snap.chop_trend_regime in ("chop", "unknown")

    def test_stop_run_below_price(self):
        """Stop run proximity must be computed from levels below current price."""
        from backend.engines.execution import ExecutionEngine
        bars = [{"open": 75.0, "high": 76.0, "low": 60.0, "close": 75.0,
                 "volume": 100_000} for _ in range(20)]
        snap = ExecutionEngine().analyze(price=70.5, bars=bars)
        if snap.stop_run_proximity_pct is not None:
            assert snap.stop_run_proximity_pct > 0  # must be positive distance


class TestTradeDecisionBotEdgeCases:
    """Edge cases for trade decision bot."""

    def test_vehicle_mapping_complete(self):
        """All 12 action types must map to a valid vehicle, not 'none'."""
        from backend.bots.trade_decision_bot import _VEHICLE_MAP
        for action in ["buy", "short", "buy_calls", "buy_puts",
                       "bull_spread", "bear_spread", "cover", "sell",
                       "add", "add_short", "trim", "hold"]:
            assert _VEHICLE_MAP.get(action) != "none", f"Action '{action}' maps to 'none'"

    def test_continuous_confidence(self):
        """Confidence must be continuous, not just 0.2/0.4/0.6."""
        from backend.bots.trade_decision_bot import TradeDecisionBot
        c1 = TradeDecisionBot._compute_confidence("good", 3.0, 0.5, 0.0)
        c2 = TradeDecisionBot._compute_confidence("good", 1.5, 0.5, 0.0)
        assert c1 != c2  # Must differ for different conviction
        assert 0 < c1 < 1
        assert 0 < c2 < 1


# ── Bot Edge Cases ──

class TestPriceActionBotEdgeCases:
    """Edge cases for price action simulation bot."""

    def test_percentile_ordering(self):
        from backend.bots.price_action_bot import PriceActionBot
        from backend.bots.base_bot import BotInput
        bot = PriceActionBot()
        inp = BotInput(current_price=70.0, scenario_params={"n_paths": 500, "horizon_days": 20})
        out = asyncio.run(bot.run(inp))
        pcts = out.results["percentiles"]
        assert pcts[5] <= pcts[25] <= pcts[50] <= pcts[75] <= pcts[95]

    def test_probability_bounds(self):
        from backend.bots.price_action_bot import PriceActionBot
        from backend.bots.base_bot import BotInput
        bot = PriceActionBot()
        inp = BotInput(current_price=70.0, scenario_params={"n_paths": 200, "horizon_days": 10})
        out = asyncio.run(bot.run(inp))
        assert 0 <= out.results["probability_above_current"] <= 1
        assert 0 <= out.results["probability_below_current"] <= 1

    def test_zero_price_floor(self):
        from backend.bots.price_action_bot import PriceActionBot
        from backend.bots.base_bot import BotInput
        bot = PriceActionBot()
        inp = BotInput(current_price=-5.0, scenario_params={})
        out = asyncio.run(bot.run(inp))
        assert out.results["expected_price"] > 0

    def test_extreme_volatility(self):
        from backend.bots.price_action_bot import PriceActionBot
        from backend.bots.base_bot import BotInput
        bot = PriceActionBot()
        inp = BotInput(current_price=70.0, scenario_params={"volatility": 0.001, "n_paths": 100, "horizon_days": 5})
        out = asyncio.run(bot.run(inp))
        # Low vol: median should be near current price
        assert abs(out.results["percentiles"][50] - 70.0) < 10


class TestOptionsReactionBotEdgeCases:
    """Edge cases for options reaction bot."""

    def test_greeks_bounds(self):
        from backend.bots.options_reaction_bot import OptionsReactionBot
        from backend.bots.base_bot import BotInput
        bot = OptionsReactionBot()
        inp = BotInput(current_price=70.0, scenario_params={"price_change_pct": 0, "iv_change_pct": 0})
        out = asyncio.run(bot.run(inp))
        g = out.results["greeks_summary"]
        assert -1 <= g["delta_call"] <= 1
        assert -1 <= g["delta_put"] <= 0
        assert g["gamma"] >= 0
        assert g["theta"] <= 0  # theta is always negative for long options

    def test_deep_itm_call(self):
        from backend.bots.options_reaction_bot import OptionsReactionBot
        from backend.bots.base_bot import BotInput
        bot = OptionsReactionBot()
        inp = BotInput(current_price=70.0, scenario_params={"price_change_pct": 50, "iv_change_pct": 0})
        out = asyncio.run(bot.run(inp))
        # After +50% move, deep ITM calls should have significant value
        calls = out.results["calls"]
        assert any(c["new_price"] > c["base_price"] for c in calls)

    def test_pl_surface_shape(self):
        from backend.bots.options_reaction_bot import OptionsReactionBot
        from backend.bots.base_bot import BotInput
        bot = OptionsReactionBot()
        inp = BotInput(current_price=70.0, scenario_params={})
        out = asyncio.run(bot.run(inp))
        surface = out.results["pl_surface"]
        assert len(surface) == 5  # 5 price shifts
        # Each row should have price_change_pct and iv change columns
        for row in surface:
            assert "price_change_pct" in row


class TestSqueezeBotEdgeCases:
    """Edge cases for short squeeze simulation bot."""

    def test_scenario_ordering(self):
        from backend.bots.squeeze_bot import SqueezeBot
        from backend.bots.base_bot import BotInput
        bot = SqueezeBot()
        inp = BotInput(current_price=70.0, scenario_params={"short_pct_float": 25})
        out = asyncio.run(bot.run(inp))
        scenarios = out.results["scenarios"]
        # Squeeze prices should increase with severity
        prices = [s["squeeze_price"] for s in scenarios]
        assert prices == sorted(prices)

    def test_probability_sum_under_one(self):
        from backend.bots.squeeze_bot import SqueezeBot
        from backend.bots.base_bot import BotInput
        bot = SqueezeBot()
        inp = BotInput(current_price=70.0, scenario_params={"short_pct_float": 50})
        out = asyncio.run(bot.run(inp))
        total_prob = out.results["overall_squeeze_probability"]
        assert 0 < total_prob < 1  # Can't be 100% certain of squeeze

    def test_monte_carlo_paths(self):
        from backend.bots.squeeze_bot import SqueezeBot
        from backend.bots.base_bot import BotInput
        bot = SqueezeBot()
        inp = BotInput(current_price=70.0, scenario_params={})
        out = asyncio.run(bot.run(inp))
        mc = out.results["monte_carlo_squeeze_prices"]
        assert mc[5] <= mc[50] <= mc[95]  # Percentile ordering


class TestFundingStressBotEdgeCases:
    """Edge cases for funding stress bot."""

    def test_projected_price_never_negative(self):
        from backend.bots.funding_stress_bot import FundingStressBot
        from backend.bots.base_bot import BotInput
        bot = FundingStressBot()
        inp = BotInput(current_price=5.0, scenario_params={"facility_count": 1})
        out = asyncio.run(bot.run(inp))
        for s in out.results["scenarios"]:
            assert s["projected_price"] > 0

    def test_single_facility_max_loss(self):
        from backend.bots.funding_stress_bot import FundingStressBot
        from backend.bots.base_bot import BotInput
        bot = FundingStressBot()
        inp = BotInput(current_price=70.0, scenario_params={"facility_count": 1})
        out = asyncio.run(bot.run(inp))
        # With 1 facility, single non-renewal = 100% loss
        single = out.results["scenarios"][0]
        assert single["capacity_loss_pct"] == 100.0

    def test_zero_origination(self):
        from backend.bots.funding_stress_bot import FundingStressBot
        from backend.bots.base_bot import BotInput
        bot = FundingStressBot()
        inp = BotInput(current_price=70.0, scenario_params={"quarterly_origination_mm": 0})
        out = asyncio.run(bot.run(inp))
        assert out.results["current_months_coverage"] == 0


class TestMacroShockBotEdgeCases:
    """Edge cases for macro shock bot."""

    def test_projected_price_floor(self):
        from backend.bots.macro_shock_bot import MacroShockBot
        from backend.bots.base_bot import BotInput
        bot = MacroShockBot()
        inp = BotInput(current_price=10.0, scenario_params={"beta": 5.0})
        out = asyncio.run(bot.run(inp))
        for s in out.results["scenarios"]:
            assert s["projected_price"] >= 0.01

    def test_expected_price_weighted(self):
        from backend.bots.macro_shock_bot import MacroShockBot
        from backend.bots.base_bot import BotInput
        bot = MacroShockBot()
        inp = BotInput(current_price=70.0, scenario_params={})
        out = asyncio.run(bot.run(inp))
        # Expected price should be between worst and best case
        assert out.results["worst_case_price"] <= out.results["expected_price"] <= out.results["best_case_price"]

    def test_beta_clamped(self):
        from backend.bots.macro_shock_bot import MacroShockBot
        from backend.bots.base_bot import BotInput
        bot = MacroShockBot()
        inp = BotInput(current_price=70.0, scenario_params={"beta": 100})
        out = asyncio.run(bot.run(inp))
        # With clamped beta=5, prices should still be reasonable
        assert out.results["worst_case_price"] >= 0.01


class TestStrategyBotEdgeCases:
    """Edge cases for options strategy bot."""

    def test_bullish_strategies_have_pl_curve(self):
        from backend.bots.strategy_bot import StrategyBot
        from backend.bots.base_bot import BotInput
        bot = StrategyBot()
        inp = BotInput(current_price=70.0, scenario_params={"direction": "bullish"})
        out = asyncio.run(bot.run(inp))
        for strat in out.results["strategies"]:
            assert "pl_curve" in strat
            assert len(strat["pl_curve"]) == 25

    def test_bearish_put_spread_positive_debit(self):
        from backend.bots.strategy_bot import StrategyBot
        from backend.bots.base_bot import BotInput
        bot = StrategyBot()
        inp = BotInput(current_price=70.0, scenario_params={"direction": "bearish", "iv": 0.7, "dte": 30})
        out = asyncio.run(bot.run(inp))
        spread = [s for s in out.results["strategies"] if s["type"] == "put_spread"][0]
        assert spread["cost"] > 0

    def test_neutral_direction(self):
        from backend.bots.strategy_bot import StrategyBot
        from backend.bots.base_bot import BotInput
        bot = StrategyBot()
        inp = BotInput(current_price=70.0, scenario_params={"direction": "neutral"})
        out = asyncio.run(bot.run(inp))
        assert out.results["direction"] == "neutral"

    def test_configurable_rfr(self):
        from backend.bots.strategy_bot import StrategyBot
        from backend.bots.base_bot import BotInput
        bot = StrategyBot()
        inp = BotInput(current_price=70.0, scenario_params={"direction": "bullish", "risk_free_rate": 0.10})
        out = asyncio.run(bot.run(inp))
        assert out.confidence > 0  # Just verify it runs without error


class TestRegimeBotEdgeCases:
    """Edge cases for market regime bot."""

    def test_transition_probabilities_sum_to_one(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(scenario_params={"vix": 18, "spy_trend": "neutral"})
        out = asyncio.run(bot.run(inp))
        total = sum(t["probability"] for t in out.results["transitions"])
        assert abs(total - 1.0) < 0.01

    def test_high_vix_detects_risk_off(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(scenario_params={"vix": 45})
        out = asyncio.run(bot.run(inp))
        assert out.results["detected_regime"] == "risk_off"

    def test_low_vix_uptrend_detects_risk_on(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(scenario_params={"vix": 10, "spy_trend": "up"})
        out = asyncio.run(bot.run(inp))
        assert out.results["detected_regime"] == "risk_on"

    def test_mid_vix_neutral_detects_chop(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(scenario_params={"vix": 22, "spy_trend": "neutral"})
        out = asyncio.run(bot.run(inp))
        assert out.results["detected_regime"] == "chop"

    def test_no_negative_probabilities(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(scenario_params={"vix": 5, "credit_spread_bps": 0})
        out = asyncio.run(bot.run(inp))
        for t in out.results["transitions"]:
            assert t["probability"] >= 0

    def test_unknown_regime_fallback(self):
        from backend.bots.regime_bot import RegimeBot
        from backend.bots.base_bot import BotInput
        bot = RegimeBot()
        inp = BotInput(scenario_params={"current_regime": "crash", "vix": 18, "spy_trend": "down"})
        out = asyncio.run(bot.run(inp))
        # Should fall through to current_regime="crash", but regimes.get uses "normal" fallback
        assert out.results is not None


# ═══════════════════════════════════════════════════════════════
# Previously Untested Engines — credit_model, dcc, news_intelligence, yield_curve
# ═══════════════════════════════════════════════════════════════


class TestCreditModelEngine:
    def test_analyze_basic(self):
        from backend.engines.credit_model import CreditModelEngine
        engine = CreditModelEngine()
        result = engine.analyze(
            market_cap=6e9, equity_vol=0.65, total_debt=1e9, cash=500e6,
            risk_free_rate=0.045,
        )
        assert result.merton_converged is True
        assert result.implied_asset_value > 0
        assert result.implied_asset_volatility > 0
        assert result.distance_to_default > 0
        assert 0 <= result.probability_of_default <= 1
        assert result.edf_1y >= 0
        assert result.fair_credit_spread_bps >= 0
        assert result.z_zone in ("safe", "grey", "distress")
        assert result.credit_risk_rating in ("low", "moderate", "elevated", "high")
        assert 0 <= result.credit_risk_score <= 100

    def test_rate_shock_sensitivity(self):
        from backend.engines.credit_model import CreditModelEngine
        result = CreditModelEngine().analyze(
            market_cap=6e9, equity_vol=0.65, total_debt=1e9, cash=500e6,
            risk_free_rate=0.045,
        )
        assert len(result.pd_rate_shock) > 0
        assert len(result.pd_spread_shock) > 0
        assert len(result.pd_funding_stress) > 0
        # Higher rates should generally increase PD
        for label, pd in result.pd_rate_shock.items():
            assert 0 <= pd <= 1, f"PD under {label} shock out of range: {pd}"

    def test_maturity_profile(self):
        from backend.engines.credit_model import CreditModelEngine
        result = CreditModelEngine().analyze(
            market_cap=6e9, equity_vol=0.65, total_debt=1e9, cash=500e6,
            risk_free_rate=0.045,
        )
        assert len(result.maturity_profile) > 0
        assert result.refinancing_risk_score >= 0
        assert result.annual_refi_cost_base > 0
        assert result.annual_refi_cost_stress >= result.annual_refi_cost_base

    def test_zero_debt(self):
        from backend.engines.credit_model import CreditModelEngine
        result = CreditModelEngine().analyze(
            market_cap=6e9, equity_vol=0.65, total_debt=0, cash=500e6,
            risk_free_rate=0.045,
        )
        # With zero debt, Merton model can't solve
        assert result.merton_converged is False or result.probability_of_default == 0

    def test_with_fundamentals(self):
        from backend.engines.credit_model import CreditModelEngine
        fundies = {
            "total_assets": 10e9, "working_capital": 500e6,
            "retained_earnings": 200e6, "ebit": 300e6, "sales": 1.5e9,
        }
        result = CreditModelEngine().analyze(
            market_cap=6e9, equity_vol=0.65, total_debt=1e9, cash=500e6,
            risk_free_rate=0.045, fundamentals=fundies,
        )
        assert result.z_score != 0  # Should compute a meaningful Z-score
        assert len(result.z_components) == 5


class TestDCCEngine:
    def test_estimate_basic(self):
        from backend.engines.dcc import DCCEngine
        np.random.seed(42)
        n = 252
        spy_r = np.random.normal(0.0005, 0.01, n)
        upst_r = 1.5 * spy_r + np.random.normal(0, 0.03, n)
        result = DCCEngine().estimate(upst_r, spy_r)
        assert result.n_observations == n
        assert result.unconditional_correlation is not None
        assert result.upst_garch_converged is True
        assert result.spy_garch_converged is True
        assert result.correlation_series is not None
        assert len(result.correlation_series) == n
        assert result.current_correlation is not None
        assert -1 <= result.current_correlation <= 1
        assert result.current_regime in ("decorrelated", "moderate", "high", "crisis")

    def test_conditional_beta(self):
        from backend.engines.dcc import DCCEngine
        np.random.seed(42)
        n = 252
        spy_r = np.random.normal(0.0005, 0.01, n)
        upst_r = 1.5 * spy_r + np.random.normal(0, 0.03, n)
        result = DCCEngine().estimate(upst_r, spy_r)
        assert result.beta_series is not None
        assert result.current_beta is not None
        assert result.mean_beta is not None
        assert result.beta_std is not None and result.beta_std >= 0

    def test_correlation_forecast(self):
        from backend.engines.dcc import DCCEngine
        np.random.seed(42)
        n = 252
        spy_r = np.random.normal(0.0005, 0.01, n)
        upst_r = 1.5 * spy_r + np.random.normal(0, 0.03, n)
        result = DCCEngine().estimate(upst_r, spy_r)
        assert "t+1" in result.correlation_forecast
        assert "t+5" in result.correlation_forecast
        assert "t+21" in result.correlation_forecast
        for h, val in result.correlation_forecast.items():
            assert -1 <= val <= 1, f"Forecast {h} out of range: {val}"

    def test_asymmetry(self):
        from backend.engines.dcc import DCCEngine
        np.random.seed(42)
        n = 252
        spy_r = np.random.normal(0.0005, 0.01, n)
        upst_r = 1.5 * spy_r + np.random.normal(0, 0.03, n)
        result = DCCEngine().estimate(upst_r, spy_r)
        assert result.corr_down_markets is not None
        assert result.corr_up_markets is not None

    def test_insufficient_data(self):
        from backend.engines.dcc import DCCEngine
        result = DCCEngine().estimate(np.array([0.01, -0.02]), np.array([0.005, -0.01]))
        assert result.n_observations == 0
        assert result.correlation_series is None

    def test_regime_detection(self):
        from backend.engines.dcc import DCCEngine
        np.random.seed(42)
        n = 252
        spy_r = np.random.normal(0.0005, 0.01, n)
        upst_r = 1.5 * spy_r + np.random.normal(0, 0.03, n)
        result = DCCEngine().estimate(upst_r, spy_r)
        assert result.regime_series is not None
        assert len(result.regime_counts) > 0
        assert len(result.regime_fractions) > 0
        total_frac = sum(result.regime_fractions.values())
        assert abs(total_frac - 1.0) < 1e-6


class TestNewsIntelligenceEngine:
    def test_analyze_defaults(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        engine = NewsIntelligenceEngine()
        snap = engine.analyze()
        assert snap.ticker == "UPST"
        assert snap.total_article_count > 0
        assert len(snap.articles) > 0
        assert 0 <= snap.news_intelligence_score <= 100
        assert snap.base_news.article_count > 0

    def test_ceo_insight(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze()
        ceo = snap.ceo_insight
        assert ceo.name == "Dave Girouard"
        assert ceo.tone in ("optimistic", "cautious", "neutral", "defensive", "aggressive")
        assert ceo.activity_level in ("high", "normal", "low", "silent")
        assert len(ceo.recent_statements) > 0

    def test_ir_insight(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze()
        ir = snap.ir_insight
        assert ir.release_frequency in ("high", "normal", "low")
        assert isinstance(ir.themes, list)

    def test_social_sentiment(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze()
        social = snap.social_sentiment
        assert social.retail_sentiment_label in (
            "very_bullish", "bullish", "neutral", "bearish", "very_bearish",
        )
        assert social.bull_bear_ratio > 0

    def test_market_narrative(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze()
        narrative = snap.market_narrative
        assert narrative.dominant_narrative != "neutral"  # should be classified
        assert 0 <= narrative.narrative_strength <= 1
        assert narrative.catalyst_proximity in ("near", "medium", "far", "none")

    def test_signals_and_risks(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze()
        assert isinstance(snap.threat_signals, list)
        assert isinstance(snap.opportunity_signals, list)
        assert isinstance(snap.risk_summary, dict)
        assert len(snap.key_headlines) <= 5

    def test_analysis_notes(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze()
        assert isinstance(snap.analysis_notes, list)
        assert len(snap.analysis_notes) >= 1
        assert len(snap.analysis_notes) <= 5

    def test_with_custom_news(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        custom_news = [
            {"headline": "UPST announces record Q1 revenue",
             "source": "Reuters", "published": "2026-03-20", "sentiment": 0.8,
             "relevance": 0.95, "category": "earnings"},
        ]
        snap = NewsIntelligenceEngine().analyze(news_data=custom_news)
        assert snap.total_article_count > 0
        assert any("record Q1" in h for h in snap.key_headlines)

    def test_empty_news(self):
        from backend.engines.news_intelligence import NewsIntelligenceEngine
        snap = NewsIntelligenceEngine().analyze(news_data=[])
        # Falls back to default news
        assert snap.total_article_count > 0


class TestYieldCurveEngine:
    def test_analyze_full_curve(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {
            "1m": 5.30, "3m": 5.25, "6m": 5.10, "1y": 4.80,
            "2y": 4.50, "3y": 4.30, "5y": 4.10, "7y": 4.05,
            "10y": 4.00, "20y": 4.20, "30y": 4.30,
        }
        result = YieldCurveEngine().analyze(rates)
        assert result.ns_converged is True
        assert result.beta0 is not None
        assert result.beta1 is not None
        assert result.beta2 is not None
        assert result.tau is not None and result.tau > 0
        assert result.fitted_maturities is not None
        assert result.fitted_yields is not None

    def test_shape_classification_inverted(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {
            "3m": 5.25, "1y": 4.80, "2y": 4.50, "5y": 4.10,
            "10y": 4.00, "30y": 4.30,
        }
        result = YieldCurveEngine().analyze(rates)
        assert result.curve_shape == "inverted"
        assert result.spread_2s10s is not None and result.spread_2s10s < 0

    def test_shape_classification_normal(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {
            "3m": 2.00, "1y": 2.50, "2y": 3.00, "5y": 3.50,
            "10y": 4.00, "30y": 4.50,
        }
        result = YieldCurveEngine().analyze(rates)
        assert result.curve_shape == "normal"
        assert result.spread_2s10s is not None and result.spread_2s10s > 0

    def test_shock_scenarios(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {
            "3m": 5.25, "1y": 4.80, "2y": 4.50, "5y": 4.10,
            "10y": 4.00, "30y": 4.30,
        }
        result = YieldCurveEngine().analyze(rates)
        assert len(result.shock_scenarios) > 0
        assert "parallel_+100bps" in result.shock_scenarios
        assert "steepening" in result.shock_scenarios
        assert "flattening" in result.shock_scenarios

    def test_forward_rates(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {
            "3m": 5.25, "1y": 4.80, "2y": 4.50, "5y": 4.10,
            "10y": 4.00, "30y": 4.30,
        }
        result = YieldCurveEngine().analyze(rates)
        assert result.forward_1y1y is not None
        assert result.forward_1y2y is not None
        assert result.forward_2y3y is not None

    def test_fed_funds_path(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {
            "3m": 5.25, "1y": 4.80, "2y": 4.50, "5y": 4.10,
            "10y": 4.00, "30y": 4.30,
        }
        result = YieldCurveEngine().analyze(rates)
        assert result.fed_funds_rate is not None
        assert result.prob_next_cut is not None
        assert result.prob_next_hike is not None
        assert result.prob_next_cut + result.prob_next_hike == pytest.approx(1.0, abs=1e-6)
        # 2y (4.50) < 3m (5.25) → cuts priced in
        assert result.cuts_priced_in is not None and result.cuts_priced_in > 0

    def test_insufficient_tenors(self):
        from backend.engines.yield_curve import YieldCurveEngine
        rates = {"2y": 4.50, "10y": 4.00}
        result = YieldCurveEngine().analyze(rates)
        assert result.ns_converged is False
        assert result.n_tenors_input == 2

    def test_duration_estimation(self):
        from backend.engines.yield_curve import YieldCurveEngine
        np.random.seed(42)
        rates = {
            "3m": 5.25, "1y": 4.80, "2y": 4.50, "5y": 4.10,
            "10y": 4.00, "30y": 4.30,
        }
        n = 252
        rate_changes = np.random.normal(0, 0.02, n)
        upst_returns = -2.0 * rate_changes + np.random.normal(0, 0.03, n)
        result = YieldCurveEngine().analyze(rates, upst_returns, rate_changes)
        assert result.effective_duration is not None
        assert result.effective_duration > 0  # UPST moves inverse to rates
        assert result.duration_r_squared is not None
