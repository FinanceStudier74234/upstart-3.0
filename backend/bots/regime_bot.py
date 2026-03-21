"""
Bot 8: Market Regime Bot
Simulates regime transitions and their effects on model weighting and recommendations.
"""

from __future__ import annotations

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class RegimeBot(BaseBot):
    name = "market_regime"

    async def run(self, input: BotInput) -> BotOutput:
        params = input.scenario_params
        current_regime = params.get("current_regime", "normal")
        vix = params.get("vix", 18)
        spy_trend = params.get("spy_trend", "neutral")
        credit_spread = params.get("credit_spread_bps", 350)

        # Define regime characteristics
        regimes = {
            "risk_on": {
                "description": "Strong risk appetite, equity rally, tight spreads",
                "upst_bias": "bullish",
                "model_weight_shift": {"technical": 1.2, "momentum": 1.3, "mean_reversion": 0.7},
                "recommendation_shift": "Favor long equity, calls",
                "short_attractiveness": "low",
            },
            "risk_off": {
                "description": "Risk aversion, equity selloff, wide spreads",
                "upst_bias": "bearish",
                "model_weight_shift": {"technical": 0.8, "momentum": 0.7, "mean_reversion": 1.3},
                "recommendation_shift": "Favor puts/spreads, reduce long exposure",
                "short_attractiveness": "high",
            },
            "squeeze": {
                "description": "Short-squeeze dynamics dominating price action",
                "upst_bias": "volatility_up",
                "model_weight_shift": {"technical": 0.5, "momentum": 1.5, "mean_reversion": 0.3},
                "recommendation_shift": "AVOID SHORTS. Long calls or stand aside.",
                "short_attractiveness": "dangerous",
            },
            "trend": {
                "description": "Strong directional trend with low chop",
                "upst_bias": "trend_following",
                "model_weight_shift": {"technical": 1.0, "momentum": 1.4, "mean_reversion": 0.5},
                "recommendation_shift": "Follow the trend. Don't fight it.",
                "short_attractiveness": "moderate_if_downtrend",
            },
            "chop": {
                "description": "Rangebound, mean-reverting, whipsaw-prone",
                "upst_bias": "neutral",
                "model_weight_shift": {"technical": 1.1, "momentum": 0.6, "mean_reversion": 1.4},
                "recommendation_shift": "Sell premium. Mean-revert. Small positions.",
                "short_attractiveness": "moderate",
            },
            "normal": {
                "description": "No dominant regime. Mixed signals.",
                "upst_bias": "neutral",
                "model_weight_shift": {"technical": 1.0, "momentum": 1.0, "mean_reversion": 1.0},
                "recommendation_shift": "Standard analysis applies.",
                "short_attractiveness": "depends_on_setup",
            },
        }

        # Detect likely regime from inputs
        if vix > 30:
            detected = "risk_off"
        elif vix < 14 and spy_trend == "up":
            detected = "risk_on"
        elif credit_spread > 500:
            detected = "risk_off"
        elif spy_trend in ("strong_up", "strong_down"):
            detected = "trend"
        else:
            detected = current_regime

        current_info = regimes.get(detected, regimes["normal"])

        # Transition probabilities
        transitions = self._transition_matrix(detected, vix, credit_spread)

        # Effect on each component
        effects = []
        for target_regime, prob in sorted(transitions.items(), key=lambda x: -x[1]):
            target_info = regimes.get(target_regime, regimes["normal"])
            effects.append({
                "target_regime": target_regime,
                "probability": round(prob, 3),
                "description": target_info["description"],
                "upst_bias": target_info["upst_bias"],
                "model_weight_shift": target_info["model_weight_shift"],
                "recommendation_shift": target_info["recommendation_shift"],
                "short_attractiveness": target_info["short_attractiveness"],
            })

        return self._create_output(
            results={
                "detected_regime": detected,
                "current_regime_info": current_info,
                "transitions": effects,
                "most_likely_next": effects[0]["target_regime"] if effects else detected,
                "regime_stability": self._stability_score(transitions, detected),
            },
            tables=[{"name": "Regime Transitions", "data": effects}],
            assumptions={
                "vix": vix,
                "spy_trend": spy_trend,
                "credit_spread": credit_spread,
                "regime_definitions": list(regimes.keys()),
                "persistence_boost": 0.20,
            },
            limitations=[
                "Transition matrix is heuristic, not calibrated to historical regime frequencies",
                "No forward regime simulation — only 1-step transition probabilities",
                "Regime duration modeling not included (no mean time in regime)",
                "6 regimes may not capture all market states (e.g. crash, euphoria)",
                "VIX/credit thresholds are fixed, not adaptive to evolving market structure",
            ],
            confidence=0.50,
            explanation=f"Current regime: {detected}. {current_info['description']}",
        )

    def _transition_matrix(self, current, vix, credit_spread):
        """Heuristic transition probabilities from current regime."""
        base = {
            "risk_on": 0.15, "risk_off": 0.15, "squeeze": 0.05,
            "trend": 0.20, "chop": 0.20, "normal": 0.25,
        }
        # Boost current regime persistence
        base[current] = base.get(current, 0.2) + 0.20

        # Adjust for conditions
        if vix > 25:
            base["risk_off"] += 0.15
            base["risk_on"] -= 0.10
        if vix < 15:
            base["risk_on"] += 0.10
            base["risk_off"] -= 0.10
        if credit_spread > 400:
            base["risk_off"] += 0.10

        # Normalize
        total = sum(base.values())
        return {k: v / total for k, v in base.items()}

    def _stability_score(self, transitions, current):
        persistence = transitions.get(current, 0)
        if persistence > 0.4:
            return "stable"
        elif persistence > 0.25:
            return "moderate"
        return "transitional"
