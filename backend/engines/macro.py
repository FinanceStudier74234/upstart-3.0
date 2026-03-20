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

        # Liquidity regime
        if snap.financial_conditions is not None:
            if snap.financial_conditions < -0.5:
                snap.liquidity_regime = "tight"
            elif snap.financial_conditions > 0.5:
                snap.liquidity_regime = "ample"
        elif snap.hy_spread is not None and snap.vix is not None:
            # Proxy: tight liquidity = wide spreads + high VIX
            if snap.hy_spread > 500 and snap.vix > 25:
                snap.liquidity_regime = "tight"
            elif snap.hy_spread < 300 and snap.vix < 18:
                snap.liquidity_regime = "ample"

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

        # Z-scores for key risk indicators
        # Use long-run historical norms as reference:
        #   HY spread: median ~400bp, std ~150bp (ICE BofA US HY OAS, 2000-2025)
        #   VIX: median ~17.5, std ~7.0 (CBOE VIX, 1990-2025)
        if snap.hy_spread is not None:
            hy_median, hy_std = 400.0, 150.0
            snap.hy_spread_z = round((snap.hy_spread - hy_median) / hy_std, 2)
        if snap.vix is not None:
            vix_median, vix_std = 17.5, 7.0
            snap.vix_z = round((snap.vix - vix_median) / vix_std, 2)

        # Macro pressure score (0-100, higher = more pressure)
        snap.macro_pressure_score = self._macro_pressure_score(snap)

        # Credit stress score (0-100, higher = more stress)
        snap.credit_stress_score = self._credit_stress_score(snap)

        # UPST impact
        if snap.macro_stress_regime in ("stressed", "crisis"):
            snap.upst_macro_impact = "headwind"
        elif snap.macro_stress_regime == "benign":
            snap.upst_macro_impact = "tailwind"

        return snap

    def _macro_pressure_score(self, snap: MacroSnapshot) -> float:
        """Compute macro pressure score (0=benign, 100=crisis)."""
        score = 50.0
        # Fed funds contribution
        if snap.fed_funds is not None:
            score += min(15, max(-15, (snap.fed_funds - 3.0) * 5))
        # Yield curve inversion
        if snap.yield_curve_inverted:
            score += 10
        # HY spread via z-score
        if snap.hy_spread_z is not None:
            score += min(15, max(-15, snap.hy_spread_z * 8))
        # VIX via z-score
        if snap.vix_z is not None:
            score += min(10, max(-10, snap.vix_z * 5))
        # Recession probability
        if snap.recession_prob is not None:
            score += min(10, max(-5, (snap.recession_prob - 15) * 0.5))
        return round(max(0, min(100, score)), 2)

    def _credit_stress_score(self, snap: MacroSnapshot) -> float:
        """Compute credit stress score (0=easy, 100=crisis)."""
        score = 50.0
        if snap.hy_spread_z is not None:
            score += min(20, max(-20, snap.hy_spread_z * 10))
        if snap.consumer_delinquency is not None:
            # Delinquency above 3% is elevated
            score += min(15, max(-10, (snap.consumer_delinquency - 3.0) * 5))
        if snap.lending_standards is not None:
            # Positive = tightening
            score += min(15, max(-10, snap.lending_standards * 3))
        return round(max(0, min(100, score)), 2)
