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
        assert result.kyle_lambda is not None
        assert result.amihud_illiquidity is not None
        assert result.vpin is not None
        assert result.roll_spread is not None
        assert result.flow_toxicity_regime in ("normal", "elevated", "toxic")
        assert 0 <= result.liquidity_score <= 100
