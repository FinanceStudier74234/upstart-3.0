"""
Central Orchestrator — coordinates all engines, adapters, and bots
into a unified analysis pipeline.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

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
        if not upst_df.empty and not spy_df.empty:
            spy_rel = self.spy_beta_engine.analyze(upst_df, spy_df)
            analysis.spy_relationship = self._snapshot_to_dict(spy_rel)

        # ── 6. Scores ──
        scores = self.scoring_engine.compute_all(
            technical=analysis.technical,
            options=analysis.options,
            short=analysis.short,
            spy_rel=analysis.spy_relationship,
        )
        analysis.scores = {k: {"value": v.value, "components": v.components, "explanation": v.explanation}
                           for k, v in scores.items()}

        # ── 7. Trade Decision ──
        decision = self.trade_decision_engine.decide(
            scores, analysis.technical, analysis.options,
            analysis.short, analysis.spy_relationship,
            price=analysis.price,
        )
        analysis.trade_decision = self._snapshot_to_dict(decision)

        # ── 8. Forecast ──
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

        # ── 9. Risk ──
        if not upst_df.empty:
            import numpy as np
            returns = upst_df["close"].pct_change().dropna().values
            risk = self.risk_engine.compute_risk(returns, analysis.price)
            analysis.risk = self._snapshot_to_dict(risk)

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
