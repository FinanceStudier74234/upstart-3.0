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

        options_env = await data_provider.get_options_chain("UPST")
        short_env = await data_provider.get_short_interest("UPST")
        loan_env = await data_provider.get_stock_loan("UPST")

        # Track data sources
        analysis.data_sources = {
            "quote": upst_quote.source,
            "bars": upst_bars_env.source,
            "options": options_env.source,
            "short": short_env.source,
        }
        for env in [upst_quote, upst_bars_env, options_env, short_env]:
            warnings.extend(env.warnings)

        # Parse price
        if upst_quote.data:
            analysis.price = upst_quote.data.get("price", 0) or 0

        # Build DataFrames
        upst_df = self._bars_to_df(upst_bars_env.data)
        spy_df = self._bars_to_df(spy_bars_env.data)

        # ── 2. Technical Analysis ──
        if not upst_df.empty:
            tech_snap = self.technical_engine.analyze(upst_df, "UPST")
            analysis.technical = self._snapshot_to_dict(tech_snap)

        # ── 3. Options Analysis ──
        if options_env.data:
            opts_snap = self.options_engine.analyze(options_env.data, "UPST")
            analysis.options = self._snapshot_to_dict(opts_snap)

        # ── 4. Short Analysis ──
        short_snap = self.short_engine.analyze(
            short_env.data, loan_env.data,
            analysis.technical, analysis.options, analysis.price,
        )
        analysis.short = self._snapshot_to_dict(short_snap)

        # ── 5. SPY/Beta Relationship ──
        upst_returns = None
        spy_returns = None
        if not upst_df.empty and not spy_df.empty:
            spy_rel = self.spy_beta_engine.analyze(upst_df, spy_df)
            analysis.spy_relationship = self._snapshot_to_dict(spy_rel)
            upst_returns = upst_df["close"].pct_change().dropna().values
            spy_returns = spy_df["close"].pct_change().dropna().values

        # ── 6. New Engines ──
        # Valuation
        val_snap = self.valuation_engine.analyze(price=analysis.price)
        analysis.valuation = self._snapshot_to_dict(val_snap)

        # Funding
        fund_snap = self.funding_engine.analyze()
        analysis.funding = self._snapshot_to_dict(fund_snap)

        # Origination
        orig_snap = self.origination_engine.analyze()
        analysis.origination = self._snapshot_to_dict(orig_snap)

        # Macro
        macro_snap = self.macro_engine.analyze({})
        analysis.macro = self._snapshot_to_dict(macro_snap)

        # Factor
        factor_snap = self.factor_engine.analyze(upst_returns, spy_returns)
        analysis.factor = self._snapshot_to_dict(factor_snap)

        # Stress
        stress_snap = self.stress_engine.analyze()
        analysis.stress = self._snapshot_to_dict(stress_snap)

        # Reflexivity
        reflex_snap = self.reflexivity_engine.analyze(
            upst_returns, analysis.short, analysis.options, analysis.price)
        analysis.reflexivity = self._snapshot_to_dict(reflex_snap)

        # Execution
        exec_snap = self.execution_engine.analyze(price=analysis.price)
        analysis.execution = self._snapshot_to_dict(exec_snap)

        # Data Governance
        dg_snap = self.data_governance_engine.analyze()
        analysis.data_governance = self._snapshot_to_dict(dg_snap)

        # Catalyst
        cat_snap = self.catalyst_engine.analyze()
        analysis.catalyst = self._snapshot_to_dict(cat_snap)

        # Overfitting
        of_snap = self.overfitting_engine.analyze()
        analysis.overfitting = self._snapshot_to_dict(of_snap)

        # Behavioral
        behav_snap = self.behavioral_engine.analyze(
            technical=analysis.technical,
            options=analysis.options,
            short=analysis.short,
        )
        analysis.behavioral = self._snapshot_to_dict(behav_snap)

        # News
        news_snap = self.news_engine.analyze()
        analysis.news = self._snapshot_to_dict(news_snap)

        # Learning
        analysis.learning = self.learning_engine.get_report()

        # ── 7. Scores (now with all engine data) ──
        scores = self.scoring_engine.compute_all(
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
        analysis.scores = {k: {"value": v.value, "components": v.components, "explanation": v.explanation}
                           for k, v in scores.items()}

        # ── 8. Trade Decision (with behavioral context) ──
        decision = self.trade_decision_engine.decide(
            scores, analysis.technical, analysis.options,
            analysis.short, analysis.spy_relationship,
            macro=analysis.macro,
            price=analysis.price,
            behavioral=analysis.behavioral,
        )
        analysis.trade_decision = self._snapshot_to_dict(decision)

        # ── 9. Forecast ──
        if not upst_df.empty:
            beta = analysis.spy_relationship.get("beta", 1.5) or 1.5
            ensemble = self.forecast_engine.forecast(upst_df, "UPST", spy_beta=beta)
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
            risk = self.risk_engine.compute_risk(returns, analysis.price)
            analysis.risk = self._snapshot_to_dict(risk)

        # ── 11. Probability ──
        if upst_returns is not None:
            target = analysis.trade_decision.get("target_price")
            stop = analysis.trade_decision.get("stop_price")
            prob_snap = self.probability_engine.analyze(
                upst_returns, analysis.price, target, stop,
                short_data=analysis.short,
            )
            analysis.probability = self._snapshot_to_dict(prob_snap)

        analysis.warnings = warnings
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
        inputs = ScenarioInputs(**{k: v for k, v in params.items() if hasattr(ScenarioInputs, k)})

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

    def _snapshot_to_dict(self, obj: Any) -> dict:
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            result = {}
            for k, v in asdict(obj).items():
                if isinstance(v, type(None)):
                    result[k] = None
                elif hasattr(v, 'tolist'):  # numpy arrays
                    continue  # Skip large arrays in API response
                else:
                    result[k] = v
            return result
        return vars(obj) if hasattr(obj, "__dict__") else {}


# Singleton
orchestrator = Orchestrator()
