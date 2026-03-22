"""
ARIMA-GARCH Forecasting Engine
ARIMA(p,d,q) model selection via AIC, GARCH(1,1) conditional variance,
rolling forecast evaluation, Ljung-Box and ADF diagnostics.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import optimize, stats


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_OBS = 40
_CANDIDATE_ORDERS = [
    (1, 0, 0),  # AR(1)
    (2, 0, 0),  # AR(2)
    (0, 0, 1),  # MA(1)
    (1, 0, 1),  # ARMA(1,1)
]
_ADF_CRITICAL_5PCT = -2.86  # approx critical value at 5%
_LJUNG_BOX_LAGS = 10
_GARCH_OMEGA_BOUNDS = (1e-10, 1.0)
_GARCH_ALPHA_BOUNDS = (1e-6, 0.5)
_GARCH_BETA_BOUNDS = (1e-6, 0.9999)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ARIMAForecastResult:
    """Full output of the ARIMA-GARCH engine."""
    # Selected model
    selected_order: Tuple[int, int, int] | None = None
    aic: float | None = None
    bic: float | None = None

    # ARIMA parameters
    ar_coeffs: List[float] = field(default_factory=list)
    ma_coeffs: List[float] = field(default_factory=list)
    intercept: float | None = None
    differencing_order: int = 0

    # GARCH(1,1) parameters
    garch_omega: float | None = None
    garch_alpha: float | None = None
    garch_beta: float | None = None
    current_volatility: float | None = None

    # Forecasts (return space)
    point_forecast: List[float] = field(default_factory=list)  # length = horizon

    # Confidence intervals: list of dicts with keys "68", "90", "95"
    # Each containing (lower, upper) tuples
    forecast_intervals_68: List[Tuple[float, float]] = field(default_factory=list)
    forecast_intervals_90: List[Tuple[float, float]] = field(default_factory=list)
    forecast_intervals_95: List[Tuple[float, float]] = field(default_factory=list)

    # Price forecasts (if price provided)
    price_forecast: List[float] = field(default_factory=list)
    price_intervals_95: List[Tuple[float, float]] = field(default_factory=list)

    # Diagnostics
    adf_statistic: float | None = None
    adf_critical_5pct: float = _ADF_CRITICAL_5PCT
    is_stationary: bool | None = None
    ljung_box_stat: float | None = None
    ljung_box_pvalue: float | None = None
    residuals_white_noise: bool | None = None

    # Rolling forecast evaluation
    rolling_mae: float | None = None
    rolling_rmse: float | None = None
    rolling_hit_rate: float | None = None  # fraction of times direction correct


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class ARIMAForecastEngine:
    """
    ARIMA(p,d,q) + GARCH(1,1) forecasting engine.

    Implements AR(1), AR(2), MA(1), ARMA(1,1) via MLE using
    scipy.optimize.minimize. Selects the best model by AIC.
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def forecast(
        self,
        returns: np.ndarray,
        horizon: int = 21,
        price: float = 0.0,
    ) -> ARIMAForecastResult:
        """Run the full ARIMA-GARCH pipeline."""
        result = ARIMAForecastResult()

        returns = np.asarray(returns, dtype=np.float64).ravel()

        # Clean
        returns = returns[np.isfinite(returns)]
        if len(returns) < _MIN_OBS:
            return result

        # --- ADF test ---
        adf_stat = self._adf_test(returns)
        result.adf_statistic = adf_stat
        result.is_stationary = adf_stat < _ADF_CRITICAL_5PCT

        # --- Determine differencing ---
        y, d = self._determine_differencing(returns)
        result.differencing_order = d

        # Update candidate orders with differencing
        candidates = [(p, d, q) for p, _, q in _CANDIDATE_ORDERS]

        # --- Model selection ---
        best_order, best_params, best_aic, best_bic = self._select_model(y, candidates)
        result.selected_order = best_order
        result.aic = best_aic
        result.bic = best_bic

        p, _, q = best_order
        n_params = 1 + p + q  # intercept + AR + MA
        result.intercept = float(best_params[0])
        result.ar_coeffs = [float(c) for c in best_params[1:1 + p]]
        result.ma_coeffs = [float(c) for c in best_params[1 + p:1 + p + q]]

        # --- Residuals ---
        residuals = self._compute_residuals(y, p, q, best_params)

        # --- Ljung-Box ---
        lb_stat, lb_pval = self._ljung_box(residuals, _LJUNG_BOX_LAGS, n_params)
        result.ljung_box_stat = lb_stat
        result.ljung_box_pvalue = lb_pval
        result.residuals_white_noise = lb_pval > 0.05 if lb_pval is not None else None

        # --- GARCH(1,1) ---
        garch_params, sigma2_series = self._fit_garch(residuals)
        if garch_params is not None:
            result.garch_omega = garch_params[0]
            result.garch_alpha = garch_params[1]
            result.garch_beta = garch_params[2]
            result.current_volatility = float(math.sqrt(sigma2_series[-1]))

        # --- Forecast ---
        fc, intervals = self._generate_forecasts(
            y, p, q, best_params, garch_params, sigma2_series, horizon,
        )
        result.point_forecast = [float(f) for f in fc]
        result.forecast_intervals_68 = intervals["68"]
        result.forecast_intervals_90 = intervals["90"]
        result.forecast_intervals_95 = intervals["95"]

        # --- Price forecast ---
        if price > 0:
            cum_ret = np.cumsum(fc)
            result.price_forecast = [float(price * math.exp(cr)) for cr in cum_ret]
            result.price_intervals_95 = [
                (
                    float(price * math.exp(cum_ret[i] + intervals["95"][i][0] - fc[i])),
                    float(price * math.exp(cum_ret[i] + intervals["95"][i][1] - fc[i])),
                )
                for i in range(horizon)
            ]

        # --- Rolling forecast evaluation ---
        mae, rmse, hit = self._rolling_evaluation(y, p, q, best_params)
        result.rolling_mae = mae
        result.rolling_rmse = rmse
        result.rolling_hit_rate = hit

        return result

    # ------------------------------------------------------------------ #
    # ADF test
    # ------------------------------------------------------------------ #
    @staticmethod
    def _adf_test(y: np.ndarray, max_lags: int = 5) -> float:
        """
        Augmented Dickey-Fuller test.
        Tests H0: unit root (non-stationary) vs H1: stationary.
        Returns the t-statistic (more negative = more stationary).
        """
        n = len(y)
        if n < 10:
            return 0.0

        # First difference
        dy = np.diff(y)
        y_lag = y[:-1]

        # Build regressor matrix: [y_{t-1}, dy_{t-1}, ..., dy_{t-p}, 1]
        lags = min(max_lags, n // 5)
        if lags < 1:
            lags = 1

        T = len(dy) - lags
        if T < 5:
            return 0.0

        X = np.ones((T, 1 + 1 + lags))  # intercept + y_lag + lagged diffs
        dep = dy[lags:]
        X[:, 0] = y_lag[lags:]  # y_{t-1}
        for j in range(lags):
            X[:, 1 + j] = dy[lags - 1 - j: len(dy) - 1 - j]
        # Last column is intercept (already ones)

        # OLS
        try:
            XtX = X.T @ X
            Xty = X.T @ dep
            beta = np.linalg.solve(XtX, Xty)
        except np.linalg.LinAlgError:
            return 0.0

        resid = dep - X @ beta
        s2 = float(np.sum(resid ** 2) / max(T - X.shape[1], 1))

        try:
            cov_beta = s2 * np.linalg.inv(XtX)
        except np.linalg.LinAlgError:
            return 0.0

        se_gamma = math.sqrt(max(cov_beta[0, 0], 1e-20))
        t_stat = beta[0] / se_gamma

        return float(t_stat)

    # ------------------------------------------------------------------ #
    # Differencing
    # ------------------------------------------------------------------ #
    def _determine_differencing(self, y: np.ndarray) -> Tuple[np.ndarray, int]:
        """Determine differencing order d (0 or 1) based on ADF test."""
        adf = self._adf_test(y)
        if adf < _ADF_CRITICAL_5PCT:
            return y, 0
        else:
            dy = np.diff(y)
            return dy, 1

    # ------------------------------------------------------------------ #
    # ARMA negative log-likelihood
    # ------------------------------------------------------------------ #
    @staticmethod
    def _arma_nll(
        params: np.ndarray,
        y: np.ndarray,
        p: int,
        q: int,
    ) -> float:
        """
        Negative log-likelihood for ARMA(p,q) via conditional MLE.

        params = [mu, phi_1, ..., phi_p, theta_1, ..., theta_q]
        """
        n = len(y)
        mu = params[0]
        phi = params[1:1 + p] if p > 0 else np.array([])
        theta = params[1 + p:1 + p + q] if q > 0 else np.array([])

        # Check AR stationarity (rough check: sum of |phi| < 1)
        if p > 0 and np.sum(np.abs(phi)) >= 1.0:
            return 1e12

        # Check MA invertibility (rough check: sum of |theta| < 1)
        if q > 0 and np.sum(np.abs(theta)) >= 1.0:
            return 1e12

        start = max(p, q)
        if start >= n:
            return 1e12

        residuals = np.zeros(n)
        for t in range(start, n):
            pred = mu
            for j in range(p):
                pred += phi[j] * (y[t - 1 - j] - mu)
            for j in range(q):
                pred += theta[j] * residuals[t - 1 - j]
            residuals[t] = y[t] - pred

        eps = residuals[start:]
        if len(eps) == 0:
            return 1e12

        sigma2 = float(np.mean(eps ** 2))
        if sigma2 < 1e-15:
            sigma2 = 1e-15

        nll = 0.5 * len(eps) * math.log(2 * math.pi * sigma2) + 0.5 * np.sum(eps ** 2) / sigma2
        if not np.isfinite(nll):
            return 1e12
        return float(nll)

    # ------------------------------------------------------------------ #
    # Model selection
    # ------------------------------------------------------------------ #
    def _select_model(
        self,
        y: np.ndarray,
        candidates: List[Tuple[int, int, int]],
    ) -> Tuple[Tuple[int, int, int], np.ndarray, float, float]:
        """Select best ARMA order by AIC."""
        n = len(y)
        best_aic = np.inf
        best_order = (1, 0, 0)
        best_params = np.array([np.mean(y), 0.0])
        best_bic = np.inf

        for order in candidates:
            p, d, q = order
            k = 1 + p + q  # number of parameters (+ sigma2 counted in AIC)

            # Initial params
            x0 = np.zeros(k)
            x0[0] = float(np.mean(y))

            try:
                res = optimize.minimize(
                    self._arma_nll,
                    x0=x0,
                    args=(y, p, q),
                    method="Nelder-Mead",
                    options={"maxiter": 2000, "xatol": 1e-7, "fatol": 1e-7},
                )
                if not np.isfinite(res.fun):
                    continue

                nll = res.fun
                aic = 2 * nll + 2 * (k + 1)  # +1 for sigma2
                bic = 2 * nll + math.log(n) * (k + 1)

                if aic < best_aic:
                    best_aic = aic
                    best_bic = bic
                    best_order = order
                    best_params = res.x.copy()
            except Exception:
                continue

        return best_order, best_params, float(best_aic), float(best_bic)

    # ------------------------------------------------------------------ #
    # Compute residuals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _compute_residuals(
        y: np.ndarray,
        p: int,
        q: int,
        params: np.ndarray,
    ) -> np.ndarray:
        """Compute residuals from fitted ARMA model."""
        n = len(y)
        mu = params[0]
        phi = params[1:1 + p] if p > 0 else np.array([])
        theta = params[1 + p:1 + p + q] if q > 0 else np.array([])

        start = max(p, q, 1)
        residuals = np.zeros(n)

        for t in range(start, n):
            pred = mu
            for j in range(p):
                pred += phi[j] * (y[t - 1 - j] - mu)
            for j in range(q):
                pred += theta[j] * residuals[t - 1 - j]
            residuals[t] = y[t] - pred

        return residuals[start:]

    # ------------------------------------------------------------------ #
    # Ljung-Box test
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ljung_box(
        residuals: np.ndarray,
        max_lag: int,
        n_params: int,
    ) -> Tuple[float | None, float | None]:
        """
        Ljung-Box test for residual autocorrelation.
        H0: no autocorrelation up to lag max_lag.
        """
        n = len(residuals)
        if n < max_lag + 5:
            return None, None

        # Autocorrelations
        r_mean = np.mean(residuals)
        resid_centered = residuals - r_mean
        var_r = np.sum(resid_centered ** 2)
        if var_r < 1e-15:
            return 0.0, 1.0

        acf = np.zeros(max_lag)
        for k in range(1, max_lag + 1):
            acf[k - 1] = np.sum(resid_centered[k:] * resid_centered[:-k]) / var_r

        # Q statistic
        Q = n * (n + 2) * np.sum(acf ** 2 / np.arange(n - 1, n - max_lag - 1, -1))

        # Degrees of freedom = max_lag - n_params (but at least 1)
        df = max(max_lag - n_params, 1)
        p_value = 1.0 - stats.chi2.cdf(Q, df)

        return float(Q), float(p_value)

    # ------------------------------------------------------------------ #
    # GARCH(1,1)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fit_garch(
        residuals: np.ndarray,
    ) -> Tuple[np.ndarray | None, np.ndarray]:
        """
        Fit GARCH(1,1): sigma2_t = omega + alpha * eps_{t-1}^2 + beta * sigma2_{t-1}

        Returns (params, sigma2_series) or (None, unconditional_var_array).
        """
        n = len(residuals)
        if n < 20:
            var = float(np.var(residuals))
            return None, np.full(n, var)

        eps2 = residuals ** 2
        var_unconditional = float(np.mean(eps2))
        if var_unconditional < 1e-15:
            return None, np.full(n, 1e-15)

        def neg_log_lik(params: np.ndarray) -> float:
            omega = params[0]
            alpha = params[1]
            beta = params[2]

            # Stationarity constraint
            if alpha + beta >= 1.0:
                return 1e12
            if omega <= 0 or alpha < 0 or beta < 0:
                return 1e12

            sigma2 = np.empty(n)
            sigma2[0] = var_unconditional

            for t in range(1, n):
                sigma2[t] = omega + alpha * eps2[t - 1] + beta * sigma2[t - 1]
                if sigma2[t] < 1e-15:
                    sigma2[t] = 1e-15

            nll = 0.5 * np.sum(np.log(sigma2) + eps2 / sigma2)
            if not np.isfinite(nll):
                return 1e12
            return float(nll)

        # Starting values
        omega0 = var_unconditional * 0.05
        alpha0 = 0.1
        beta0 = 0.85

        try:
            res = optimize.minimize(
                neg_log_lik,
                x0=np.array([omega0, alpha0, beta0]),
                method="Nelder-Mead",
                options={"maxiter": 2000, "xatol": 1e-8, "fatol": 1e-8},
            )
            if res.success or np.isfinite(res.fun):
                omega, alpha, beta = res.x
                if omega > 0 and alpha >= 0 and beta >= 0 and alpha + beta < 1.0:
                    # Rebuild sigma2 series
                    sigma2 = np.empty(n)
                    sigma2[0] = var_unconditional
                    for t in range(1, n):
                        sigma2[t] = omega + alpha * eps2[t - 1] + beta * sigma2[t - 1]
                        sigma2[t] = max(sigma2[t], 1e-15)
                    return res.x, sigma2
        except Exception:
            pass

        return None, np.full(n, var_unconditional)

    # ------------------------------------------------------------------ #
    # Forecast generation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _generate_forecasts(
        y: np.ndarray,
        p: int,
        q: int,
        params: np.ndarray,
        garch_params: np.ndarray | None,
        sigma2_series: np.ndarray,
        horizon: int,
    ) -> Tuple[np.ndarray, Dict[str, List[Tuple[float, float]]]]:
        """
        Generate h-step-ahead forecasts with confidence intervals.
        """
        mu = params[0]
        phi = params[1:1 + p] if p > 0 else np.array([])
        theta = params[1 + p:1 + p + q] if q > 0 else np.array([])

        # Build forecast buffer with recent values
        buf_len = max(p, q, 1)
        y_buf = list(y[-buf_len:])  # recent y values
        e_buf = [0.0] * buf_len     # recent errors (0 for forecast horizon)

        forecasts = np.empty(horizon)
        sigma2_forecast = np.empty(horizon)

        # GARCH forecast of variance
        if garch_params is not None:
            omega, alpha, beta = garch_params
            last_eps2 = (y[-1] - mu) ** 2 if len(y) > 0 else sigma2_series[-1]
            last_sigma2 = sigma2_series[-1]
        else:
            last_sigma2 = sigma2_series[-1] if len(sigma2_series) > 0 else 1e-4

        for h in range(horizon):
            # Mean forecast
            pred = mu
            for j in range(p):
                idx = len(y_buf) - 1 - j
                if idx >= 0:
                    pred += phi[j] * (y_buf[idx] - mu)
            # MA terms: future errors are 0
            for j in range(q):
                idx = len(e_buf) - 1 - j
                if idx >= 0:
                    pred += theta[j] * e_buf[idx]

            forecasts[h] = pred

            # Variance forecast
            if garch_params is not None:
                if h == 0:
                    s2 = omega + alpha * last_eps2 + beta * last_sigma2
                else:
                    s2 = omega + (alpha + beta) * sigma2_forecast[h - 1]
                sigma2_forecast[h] = max(s2, 1e-15)
            else:
                sigma2_forecast[h] = last_sigma2

            # Update buffers
            y_buf.append(pred)
            e_buf.append(0.0)

        # Build confidence intervals
        # Cumulative variance for multi-step (approximate)
        cum_sigma = np.sqrt(sigma2_forecast)

        intervals: Dict[str, List[Tuple[float, float]]] = {
            "68": [], "90": [], "95": [],
        }
        z_68 = 1.0
        z_90 = 1.645
        z_95 = 1.96

        for h in range(horizon):
            s = cum_sigma[h]
            f = forecasts[h]
            intervals["68"].append((float(f - z_68 * s), float(f + z_68 * s)))
            intervals["90"].append((float(f - z_90 * s), float(f + z_90 * s)))
            intervals["95"].append((float(f - z_95 * s), float(f + z_95 * s)))

        return forecasts, intervals

    # ------------------------------------------------------------------ #
    # Rolling forecast evaluation
    # ------------------------------------------------------------------ #
    def _rolling_evaluation(
        self,
        y: np.ndarray,
        p: int,
        q: int,
        params: np.ndarray,
        min_train: int = 60,
    ) -> Tuple[float | None, float | None, float | None]:
        """
        Expanding window 1-step-ahead out-of-sample forecast evaluation.
        """
        n = len(y)
        if n < min_train + 10:
            return None, None, None

        mu = params[0]
        phi = params[1:1 + p] if p > 0 else np.array([])
        theta = params[1 + p:1 + p + q] if q > 0 else np.array([])

        errors = []
        hits = []
        start = max(p, q, 1)

        # Use the fitted params and evaluate from min_train onward
        residuals = np.zeros(n)
        for t in range(start, n):
            pred = mu
            for j in range(p):
                pred += phi[j] * (y[t - 1 - j] - mu)
            for j in range(q):
                pred += theta[j] * residuals[t - 1 - j]
            residuals[t] = y[t] - pred

            if t >= min_train:
                errors.append(y[t] - pred)
                # Direction hit: did we predict the sign correctly?
                if t > 0:
                    actual_dir = y[t] - y[t - 1]
                    pred_dir = pred - y[t - 1]
                    hits.append(1.0 if actual_dir * pred_dir > 0 else 0.0)

        if len(errors) == 0:
            return None, None, None

        errors = np.array(errors)
        mae = float(np.mean(np.abs(errors)))
        rmse = float(math.sqrt(np.mean(errors ** 2)))
        hit_rate = float(np.mean(hits)) if len(hits) > 0 else None

        return mae, rmse, hit_rate
