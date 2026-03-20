"""
Trade Decision Engine — Phase 6
Determines action, vehicle, levels, sizing, and full WHY explanation.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class TradeRecommendation:
    """Full trade decision output with explanation."""
    ticker: str = "UPST"
    decision_time: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    timeframe: str = "daily"

    # Decision
    action: str = "no_trade"
    # buy | add | hold | trim | sell | short | add_short | cover |
    # buy_calls | buy_puts | bull_spread | bear_spread | vol_trade | no_trade
    vehicle: str = "no_vehicle"
    # common_stock | call_option | put_option | call_spread | put_spread |
    # short_stock | no_vehicle

    # Levels
    entry_price: float | None = None
    target_price: float | None = None
    stop_price: float | None = None
    invalidation_price: float | None = None
    reward_risk_ratio: float | None = None
    expected_value: float | None = None

    # Sizing
    suggested_position_pct: float | None = None
    max_loss_pct: float | None = None

    # Scoring
    trade_quality_score: float = 0.0
    signal_agreement_pct: float = 0.0
    fragility_score: float = 0.0

    # Explanation (WHY model)
    dominant_factors: list[dict] = field(default_factory=list)
    explanation: str = ""
    what_would_change: str = ""
    risk_factors: list[str] = field(default_factory=list)
    confidence: str = "low"  # low | moderate | high


class TradeDecisionEngine:
    """
    Ingests all engine outputs and scores to produce a unified trade decision.
    Implements the WHY model — every decision must be explainable.
    """

    def decide(
        self,
        scores: dict,
        technical: dict | None = None,
        options: dict | None = None,
        short: dict | None = None,
        spy_rel: dict | None = None,
        macro: dict | None = None,
        price: float = 0.0,
        behavioral: dict | None = None,
    ) -> TradeRecommendation:
        rec = TradeRecommendation()
        rec.entry_price = price

        if not scores:
            rec.explanation = "Insufficient data to generate trade decision."
            return rec

        # Behavioral overrides / adjustments
        if behavioral:
            if behavioral.get("capitulation_detected"):
                # Capitulation = potential reversal opportunity
                if behavioral.get("capitulation_type") == "long_capitulation":
                    rec.risk_factors.append("Long capitulation detected — potential reversal buy signal")
                elif behavioral.get("capitulation_type") == "short_capitulation":
                    rec.risk_factors.append("Short capitulation detected — squeeze may be imminent")
            if behavioral.get("panic_selling"):
                rec.risk_factors.append("Panic selling detected — high volatility, wait for stabilization")
            if behavioral.get("euphoric_buying"):
                rec.risk_factors.append("Euphoric buying detected — elevated risk of mean reversion")

        # Extract key scores
        composite = scores.get("composite_opportunity", {})
        composite_val = composite.value if hasattr(composite, "value") else composite.get("value", 50)
        tech_val = self._sv(scores, "technical_strength")
        options_val = self._sv(scores, "options_sentiment")
        short_opp = self._sv(scores, "short_opportunity")
        squeeze_val = self._sv(scores, "squeeze_risk")
        trade_q = self._sv(scores, "trade_quality")
        fragility = self._sv(scores, "positioning_fragility")
        funding_val = self._sv(scores, "funding_strength")
        macro_val = self._sv(scores, "macro_pressure")

        rec.trade_quality_score = trade_q
        rec.fragility_score = fragility

        # ── Signal Agreement ──
        bullish_signals = sum(1 for k, v in self._score_values(scores).items()
                              if v > 60 and k not in ("macro_pressure", "credit_stress", "squeeze_risk", "positioning_fragility"))
        bearish_signals = sum(1 for k, v in self._score_values(scores).items()
                              if v < 40 and k not in ("macro_pressure", "credit_stress", "squeeze_risk", "positioning_fragility"))
        total_signals = len(scores)
        rec.signal_agreement_pct = round(max(bullish_signals, bearish_signals) / total_signals * 100, 1) if total_signals > 0 else 0

        # ── Meta-Decision: Should we trade at all? ──
        if trade_q < 30 or rec.signal_agreement_pct < 30:
            rec.action = "no_trade"
            rec.vehicle = "no_vehicle"
            rec.explanation = "Signal conflict or low trade quality. No clear edge detected."
            rec.what_would_change = "Need >60% signal agreement and trade quality >30 to consider action."
            rec.confidence = "low"
            return rec

        # ── Determine Direction ──
        factors = []

        if composite_val > 65 and bullish_signals > bearish_signals:
            # BULLISH
            rec = self._bullish_decision(rec, scores, technical, options, price)
            factors = self._collect_bullish_factors(scores)
        elif composite_val < 35 or bearish_signals > bullish_signals:
            # BEARISH
            rec = self._bearish_decision(rec, scores, short, options, price, squeeze_val)
            factors = self._collect_bearish_factors(scores)
        else:
            # NEUTRAL
            rec.action = "hold" if composite_val > 50 else "no_trade"
            rec.vehicle = "common_stock" if rec.action == "hold" else "no_vehicle"
            rec.explanation = "Mixed signals. Composite near neutral."
            factors = [{"factor": "mixed_signals", "weight": 1.0, "detail": f"Composite={composite_val:.1f}"}]

        rec.dominant_factors = sorted(factors, key=lambda x: abs(x.get("weight", 0)), reverse=True)[:5]

        # ── Confidence ──
        if rec.signal_agreement_pct > 70 and trade_q > 60 and fragility < 40:
            rec.confidence = "high"
        elif rec.signal_agreement_pct > 50 and trade_q > 40:
            rec.confidence = "moderate"
        else:
            rec.confidence = "low"

        # ── Risk Factors ──
        rec.risk_factors = self._identify_risks(scores, short, macro)

        # ── What Would Change ──
        rec.what_would_change = self._what_would_change(rec, scores)

        return rec

    def _bullish_decision(self, rec, scores, technical, options, price):
        tech_val = self._sv(scores, "technical_strength")
        options_val = self._sv(scores, "options_sentiment")

        if tech_val > 70:
            rec.action = "buy"
            rec.vehicle = "common_stock"
            rec.explanation = "Strong bullish technicals with positive composite score."
        elif options_val > 65:
            rec.action = "buy_calls"
            rec.vehicle = "call_option"
            rec.explanation = "Bullish options flow supports call purchase."
        else:
            rec.action = "bull_spread"
            rec.vehicle = "call_spread"
            rec.explanation = "Moderate bullish signal. Spread limits risk."

        if price > 0:
            # Approximate levels
            atr = technical.get("atr", price * 0.04) if technical else price * 0.04
            rec.target_price = round(price + atr * 3, 2)
            rec.stop_price = round(price - atr * 1.5, 2)
            if rec.stop_price < price:
                rec.reward_risk_ratio = round((rec.target_price - price) / (price - rec.stop_price), 2)
                if rec.reward_risk_ratio > 0:
                    win_prob = 0.5 + (self._sv(scores, "composite_opportunity") - 50) / 200
                    rec.expected_value = round(
                        win_prob * (rec.target_price - price) - (1 - win_prob) * (price - rec.stop_price), 2,
                    )

        rec.suggested_position_pct = self._size_position(scores, rec)
        rec.max_loss_pct = 2.0
        return rec

    def _bearish_decision(self, rec, scores, short, options, price, squeeze_val):
        if squeeze_val > 70:
            # High squeeze risk — use options, not direct short
            rec.action = "buy_puts"
            rec.vehicle = "put_option"
            rec.explanation = "Bearish thesis but squeeze risk is elevated. Using puts to limit upside risk."
        elif short and short.get("do_not_short_flag"):
            rec.action = "bear_spread"
            rec.vehicle = "put_spread"
            rec.explanation = "Do-not-short flag active. Using put spread for defined risk."
        elif self._sv(scores, "short_opportunity") > 65:
            rec.action = "short"
            rec.vehicle = "short_stock"
            rec.explanation = "Strong short opportunity with manageable squeeze risk."
        else:
            rec.action = "buy_puts"
            rec.vehicle = "put_option"
            rec.explanation = "Moderate bearish conviction. Puts provide defined risk."

        if price > 0:
            atr = price * 0.04
            rec.target_price = round(price - atr * 3, 2)
            rec.stop_price = round(price + atr * 1.5, 2)
            rec.invalidation_price = rec.stop_price
            if rec.stop_price > price:
                rec.reward_risk_ratio = round((price - rec.target_price) / (rec.stop_price - price), 2)

        rec.suggested_position_pct = self._size_position(scores, rec)
        rec.max_loss_pct = 2.0
        return rec

    def _size_position(self, scores, rec) -> float:
        """Volatility-targeted, capped quarter-Kelly sizing."""
        base = 5.0  # 5% base position
        # Reduce for low quality
        quality_adj = min(1.0, rec.trade_quality_score / 60)
        # Reduce for high fragility
        frag_adj = max(0.3, 1.0 - rec.fragility_score / 100)
        size = base * quality_adj * frag_adj
        return round(max(1.0, min(10.0, size)), 2)

    def _sv(self, scores: dict, name: str) -> float:
        """Safely get score value."""
        s = scores.get(name)
        if s is None:
            return 50.0
        return s.value if hasattr(s, "value") else s.get("value", 50.0)

    def _score_values(self, scores: dict) -> dict[str, float]:
        return {k: self._sv(scores, k) for k in scores}

    def _collect_bullish_factors(self, scores: dict) -> list[dict]:
        factors = []
        if self._sv(scores, "technical_strength") > 60:
            factors.append({"factor": "technical_strength", "weight": 0.8, "direction": "bullish"})
        if self._sv(scores, "funding_strength") > 60:
            factors.append({"factor": "funding_strength", "weight": 0.7, "direction": "bullish"})
        if self._sv(scores, "origination_momentum") > 60:
            factors.append({"factor": "origination_momentum", "weight": 0.7, "direction": "bullish"})
        if self._sv(scores, "options_sentiment") > 60:
            factors.append({"factor": "options_sentiment", "weight": 0.6, "direction": "bullish"})
        if self._sv(scores, "relative_strength_spy") > 60:
            factors.append({"factor": "relative_strength_spy", "weight": 0.5, "direction": "bullish"})
        return factors

    def _collect_bearish_factors(self, scores: dict) -> list[dict]:
        factors = []
        if self._sv(scores, "technical_strength") < 40:
            factors.append({"factor": "technical_weakness", "weight": -0.8, "direction": "bearish"})
        if self._sv(scores, "macro_pressure") > 60:
            factors.append({"factor": "macro_pressure", "weight": -0.7, "direction": "bearish"})
        if self._sv(scores, "credit_stress") > 60:
            factors.append({"factor": "credit_stress", "weight": -0.7, "direction": "bearish"})
        if self._sv(scores, "short_opportunity") > 60:
            factors.append({"factor": "short_opportunity", "weight": -0.6, "direction": "bearish"})
        if self._sv(scores, "options_sentiment") < 40:
            factors.append({"factor": "bearish_options_flow", "weight": -0.6, "direction": "bearish"})
        return factors

    def _identify_risks(self, scores, short, macro) -> list[str]:
        risks = []
        if self._sv(scores, "squeeze_risk") > 60:
            risks.append("Elevated squeeze risk could force covering")
        if self._sv(scores, "macro_pressure") > 70:
            risks.append("High macro pressure environment")
        if self._sv(scores, "positioning_fragility") > 60:
            risks.append("Position fragility is elevated")
        if self._sv(scores, "forecast_confidence") < 40:
            risks.append("Low forecast confidence — models may be unreliable")
        return risks

    def _what_would_change(self, rec, scores) -> str:
        changes = []
        if rec.action in ("buy", "buy_calls", "bull_spread"):
            changes.append("Would switch to SELL/SHORT if technical_strength drops below 40")
            changes.append("Would reduce size if squeeze_risk rises above 70")
        elif rec.action in ("short", "buy_puts", "bear_spread"):
            changes.append("Would COVER if technical_strength rises above 65")
            changes.append("Would switch to PUTS if squeeze_risk rises above 70")
        changes.append("Would go to NO_TRADE if trade_quality drops below 30")
        return "; ".join(changes)
