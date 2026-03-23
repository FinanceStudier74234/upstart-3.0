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

        # Use GARCH conditional vol if available for more accurate estimates
        garch_sigma = None
        try:
            from backend.engines.garch import GARCHEngine
            garch = GARCHEngine()
            garch_result = garch.fit(returns)
            if garch_result.garch_converged and garch_result.conditional_volatility is not None:
                garch_sigma = float(garch_result.conditional_volatility[-1])
                sigma = garch_sigma  # Use GARCH vol as primary estimate
                snap.calibration_score = 70.0  # Higher calibration with GARCH
        except Exception:
            pass  # Fall back to constant vol

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
        # Squeeze probability — multi-factor: SI level + borrow cost + utilization
        if si and si > 5:
            si_factor = min(0.4, (si - 5) / 50)  # SI contributes up to 40%
            ctb = (short_data or {}).get("cost_to_borrow", 5)
            ctb_factor = min(0.2, max(0, ctb - 5) / 50)  # High borrow cost adds up to 20%
            util = (short_data or {}).get("utilization", 50)
            util_factor = min(0.15, max(0, util - 70) / 200)  # High utilization adds up to 15%
            dtc = (short_data or {}).get("days_to_cover", 2)
            dtc_factor = min(0.1, max(0, dtc - 2) / 20)  # High days-to-cover adds up to 10%
            snap.prob_squeeze = round(max(0.02, min(0.80, si_factor + ctb_factor + util_factor + dtc_factor)), 4)
        else:
            snap.prob_squeeze = 0.02

        # Earnings beat probability — derived from recent volatility and trend
        # Higher momentum + lower vol → higher beat probability
        recent_mom = float(np.sum(returns[-21:])) if len(returns) >= 21 else 0
        vol_adj = max(0, 1 - sigma * np.sqrt(252) / 2)  # Lower vol = higher confidence
        snap.prob_earnings_beat = round(max(0.30, min(0.75, 0.50 + recent_mom * 2 + vol_adj * 0.1)), 4)

        # Funding event probability — elevated if vol is high or trend is negative
        base_funding_prob = 0.08
        if sigma * np.sqrt(252) > 0.6:  # High vol environment
            base_funding_prob += 0.05
        if recent_mom < -0.05:  # Negative momentum
            base_funding_prob += 0.05
        snap.prob_funding_event = round(min(0.30, base_funding_prob), 4)

        snap.overall_confidence = self._confidence(returns)

        # Brier score: calibration metric based on directional probabilities
        # Brier = mean( (forecast_prob - outcome)^2 ) over recent data
        # Use a proxy: compare our 1-week directional prob vs realized outcomes
        if len(returns) >= 10:
            recent_weeks = [returns[i:i+5] for i in range(max(0, len(returns)-50), len(returns)-5, 5)]
            if recent_weeks:
                brier_sum = 0.0
                count = 0
                for week_rets in recent_weeks:
                    actual_up = 1.0 if float(np.sum(week_rets)) > 0 else 0.0
                    forecast_prob = snap.prob_up_1w or 0.5
                    brier_sum += (forecast_prob - actual_up) ** 2
                    count += 1
                if count > 0:
                    snap.brier_score = round(brier_sum / count, 4)

        return snap

    def _prob_positive(self, mu: float, sigma: float, days: int) -> float:
        drift = mu * days
        vol = sigma * np.sqrt(days)
        if vol <= 0:
            return 0.5
        z = drift / vol
        return round(float(stats.norm.cdf(z)), 4)

    def _prob_above(self, price: float, target: float, mu: float, sigma: float, days: int) -> float:
        if price <= 0 or target <= 0:
            return 0.5
        log_return = np.log(target / price)
        drift = mu * days
        vol = sigma * np.sqrt(days)
        if vol <= 0:
            return 0.5
        z = (log_return - drift) / vol
        return round(float(1 - stats.norm.cdf(z)), 4)

    def _prob_below(self, price: float, stop: float, mu: float, sigma: float, days: int) -> float:
        if price <= 0 or stop <= 0:
            return 0.5
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
        # Try HMM-based regime detection first (proper statistical model)
        try:
            from backend.engines.hmm_regime import HMMRegimeEngine
            hmm = HMMRegimeEngine()
            result = hmm.fit(returns)
            if result.current_regime_probabilities:
                probs = result.current_regime_probabilities
                # Map to bull/neutral/bear ordering
                bull = probs.get("bull", probs.get("Bull", 0.33))
                neutral = probs.get("neutral", probs.get("Neutral", 0.34))
                bear = probs.get("bear", probs.get("Bear", 0.33))
                total = bull + neutral + bear
                if total > 0:
                    return (round(bull / total, 4), round(neutral / total, 4), round(bear / total, 4))
        except Exception:
            pass

        # Fallback: graduated momentum + volatility heuristic
        recent = returns[-21:] if len(returns) >= 21 else returns
        cum = float(np.sum(recent))
        vol = float(np.std(recent)) * np.sqrt(252)

        # Logistic mapping of momentum to bull/bear probability
        import math
        bull_raw = 1 / (1 + math.exp(-cum * 20))  # Sigmoid: maps cum to (0, 1)

        # High vol → more neutral uncertainty
        vol_uncertainty = min(0.3, max(0, (vol - 0.3) * 0.5))

        bull = max(0.10, min(0.70, bull_raw * (1 - vol_uncertainty)))
        bear = max(0.10, min(0.70, (1 - bull_raw) * (1 - vol_uncertainty)))
        neutral = max(0.10, 1 - bull - bear)

        # Normalize
        total = bull + neutral + bear
        return (round(bull / total, 4), round(neutral / total, 4), round(bear / total, 4))

    def _confidence(self, returns: np.ndarray) -> float:
        # More data = more confidence, less volatility = more confidence
        n_factor = min(30, len(returns) / 10)
        vol = float(np.std(returns)) * np.sqrt(252)
        vol_penalty = max(0, (vol - 0.3) * 30)
        return round(max(10, min(90, 50 + n_factor - vol_penalty)), 2)
