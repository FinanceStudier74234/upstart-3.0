"""
Calibration Engine — Model calibration and validation against historical data.
Walk-forward threshold optimization, score-to-return mapping, probability
calibration, regime-conditional thresholds, signal decay analysis, ensemble
weight optimization, and directional confusion matrices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats


# ── Score names (all 15 mandatory scores) ──

SCORE_NAMES: list[str] = [
    "funding_strength",
    "origination_momentum",
    "macro_pressure",
    "credit_stress",
    "valuation_attractiveness",
    "technical_strength",
    "options_sentiment",
    "short_opportunity",
    "squeeze_risk",
    "news_regime",
    "forecast_confidence",
    "relative_strength_spy",
    "trade_quality",
    "positioning_fragility",
    "composite_opportunity",
]

HORIZONS: list[int] = [1, 5, 21, 63]


# ── Dataclass ──


@dataclass
class CalibrationResult:
    """Complete calibration output."""

    # Walk-forward optimal thresholds
    buy_threshold: float = 65.0
    sell_threshold: float = 35.0
    hold_band: tuple[float, float] = (35.0, 65.0)
    threshold_history: list[dict] = field(default_factory=list)
    threshold_stability: float = 0.0  # std of threshold over windows

    # Score-to-return calibration curves
    score_return_curves: dict[str, list[dict]] = field(default_factory=dict)
    # { score_name: [ {threshold, avg_fwd_return, hit_rate, n_obs}, ... ] }

    # Probability calibration
    calibration_curve: list[dict] = field(default_factory=list)
    # [ {bin_center, predicted_prob, actual_freq, count}, ... ]
    brier_score: float = 1.0
    platt_a: float = 0.0  # logistic recalibration slope
    platt_b: float = 0.0  # logistic recalibration intercept
    calibration_error: float = 1.0  # expected calibration error (ECE)

    # Regime-conditional thresholds
    regime_thresholds: dict[str, dict] = field(default_factory=dict)
    # { "bull": {buy, sell}, "neutral": {buy, sell}, "bear": {buy, sell} }

    # Signal decay
    signal_decay: dict[str, dict[int, float]] = field(default_factory=dict)
    # { score_name: {1: corr, 5: corr, 21: corr, 63: corr} }
    persistent_signals: list[str] = field(default_factory=list)
    short_lived_signals: list[str] = field(default_factory=list)

    # Ensemble weights
    ensemble_weights: dict[str, float] = field(default_factory=dict)
    ensemble_variance: float = 0.0

    # Confusion matrix by regime
    confusion: dict[str, dict] = field(default_factory=dict)
    # { regime: {tp, fp, tn, fn, precision, recall, f1, accuracy} }

    # Summary
    overall_accuracy: float = 0.0
    overall_sharpe_calibrated: float = 0.0
    n_observations: int = 0


class CalibrationEngine:
    """Calibrates scoring thresholds and validates model forecasts
    against historical data."""

    # ── Public entry point ──

    def calibrate(
        self,
        returns: np.ndarray,
        scores_history: list[dict],
        signals_history: list[dict],
    ) -> CalibrationResult:
        """Run full calibration suite.

        Parameters
        ----------
        returns : np.ndarray
            Daily return series (T,).
        scores_history : list[dict]
            One dict per day with score values keyed by score name.
        signals_history : list[dict]
            One dict per day with keys:
                - prob_up: float in [0,1]
                - regime: str ("bull" | "neutral" | "bear")
                - direction: str ("bullish" | "bearish" | "neutral")
                - forecast_models: dict[str, float]  (model_name -> forecast)

        Returns
        -------
        CalibrationResult
        """
        result = CalibrationResult()
        n = min(len(returns), len(scores_history), len(signals_history))
        if n < 30:
            return result
        result.n_observations = n

        returns = np.asarray(returns[:n], dtype=np.float64)
        scores_history = scores_history[:n]
        signals_history = signals_history[:n]

        # Extract composite scores for threshold work
        composites = np.array(
            [s.get("composite_opportunity", 50.0) for s in scores_history],
            dtype=np.float64,
        )

        regimes = np.array([s.get("regime", "neutral") for s in signals_history])

        # 1. Walk-forward calibration
        self._walk_forward_calibration(returns, composites, result)

        # 2. Score-to-return mapping
        self._score_return_mapping(returns, scores_history, result)

        # 3. Probability calibration
        prob_ups = np.array(
            [s.get("prob_up", 0.5) for s in signals_history], dtype=np.float64
        )
        self._probability_calibration(returns, prob_ups, result)

        # 4. Regime-conditional calibration
        self._regime_calibration(returns, composites, regimes, result)

        # 5. Signal decay analysis
        self._signal_decay_analysis(returns, scores_history, result)

        # 6. Ensemble weight optimization
        self._ensemble_weight_optimization(returns, signals_history, result)

        # 7. Confusion matrix
        directions = np.array(
            [s.get("direction", "neutral") for s in signals_history]
        )
        self._confusion_matrix(returns, directions, regimes, result)

        # Overall calibrated Sharpe
        self._compute_calibrated_sharpe(returns, composites, result)

        return result

    # ── 1. Walk-forward calibration ──

    def _walk_forward_calibration(
        self,
        returns: np.ndarray,
        composites: np.ndarray,
        result: CalibrationResult,
        min_window: int = 60,
        step: int = 21,
    ) -> None:
        """Expanding-window walk-forward to find optimal buy/sell thresholds.

        At each step the window grows by *step* observations and we optimise
        thresholds on all data seen so far, then record the result.
        """
        n = len(returns)
        buy_history: list[float] = []
        sell_history: list[float] = []
        history: list[dict] = []

        for end in range(min_window, n, step):
            window_ret = returns[:end]
            window_comp = composites[:end]
            buy_t, sell_t = self._optimize_thresholds(window_ret, window_comp)
            buy_history.append(buy_t)
            sell_history.append(sell_t)
            history.append(
                {"window_end": int(end), "buy_threshold": buy_t, "sell_threshold": sell_t}
            )

        if buy_history:
            result.buy_threshold = buy_history[-1]
            result.sell_threshold = sell_history[-1]
            result.hold_band = (result.sell_threshold, result.buy_threshold)
            result.threshold_history = history
            result.threshold_stability = float(
                np.std(buy_history) + np.std(sell_history)
            ) / 2.0

    def _optimize_thresholds(
        self, returns: np.ndarray, composites: np.ndarray
    ) -> tuple[float, float]:
        """Find buy/sell thresholds that maximise risk-adjusted return."""
        best_sharpe = -np.inf
        best_buy = 65.0
        best_sell = 35.0

        for buy_t in np.arange(55, 85, 2.5):
            for sell_t in np.arange(15, 45, 2.5):
                if sell_t >= buy_t:
                    continue
                pnl = self._threshold_pnl(returns, composites, buy_t, sell_t)
                if len(pnl) < 10:
                    continue
                mu = np.mean(pnl)
                sigma = np.std(pnl)
                if sigma < 1e-12:
                    continue
                sharpe = mu / sigma * np.sqrt(252)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_buy = float(buy_t)
                    best_sell = float(sell_t)

        return best_buy, best_sell

    @staticmethod
    def _threshold_pnl(
        returns: np.ndarray,
        composites: np.ndarray,
        buy_t: float,
        sell_t: float,
    ) -> np.ndarray:
        """Simulate simple long/flat/short PnL from threshold strategy."""
        position = 0.0
        pnl: list[float] = []
        for i in range(1, len(returns)):
            score = composites[i - 1]
            if score >= buy_t:
                position = 1.0
            elif score <= sell_t:
                position = -1.0
            else:
                position *= 0.95  # decay toward flat in hold band
            pnl.append(position * returns[i])
        return np.array(pnl, dtype=np.float64)

    # ── 2. Score-to-return mapping ──

    def _score_return_mapping(
        self,
        returns: np.ndarray,
        scores_history: list[dict],
        result: CalibrationResult,
        forward_days: int = 5,
    ) -> None:
        """For each of the 15 scores, compute average forward return at
        different threshold buckets and build a calibration curve."""
        n = len(returns)
        if n <= forward_days:
            return

        # Pre-compute forward returns
        fwd_returns = np.full(n, np.nan)
        for i in range(n - forward_days):
            fwd_returns[i] = float(np.sum(returns[i + 1 : i + 1 + forward_days]))

        valid = ~np.isnan(fwd_returns)

        for score_name in SCORE_NAMES:
            score_vals = np.array(
                [s.get(score_name, np.nan) for s in scores_history], dtype=np.float64
            )
            mask = valid & ~np.isnan(score_vals)
            if mask.sum() < 20:
                continue

            sv = score_vals[mask]
            fr = fwd_returns[mask]

            curve: list[dict] = []
            for threshold in np.arange(10, 95, 5):
                above = sv >= threshold
                n_obs = int(above.sum())
                if n_obs < 5:
                    continue
                avg_ret = float(np.mean(fr[above]))
                hit_rate = float(np.mean(fr[above] > 0))
                curve.append(
                    {
                        "threshold": float(threshold),
                        "avg_fwd_return": round(avg_ret, 6),
                        "hit_rate": round(hit_rate, 4),
                        "n_obs": n_obs,
                    }
                )
            result.score_return_curves[score_name] = curve

    # ── 3. Probability calibration ──

    def _probability_calibration(
        self,
        returns: np.ndarray,
        prob_ups: np.ndarray,
        result: CalibrationResult,
        n_bins: int = 10,
    ) -> None:
        """Reliability diagram + Platt scaling for probability forecasts."""
        actuals = (returns > 0).astype(np.float64)
        valid = ~np.isnan(prob_ups) & ~np.isnan(actuals)
        p = prob_ups[valid]
        a = actuals[valid]
        if len(p) < 30:
            return

        # Brier score
        result.brier_score = float(np.mean((p - a) ** 2))

        # Reliability diagram
        bin_edges = np.linspace(0, 1, n_bins + 1)
        curve: list[dict] = []
        for i in range(n_bins):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            mask = (p >= lo) & (p < hi)
            count = int(mask.sum())
            if count == 0:
                continue
            pred_mean = float(np.mean(p[mask]))
            actual_freq = float(np.mean(a[mask]))
            curve.append(
                {
                    "bin_center": round((lo + hi) / 2, 3),
                    "predicted_prob": round(pred_mean, 4),
                    "actual_freq": round(actual_freq, 4),
                    "count": count,
                }
            )
        result.calibration_curve = curve

        # Expected calibration error
        ece = 0.0
        total = len(p)
        for entry in curve:
            w = entry["count"] / total
            ece += w * abs(entry["predicted_prob"] - entry["actual_freq"])
        result.calibration_error = round(ece, 6)

        # Platt scaling (logistic recalibration) if miscalibrated
        if result.calibration_error > 0.02:
            platt_a, platt_b = self._platt_scaling(p, a)
            result.platt_a = platt_a
            result.platt_b = platt_b

    @staticmethod
    def _platt_scaling(
        probs: np.ndarray, actuals: np.ndarray
    ) -> tuple[float, float]:
        """Fit Platt scaling: P_calibrated = 1 / (1 + exp(a * logit(p) + b)).

        We parameterise on the log-odds to keep numerics stable.
        """
        eps = 1e-8
        logits = np.log(np.clip(probs, eps, 1 - eps) / (1 - np.clip(probs, eps, 1 - eps)))

        def neg_log_likelihood(params: np.ndarray) -> float:
            a, b = params
            z = a * logits + b
            # Stable log-sigmoid
            ll = actuals * (-np.logaddexp(0, -z)) + (1 - actuals) * (-np.logaddexp(0, z))
            return -float(np.sum(ll))

        res = optimize.minimize(
            neg_log_likelihood,
            x0=np.array([1.0, 0.0]),
            method="Nelder-Mead",
            options={"maxiter": 2000, "xatol": 1e-8, "fatol": 1e-8},
        )
        return float(res.x[0]), float(res.x[1])

    # ── 4. Regime-conditional calibration ──

    def _regime_calibration(
        self,
        returns: np.ndarray,
        composites: np.ndarray,
        regimes: np.ndarray,
        result: CalibrationResult,
    ) -> None:
        """Compute separate buy/sell thresholds per regime."""
        for regime in ("bull", "neutral", "bear"):
            mask = regimes == regime
            if mask.sum() < 30:
                result.regime_thresholds[regime] = {
                    "buy": 65.0,
                    "sell": 35.0,
                    "n_obs": int(mask.sum()),
                }
                continue
            r = returns[mask]
            c = composites[mask]
            buy_t, sell_t = self._optimize_thresholds(r, c)
            result.regime_thresholds[regime] = {
                "buy": buy_t,
                "sell": sell_t,
                "n_obs": int(mask.sum()),
            }

    # ── 5. Signal decay analysis ──

    def _signal_decay_analysis(
        self,
        returns: np.ndarray,
        scores_history: list[dict],
        result: CalibrationResult,
    ) -> None:
        """Measure rank correlation between each score and forward returns
        at 1d, 5d, 21d, 63d horizons."""
        n = len(returns)

        for score_name in SCORE_NAMES:
            score_vals = np.array(
                [s.get(score_name, np.nan) for s in scores_history], dtype=np.float64
            )
            decay_map: dict[int, float] = {}

            for horizon in HORIZONS:
                if n <= horizon:
                    decay_map[horizon] = 0.0
                    continue

                fwd = np.full(n, np.nan)
                for i in range(n - horizon):
                    fwd[i] = float(np.sum(returns[i + 1 : i + 1 + horizon]))

                valid = ~np.isnan(score_vals) & ~np.isnan(fwd)
                if valid.sum() < 20:
                    decay_map[horizon] = 0.0
                    continue

                corr, _ = stats.spearmanr(score_vals[valid], fwd[valid])
                decay_map[horizon] = round(float(corr), 6)

            result.signal_decay[score_name] = decay_map

        # Classify persistent vs short-lived
        for name, decay in result.signal_decay.items():
            short_corr = abs(decay.get(1, 0)) + abs(decay.get(5, 0))
            long_corr = abs(decay.get(21, 0)) + abs(decay.get(63, 0))
            if long_corr > short_corr * 0.7 and long_corr > 0.05:
                result.persistent_signals.append(name)
            elif short_corr > 0.05 and long_corr < short_corr * 0.3:
                result.short_lived_signals.append(name)

    # ── 6. Ensemble weight optimization ──

    def _ensemble_weight_optimization(
        self,
        returns: np.ndarray,
        signals_history: list[dict],
        result: CalibrationResult,
    ) -> None:
        """Minimum-variance combination of multiple forecast models."""
        # Collect model forecasts
        model_names: list[str] = []
        model_forecasts: dict[str, list[float]] = {}

        for sig in signals_history:
            fm = sig.get("forecast_models", {})
            if not model_names and fm:
                model_names = sorted(fm.keys())
                for mn in model_names:
                    model_forecasts[mn] = []
            for mn in model_names:
                model_forecasts.setdefault(mn, []).append(fm.get(mn, np.nan))

        if len(model_names) < 2:
            return

        n = len(returns)
        # Compute forecast errors for each model
        error_matrix: list[np.ndarray] = []
        for mn in model_names:
            fc = np.array(model_forecasts[mn][:n], dtype=np.float64)
            err = returns[:len(fc)] - fc
            error_matrix.append(err)

        error_arr = np.column_stack(error_matrix)  # (T, K)
        valid_rows = ~np.any(np.isnan(error_arr), axis=1)
        error_arr = error_arr[valid_rows]

        if len(error_arr) < 20 or error_arr.shape[1] < 2:
            return

        k = error_arr.shape[1]
        cov = np.cov(error_arr, rowvar=False)  # (K, K)

        # Ensure positive-definite by adding ridge
        cov += np.eye(k) * 1e-8

        # Minimum variance weights: w = (Σ^-1 @ 1) / (1^T @ Σ^-1 @ 1)
        try:
            inv_cov = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            inv_cov = np.linalg.pinv(cov)

        ones = np.ones(k)
        raw_w = inv_cov @ ones
        weights = raw_w / np.sum(raw_w)

        for i, mn in enumerate(model_names):
            result.ensemble_weights[mn] = round(float(weights[i]), 6)

        # Portfolio variance
        result.ensemble_variance = float(weights @ cov @ weights)

    # ── 7. Confusion matrix ──

    def _confusion_matrix(
        self,
        returns: np.ndarray,
        directions: np.ndarray,
        regimes: np.ndarray,
        result: CalibrationResult,
    ) -> None:
        """Directional confusion matrix: predicted bullish/bearish vs actual
        up/down, segmented by regime."""
        actual_dir = np.where(returns > 0, "bullish", "bearish")
        all_regimes = ["bull", "neutral", "bear", "all"]

        for regime in all_regimes:
            if regime == "all":
                mask = np.ones(len(returns), dtype=bool)
            else:
                mask = regimes == regime

            # Only count non-neutral predictions
            pred_mask = mask & ((directions == "bullish") | (directions == "bearish"))
            n_obs = int(pred_mask.sum())
            if n_obs < 10:
                result.confusion[regime] = {
                    "tp": 0, "fp": 0, "tn": 0, "fn": 0,
                    "precision": 0.0, "recall": 0.0, "f1": 0.0,
                    "accuracy": 0.0, "n_obs": n_obs,
                }
                continue

            pred = directions[pred_mask]
            actual = actual_dir[pred_mask]

            tp = int(np.sum((pred == "bullish") & (actual == "bullish")))
            fp = int(np.sum((pred == "bullish") & (actual == "bearish")))
            fn = int(np.sum((pred == "bearish") & (actual == "bullish")))
            tn = int(np.sum((pred == "bearish") & (actual == "bearish")))

            precision = tp / max(tp + fp, 1)
            recall = tp / max(tp + fn, 1)
            f1 = (
                2 * precision * recall / max(precision + recall, 1e-12)
            )
            accuracy = (tp + tn) / max(tp + fp + fn + tn, 1)

            result.confusion[regime] = {
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "accuracy": round(accuracy, 4),
                "n_obs": n_obs,
            }

        # Overall accuracy from "all" regime
        if "all" in result.confusion:
            result.overall_accuracy = result.confusion["all"].get("accuracy", 0.0)

    # ── Calibrated Sharpe ──

    def _compute_calibrated_sharpe(
        self,
        returns: np.ndarray,
        composites: np.ndarray,
        result: CalibrationResult,
    ) -> None:
        """Compute annualised Sharpe of the calibrated threshold strategy."""
        pnl = self._threshold_pnl(
            returns, composites, result.buy_threshold, result.sell_threshold
        )
        if len(pnl) < 10:
            return
        mu = np.mean(pnl)
        sigma = np.std(pnl)
        if sigma < 1e-12:
            return
        result.overall_sharpe_calibrated = round(float(mu / sigma * np.sqrt(252)), 4)
