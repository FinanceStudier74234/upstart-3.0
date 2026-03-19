"""
Macro / Credit Engine — Domain G
Processes macro indicators into regime classifications and pressure scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MacroSnapshot:
    """Macro/credit environment snapshot."""
    # Current levels
    fed_funds: float | None = None
    treasury_2y: float | None = None
    treasury_10y: float | None = None
    yield_curve_2_10: float | None = None
    yield_curve_inverted: bool = False
    cpi_yoy: float | None = None
    pce_yoy: float | None = None
    unemployment: float | None = None
    initial_claims: float | None = None
    hy_spread: float | None = None
    ig_spread: float | None = None
    vix: float | None = None
    financial_conditions: float | None = None
    recession_prob: float | None = None
    consumer_delinquency: float | None = None
    lending_standards: float | None = None

    # Regimes
    rate_regime: str = "neutral"  # tightening | neutral | easing
    credit_regime: str = "normal"  # tight | normal | easy
    risk_regime: str = "neutral"  # risk_on | neutral | risk_off
    liquidity_regime: str = "normal"  # tight | normal | ample
    macro_stress_regime: str = "normal"  # benign | normal | stressed | crisis

    # Z-scores
    hy_spread_z: float | None = None
    vix_z: float | None = None

    # Scores
    macro_pressure_score: float = 50.0
    credit_stress_score: float = 50.0

    # UPST sensitivity
    rate_sensitivity: str = "high"
    credit_sensitivity: str = "high"
    upst_macro_impact: str = "neutral"  # headwind | neutral | tailwind


class MacroEngine:
    """Processes macro data into regime classifications."""

    def analyze(self, indicators: dict) -> MacroSnapshot:
        snap = MacroSnapshot()

        for k, v in indicators.items():
            if hasattr(snap, k.lower()):
                setattr(snap, k.lower(), v)

        # Yield curve
        if snap.treasury_2y is not None and snap.treasury_10y is not None:
            snap.yield_curve_2_10 = round(snap.treasury_10y - snap.treasury_2y, 4)
            snap.yield_curve_inverted = snap.yield_curve_2_10 < 0

        # Rate regime
        if snap.fed_funds is not None:
            if snap.fed_funds > 5.0:
                snap.rate_regime = "tightening"
            elif snap.fed_funds < 2.0:
                snap.rate_regime = "easing"

        # Credit regime
        if snap.hy_spread is not None:
            if snap.hy_spread > 500:
                snap.credit_regime = "tight"
            elif snap.hy_spread < 250:
                snap.credit_regime = "easy"

        # Risk regime
        if snap.vix is not None:
            if snap.vix > 25:
                snap.risk_regime = "risk_off"
            elif snap.vix < 15:
                snap.risk_regime = "risk_on"

        # Macro stress
        stress_count = 0
        if snap.rate_regime == "tightening": stress_count += 1
        if snap.credit_regime == "tight": stress_count += 1
        if snap.risk_regime == "risk_off": stress_count += 1
        if snap.yield_curve_inverted: stress_count += 1
        if snap.recession_prob and snap.recession_prob > 30: stress_count += 1

        if stress_count >= 4:
            snap.macro_stress_regime = "crisis"
        elif stress_count >= 3:
            snap.macro_stress_regime = "stressed"
        elif stress_count >= 1:
            snap.macro_stress_regime = "normal"
        else:
            snap.macro_stress_regime = "benign"

        # UPST impact
        if snap.macro_stress_regime in ("stressed", "crisis"):
            snap.upst_macro_impact = "headwind"
        elif snap.macro_stress_regime == "benign":
            snap.upst_macro_impact = "tailwind"

        return snap
