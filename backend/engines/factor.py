"""
Factor / Style / Market Exposure Engine — Factor decomposition,
style tilts, sector/market exposure analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class FactorSnapshot:
    """Factor exposure profile."""
    # Factor loadings
    market_beta: float | None = None
    size_loading: float | None = None  # SMB
    value_loading: float | None = None  # HML
    momentum_loading: float | None = None  # UMD
    quality_loading: float | None = None
    volatility_loading: float | None = None

    # Sector exposure
    fintech_correlation: float | None = None
    banking_correlation: float | None = None
    growth_correlation: float | None = None
    rate_sensitivity: float | None = None

    # Style classification
    style: str = "growth"  # growth | value | blend
    size: str = "mid_cap"  # mega | large | mid | small | micro
    factor_tilt: str = "momentum"  # value | momentum | quality | low_vol

    # Risk decomposition
    systematic_risk_pct: float | None = None  # R² from market model
    idiosyncratic_risk_pct: float | None = None
    factor_explained_pct: float | None = None  # R² from multi-factor

    # Crowding
    factor_crowding_score: float = 50.0  # how crowded is the dominant factor

    # Z-scores for mean reversion signals
    momentum_z: float | None = None
    value_z: float | None = None
    quality_z: float | None = None


class FactorEngine:
    """Decomposes returns into factor exposures."""

    def analyze(
        self,
        upst_returns: np.ndarray | None = None,
        spy_returns: np.ndarray | None = None,
        factor_data: dict | None = None,
    ) -> FactorSnapshot:
        snap = FactorSnapshot()

        if upst_returns is not None and spy_returns is not None and len(upst_returns) > 30:
            min_len = min(len(upst_returns), len(spy_returns))
            u = upst_returns[-min_len:]
            s = spy_returns[-min_len:]

            slope, intercept, r, _, _ = stats.linregress(s, u)
            if not np.isnan(slope) and not np.isnan(r):
                snap.market_beta = round(slope, 4)
                snap.systematic_risk_pct = round(r ** 2 * 100, 1)
                snap.idiosyncratic_risk_pct = round(100 - snap.systematic_risk_pct, 1)

        if factor_data:
            for k, v in factor_data.items():
                if hasattr(snap, k):
                    setattr(snap, k, v)
        else:
            self._apply_defaults(snap)

        snap.factor_explained_pct = snap.systematic_risk_pct  # simplified
        return snap

    def _apply_defaults(self, snap: FactorSnapshot):
        if snap.market_beta is None:
            snap.market_beta = 2.1
        snap.size_loading = -0.3  # tilts small
        snap.value_loading = -0.8  # anti-value (growth)
        snap.momentum_loading = 0.6
        snap.quality_loading = -0.2
        snap.volatility_loading = 1.5  # high vol name

        snap.fintech_correlation = 0.72
        snap.banking_correlation = 0.35
        snap.growth_correlation = 0.65
        snap.rate_sensitivity = -0.45

        snap.style = "growth"
        snap.size = "mid_cap"
        snap.factor_tilt = "momentum"
        snap.factor_crowding_score = 55

        snap.momentum_z = 0.8
        snap.value_z = -1.2
        snap.quality_z = -0.3

        if snap.systematic_risk_pct is None:
            snap.systematic_risk_pct = 35.0
            snap.idiosyncratic_risk_pct = 65.0
