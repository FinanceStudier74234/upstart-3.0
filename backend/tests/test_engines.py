"""
Tests for all analytics engines — verifies each engine produces
valid output with correct score ranges and required fields.
"""

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

    def test_empty_df(self):
        from backend.engines.technical import TechnicalEngine
        snap = TechnicalEngine().analyze(pd.DataFrame(), "UPST")
        assert snap.price == 0.0


# ── Options Engine ──

class TestOptionsEngine:
    def test_analyze_returns_snapshot(self):
        from backend.engines.options import OptionsEngine
        engine = OptionsEngine()
        # Use mock data structure
        chain = {
            "options": [
                {"strike": 70, "expiry": "2026-04-17", "type": "call",
                 "bid": 5.0, "ask": 5.5, "volume": 1000, "oi": 5000, "iv": 0.65},
                {"strike": 70, "expiry": "2026-04-17", "type": "put",
                 "bid": 4.0, "ask": 4.5, "volume": 800, "oi": 4000, "iv": 0.70},
                {"strike": 75, "expiry": "2026-04-17", "type": "call",
                 "bid": 3.0, "ask": 3.5, "volume": 500, "oi": 3000, "iv": 0.60},
            ],
            "underlying_price": 70.0,
        }
        snap = engine.analyze(chain, "UPST")
        assert 0 <= snap.options_sentiment_score <= 100


# ── Short Engine ──

class TestShortEngine:
    def test_analyze_returns_snapshot(self):
        from backend.engines.short import ShortEngine
        engine = ShortEngine()
        short_data = {"short_interest": 15_000_000, "avg_volume": 8_000_000, "float_shares": 80_000_000}
        loan_data = {"fee_rate": 5.0, "available": 500_000, "utilization": 85}
        snap = engine.analyze(short_data, loan_data, {}, {}, 70.0)
        assert 0 <= snap.squeeze_risk_score <= 100
        assert snap.short_decision is not None
        assert isinstance(snap.do_not_short_flag, bool)


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


# ── Valuation Engine ──

class TestValuationEngine:
    def test_analyze(self):
        from backend.engines.valuation import ValuationEngine
        snap = ValuationEngine().analyze(price=70.0)
        assert snap.price_to_sales is not None
        assert snap.fair_value_base is not None
        assert snap.fair_value_bull > snap.fair_value_base > snap.fair_value_bear
        assert 0 <= snap.valuation_attractiveness_score <= 100


# ── Funding Analysis Engine ──

class TestFundingAnalysisEngine:
    def test_analyze(self):
        from backend.engines.funding_analysis import FundingAnalysisEngine
        snap = FundingAnalysisEngine().analyze()
        assert snap.total_committed > 0
        assert len(snap.facilities) > 0
        assert snap.partner_count > 0
        assert 0 <= snap.funding_strength_score <= 100


# ── Origination Analysis Engine ──

class TestOriginationAnalysisEngine:
    def test_analyze(self):
        from backend.engines.origination_analysis import OriginationAnalysisEngine
        snap = OriginationAnalysisEngine().analyze()
        assert snap.quarterly_volume > 0
        assert snap.product_count > 0
        assert 0 <= snap.origination_momentum_score <= 100


# ── Factor Engine ──

class TestFactorEngine:
    def test_analyze(self):
        from backend.engines.factor import FactorEngine
        snap = FactorEngine().analyze()
        assert snap.market_beta is not None
        assert snap.style in ("growth", "value", "blend")
        assert snap.systematic_risk_pct is not None


# ── Stress Engine ──

class TestStressEngine:
    def test_analyze(self):
        from backend.engines.stress import StressEngine
        snap = StressEngine().analyze()
        assert len(snap.scenarios) > 0
        assert snap.runway_months > 0
        assert 0 <= snap.balance_sheet_health_score <= 100


# ── Reflexivity Engine ──

class TestReflexivityEngine:
    def test_analyze(self):
        from backend.engines.reflexivity import ReflexivityEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        snap = ReflexivityEngine().analyze(returns, price=70.0)
        assert len(snap.feedback_loops) > 0
        assert 0 <= snap.reflexivity_score <= 100
        assert snap.return_autocorrelation is not None


# ── Execution Engine ──

class TestExecutionEngine:
    def test_analyze(self):
        from backend.engines.execution import ExecutionEngine
        snap = ExecutionEngine().analyze(price=70.0)
        assert snap.bid_ask_spread is not None
        assert snap.est_slippage_100k is not None
        assert 0 <= snap.liquidity_score <= 100


# ── Data Governance Engine ──

class TestDataGovernanceEngine:
    def test_analyze(self):
        from backend.engines.data_governance import DataGovernanceEngine
        snap = DataGovernanceEngine().analyze()
        assert len(snap.sources) > 0
        assert 0 <= snap.data_governance_score <= 100


# ── Catalyst Engine ──

class TestCatalystEngine:
    def test_analyze(self):
        from backend.engines.catalyst import CatalystEngine
        snap = CatalystEngine().analyze()
        assert len(snap.upcoming) > 0
        assert snap.next_earnings_date is not None
        assert 0 <= snap.binary_event_risk <= 100


# ── Overfitting Engine ──

class TestOverfittingEngine:
    def test_analyze(self):
        from backend.engines.overfitting import OverfittingEngine
        snap = OverfittingEngine().analyze()
        assert snap.risk_level in ("low", "medium", "high", "critical")
        assert 0 <= snap.overfitting_risk_score <= 100


# ── Probability Engine ──

class TestProbabilityEngine:
    def test_analyze(self):
        from backend.engines.probability import ProbabilityEngine
        returns = make_ohlcv_df()["close"].pct_change().dropna().values
        snap = ProbabilityEngine().analyze(returns, 70.0, target=80.0, stop=65.0)
        assert snap.prob_up_1w is not None
        assert 0 <= snap.prob_up_1w <= 1
        assert snap.cone_1m is not None and len(snap.cone_1m) > 0


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
