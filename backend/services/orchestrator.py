"""
Central Orchestrator — coordinates all engines, adapters, and bots
into a unified analysis pipeline.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

from backend.adapters.provider import data_provider
from backend.engines.technical import TechnicalEngine, TechnicalSnapshot
from backend.engines.options import OptionsEngine, OptionsSnapshot
from backend.engines.short import ShortEngine, ShortSnapshot
from backend.engines.spy_beta import SPYBetaEngine, SPYRelationship
from backend.engines.scoring import ScoringEngine
from backend.engines.trade_decision import TradeDecisionEngine
from backend.engines.forecast import ForecastEngine
from backend.engines.risk import RiskEngine
from backend.engines.scenario import ScenarioEngine, ScenarioInputs
from backend.engines.valuation import ValuationEngine
from backend.engines.funding_analysis import FundingAnalysisEngine
from backend.engines.origination_analysis import OriginationAnalysisEngine
from backend.engines.factor import FactorEngine
from backend.engines.stress import StressEngine
from backend.engines.reflexivity import ReflexivityEngine
from backend.engines.execution import ExecutionEngine
from backend.engines.data_governance import DataGovernanceEngine
from backend.engines.catalyst import CatalystEngine
from backend.engines.overfitting import OverfittingEngine
from backend.engines.probability import ProbabilityEngine
from backend.engines.macro import MacroEngine
from backend.engines.backtest import BacktestEngine
from backend.engines.behavioral import BehavioralEngine
from backend.engines.learning import LearningEngine
from backend.engines.news import NewsEngine
from backend.engines.news_intelligence import NewsIntelligenceEngine

# Advanced PhD-level engines
try:
    from backend.engines.garch import GARCHEngine
except ImportError:
    GARCHEngine = None
try:
    from backend.engines.hmm_regime import HMMRegimeEngine
except ImportError:
    HMMRegimeEngine = None
try:
    from backend.engines.multifactor import MultiFactorEngine
except ImportError:
    MultiFactorEngine = None
try:
    from backend.engines.vol_surface import VolSurfaceEngine
except ImportError:
    VolSurfaceEngine = None
try:
    from backend.engines.microstructure import MicrostructureEngine
except ImportError:
    MicrostructureEngine = None
try:
    from backend.engines.kalman_beta import KalmanBetaEngine
except ImportError:
    KalmanBetaEngine = None
try:
    from backend.engines.copula_risk import CopulaRiskEngine
except ImportError:
    CopulaRiskEngine = None
try:
    from backend.engines.arima_forecast import ARIMAForecastEngine
except ImportError:
    ARIMAForecastEngine = None
try:
    from backend.engines.dcc import DCCEngine
except ImportError:
    DCCEngine = None
try:
    from backend.engines.intraday import IntradayEngine
except ImportError:
    IntradayEngine = None
try:
    from backend.engines.calibration import CalibrationEngine
except ImportError:
    CalibrationEngine = None
try:
    from backend.engines.credit_model import CreditModelEngine
except ImportError:
    CreditModelEngine = None
try:
    from backend.engines.yield_curve import YieldCurveEngine
except ImportError:
    YieldCurveEngine = None

from backend.bots.price_action_bot import PriceActionBot
from backend.bots.squeeze_bot import SqueezeBot
from backend.bots.macro_shock_bot import MacroShockBot
from backend.bots.strategy_bot import StrategyBot
from backend.bots.trade_decision_bot import TradeDecisionBot
from backend.bots.regime_bot import RegimeBot
from backend.bots.funding_stress_bot import FundingStressBot
from backend.bots.options_reaction_bot import OptionsReactionBot
from backend.bots.base_bot import BotInput

logger = logging.getLogger(__name__)


@dataclass
class FullAnalysis:
    """Complete platform analysis output."""
    ticker: str = "UPST"
    timestamp: str = ""
    price: float = 0.0

    # Engine outputs (serialized)
    technical: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)
    short: dict = field(default_factory=dict)
    spy_relationship: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    trade_decision: dict = field(default_factory=dict)
    forecast: dict = field(default_factory=dict)
    risk: dict = field(default_factory=dict)

    # New engine outputs
    valuation: dict = field(default_factory=dict)
    funding: dict = field(default_factory=dict)
    origination: dict = field(default_factory=dict)
    macro: dict = field(default_factory=dict)
    factor: dict = field(default_factory=dict)
    stress: dict = field(default_factory=dict)
    reflexivity: dict = field(default_factory=dict)
    execution: dict = field(default_factory=dict)
    data_governance: dict = field(default_factory=dict)
    catalyst: dict = field(default_factory=dict)
    overfitting: dict = field(default_factory=dict)
    probability: dict = field(default_factory=dict)
    behavioral: dict = field(default_factory=dict)
    news: dict = field(default_factory=dict)
    learning: dict = field(default_factory=dict)

    # News intelligence
    news_intelligence: dict = field(default_factory=dict)

    # Advanced PhD-level engine outputs
    garch: dict = field(default_factory=dict)
    hmm_regime: dict = field(default_factory=dict)
    multifactor: dict = field(default_factory=dict)
    vol_surface: dict = field(default_factory=dict)
    microstructure: dict = field(default_factory=dict)
    kalman_beta: dict = field(default_factory=dict)
    copula_risk: dict = field(default_factory=dict)
    dcc: dict = field(default_factory=dict)
    intraday: dict = field(default_factory=dict)
    arima_forecast: dict = field(default_factory=dict)
    credit_model: dict = field(default_factory=dict)
    yield_curve: dict = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)

    # Data quality
    data_sources: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Orchestrator:
    """Runs the full analysis pipeline."""

    def __init__(self):
        self.technical_engine = TechnicalEngine()
        self.options_engine = OptionsEngine()
        self.short_engine = ShortEngine()
        self.spy_beta_engine = SPYBetaEngine()
        self.scoring_engine = ScoringEngine()
        self.trade_decision_engine = TradeDecisionEngine()
        self.forecast_engine = ForecastEngine()
        self.risk_engine = RiskEngine()
        self.scenario_engine = ScenarioEngine()
        self.valuation_engine = ValuationEngine()
        self.funding_engine = FundingAnalysisEngine()
        self.origination_engine = OriginationAnalysisEngine()
        self.factor_engine = FactorEngine()
        self.stress_engine = StressEngine()
        self.reflexivity_engine = ReflexivityEngine()
        self.execution_engine = ExecutionEngine()
        self.data_governance_engine = DataGovernanceEngine()
        self.catalyst_engine = CatalystEngine()
        self.overfitting_engine = OverfittingEngine()
        self.probability_engine = ProbabilityEngine()
        self.macro_engine = MacroEngine()
        self.backtest_engine = BacktestEngine()
        self.behavioral_engine = BehavioralEngine()
        self.learning_engine = LearningEngine()
        self.news_engine = NewsEngine()
        self.news_intelligence_engine = NewsIntelligenceEngine()

        # Advanced PhD-level engines (graceful if not installed)
        self.garch_engine = GARCHEngine() if GARCHEngine else None
        self.hmm_engine = HMMRegimeEngine() if HMMRegimeEngine else None
        self.multifactor_engine = MultiFactorEngine() if MultiFactorEngine else None
        self.vol_surface_engine = VolSurfaceEngine() if VolSurfaceEngine else None
        self.microstructure_engine = MicrostructureEngine() if MicrostructureEngine else None
        self.kalman_beta_engine = KalmanBetaEngine() if KalmanBetaEngine else None
        self.copula_risk_engine = CopulaRiskEngine() if CopulaRiskEngine else None
        self.dcc_engine = DCCEngine() if DCCEngine else None
        self.intraday_engine = IntradayEngine() if IntradayEngine else None
        self.credit_model_engine = CreditModelEngine() if CreditModelEngine else None
        self.yield_curve_engine = YieldCurveEngine() if YieldCurveEngine else None
        self.arima_engine = ARIMAForecastEngine() if ARIMAForecastEngine else None
        self.calibration_engine = CalibrationEngine() if CalibrationEngine else None

        # Bots
        self.bots = {
            "price_action": PriceActionBot(),
            "options_reaction": OptionsReactionBot(),
            "squeeze": SqueezeBot(),
            "funding_stress": FundingStressBot(),
            "macro_shock": MacroShockBot(),
            "strategy": StrategyBot(),
            "trade_decision": TradeDecisionBot(),
            "regime": RegimeBot(),
        }

    async def run_full_analysis(self) -> FullAnalysis:
        """Execute the complete analysis pipeline."""
        analysis = FullAnalysis(timestamp=dt.datetime.now(dt.timezone.utc).isoformat())
        warnings = []

        # ── 1. Fetch Data ──
        logger.info("Fetching UPST and SPY data...")
        upst_quote = await data_provider.get_quote("UPST")
        spy_quote = await data_provider.get_quote("SPY")

        end = dt.date.today()
        start = end - dt.timedelta(days=365)
        upst_bars_env = await data_provider.get_bars("UPST", "1d", start, end)
        spy_bars_env = await data_provider.get_bars("SPY", "1d", start, end)
        intraday_start = end - dt.timedelta(days=1)
        upst_1min_env = await data_provider.get_bars("UPST", "1min", intraday_start, end)

        options_env = await data_provider.get_options_chain("UPST")
        short_env = await data_provider.get_short_interest("UPST")
        loan_env = await data_provider.get_stock_loan("UPST")

        # Fetch fundamentals and news from adapters
        news_env = await data_provider.get_news("UPST", limit=50)
        financials_env = await data_provider.get_financials("UPST")
        earnings_env = await data_provider.get_earnings("UPST")

        # Fetch macro indicators (multiple series)
        macro_indicators = ["FED_FUNDS", "TREASURY_2Y", "TREASURY_10Y", "CPI_YOY",
                            "UNEMPLOYMENT", "HY_SPREAD", "IG_SPREAD", "VIX",
                            "RECESSION_PROB", "CONSUMER_DELINQUENCY", "LENDING_STANDARDS",
                            "PCE_YOY", "INITIAL_CLAIMS", "FINANCIAL_CONDITIONS"]
        macro_latest = {}
        macro_env = None
        for ind in macro_indicators:
            env = await data_provider.get_macro(ind)
            if macro_env is None:
                macro_env = env  # Use first for source tracking
            if env.data and isinstance(env.data, list) and len(env.data) > 0:
                # Get latest value from the time series
                macro_latest[ind.lower()] = env.data[0].get("value", 0)

        # Track data sources
        analysis.data_sources = {
            "quote": upst_quote.source,
            "bars": upst_bars_env.source,
            "options": options_env.source,
            "short": short_env.source,
            "news": news_env.source,
            "fundamentals": financials_env.source,
            "macro": macro_env.source if macro_env is not None else "none",
        }
        for env in [upst_quote, upst_bars_env, spy_bars_env, options_env, short_env,
                     news_env, financials_env, earnings_env]:
            warnings.extend(env.warnings)
        if macro_env is not None:
            warnings.extend(macro_env.warnings)

        # Flag if running on mock data
        mock_sources = [k for k, v in analysis.data_sources.items() if v == "mock"]
        if mock_sources:
            warnings.append(f"Running on mock data for: {', '.join(mock_sources)}. Connect API keys for real data.")

        # Parse price
        if upst_quote.data:
            analysis.price = upst_quote.data.get("price", 0) or 0

        # Build DataFrames
        upst_df = self._bars_to_df(upst_bars_env.data)
        spy_df = self._bars_to_df(spy_bars_env.data)

        # ── 2. Technical Analysis ──
        if not upst_df.empty:
            tech_snap = self._safe_engine_call(
                "technical", self.technical_engine.analyze, upst_df, "UPST")
            if tech_snap:
                analysis.technical = self._snapshot_to_dict(tech_snap)

        # ── 3. Options Analysis ──
        if options_env.data:
            opts_snap = self._safe_engine_call(
                "options", self.options_engine.analyze, options_env.data, "UPST")
            if opts_snap:
                analysis.options = self._snapshot_to_dict(opts_snap)

        # ── 4. Short Analysis ──
        short_snap = self._safe_engine_call(
            "short", self.short_engine.analyze,
            short_env.data, loan_env.data,
            analysis.technical, analysis.options, analysis.price,
        )
        if short_snap:
            analysis.short = self._snapshot_to_dict(short_snap)

        # ── 5. SPY/Beta Relationship ──
        upst_returns = None
        spy_returns = None
        if not upst_df.empty and not spy_df.empty:
            spy_rel = self._safe_engine_call(
                "spy_beta", self.spy_beta_engine.analyze, upst_df, spy_df)
            if spy_rel:
                analysis.spy_relationship = self._snapshot_to_dict(spy_rel)
            upst_returns = upst_df["close"].pct_change().dropna().values
            spy_returns = spy_df["close"].pct_change().dropna().values

        # ── 6. New Engines ──
        # Valuation (transform quarterly data into expected dict format)
        fundamentals_dict = None
        if financials_env.data and isinstance(financials_env.data, list) and len(financials_env.data) > 0:
            latest_q = financials_env.data[0]
            # Build TTM (trailing twelve months) from up to 4 quarters
            quarters = financials_env.data[:4]
            ttm_revenue = sum(q.get("revenue", 0) for q in quarters)
            ttm_ebitda = sum(q.get("adjusted_ebitda", 0) or q.get("ebitda", 0) for q in quarters)
            fundamentals_dict = {
                "revenue_ttm": ttm_revenue,
                "ebitda_ttm": ttm_ebitda,
                "net_income_ttm": sum(q.get("eps_diluted", 0) * q.get("shares_outstanding", 85e6) for q in quarters),
                "fcf_ttm": int(ttm_ebitda * 0.6),  # Estimate FCF as 60% of EBITDA
                "shares_outstanding": latest_q.get("shares_outstanding", 85_000_000),
                "book_value": int(latest_q.get("cash_and_equivalents", 800e6)),
                "net_debt": int(latest_q.get("total_debt", 1000e6) - latest_q.get("cash_and_equivalents", 800e6)),
                "revenue_growth_yoy": 0.25,  # Default; would calculate from 4Q ago
            }
            # Calculate YoY growth if we have enough data
            if len(financials_env.data) >= 5:
                prior_4q = financials_env.data[4:8]
                prior_rev = sum(q.get("revenue", 0) for q in prior_4q)
                if prior_rev > 0:
                    fundamentals_dict["revenue_growth_yoy"] = round((ttm_revenue - prior_rev) / prior_rev, 4)

        val_snap = self._safe_engine_call(
            "valuation", self.valuation_engine.analyze,
            price=analysis.price, fundamentals=fundamentals_dict)
        if val_snap:
            analysis.valuation = self._snapshot_to_dict(val_snap)

        # Funding
        fund_snap = self._safe_engine_call("funding", self.funding_engine.analyze)
        if fund_snap:
            analysis.funding = self._snapshot_to_dict(fund_snap)

        # Origination
        orig_snap = self._safe_engine_call("origination", self.origination_engine.analyze)
        if orig_snap:
            analysis.origination = self._snapshot_to_dict(orig_snap)

        # Macro (pass transformed indicator dict)
        macro_snap = self._safe_engine_call("macro", self.macro_engine.analyze, macro_latest)
        if macro_snap:
            analysis.macro = self._snapshot_to_dict(macro_snap)

        # Factor
        factor_snap = self._safe_engine_call(
            "factor", self.factor_engine.analyze, upst_returns, spy_returns)
        if factor_snap:
            analysis.factor = self._snapshot_to_dict(factor_snap)

        # Stress
        stress_snap = self._safe_engine_call("stress", self.stress_engine.analyze)
        if stress_snap:
            analysis.stress = self._snapshot_to_dict(stress_snap)

        # Reflexivity
        reflex_snap = self._safe_engine_call(
            "reflexivity", self.reflexivity_engine.analyze,
            upst_returns, analysis.short, analysis.options, analysis.price,
        )
        if reflex_snap:
            analysis.reflexivity = self._snapshot_to_dict(reflex_snap)

        # Execution
        exec_snap = self._safe_engine_call(
            "execution", self.execution_engine.analyze, price=analysis.price)
        if exec_snap:
            analysis.execution = self._snapshot_to_dict(exec_snap)

        # Data Governance
        dg_snap = self._safe_engine_call("data_governance", self.data_governance_engine.analyze)
        if dg_snap:
            analysis.data_governance = self._snapshot_to_dict(dg_snap)

        # Catalyst
        cat_snap = self._safe_engine_call("catalyst", self.catalyst_engine.analyze)
        if cat_snap:
            analysis.catalyst = self._snapshot_to_dict(cat_snap)

        # Overfitting
        of_snap = self._safe_engine_call("overfitting", self.overfitting_engine.analyze)
        if of_snap:
            analysis.overfitting = self._snapshot_to_dict(of_snap)

        # Behavioral
        behav_snap = self._safe_engine_call(
            "behavioral", self.behavioral_engine.analyze,
            technical=analysis.technical,
            options=analysis.options,
            short=analysis.short,
        )
        if behav_snap:
            analysis.behavioral = self._snapshot_to_dict(behav_snap)

        # News (transform adapter data to engine format)
        news_items = None
        if news_env.data and isinstance(news_env.data, list):
            news_items = []
            for item in news_env.data:
                news_items.append({
                    "headline": item.get("headline", ""),
                    "source": item.get("source_name", item.get("source", "unknown")),
                    "published": item.get("published_at", item.get("published", "")),
                    "sentiment": item.get("sentiment_score", item.get("sentiment", 0.0)),
                    "relevance": item.get("relevance_score", item.get("relevance", 0.5)),
                    "category": item.get("category", "general"),
                    "flags": item.get("flags", {}),
                })
        news_snap = self._safe_engine_call(
            "news", self.news_engine.analyze, news_data=news_items)
        if news_snap:
            analysis.news = self._snapshot_to_dict(news_snap)

        # News Intelligence (enhanced analysis across all sources)
        ni_snap = self._safe_engine_call(
            "news_intelligence", self.news_intelligence_engine.analyze,
            news_data=news_items,
        )
        if ni_snap:
            analysis.news_intelligence = self._snapshot_to_dict(ni_snap)

        # Learning
        learning_report = self._safe_engine_call("learning", self.learning_engine.get_report)
        if learning_report:
            analysis.learning = learning_report

        # ── 6b. Advanced PhD-Level Engines ──

        # GARCH volatility modeling
        garch_result = None
        if self.garch_engine and upst_returns is not None and len(upst_returns) > 100:
            garch_result = self._safe_engine_call(
                "garch", self.garch_engine.fit, upst_returns)
            if garch_result:
                analysis.garch = self._snapshot_to_dict(garch_result)

        # HMM regime detection
        hmm_result = None
        if self.hmm_engine and upst_returns is not None and len(upst_returns) > 60:
            hmm_result = self._safe_engine_call(
                "hmm_regime", self.hmm_engine.fit, upst_returns)
            if hmm_result:
                analysis.hmm_regime = self._snapshot_to_dict(hmm_result)

        # Multi-factor regression
        if self.multifactor_engine and upst_returns is not None and spy_returns is not None:
            factor_returns = {"market": spy_returns[:len(upst_returns)]}
            mf_result = self._safe_engine_call(
                "multifactor", self.multifactor_engine.analyze,
                upst_returns, factor_returns)
            if mf_result:
                analysis.multifactor = self._snapshot_to_dict(mf_result)

        # Vol surface (from options chain)
        if self.vol_surface_engine and options_env.data:
            contracts = options_env.data.get("contracts", [])
            spot = options_env.data.get("underlying_price") or analysis.price
            if contracts and spot > 0:
                vs_result = self._safe_engine_call(
                    "vol_surface", self.vol_surface_engine.fit, contracts, spot)
                if vs_result:
                    analysis.vol_surface = self._snapshot_to_dict(vs_result)

        # Microstructure analysis
        if self.microstructure_engine and upst_bars_env.data:
            micro_result = self._safe_engine_call(
                "microstructure", self.microstructure_engine.analyze,
                upst_bars_env.data)
            if micro_result:
                analysis.microstructure = self._snapshot_to_dict(micro_result)

        # Kalman filter time-varying beta
        if self.kalman_beta_engine and upst_returns is not None and spy_returns is not None:
            min_len = min(len(upst_returns), len(spy_returns))
            kalman_result = self._safe_engine_call(
                "kalman_beta", self.kalman_beta_engine.filter,
                upst_returns[:min_len], spy_returns[:min_len])
            if kalman_result:
                analysis.kalman_beta = self._snapshot_to_dict(kalman_result)

        # Copula tail risk
        if self.copula_risk_engine and upst_returns is not None and spy_returns is not None:
            min_len = min(len(upst_returns), len(spy_returns))
            copula_result = self._safe_engine_call(
                "copula_risk", self.copula_risk_engine.analyze,
                upst_returns[:min_len], spy_returns[:min_len])
            if copula_result:
                analysis.copula_risk = self._snapshot_to_dict(copula_result)

        # DCC (Dynamic Conditional Correlation)
        if self.dcc_engine and upst_returns is not None and spy_returns is not None:
            min_len = min(len(upst_returns), len(spy_returns))
            dcc_result = self._safe_engine_call(
                "dcc", self.dcc_engine.estimate,
                upst_returns[:min_len], spy_returns[:min_len])
            if dcc_result:
                analysis.dcc = self._snapshot_to_dict(dcc_result)

        # Intraday analysis (VWAP, ORB, regime, volume profile, momentum, gap, auction)
        if self.intraday_engine and upst_1min_env.data:
            minute_bars = upst_1min_env.data if isinstance(upst_1min_env.data, list) else []
            if minute_bars:
                daily_atr = None
                intraday_prev_close = None
                if not upst_df.empty and len(upst_df) >= 2:
                    tr = np.maximum(
                        upst_df["high"].values - upst_df["low"].values,
                        np.maximum(
                            np.abs(upst_df["high"].values[1:] - upst_df["close"].values[:-1]),
                            np.abs(upst_df["low"].values[1:] - upst_df["close"].values[:-1]),
                        ).tolist() + [0.0],  # pad last bar
                    )
                    daily_atr = float(np.mean(tr[-14:]))
                    intraday_prev_close = float(upst_df["close"].iloc[-1])
                intraday_result = self._safe_engine_call(
                    "intraday", self.intraday_engine.analyze,
                    minute_bars, daily_atr=daily_atr, prev_close=intraday_prev_close)
                if intraday_result:
                    analysis.intraday = self._snapshot_to_dict(intraday_result)

        # Credit model (Merton structural)
        if self.credit_model_engine and analysis.price > 0:
            market_cap = analysis.price * 85e6  # Approx shares outstanding
            equity_vol = float(np.std(upst_returns) * np.sqrt(252)) if upst_returns is not None and len(upst_returns) > 30 else 0.65
            total_debt = analysis.stress.get("total_debt", 1000e6) if analysis.stress else 1000e6
            cash = analysis.stress.get("cash", 500e6) if analysis.stress else 500e6
            rf = (analysis.macro.get("fed_funds", 5.0) or 5.0) / 100
            credit_result = self._safe_engine_call(
                "credit_model", self.credit_model_engine.analyze,
                market_cap, equity_vol, total_debt, cash, rf)
            if credit_result:
                analysis.credit_model = self._snapshot_to_dict(credit_result)

        # Yield curve (Nelson-Siegel)
        if self.yield_curve_engine and analysis.macro:
            treasury_rates = {}
            macro = analysis.macro
            if macro.get("treasury_2y"):
                treasury_rates["2y"] = macro["treasury_2y"]
            if macro.get("treasury_10y"):
                treasury_rates["10y"] = macro["treasury_10y"]
            if macro.get("fed_funds"):
                treasury_rates["3m"] = macro["fed_funds"]
            if treasury_rates:
                yc_result = self._safe_engine_call(
                    "yield_curve", self.yield_curve_engine.analyze,
                    treasury_rates, upst_returns)
                if yc_result:
                    analysis.yield_curve = self._snapshot_to_dict(yc_result)

        # ARIMA-GARCH return forecasting
        if self.arima_engine and upst_returns is not None and len(upst_returns) >= 40:
            arima_result = self._safe_engine_call(
                "arima_forecast", self.arima_engine.forecast,
                upst_returns, horizon=21, price=analysis.price)
            if arima_result:
                analysis.arima_forecast = self._snapshot_to_dict(arima_result)

        # ── 7. Scores (now with all engine data) ──
        scores = self._safe_engine_call(
            "scoring", self.scoring_engine.compute_all,
            technical=analysis.technical,
            options=analysis.options,
            short=analysis.short,
            funding=analysis.funding,
            origination=analysis.origination,
            macro=analysis.macro,
            valuation=analysis.valuation,
            news=analysis.news,
            spy_rel=analysis.spy_relationship,
            forecast=analysis.forecast,
        )
        if scores:
            analysis.scores = {k: {"value": v.value, "components": v.components, "explanation": v.explanation}
                               for k, v in scores.items()}

        # ── 8. Trade Decision (with behavioral context) ──
        decision = self._safe_engine_call(
            "trade_decision", self.trade_decision_engine.decide,
            scores or {}, analysis.technical, analysis.options,
            analysis.short, analysis.spy_relationship,
            macro=analysis.macro,
            price=analysis.price,
            behavioral=analysis.behavioral,
            hmm_regime=analysis.hmm_regime if analysis.hmm_regime else None,
            garch=analysis.garch if analysis.garch else None,
        )
        if decision:
            analysis.trade_decision = self._snapshot_to_dict(decision)

        # ── 9. Forecast ──
        if not upst_df.empty:
            beta = analysis.spy_relationship.get("beta", 1.5) or 1.5
            ensemble = self._safe_engine_call(
                "forecast", self.forecast_engine.forecast,
                upst_df, "UPST", spy_beta=beta)
            if ensemble:
                analysis.forecast = {
                    "ensemble_point": ensemble.ensemble_point,
                    "ensemble_lower": ensemble.ensemble_lower,
                    "ensemble_upper": ensemble.ensemble_upper,
                    "model_agreement": ensemble.model_agreement,
                    "confidence_score": ensemble.confidence_score,
                    "models": [
                        {"name": f.model_name, "point": f.point_estimate,
                         "lower": f.lower_bound, "upper": f.upper_bound}
                        for f in ensemble.individual_forecasts
                    ],
                }

        # ── 10. Risk ──
        if not upst_df.empty:
            returns = upst_df["close"].pct_change().dropna().values
            risk = self._safe_engine_call(
                "risk", self.risk_engine.compute_risk, returns, analysis.price)
            if risk:
                analysis.risk = self._snapshot_to_dict(risk)

        # ── 11. Probability ──
        if upst_returns is not None:
            target = analysis.trade_decision.get("target_price")
            stop = analysis.trade_decision.get("stop_price")
            prob_snap = self._safe_engine_call(
                "probability", self.probability_engine.analyze,
                upst_returns, analysis.price, target, stop,
                short_data=analysis.short,
                garch_result=garch_result,
                hmm_result=hmm_result,
            )
            if prob_snap:
                analysis.probability = self._snapshot_to_dict(prob_snap)

        analysis.warnings = warnings

        # Persist to database (non-blocking)
        try:
            from backend.services.database import save_analysis
            await save_analysis(analysis.to_dict())
        except Exception as e:
            logger.debug("Analysis persistence skipped: %s", e)

        return analysis

    async def run_bot(self, bot_name: str, params: dict) -> dict:
        """Run a specific simulation bot."""
        bot = self.bots.get(bot_name)
        if not bot:
            return {"error": f"Unknown bot: {bot_name}"}

        upst_quote = await data_provider.get_quote("UPST")
        price = upst_quote.data.get("price", 70.0) if upst_quote.data else 70.0

        input = BotInput(
            ticker="UPST",
            current_price=price,
            scenario_params=params,
        )
        output = await bot.run(input)
        return self._snapshot_to_dict(output)

    async def run_scenario(self, params: dict) -> dict:
        """Run interactive scenario lab."""
        inputs = ScenarioInputs(**{k: v for k, v in params.items() if k in ScenarioInputs.__dataclass_fields__})

        upst_quote = await data_provider.get_quote("UPST")
        price = upst_quote.data.get("price", 70.0) if upst_quote.data else 70.0

        # Get current scores for baseline
        analysis = await self.run_full_analysis()
        base_scores = {}
        for k, v in analysis.scores.items():
            base_scores[k] = type("Score", (), {"value": v.get("value", 50)})()

        beta = analysis.spy_relationship.get("beta", 1.5) or 1.5
        base_iv = analysis.options.get("atm_iv", 0.70) or 0.70

        result = self.scenario_engine.run_scenario(inputs, price, base_scores, beta, base_iv)
        return self._snapshot_to_dict(result)

    async def run_backtest(self, params: dict) -> dict:
        """Run a backtest with given parameters."""
        end = dt.date.today()
        start = end - dt.timedelta(days=params.get("days", 365))
        upst_bars = await data_provider.get_bars("UPST", "1d", start, end)
        spy_bars = await data_provider.get_bars("SPY", "1d", start, end)

        upst_df = self._bars_to_df(upst_bars.data)
        spy_df = self._bars_to_df(spy_bars.data)

        if upst_df.empty:
            return {"error": "No price data available for backtest"}

        # Generate simple signals from technical analysis
        signals = self._generate_backtest_signals(upst_df, params)

        result = self.backtest_engine.run(
            upst_df, signals,
            strategy_name=params.get("strategy", "technical_signals"),
            position_size_pct=params.get("position_size_pct", 10),
            stop_loss_pct=params.get("stop_loss_pct", 5),
            take_profit_pct=params.get("take_profit_pct", 10),
            spy_df=spy_df if not spy_df.empty else None,
        )
        return self._snapshot_to_dict(result)

    def _generate_backtest_signals(self, df: pd.DataFrame, params: dict) -> list[dict]:
        """Generate trading signals for backtesting."""
        signals = []
        close = df["close"].astype(float)

        # Simple RSI-based signals
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        for i in range(14, len(close)):
            rsi_val = rsi.iloc[i]
            if pd.notna(rsi_val):
                date_str = str(df.index[i].date()) if hasattr(df.index[i], 'date') else str(df.index[i])
                if rsi_val < 30:
                    signals.append({"date": date_str, "direction": "long", "strength": 0.8})
                elif rsi_val > 70:
                    signals.append({"date": date_str, "direction": "short", "strength": 0.8})

        return signals

    def _bars_to_df(self, bars: list | None) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(bars)
        if "bar_time" in df.columns:
            df["bar_time"] = pd.to_datetime(df["bar_time"], utc=True)
            df = df.set_index("bar_time").sort_index()
        return df

    def _safe_engine_call(self, engine_name: str, func, *args, **kwargs):
        """Call an engine method with error isolation — returns None on failure."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error("Engine '%s' failed: %s", engine_name, e, exc_info=True)
            return None

    def _snapshot_to_dict(self, obj: Any) -> dict:
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            result = {}
            for k, v in asdict(obj).items():
                if isinstance(v, type(None)):
                    result[k] = None
                elif hasattr(v, 'tolist'):
                    # Convert numpy types to Python natives
                    arr = v.tolist()
                    if isinstance(arr, list):
                        # Preserve small arrays; truncate large ones
                        if len(arr) <= 500:
                            result[k] = arr
                        else:
                            result[k] = arr[:500]
                    else:
                        # Scalar numpy values (np.float64, np.int64, etc.)
                        result[k] = arr
                else:
                    result[k] = v
            return result
        return vars(obj) if hasattr(obj, "__dict__") else {}

    def run_calibration(
        self,
        returns: "np.ndarray",
        scores_history: list[dict],
        signals_history: list[dict],
    ) -> dict:
        """Run model calibration against historical score and signal data.

        This is a batch method intended to be called with accumulated
        historical analysis results, not during a live run_full_analysis pass.

        Parameters
        ----------
        returns : np.ndarray
            Daily return series aligned with scores_history / signals_history.
        scores_history : list[dict]
            One dict per day with values for each of the 15 score dimensions.
        signals_history : list[dict]
            One dict per day with keys: prob_up, regime, direction,
            forecast_models (dict[str, float]).
        """
        if not self.calibration_engine:
            return {"error": "CalibrationEngine not available"}
        result = self._safe_engine_call(
            "calibration", self.calibration_engine.calibrate,
            returns, scores_history, signals_history,
        )
        return self._snapshot_to_dict(result) if result else {}


# Singleton
orchestrator = Orchestrator()
