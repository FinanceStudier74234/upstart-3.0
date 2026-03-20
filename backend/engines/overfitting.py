"""
Overfitting / False Edge Detection Engine — Detects data mining bias,
curve fitting, and spurious signals in backtests and models.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class OverfittingSnapshot:
    """Overfitting and false edge detection results."""
    # Multiple testing adjustment
    strategies_tested: int = 0
    bonferroni_threshold: float | None = None  # adjusted p-value
    expected_false_discoveries: float = 0.0

    # In-sample vs out-of-sample
    is_sharpe: float | None = None
    oos_sharpe: float | None = None
    sharpe_decay_pct: float | None = None  # (IS - OOS) / IS * 100
    haircut_sharpe: float | None = None  # deflated Sharpe

    # Complexity penalties
    parameter_count: int = 0
    data_points: int = 0
    degrees_of_freedom_ratio: float | None = None
    aic: float | None = None
    bic: float | None = None

    # White's Reality Check
    whites_p_value: float | None = None
    passes_whites_test: bool = True

    # Probability of backtest overfitting (PBO)
    pbo: float | None = None  # 0-1, probability that best IS strategy is worst OOS

    # Minimum backtest length
    min_track_record_months: float | None = None

    # Warnings
    warnings: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low | medium | high | critical

    # Score (higher = more likely overfit)
    overfitting_risk_score: float = 30.0


class OverfittingEngine:
    """Detects overfitting and false edges in trading strategies."""

    def analyze(
        self,
        backtest_results: list[dict] | None = None,
        model_metadata: dict | None = None,
    ) -> OverfittingSnapshot:
        snap = OverfittingSnapshot()

        if not model_metadata:
            model_metadata = self._defaults()

        snap.strategies_tested = model_metadata.get("strategies_tested", 1)
        snap.parameter_count = model_metadata.get("parameter_count", 5)
        snap.data_points = model_metadata.get("data_points", 252)

        # Degrees of freedom
        if snap.data_points > 0:
            snap.degrees_of_freedom_ratio = round(snap.data_points / max(1, snap.parameter_count), 2)

        # Multiple testing (Bonferroni)
        if snap.strategies_tested > 1:
            snap.bonferroni_threshold = round(0.05 / snap.strategies_tested, 6)
            snap.expected_false_discoveries = round(snap.strategies_tested * 0.05, 2)

        # In-sample vs out-of-sample
        snap.is_sharpe = model_metadata.get("is_sharpe", 1.5)
        snap.oos_sharpe = model_metadata.get("oos_sharpe", 0.8)
        if snap.is_sharpe and snap.is_sharpe > 0:
            snap.sharpe_decay_pct = round(
                (snap.is_sharpe - (snap.oos_sharpe or 0)) / snap.is_sharpe * 100, 1)

        # Deflated Sharpe (Bailey & de Prado)
        snap.haircut_sharpe = self._deflated_sharpe(
            snap.is_sharpe or 0, snap.strategies_tested,
            snap.data_points, model_metadata.get("skewness", 0),
            model_metadata.get("kurtosis", 3),
        )

        # Minimum track record length
        snap.min_track_record_months = self._min_track_record(
            snap.is_sharpe or 0, snap.oos_sharpe or 0)

        # White's Reality Check (bootstrap-based)
        if backtest_results:
            snap.whites_p_value = self._whites_reality_check(backtest_results)
            snap.passes_whites_test = (
                snap.whites_p_value is not None and snap.whites_p_value < 0.05
            )

        # PBO estimate
        snap.pbo = self._estimate_pbo(snap)

        # Warnings
        snap.warnings = self._generate_warnings(snap)
        snap.risk_level = self._risk_level(snap)
        snap.overfitting_risk_score = self._compute_score(snap)

        return snap

    def _deflated_sharpe(
        self, observed_sharpe: float, trials: int,
        T: int, skew: float, kurtosis: float,
    ) -> float | None:
        if T <= 0 or observed_sharpe <= 0:
            return None
        import math
        # Expected max Sharpe under null (iid normal)
        euler = 0.5772
        expected_max = ((1 - euler) * stats.norm.ppf(1 - 1 / trials) +
                        euler * stats.norm.ppf(1 - 1 / (trials * math.e)))
        sr_std = math.sqrt((1 + 0.5 * observed_sharpe ** 2 -
                            skew * observed_sharpe +
                            (kurtosis - 3) / 4 * observed_sharpe ** 2) / T)
        if sr_std <= 0:
            return None
        deflated = (observed_sharpe - expected_max) / sr_std
        p_value = 1 - stats.norm.cdf(deflated)
        adjusted = observed_sharpe * (1 - p_value)
        return round(max(0, adjusted), 4)

    def _min_track_record(self, is_sharpe: float, target_sharpe: float) -> float | None:
        if is_sharpe <= target_sharpe or is_sharpe <= 0:
            return None
        # MinTRL formula (Bailey)
        n = max(1, (1 + (1 - 0) * is_sharpe ** 2) / ((is_sharpe - target_sharpe) ** 2))
        return round(n / 12, 1)  # months

    def _estimate_pbo(self, snap: OverfittingSnapshot) -> float:
        pbo = 0.1
        if snap.sharpe_decay_pct and snap.sharpe_decay_pct > 50:
            pbo += 0.3
        if snap.strategies_tested > 50:
            pbo += 0.2
        if snap.degrees_of_freedom_ratio and snap.degrees_of_freedom_ratio < 10:
            pbo += 0.2
        return round(min(1.0, pbo), 2)

    def _whites_reality_check(
        self,
        backtest_results: list[dict],
        n_bootstrap: int = 1000,
    ) -> float | None:
        """
        White's Reality Check (2000) — tests whether the best strategy's
        performance is significantly better than a zero-mean benchmark after
        accounting for data snooping across all tested strategies.

        Each dict in backtest_results should have a 'returns' key with a list
        of period returns. All return series must be the same length.

        Returns a p-value. Low p-value (< 0.05) = best strategy is significant
        even after accounting for multiple testing.
        """
        # Extract return matrices
        return_series = []
        for bt in backtest_results:
            rets = bt.get("returns")
            if rets is not None and len(rets) > 0:
                return_series.append(np.array(rets, dtype=float))

        if len(return_series) < 2:
            return None

        # Align to shortest series length
        min_len = min(len(r) for r in return_series)
        if min_len < 20:
            return None
        returns_matrix = np.column_stack([r[:min_len] for r in return_series])
        n_periods, n_strategies = returns_matrix.shape

        # Observed test statistic: max average return across strategies
        avg_returns = returns_matrix.mean(axis=0)
        observed_stat = avg_returns.max()

        # Bootstrap: resample periods with replacement, compute max avg
        rng = np.random.default_rng(42)
        bootstrap_stats = np.empty(n_bootstrap)
        for b in range(n_bootstrap):
            indices = rng.integers(0, n_periods, size=n_periods)
            resampled = returns_matrix[indices, :]
            # Center the resampled returns (null: zero mean)
            centered = resampled - returns_matrix.mean(axis=0, keepdims=True)
            bootstrap_stats[b] = centered.mean(axis=0).max()

        # p-value: fraction of bootstrap stats >= observed
        p_value = float(np.mean(bootstrap_stats >= observed_stat))
        return round(p_value, 4)

    def _generate_warnings(self, snap: OverfittingSnapshot) -> list[str]:
        warnings = []
        if snap.sharpe_decay_pct and snap.sharpe_decay_pct > 40:
            warnings.append(f"High Sharpe decay ({snap.sharpe_decay_pct:.0f}%) — likely overfit")
        if snap.degrees_of_freedom_ratio and snap.degrees_of_freedom_ratio < 10:
            warnings.append(f"Low DoF ratio ({snap.degrees_of_freedom_ratio:.1f}) — too many parameters")
        if snap.strategies_tested > 20:
            warnings.append(f"Tested {snap.strategies_tested} strategies — multiple testing bias")
        if snap.is_sharpe and snap.is_sharpe > 3.0:
            warnings.append(f"Suspiciously high IS Sharpe ({snap.is_sharpe:.2f})")
        if snap.haircut_sharpe is not None and snap.haircut_sharpe < 0.5:
            warnings.append(f"Deflated Sharpe only {snap.haircut_sharpe:.2f} after haircut")
        if snap.pbo and snap.pbo > 0.5:
            warnings.append(f"PBO = {snap.pbo:.0%} — high probability of backtest overfitting")
        if snap.whites_p_value is not None and not snap.passes_whites_test:
            warnings.append(
                f"Fails White's Reality Check (p={snap.whites_p_value:.3f}) "
                f"— best strategy not significant after data snooping adjustment"
            )
        return warnings

    def _risk_level(self, snap: OverfittingSnapshot) -> str:
        count = len(snap.warnings)
        if count >= 4:
            return "critical"
        if count >= 2:
            return "high"
        if count >= 1:
            return "medium"
        return "low"

    def _compute_score(self, snap: OverfittingSnapshot) -> float:
        score = 20.0
        if snap.sharpe_decay_pct:
            score += min(25, snap.sharpe_decay_pct * 0.5)
        if snap.pbo:
            score += snap.pbo * 30
        if snap.strategies_tested > 10:
            score += min(15, snap.strategies_tested * 0.3)
        if snap.degrees_of_freedom_ratio and snap.degrees_of_freedom_ratio < 20:
            score += max(0, (20 - snap.degrees_of_freedom_ratio))
        return round(max(0, min(100, score)), 2)

    def _defaults(self) -> dict:
        return {
            "strategies_tested": 5,
            "parameter_count": 8,
            "data_points": 504,
            "is_sharpe": 1.8,
            "oos_sharpe": 1.0,
            "skewness": -0.3,
            "kurtosis": 4.5,
        }
