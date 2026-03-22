"""
Behavioral / Psychology Engine
Detects panic, euphoria, trapped traders, exhaustion, capitulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BehavioralSnapshot:
    """Behavioral and crowd psychology state."""
    # Sentiment extremes
    panic_selling: bool = False
    euphoric_buying: bool = False
    sentiment_extreme: str = "none"  # panic | fear | neutral | greed | euphoria

    # Trapped traders
    trapped_longs: bool = False
    trapped_shorts: bool = False
    trapped_direction: str = "none"  # longs | shorts | none

    # Exhaustion
    exhaustion_move: bool = False
    exhaustion_type: str = "none"  # buying_exhaustion | selling_exhaustion | none

    # Capitulation
    capitulation_detected: bool = False
    capitulation_type: str = "none"  # long_capitulation | short_capitulation | none

    # Crowd psychology
    crowd_shift: str = "stable"  # shifting_bullish | stable | shifting_bearish

    # Decision fatigue
    signal_clarity_score: float = 50.0  # 0-100, high = clear signals
    dominant_signals: list[str] = field(default_factory=list)  # Top 3 signals
    noise_level: str = "normal"  # low | normal | high


class BehavioralEngine:
    """Detects behavioral patterns from price/volume/options data."""

    def analyze(
        self,
        technical: dict | None = None,
        options: dict | None = None,
        short: dict | None = None,
        volume_ratio: float = 1.0,  # current vol / avg vol
    ) -> BehavioralSnapshot:
        snap = BehavioralSnapshot()

        rsi = technical.get("rsi") if technical else None
        trend = technical.get("trend_direction", "neutral") if technical else "neutral"
        vol_regime = technical.get("volatility_regime", "normal") if technical else "normal"

        # Panic / Euphoria
        if rsi is not None:
            if rsi < 25 and volume_ratio > 2.0:
                snap.panic_selling = True
                snap.sentiment_extreme = "panic"
            elif rsi > 80 and volume_ratio > 2.0:
                snap.euphoric_buying = True
                snap.sentiment_extreme = "euphoria"
            elif rsi < 30:
                snap.sentiment_extreme = "fear"
            elif rsi > 70:
                snap.sentiment_extreme = "greed"

        # Trapped traders
        if trend == "down" and rsi is not None and rsi < 40:
            snap.trapped_longs = True
            snap.trapped_direction = "longs"
        elif trend == "up" and short and short.get("squeeze_risk_score", 0) > 60:
            snap.trapped_shorts = True
            snap.trapped_direction = "shorts"

        # Exhaustion
        if rsi is not None and rsi > 75 and vol_regime == "expanded":
            snap.exhaustion_move = True
            snap.exhaustion_type = "buying_exhaustion"
        elif rsi is not None and rsi < 25 and vol_regime == "expanded":
            snap.exhaustion_move = True
            snap.exhaustion_type = "selling_exhaustion"

        # Capitulation
        if snap.panic_selling and volume_ratio > 3.0:
            snap.capitulation_detected = True
            snap.capitulation_type = "long_capitulation"
        elif snap.trapped_shorts and volume_ratio > 3.0:
            snap.capitulation_detected = True
            snap.capitulation_type = "short_capitulation"

        # Signal clarity (decision fatigue filter)
        signals = []
        if technical:
            if technical.get("technical_strength_score", 50) > 60:
                signals.append("technical_bullish")
            elif technical.get("technical_strength_score", 50) < 40:
                signals.append("technical_bearish")
        if options:
            if options.get("options_sentiment_score", 50) > 60:
                signals.append("options_bullish")
            elif options.get("options_sentiment_score", 50) < 40:
                signals.append("options_bearish")
        if short:
            if short.get("short_opportunity_score", 50) > 60:
                signals.append("short_opportunity")

        snap.dominant_signals = signals[:3]

        # Clarity: high agreement = high clarity
        bullish = sum(1 for s in signals if "bullish" in s)
        bearish = sum(1 for s in signals if "bearish" in s or "short" in s)
        if signals:
            agreement = max(bullish, bearish) / len(signals)
            snap.signal_clarity_score = round(agreement * 100, 2)
        snap.noise_level = "low" if snap.signal_clarity_score > 70 else ("high" if snap.signal_clarity_score < 30 else "normal")

        return snap
