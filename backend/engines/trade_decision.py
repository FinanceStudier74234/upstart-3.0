"""
Trade Decision Engine — Phase 6
Determines action, vehicle, levels, sizing, and full WHY explanation.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from backend.config.constants import (
    TD_MIN_TRADE_QUALITY, TD_MIN_SIGNAL_AGREEMENT,
    TD_COMPOSITE_BULLISH, TD_COMPOSITE_BEARISH,
    TD_TECH_BUY_THRESHOLD, TD_OPTIONS_BUY_THRESHOLD,
    TD_SQUEEZE_OPTIONS_THRESHOLD, TD_SHORT_OPP_THRESHOLD,
    TD_BASE_POSITION_PCT, TD_MIN_POSITION_PCT, TD_MAX_POSITION_PCT,
    TD_QUALITY_NORM,
    TD_REGIME_CRISIS, TD_REGIME_HIGH_VOL, TD_REGIME_BEAR, TD_REGIME_BULL,
    TD_ATR_TARGET_MULT, TD_ATR_STOP_MULT, TD_ATR_NEUTRAL_MULT,
    TD_WIN_PROB_MIN, TD_WIN_PROB_MAX,
    TD_COMPOSITE_PROB_SCALING, TD_AGREEMENT_BONUS_SCALING,
    TD_QUALITY_BONUS_SCALING, TD_FRAGILITY_PENALTY_SCALING,
    TD_HIGH_AGREEMENT, TD_HIGH_QUALITY, TD_LOW_FRAGILITY,
    TD_FALLBACK_STOP_PCT,
    TRADE_QUALITY_BULLISH_THRESHOLD, TRADE_QUALITY_BEARISH_THRESHOLD,
)


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
        hmm_regime: dict | None = None,
        garch: dict | None = None,
    ) -> TradeRecommendation:
        rec = TradeRecommendation()
        rec.entry_price = price

        if not scores:
            rec.explanation = "Insufficient data to generate trade decision."
            return rec

        # ── HMM Regime Context ──
        regime_context = ""
        if hmm_regime:
            current_regime = hmm_regime.get("current_regime")
            regime_names = ["bull", "neutral", "bear"]
            if isinstance(current_regime, int) and current_regime < len(regime_names):
                regime_context = regime_names[current_regime]
            elif isinstance(current_regime, str) and current_regime in regime_names:
                regime_context = current_regime
                if hmm_regime.get("regime_change_detected"):
                    rec.risk_factors.append(f"HMM regime change detected — transitioning {regime_context}")

        # ── GARCH Vol Context ──
        vol_regime = ""
        if garch:
            vol_regime = garch.get("vol_regime", "")
            if vol_regime == "crisis_vol":
                rec.risk_factors.append("GARCH: Crisis-level volatility — reduce position sizes")
            elif vol_regime == "high_vol":
                rec.risk_factors.append("GARCH: Elevated volatility — widen stops, use options instead of stock")

        # Behavioral overrides / adjustments
        if behavioral:
            if behavioral.get("capitulation_detected"):
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
        squeeze_val = self._sv(scores, "squeeze_risk")
        trade_q = self._sv(scores, "trade_quality")
        fragility = self._sv(scores, "positioning_fragility")

        rec.trade_quality_score = trade_q
        rec.fragility_score = fragility

        # ── Signal Agreement ──
        # Count all scores for agreement, but exclude inverse-direction scores
        inverse_scores = {"macro_pressure", "credit_stress", "squeeze_risk", "positioning_fragility"}
        score_vals = self._score_values(scores)
        directional_scores = {k: v for k, v in score_vals.items() if k not in inverse_scores}
        bullish_signals = sum(1 for v in directional_scores.values() if v > TRADE_QUALITY_BULLISH_THRESHOLD)
        bearish_signals = sum(1 for v in directional_scores.values() if v < TRADE_QUALITY_BEARISH_THRESHOLD)
        # Use directional count for agreement, not total (avoids inflation)
        directional_count = len(directional_scores)
        rec.signal_agreement_pct = round(
            max(bullish_signals, bearish_signals) / directional_count * 100, 1
        ) if directional_count > 0 else 0

        # ── Meta-Decision: Should we trade at all? ──
        if trade_q < TD_MIN_TRADE_QUALITY or rec.signal_agreement_pct < TD_MIN_SIGNAL_AGREEMENT:
            rec.action = "no_trade"
            rec.vehicle = "no_vehicle"
            rec.explanation = "Signal conflict or low trade quality. No clear edge detected."
            rec.what_would_change = (
                f"Need >{TD_MIN_SIGNAL_AGREEMENT}% signal agreement and "
                f"trade quality >{TD_MIN_TRADE_QUALITY} to consider action."
            )
            rec.confidence = "low"
            return rec

        # ── Determine Direction ──
        factors = []

        # Store regime context on rec for sizing
        rec._regime_context = regime_context
        rec._vol_regime = vol_regime

        if composite_val > TD_COMPOSITE_BULLISH and bullish_signals > bearish_signals:
            rec = self._bullish_decision(rec, scores, technical, options, price)
            factors = self._collect_bullish_factors(scores)
        elif composite_val < TD_COMPOSITE_BEARISH or bearish_signals > bullish_signals:
            rec = self._bearish_decision(rec, scores, short, options, technical, price, squeeze_val)
            factors = self._collect_bearish_factors(scores)
        else:
            # NEUTRAL — still provide defensive stops
            rec.action = "hold" if composite_val > 50 else "no_trade"
            rec.vehicle = "common_stock" if rec.action == "hold" else "no_vehicle"
            rec.explanation = "Mixed signals. Composite near neutral."
            if price > 0:
                atr = technical.get("atr", price * 0.04) if technical else price * 0.04
                rec.stop_price = round(price - atr * TD_ATR_NEUTRAL_MULT, 2)
                rec.target_price = round(price + atr * TD_ATR_NEUTRAL_MULT, 2)
            factors = [{"factor": "mixed_signals", "weight": 1.0, "detail": f"Composite={composite_val:.1f}"}]

        rec.dominant_factors = sorted(factors, key=lambda x: abs(x.get("weight", 0)), reverse=True)[:5]

        # ── Confidence ──
        if rec.signal_agreement_pct > TD_HIGH_AGREEMENT and trade_q > TD_HIGH_QUALITY and fragility < TD_LOW_FRAGILITY:
            rec.confidence = "high"
        elif rec.signal_agreement_pct > 50 and trade_q > 40:
            rec.confidence = "moderate"
        else:
            rec.confidence = "low"

        # ── Risk Factors ──
        rec.risk_factors.extend(self._identify_risks(scores, short, macro))

        # ── What Would Change ──
        rec.what_would_change = self._what_would_change(rec, scores)

        return rec

    def _bullish_decision(self, rec, scores, technical, options, price):
        tech_val = self._sv(scores, "technical_strength")
        options_val = self._sv(scores, "options_sentiment")

        if tech_val > TD_TECH_BUY_THRESHOLD:
            rec.action = "buy"
            rec.vehicle = "common_stock"
            rec.explanation = "Strong bullish technicals with positive composite score."
        elif options_val > TD_OPTIONS_BUY_THRESHOLD:
            rec.action = "buy_calls"
            rec.vehicle = "call_option"
            rec.explanation = "Bullish options flow supports call purchase."
        else:
            rec.action = "bull_spread"
            rec.vehicle = "call_spread"
            rec.explanation = "Moderate bullish signal. Spread limits risk."

        if price > 0:
            atr = technical.get("atr", price * 0.04) if technical else price * 0.04
            rec.target_price = round(price + atr * TD_ATR_TARGET_MULT, 2)
            rec.stop_price = round(price - atr * TD_ATR_STOP_MULT, 2)
            if rec.stop_price < price:
                rec.reward_risk_ratio = round((rec.target_price - price) / (price - rec.stop_price), 2)
                if rec.reward_risk_ratio > 0:
                    win_prob = self._estimate_win_prob(scores, rec, bullish=True)
                    rec.expected_value = round(
                        win_prob * (rec.target_price - price) - (1 - win_prob) * (price - rec.stop_price), 2,
                    )

        rec.suggested_position_pct = self._size_position(scores, rec)
        rec.max_loss_pct = self._compute_max_loss_pct(price, rec.stop_price, rec.suggested_position_pct, long=True)
        return rec

    def _bearish_decision(self, rec, scores, short, options, technical, price, squeeze_val):
        if squeeze_val > TD_SQUEEZE_OPTIONS_THRESHOLD:
            rec.action = "buy_puts"
            rec.vehicle = "put_option"
            rec.explanation = "Bearish thesis but squeeze risk is elevated. Using puts to limit upside risk."
        elif short and short.get("do_not_short_flag"):
            rec.action = "bear_spread"
            rec.vehicle = "put_spread"
            rec.explanation = "Do-not-short flag active. Using put spread for defined risk."
        elif self._sv(scores, "short_opportunity") > TD_SHORT_OPP_THRESHOLD:
            rec.action = "short"
            rec.vehicle = "short_stock"
            rec.explanation = "Strong short opportunity with manageable squeeze risk."
        else:
            rec.action = "buy_puts"
            rec.vehicle = "put_option"
            rec.explanation = "Moderate bearish conviction. Puts provide defined risk."

        if price > 0:
            atr = technical.get("atr", price * 0.04) if technical else price * 0.04
            rec.target_price = round(price - atr * TD_ATR_TARGET_MULT, 2)
            rec.stop_price = round(price + atr * TD_ATR_STOP_MULT, 2)
            rec.invalidation_price = rec.stop_price
            if rec.stop_price > price:
                rec.reward_risk_ratio = round((price - rec.target_price) / (rec.stop_price - price), 2)
                if rec.reward_risk_ratio > 0:
                    win_prob = self._estimate_win_prob(scores, rec, bullish=False)
                    rec.expected_value = round(
                        win_prob * (price - rec.target_price) - (1 - win_prob) * (rec.stop_price - price), 2,
                    )

        rec.suggested_position_pct = self._size_position(scores, rec)
        rec.max_loss_pct = self._compute_max_loss_pct(price, rec.stop_price, rec.suggested_position_pct, long=False)
        return rec

    def _size_position(self, scores, rec) -> float:
        """Regime-aware, volatility-targeted, capped quarter-Kelly sizing."""
        base = TD_BASE_POSITION_PCT
        quality_adj = min(1.0, rec.trade_quality_score / TD_QUALITY_NORM)
        frag_adj = max(0.3, 1.0 - rec.fragility_score / 100)
        regime_adj = 1.0
        regime = getattr(rec, "_regime_context", "")
        vol_regime = getattr(rec, "_vol_regime", "")
        if vol_regime == "crisis_vol":
            regime_adj = TD_REGIME_CRISIS
        elif vol_regime == "high_vol":
            regime_adj = TD_REGIME_HIGH_VOL
        elif regime == "bear":
            regime_adj = TD_REGIME_BEAR
        elif regime == "bull":
            regime_adj = TD_REGIME_BULL
        size = base * quality_adj * frag_adj * regime_adj
        return round(max(TD_MIN_POSITION_PCT, min(TD_MAX_POSITION_PCT, size)), 2)

    def _estimate_win_prob(self, scores: dict, rec, bullish: bool) -> float:
        """Multi-factor win probability combining composite, agreement, and quality."""
        composite = self._sv(scores, "composite_opportunity")
        if bullish:
            base_prob = 0.5 + (composite - 50) / TD_COMPOSITE_PROB_SCALING
        else:
            base_prob = 0.5 + (50 - composite) / TD_COMPOSITE_PROB_SCALING
        agreement_bonus = (rec.signal_agreement_pct - 50) / TD_AGREEMENT_BONUS_SCALING if rec.signal_agreement_pct > 50 else 0
        quality_bonus = (rec.trade_quality_score - 50) / TD_QUALITY_BONUS_SCALING if rec.trade_quality_score > 50 else 0
        fragility_penalty = max(0, (rec.fragility_score - 50)) / TD_FRAGILITY_PENALTY_SCALING
        win_prob = base_prob + agreement_bonus + quality_bonus - fragility_penalty
        return max(TD_WIN_PROB_MIN, min(TD_WIN_PROB_MAX, win_prob))

    @staticmethod
    def _compute_max_loss_pct(price: float, stop_price: float | None, position_pct: float | None, long: bool) -> float:
        """Max portfolio loss = stop distance * position size."""
        if price and price > 0 and stop_price and position_pct and position_pct > 0:
            if long and stop_price < price:
                stop_dist = (price - stop_price) / price
            elif not long and stop_price > price:
                stop_dist = (stop_price - price) / price
            else:
                stop_dist = TD_FALLBACK_STOP_PCT
            return round(stop_dist * (position_pct / 100) * 100, 2)
        return round((position_pct or TD_BASE_POSITION_PCT) * TD_FALLBACK_STOP_PCT, 2)

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
        if self._sv(scores, "technical_strength") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "technical_strength", "weight": 0.8, "direction": "bullish"})
        if self._sv(scores, "funding_strength") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "funding_strength", "weight": 0.7, "direction": "bullish"})
        if self._sv(scores, "origination_momentum") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "origination_momentum", "weight": 0.7, "direction": "bullish"})
        if self._sv(scores, "options_sentiment") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "options_sentiment", "weight": 0.6, "direction": "bullish"})
        if self._sv(scores, "relative_strength_spy") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "relative_strength_spy", "weight": 0.5, "direction": "bullish"})
        return factors

    def _collect_bearish_factors(self, scores: dict) -> list[dict]:
        factors = []
        if self._sv(scores, "technical_strength") < TRADE_QUALITY_BEARISH_THRESHOLD:
            factors.append({"factor": "technical_weakness", "weight": -0.8, "direction": "bearish"})
        if self._sv(scores, "macro_pressure") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "macro_pressure", "weight": -0.7, "direction": "bearish"})
        if self._sv(scores, "credit_stress") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "credit_stress", "weight": -0.7, "direction": "bearish"})
        if self._sv(scores, "short_opportunity") > TRADE_QUALITY_BULLISH_THRESHOLD:
            factors.append({"factor": "short_opportunity", "weight": -0.6, "direction": "bearish"})
        if self._sv(scores, "options_sentiment") < TRADE_QUALITY_BEARISH_THRESHOLD:
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
            changes.append(f"Would switch to SELL/SHORT if technical_strength drops below {TRADE_QUALITY_BEARISH_THRESHOLD}")
            changes.append(f"Would reduce size if squeeze_risk rises above {TD_SQUEEZE_OPTIONS_THRESHOLD}")
        elif rec.action in ("short", "buy_puts", "bear_spread"):
            changes.append(f"Would COVER if technical_strength rises above {TD_TECH_BUY_THRESHOLD - 5}")
            changes.append(f"Would switch to PUTS if squeeze_risk rises above {TD_SQUEEZE_OPTIONS_THRESHOLD}")
        changes.append(f"Would go to NO_TRADE if trade_quality drops below {TD_MIN_TRADE_QUALITY}")
        return "; ".join(changes)
