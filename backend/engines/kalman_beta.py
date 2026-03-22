"""
Kalman Filter Beta Engine
Time-varying beta estimation via state-space modeling with RTS smoother,
adaptive noise estimation, structural break detection, and beta forecasting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
from scipy import optimize, stats


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_OBS = 30
_INNOVATION_BREAK_THRESHOLD = 3.0  # multiples of expected innovation variance
_DEFAULT_TRANSITION_NOISE = 1e-4
_DEFAULT_OBSERVATION_NOISE = 1e-2
_FORECAST_HORIZONS = (5, 21)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class KalmanBetaResult:
    """Full output of the Kalman beta engine."""
    # Current filtered estimates
    current_beta: float | None = None
    beta_std: float | None = None
    alpha_filtered: float | None = None
    r_squared_filtered: float | None = None

    # Full series
    beta_series: List[float] = field(default_factory=list)
    beta_smoothed_series: List[float] = field(default_factory=list)
    beta_std_series: List[float] = field(default_factory=list)

    # Forecasts
    beta_forecast_5d: float | None = None
    beta_forecast_21d: float | None = None
    beta_forecast_5d_upper: float | None = None
    beta_forecast_5d_lower: float | None = None
    beta_forecast_21d_upper: float | None = None
    beta_forecast_21d_lower: float | None = None

    # Structural breaks (indices where innovation exceeded threshold)
    structural_breaks: List[int] = field(default_factory=list)

    # Adaptive noise estimates
    observation_noise: float | None = None
    transition_noise: float | None = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class KalmanBetaEngine:
    """
    Kalman filter for time-varying beta estimation.

    State-space model
    -----------------
    Observation:  y_t = alpha + beta_t * x_t + eps_t,   eps_t ~ N(0, R)
    Transition:   beta_t = beta_{t-1} + eta_t,           eta_t ~ N(0, Q)

    Provides filtered, smoothed, and forecast beta with adaptive noise
    estimation and structural break detection.
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def filter(
        self,
        upst_returns: np.ndarray,
        spy_returns: np.ndarray,
    ) -> KalmanBetaResult:
        """Run the full Kalman pipeline and return results."""
        result = KalmanBetaResult()

        # --- Input validation ---
        upst_returns = np.asarray(upst_returns, dtype=np.float64).ravel()
        spy_returns = np.asarray(spy_returns, dtype=np.float64).ravel()

        n = min(len(upst_returns), len(spy_returns))
        if n < _MIN_OBS:
            return result

        y = upst_returns[:n].copy()
        x = spy_returns[:n].copy()

        # Replace NaN / Inf with 0
        mask = np.isfinite(y) & np.isfinite(x)
        y[~mask] = 0.0
        x[~mask] = 0.0

        # --- OLS for initial values ---
        alpha_ols, beta_ols = self._ols(y, x)

        # --- Adaptive noise estimation ---
        Q, R = self._estimate_noise(y, x, alpha_ols, beta_ols)
        result.observation_noise = float(R)
        result.transition_noise = float(Q)

        # --- Kalman filter ---
        betas, Ps, innovations, S_vals = self._kalman_filter(
            y, x, alpha_ols, beta_ols, Q, R,
        )

        # --- Rauch-Tung-Striebel smoother ---
        betas_smooth, Ps_smooth = self._rts_smoother(betas, Ps, Q)

        # --- Structural break detection ---
        breaks = self._detect_breaks(innovations, S_vals)

        # --- Alpha & R² from filtered estimates ---
        alpha_filt, r2_filt = self._filtered_stats(y, x, betas[1:])

        # --- Forecasting ---
        beta_last = betas[-1]
        P_last = Ps[-1]
        forecasts = self._forecast_beta(beta_last, P_last, Q)

        # --- Pack result ---
        result.current_beta = float(beta_last)
        result.beta_std = float(math.sqrt(max(P_last, 0.0)))
        result.alpha_filtered = float(alpha_filt)
        result.r_squared_filtered = float(r2_filt)

        result.beta_series = [float(b) for b in betas[1:]]  # skip prior
        result.beta_smoothed_series = [float(b) for b in betas_smooth[1:]]
        result.beta_std_series = [float(math.sqrt(max(p, 0.0))) for p in Ps[1:]]

        result.beta_forecast_5d = forecasts[5]["mean"]
        result.beta_forecast_21d = forecasts[21]["mean"]
        result.beta_forecast_5d_upper = forecasts[5]["upper"]
        result.beta_forecast_5d_lower = forecasts[5]["lower"]
        result.beta_forecast_21d_upper = forecasts[21]["upper"]
        result.beta_forecast_21d_lower = forecasts[21]["lower"]

        result.structural_breaks = breaks

        return result

    # ------------------------------------------------------------------ #
    # OLS baseline
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ols(y: np.ndarray, x: np.ndarray) -> Tuple[float, float]:
        """Simple OLS: y = alpha + beta * x.  Returns (alpha, beta)."""
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        cov_xy = np.mean((x - x_mean) * (y - y_mean))
        var_x = np.mean((x - x_mean) ** 2)
        if var_x < 1e-15:
            return float(y_mean), 0.0
        beta = cov_xy / var_x
        alpha = y_mean - beta * x_mean
        return float(alpha), float(beta)

    # ------------------------------------------------------------------ #
    # Adaptive noise estimation (innovations-based MLE)
    # ------------------------------------------------------------------ #
    def _estimate_noise(
        self,
        y: np.ndarray,
        x: np.ndarray,
        alpha: float,
        beta_init: float,
    ) -> Tuple[float, float]:
        """
        Estimate Q (transition noise) and R (observation noise) via
        maximum likelihood on the innovations sequence.
        """
        def neg_log_lik(params: np.ndarray) -> float:
            log_Q = params[0]
            log_R = params[1]
            Q = math.exp(log_Q)
            R = math.exp(log_R)

            beta = beta_init
            P = 1.0
            nll = 0.0

            for t in range(len(y)):
                # Predict
                beta_pred = beta
                P_pred = P + Q

                # Innovation
                H_t = x[t]
                v_t = y[t] - alpha - beta_pred * H_t
                S_t = H_t * P_pred * H_t + R

                if S_t < 1e-15:
                    S_t = 1e-15

                # Log-likelihood contribution
                nll += 0.5 * (math.log(S_t) + v_t * v_t / S_t)

                # Update
                K_t = P_pred * H_t / S_t
                beta = beta_pred + K_t * v_t
                P = P_pred - K_t * H_t * P_pred
                P = max(P, 1e-15)

            return nll

        # Optimise in log-space to ensure positivity
        init_log_Q = math.log(_DEFAULT_TRANSITION_NOISE)
        init_log_R = math.log(_DEFAULT_OBSERVATION_NOISE)

        try:
            res = optimize.minimize(
                neg_log_lik,
                x0=np.array([init_log_Q, init_log_R]),
                method="Nelder-Mead",
                options={"maxiter": 500, "xatol": 1e-6, "fatol": 1e-6},
            )
            if res.success or res.fun < neg_log_lik(np.array([init_log_Q, init_log_R])):
                Q = math.exp(res.x[0])
                R = math.exp(res.x[1])
            else:
                Q = _DEFAULT_TRANSITION_NOISE
                R = _DEFAULT_OBSERVATION_NOISE
        except Exception:
            Q = _DEFAULT_TRANSITION_NOISE
            R = _DEFAULT_OBSERVATION_NOISE

        # Clamp to sensible range
        Q = np.clip(Q, 1e-8, 1.0)
        R = np.clip(R, 1e-8, 10.0)

        return float(Q), float(R)

    # ------------------------------------------------------------------ #
    # Kalman filter
    # ------------------------------------------------------------------ #
    @staticmethod
    def _kalman_filter(
        y: np.ndarray,
        x: np.ndarray,
        alpha: float,
        beta_init: float,
        Q: float,
        R: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Standard Kalman filter.

        Returns
        -------
        betas : array of length n+1 (index 0 is prior)
        Ps    : array of length n+1
        innovations : array of length n
        S_vals      : array of length n (innovation variances)
        """
        n = len(y)
        betas = np.empty(n + 1)
        Ps = np.empty(n + 1)
        innovations = np.empty(n)
        S_vals = np.empty(n)

        betas[0] = beta_init
        Ps[0] = 1.0  # diffuse prior

        for t in range(n):
            # --- Predict ---
            beta_pred = betas[t]
            P_pred = Ps[t] + Q

            # --- Innovation ---
            H_t = x[t]
            v_t = y[t] - alpha - beta_pred * H_t
            S_t = H_t * P_pred * H_t + R
            S_t = max(S_t, 1e-15)

            innovations[t] = v_t
            S_vals[t] = S_t

            # --- Update ---
            K_t = P_pred * H_t / S_t
            betas[t + 1] = beta_pred + K_t * v_t
            Ps[t + 1] = P_pred - K_t * H_t * P_pred
            Ps[t + 1] = max(Ps[t + 1], 1e-15)

        return betas, Ps, innovations, S_vals

    # ------------------------------------------------------------------ #
    # RTS smoother
    # ------------------------------------------------------------------ #
    @staticmethod
    def _rts_smoother(
        betas: np.ndarray,
        Ps: np.ndarray,
        Q: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Rauch-Tung-Striebel smoother.

        Parameters
        ----------
        betas : filtered state estimates (length n+1, index 0 is prior)
        Ps    : filtered covariances   (length n+1)
        Q     : transition noise variance
        """
        n = len(betas) - 1
        betas_s = betas.copy()
        Ps_s = Ps.copy()

        for t in range(n - 1, -1, -1):
            P_pred = Ps[t] + Q
            if P_pred < 1e-15:
                P_pred = 1e-15
            L_t = Ps[t] / P_pred

            betas_s[t] = betas[t] + L_t * (betas_s[t + 1] - betas[t])
            Ps_s[t] = Ps[t] + L_t * L_t * (Ps_s[t + 1] - P_pred)
            Ps_s[t] = max(Ps_s[t], 1e-15)

        return betas_s, Ps_s

    # ------------------------------------------------------------------ #
    # Structural break detection
    # ------------------------------------------------------------------ #
    @staticmethod
    def _detect_breaks(
        innovations: np.ndarray,
        S_vals: np.ndarray,
    ) -> List[int]:
        """
        Flag time indices where the normalised innovation exceeds the
        threshold, indicating a structural break in beta.
        """
        breaks: List[int] = []
        for t in range(len(innovations)):
            if S_vals[t] < 1e-15:
                continue
            normalised_sq = (innovations[t] ** 2) / S_vals[t]
            # Under H0 (correct model), normalised_sq ~ chi2(1)
            # 3x expected variance means normalised_sq > 3
            if normalised_sq > _INNOVATION_BREAK_THRESHOLD ** 2:
                breaks.append(int(t))
        return breaks

    # ------------------------------------------------------------------ #
    # Filtered alpha & R²
    # ------------------------------------------------------------------ #
    @staticmethod
    def _filtered_stats(
        y: np.ndarray,
        x: np.ndarray,
        beta_series: np.ndarray,
    ) -> Tuple[float, float]:
        """Compute filtered alpha and R² from the time-varying beta series."""
        n = len(y)
        fitted = np.empty(n)
        # Use time-varying beta to compute fitted values
        residuals_for_alpha = y - beta_series * x
        alpha = float(np.mean(residuals_for_alpha))

        fitted = alpha + beta_series * x
        residuals = y - fitted
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)

        r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-15 else 0.0
        r2 = float(np.clip(r2, 0.0, 1.0))

        return alpha, r2

    # ------------------------------------------------------------------ #
    # Beta forecast
    # ------------------------------------------------------------------ #
    @staticmethod
    def _forecast_beta(
        beta_last: float,
        P_last: float,
        Q: float,
    ) -> dict:
        """
        Project beta forward under the random walk model.

        beta_{t+h} = beta_t   (point forecast)
        Var(beta_{t+h}) = P_t + h * Q

        Returns dict keyed by horizon with mean, upper, lower (95% band).
        """
        forecasts = {}
        z_95 = 1.96

        for h in _FORECAST_HORIZONS:
            var_h = P_last + h * Q
            std_h = math.sqrt(max(var_h, 0.0))
            forecasts[h] = {
                "mean": float(beta_last),
                "upper": float(beta_last + z_95 * std_h),
                "lower": float(beta_last - z_95 * std_h),
            }

        return forecasts
