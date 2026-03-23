"""
Bot 7: Trade Decision Bot
Virtual research/trading assistant that ranks setups and recommends actions.
"""

from __future__ import annotations

from backend.bots.base_bot import BaseBot, BotInput, BotOutput

# Map every possible action to its recommended vehicle
_VEHICLE_MAP = {
    "buy": "common_stock",
    "add": "common_stock",
    "hold": "common_stock",
    "trim": "common_stock",
    "sell": "common_stock",
    "short": "short_stock",
    "add_short": "short_stock",
    "cover": "common_stock",
    "buy_calls": "calls",
    "buy_puts": "puts",
    "bull_spread": "spreads",
    "bear_spread": "spreads",
    "vol_trade": "spreads",
    "no_trade": "none",
}


class TradeDecisionBot(BaseBot):
    name = "trade_decision"

    async def run(self, input: BotInput) -> BotOutput:
        price = max(0.01, input.current_price or 70.0)
        data = input.market_data

        scores = data.get("scores", {})
        tech = data.get("technical", {})
        options = data.get("options", {})
        short = data.get("short", {})

        # Collect all signals
        signals = []

        tech_score = self._get_val(scores, "technical_strength")
        if tech_score > 60:
            signals.append({"signal": "Technical Bullish", "direction": "bullish", "strength": (tech_score - 50) / 50})
        elif tech_score < 40:
            signals.append({"signal": "Technical Bearish", "direction": "bearish", "strength": (50 - tech_score) / 50})

        options_score = self._get_val(scores, "options_sentiment")
        if options_score > 60:
            signals.append({"signal": "Bullish Options Flow", "direction": "bullish", "strength": (options_score - 50) / 50})
        elif options_score < 40:
            signals.append({"signal": "Bearish Options Flow", "direction": "bearish", "strength": (50 - options_score) / 50})

        funding_score = self._get_val(scores, "funding_strength")
        if funding_score > 65:
            signals.append({"signal": "Strong Funding", "direction": "bullish", "strength": 0.6})
        elif funding_score < 35:
            signals.append({"signal": "Weak Funding", "direction": "bearish", "strength": 0.7})

        macro_score = self._get_val(scores, "macro_pressure")
        if macro_score > 65:
            signals.append({"signal": "Macro Headwinds", "direction": "bearish", "strength": 0.6})
        elif macro_score < 35:
            signals.append({"signal": "Macro Tailwinds", "direction": "bullish", "strength": 0.5})

        short_opp = self._get_val(scores, "short_opportunity")
        if short_opp > 65:
            signals.append({"signal": "Short Opportunity", "direction": "bearish", "strength": 0.7})

        squeeze = self._get_val(scores, "squeeze_risk")
        if squeeze > 70:
            signals.append({"signal": "Squeeze Risk", "direction": "caution", "strength": 0.9})

        # Rank signals
        signals.sort(key=lambda s: s["strength"], reverse=True)
        top_3 = signals[:3]

        # Determine overall direction
        bullish_str = sum(s["strength"] for s in signals if s["direction"] == "bullish")
        bearish_str = sum(s["strength"] for s in signals if s["direction"] == "bearish")
        caution_str = sum(s["strength"] for s in signals if s["direction"] == "caution")

        if caution_str > 0.8:
            action = "no_trade"
            explanation = "Caution signals (squeeze risk) dominate. Wait for resolution."
            quality = "poor"
        elif bullish_str > bearish_str * 1.3 and bullish_str > 1.0:
            action = "buy"
            explanation = f"Bullish conviction ({bullish_str:.1f}) outweighs bearish ({bearish_str:.1f})"
            quality = "good" if bullish_str > 2 else "moderate"
        elif bearish_str > bullish_str * 1.3 and bearish_str > 1.0:
            if squeeze > 60:
                action = "buy_puts"
                explanation = f"Bearish conviction but elevated squeeze risk. Use puts."
            else:
                action = "short"
                explanation = f"Bearish conviction ({bearish_str:.1f}) outweighs bullish ({bullish_str:.1f})"
            quality = "good" if bearish_str > 2 else "moderate"
        else:
            action = "no_trade"
            explanation = f"Signal conflict: bullish={bullish_str:.1f}, bearish={bearish_str:.1f}. No clear edge."
            quality = "poor"

        # Vehicle comparison
        vehicles = {
            "common_stock": {"pros": "Simple, no time decay", "cons": "Full downside exposure"},
            "calls": {"pros": "Leveraged upside, defined risk", "cons": "Time decay, IV sensitivity"},
            "puts": {"pros": "Defined risk, no squeeze exposure", "cons": "Time decay, need timing"},
            "short_stock": {"pros": "Direct bearish exposure", "cons": "Unlimited risk, squeeze exposure"},
            "spreads": {"pros": "Defined risk, reduced IV impact", "cons": "Capped profit"},
        }

        return self._create_output(
            results={
                "action": action,
                "trade_quality": quality,
                "top_signals": top_3,
                "all_signals": signals,
                "bullish_conviction": round(bullish_str, 2),
                "bearish_conviction": round(bearish_str, 2),
                "signal_conflict": abs(bullish_str - bearish_str) < 0.5,
                "vehicle_comparison": vehicles,
                "recommended_vehicle": _VEHICLE_MAP.get(action, "none"),
            },
            explanation=explanation,
            confidence=self._compute_confidence(quality, bullish_str, bearish_str, caution_str),
            assumptions={
                "score_thresholds": {"bullish": 60, "bearish": 40, "strong": 65, "weak": 35},
                "conviction_multiplier": 1.3,
                "squeeze_caution_threshold": 0.8,
                "price": price,
            },
            limitations=[
                "Signal weights are heuristic, not calibrated to historical accuracy",
                "Vehicle comparison is qualitative, not quantitative P/L analysis",
            ],
        )

    @staticmethod
    def _compute_confidence(quality: str, bull_str: float, bear_str: float, caution_str: float) -> float:
        """Continuous confidence from signal strength and quality."""
        base = {"good": 0.55, "moderate": 0.35, "poor": 0.15}.get(quality, 0.15)
        # Stronger directional conviction → higher confidence
        dominant = max(bull_str, bear_str)
        conviction_bonus = min(0.25, dominant / 10)  # up to +0.25
        # Caution penalizes confidence
        caution_penalty = min(0.20, caution_str / 5)
        return round(max(0.05, min(0.95, base + conviction_bonus - caution_penalty)), 3)

    def _get_val(self, scores, name, default=50):
        s = scores.get(name)
        if s is None:
            return default
        if hasattr(s, "value"):
            return s.value
        if isinstance(s, dict):
            return s.get("value", default)
        if isinstance(s, (int, float)):
            return s
        return default
