"""
Interactive Scenario Lab Engine — Phase 5
Recalculates all outputs based on user-controlled scenario levers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ScenarioInputs:
    """All interactive levers the user can adjust."""
    # Market / SPY
    spy_return_pct: float = 0.0
    spy_drawdown_pct: float = 0.0
    beta_override: float | None = None
    correlation_override: float | None = None

    # Rates / Macro
    fed_funds_change_bps: float = 0.0
    treasury_2y_change_bps: float = 0.0
    treasury_10y_change_bps: float = 0.0
    inflation_change_pct: float = 0.0
    unemployment_change_pct: float = 0.0
    recession_prob_change_pct: float = 0.0

    # UPST-specific
    origination_growth_change_pct: float = 0.0
    funding_capacity_change_pct: float = 0.0
    funding_expiry_months_change: float = 0.0
    ebitda_margin_change_pct: float = 0.0
    valuation_multiple_change_pct: float = 0.0

    # Volatility / Options / Short
    iv_change_pct: float = 0.0
    short_interest_change_pct: float = 0.0
    squeeze_risk_change_pct: float = 0.0

    # External
    peer_valuation_change_pct: float = 0.0
    market_drawdown_pct: float = 0.0
    world_risk_shock: float = 0.0  # 0..1
    news_sentiment_shock: float = 0.0  # -1..+1
    macro_stress_shock: float = 0.0  # 0..1
    credit_deterioration_shock: float = 0.0  # 0..1
    options_flow_shock: float = 0.0  # -1..+1, negative=bearish


@dataclass
class ScenarioOutput:
    """Recalculated outputs after applying scenario levers."""
    inputs: ScenarioInputs
    adjusted_price_target: float | None = None
    adjusted_upside_pct: float | None = None
    adjusted_downside_pct: float | None = None
    probability_up: float | None = None
    probability_down: float | None = None

    adjusted_scores: dict = field(default_factory=dict)
    adjusted_trade_recommendation: str = ""
    adjusted_vehicle: str = ""
    adjusted_position_size_pct: float | None = None

    spy_adjusted_expected_move: float | None = None
    adjusted_valuation: dict = field(default_factory=dict)
    adjusted_risk_metrics: dict = field(default_factory=dict)

    confidence: float = 0.0
    fragility: float = 0.0
    explanation: str = ""


class ScenarioEngine:
    """Applies scenario inputs to recalculate all platform outputs."""

    def run_scenario(
        self,
        inputs: ScenarioInputs,
        base_price: float,
        base_scores: dict,
        beta: float = 1.5,
        base_iv: float = 0.70,
    ) -> ScenarioOutput:
        out = ScenarioOutput(inputs=inputs)

        # ── Price impact from SPY ──
        effective_beta = inputs.beta_override or beta
        spy_impact = effective_beta * (inputs.spy_return_pct + inputs.spy_drawdown_pct)

        # ── Rates impact ──
        # UPST is rate-sensitive: higher rates hurt origination
        rates_impact = -0.02 * (inputs.fed_funds_change_bps / 25)  # Each 25bps = -2%
        rates_impact += -0.01 * (inputs.treasury_10y_change_bps / 25)

        # ── Origination impact ──
        orig_impact = 0.015 * inputs.origination_growth_change_pct  # 1% orig growth → 1.5% price

        # ── Funding impact ──
        funding_impact = 0.01 * inputs.funding_capacity_change_pct

        # ── Valuation multiple impact ──
        val_impact = inputs.valuation_multiple_change_pct / 100

        # ── Macro stress ──
        macro_impact = -0.10 * inputs.macro_stress_shock  # Up to -10%
        credit_impact = -0.08 * inputs.credit_deterioration_shock
        world_impact = -0.05 * inputs.world_risk_shock

        # ── Total price impact ──
        total_impact = (
            spy_impact / 100 + rates_impact + orig_impact / 100 +
            funding_impact / 100 + val_impact + macro_impact +
            credit_impact + world_impact
        )

        out.adjusted_price_target = round(base_price * (1 + total_impact), 2)
        out.adjusted_upside_pct = round(max(0, total_impact * 100), 2)
        out.adjusted_downside_pct = round(abs(min(0, total_impact * 100)), 2)
        out.spy_adjusted_expected_move = round(spy_impact, 2)

        # ── Probabilities (heuristic, must stay in [0, 1] and sum <= 1) ──
        flat_prob = 0.10  # reserved for flat/unchanged outcome
        if total_impact > 0.02:
            out.probability_up = round(min(0.85, 0.5 + total_impact), 4)
            out.probability_down = round(max(0.05, 1 - out.probability_up - flat_prob), 4)
        elif total_impact < -0.02:
            out.probability_down = round(min(0.85, 0.5 - total_impact), 4)
            out.probability_up = round(max(0.05, 1 - out.probability_down - flat_prob), 4)
        else:
            out.probability_up = 0.35
            out.probability_down = 0.35

        # ── Adjust Scores ──
        out.adjusted_scores = self._adjust_scores(base_scores, inputs)

        # ── Adjusted IV ──
        adjusted_iv = base_iv * (1 + inputs.iv_change_pct / 100)

        # ── Risk Metrics ──
        out.adjusted_risk_metrics = {
            "expected_price": out.adjusted_price_target,
            "price_change_pct": round(total_impact * 100, 2),
            "vol_adjusted": round(adjusted_iv, 4),
            "var_95": round(base_price * adjusted_iv * 1.645 * math.sqrt(21/252), 2),
            "cvar_95": round(base_price * adjusted_iv * 2.063 * math.sqrt(21/252), 2),
        }

        # ── Confidence & Fragility ──
        shock_magnitude = abs(total_impact)
        out.confidence = round(max(10, 80 - shock_magnitude * 200), 2)
        out.fragility = round(min(95, 20 + shock_magnitude * 300), 2)

        # ── Trade Recommendation ──
        if total_impact > 0.05 and out.confidence > 40:
            out.adjusted_trade_recommendation = "buy"
            out.adjusted_vehicle = "common_stock"
        elif total_impact < -0.05 and out.confidence > 40:
            out.adjusted_trade_recommendation = "short" if inputs.squeeze_risk_change_pct < 20 else "buy_puts"
            out.adjusted_vehicle = "short_stock" if inputs.squeeze_risk_change_pct < 20 else "put_option"
        else:
            out.adjusted_trade_recommendation = "no_trade"
            out.adjusted_vehicle = "no_vehicle"

        out.adjusted_position_size_pct = round(max(1, 5 * out.confidence / 80), 2)

        out.explanation = (
            f"Scenario impact: {total_impact*100:+.2f}% "
            f"(SPY={spy_impact:+.2f}%, rates={rates_impact*100:+.2f}%, "
            f"orig={orig_impact:+.2f}%, funding={funding_impact:+.2f}%, "
            f"macro={macro_impact*100:+.2f}%, credit={credit_impact*100:+.2f}%)"
        )

        return out

    def _adjust_scores(self, base_scores: dict, inputs: ScenarioInputs) -> dict:
        """Apply scenario shocks to base scores."""
        adjusted = {}
        for name, score in base_scores.items():
            val = score.value if hasattr(score, "value") else score.get("value", 50)

            # Apply relevant adjustments
            if name == "macro_pressure":
                val += inputs.macro_stress_shock * 20
                val += inputs.fed_funds_change_bps / 25 * 5
            elif name == "credit_stress":
                val += inputs.credit_deterioration_shock * 25
            elif name == "funding_strength":
                val += inputs.funding_capacity_change_pct * 0.5
            elif name == "origination_momentum":
                val += inputs.origination_growth_change_pct * 0.8
            elif name == "squeeze_risk":
                val += inputs.squeeze_risk_change_pct * 0.5
            elif name == "options_sentiment":
                val += inputs.options_flow_shock * 20
            elif name == "news_regime":
                val += inputs.news_sentiment_shock * 25

            adjusted[name] = round(max(0, min(100, val)), 2)
        return adjusted
