"""
Probability Engine — Bayesian probability estimates for key outcomes,
probability cones, and calibrated confidence intervals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class ProbabilitySnapshot:
    """Probability estimates for key scenarios."""
    # Directional probabilities
    prob_up_1w: float | None = None
    prob_up_1m: float | None = None
    prob_up_3m: float | None = None

    # Target probabilities
    prob_above_target: float | None = None
    prob_below_stop: float | None = None

    # Magnitude probabilities
    prob_move_gt_5pct_1w: float | None = None
    prob_move_gt_10pct_1m: float | None = None
    prob_move_gt_20pct_3m: float | None = None

    # Probability cones
    cone_1w: dict = field(default_factory=dict)  # {p10, p25, p50, p75, p90}
    cone_1m: dict = field(default_factory=dict)
    cone_3m: dict = field(default_factory=dict)

    # Regime probabilities
    prob_bull_regime: float = 0.33
    prob_neutral_regime: float = 0.34
    prob_bear_regime: float = 0.33

    # Event probabilities
    prob_squeeze: float | None = None
    prob_earnings_beat: float | None = None
    prob_funding_event: float | None = None

    # Calibration
    calibration_score: float = 50.0  # how well-calibrated are our probabilities
    brier_score: float | None = None

    # Confidence
    overall_confidence: float = 50.0


class ProbabilityEngine:
    """Generates calibrated probability estimates."""

    def analyze(
        self,
        returns: np.ndarray | None = None,
        price: float = 0.0,
        target: float | None = None,
        stop: float | None = None,
        vol: float | None = None,
        short_data: dict | None = None,
    ) -> ProbabilitySnapshot:
        snap = ProbabilitySnapshot()

        if returns is None or len(returns) < 30:
            return snap

        mu = float(np.mean(returns))
        sigma = float(np.std(returns))

        if sigma <= 0 or price <= 0:
            return snap

        # Directional probabilities (log-normal model)
        snap.prob_up_1w = self._prob_positive(mu, sigma, 5)
        snap.prob_up_1m = self._prob_positive(mu, sigma, 21)
        snap.prob_up_3m = self._prob_positive(mu, sigma, 63)

        # Target / stop probabilities
        if target and target > 0:
            snap.prob_above_target = self._prob_above(price, target, mu, sigma, 63)
        if stop and stop > 0:
            snap.prob_below_stop = self._prob_below(price, stop, mu, sigma, 63)

        # Magnitude probabilities
        snap.prob_move_gt_5pct_1w = self._prob_abs_move(mu, sigma, 5, 0.05)
        snap.prob_move_gt_10pct_1m = self._prob_abs_move(mu, sigma, 21, 0.10)
        snap.prob_move_gt_20pct_3m = self._prob_abs_move(mu, sigma, 63, 0.20)

        # Probability cones
        snap.cone_1w = self._probability_cone(price, mu, sigma, 5)
        snap.cone_1m = self._probability_cone(price, mu, sigma, 21)
        snap.cone_3m = self._probability_cone(price, mu, sigma, 63)

        # Regime probabilities (simplified momentum-based)
        snap.prob_bull_regime, snap.prob_neutral_regime, snap.prob_bear_regime = (
            self._regime_probs(returns))

        # Event probabilities
        si = (short_data or {}).get("short_pct_float", 0)
        snap.prob_squeeze = round(min(0.8, si / 100 * 2), 2) if si else 0.05

        snap.prob_earnings_beat = 0.55  # base rate for UPST
        snap.prob_funding_event = 0.10

        snap.overall_confidence = self._confidence(returns)

        return snap

    def _prob_positive(self, mu: float, sigma: float, days: int) -> float:
        drift = mu * days
        vol = sigma * np.sqrt(days)
        if vol <= 0:
            return 0.5
        z = drift / vol
        return round(float(stats.norm.cdf(z)), 4)

    def _prob_above(self, price: float, target: float, mu: float, sigma: float, days: int) -> float:
        log_return = np.log(target / price)
        drift = mu * days
        vol = sigma * np.sqrt(days)
        if vol <= 0:
            return 0.5
        z = (log_return - drift) / vol
        return round(float(1 - stats.norm.cdf(z)), 4)

    def _prob_below(self, price: float, stop: float, mu: float, sigma: float, days: int) -> float:
        log_return = np.log(stop / price)
        drift = mu * days
        vol = sigma * np.sqrt(days)
        if vol <= 0:
            return 0.5
        z = (log_return - drift) / vol
        return round(float(stats.norm.cdf(z)), 4)

    def _prob_abs_move(self, mu: float, sigma: float, days: int, threshold: float) -> float:
        drift = mu * days
        vol = sigma * np.sqrt(days)
        if vol <= 0:
            return 0.0
        p_up = 1 - stats.norm.cdf((threshold - drift) / vol)
        p_down = stats.norm.cdf((-threshold - drift) / vol)
        return round(float(p_up + p_down), 4)

    def _probability_cone(self, price: float, mu: float, sigma: float, days: int) -> dict:
        drift = mu * days
        vol = sigma * np.sqrt(days)
        percentiles = {10: -1.282, 25: -0.674, 50: 0, 75: 0.674, 90: 1.282}
        cone = {}
        for pct, z in percentiles.items():
            ret = drift + z * vol
            cone[f"p{pct}"] = round(price * np.exp(ret), 2)
        return cone

    def _regime_probs(self, returns: np.ndarray) -> tuple[float, float, float]:
        recent = returns[-21:] if len(returns) >= 21 else returns
        cum = float(np.sum(recent))
        if cum > 0.05:
            return (0.55, 0.30, 0.15)
        elif cum < -0.05:
            return (0.15, 0.30, 0.55)
        return (0.30, 0.40, 0.30)

    def _confidence(self, returns: np.ndarray) -> float:
        # More data = more confidence, less volatility = more confidence
        n_factor = min(30, len(returns) / 10)
        vol = float(np.std(returns)) * np.sqrt(252)
        vol_penalty = max(0, (vol - 0.3) * 30)
        return round(max(10, min(90, 50 + n_factor - vol_penalty)), 2)
