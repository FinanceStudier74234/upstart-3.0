"""
Dynamic Conditional Correlation (DCC) Engine — Time-Varying Correlation Analysis
DCC-GARCH(1,1) model (Engle 2002) with correlation regime detection,
conditional beta, correlation asymmetry, and multi-horizon forecasting.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_OBSERVATIONS = 100
_TRADING_DAYS_PER_YEAR = 252
_ANNUALIZATION_FACTOR = math.sqrt(_TRADING_DAYS_PER_YEAR)

# DCC optimiser settings
_MAX_ITER = 500
_FTOL = 1e-12
_GTOL = 1e-8

# GARCH(1,1) defaults
_GARCH_OMEGA_INIT = 1e-6
_GARCH_ALPHA_INIT = 0.05
_GARCH_BETA_INIT = 0.90

# DCC parameter defaults
_DCC_A_INIT = 0.05
_DCC_B_INIT = 0.90

# Correlation regime thresholds
_REGIME_DECORRELATED = 0.3
_REGIME_MODERATE = 0.6
_REGIME_HIGH = 0.8

_REGIME_LABELS: dict[str, tuple[float, float]] = {
    "decorrelated": (0.0, _REGIME_DECORRELATED),
    "moderate": (_REGIME_DECORRELATED, _REGIME_MODERATE),
    "high": (_REGIME_MODERATE, _REGIME_HIGH),
    "crisis": (_REGIME_HIGH, 1.0),
}

_FORECAST_HORIZONS: dict[str, int] = {
    "t+1": 1,
    "t+5": 5,
    "t+21": 21,
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DCCResult:
    """Complete DCC correlation analysis output."""

    # ── GARCH(1,1) parameters for UPST ──
    upst_omega: float | None = None
    upst_alpha: float | None = None
    upst_beta: float | None = None
    upst_garch_converged: bool = False
    upst_persistence: float | None = None

    # ── GARCH(1,1) parameters for SPY ──
    spy_omega: float | None = None
    spy_alpha: float | None = None
    spy_beta: float | None = None
    spy_garch_converged: bool = False
    spy_persistence: float | None = None

    # ── DCC parameters ──
    dcc_a: float | None = None
    dcc_b: float | None = None
    dcc_converged: bool = False
    dcc_persistence: float | None = None          # a + b
    dcc_log_likelihood: float | None = None

    # ── Conditional variance series ──
    upst_cond_vol: np.ndarray | None = None
    spy_cond_vol: np.ndarray | None = None

    # ── Time-varying correlation series ──
    correlation_series: np.ndarray | None = None
    current_correlation: float | None = None
    mean_correlation: float | None = None
    median_correlation: float | None = None
    min_correlation: float | None = None
    max_correlation: float | None = None
    correlation_std: float | None = None

    # ── Correlation regime detection ──
    current_regime: str = "moderate"
    regime_series: np.ndarray | None = None       # array of regime labels per timestep
    regime_counts: dict[str, int] = field(default_factory=dict)
    regime_fractions: dict[str, float] = field(default_factory=dict)
    correlation_breakdowns: list[int] = field(default_factory=list)   # indices of sharp drops
    correlation_spikes: list[int] = field(default_factory=list)       # indices of sharp rises

    # ── Correlation forecasts ──
    correlation_forecast: dict[str, float] = field(default_factory=dict)  # t+1, t+5, t+21

    # ── Conditional beta ──
    beta_series: np.ndarray | None = None
    current_beta: float | None = None
    mean_beta: float | None = None
    beta_std: float | None = None

    # ── Correlation asymmetry ──
    corr_down_markets: float | None = None        # correlation when SPY < 0
    corr_up_markets: float | None = None          # correlation when SPY > 0
    asymmetry_ratio: float | None = None          # down / up
    exceedance_corr_1pct: float | None = None     # correlation in worst 1% of SPY days
    exceedance_corr_5pct: float | None = None     # correlation in worst 5% of SPY days

    # ── Diagnostics ──
    n_observations: int = 0
    unconditional_correlation: float | None = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DCCEngine:
    """DCC-GARCH(1,1) engine for time-varying correlation analysis.

    Implements the two-step Engle (2002) estimator:
      Step 1 — fit univariate GARCH(1,1) to each return series,
      Step 2 — estimate DCC parameters from the standardised residuals.

    Produces filtered correlation path, regime classification, conditional
    beta, correlation forecasts, and asymmetry diagnostics.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def estimate(
        self,
        upst_returns: np.ndarray,
        spy_returns: np.ndarray,
    ) -> DCCResult:
        """Run full DCC-GARCH estimation and analytics.

        Parameters
        ----------
        upst_returns : np.ndarray
            1-D array of daily UPST returns.
        spy_returns : np.ndarray
            1-D array of daily SPY returns (same length).

        Returns
        -------
        DCCResult
            Populated result dataclass.
        """
        result = DCCResult()
        upst_r, spy_r = self._validate_inputs(upst_returns, spy_returns)
        if upst_r is None or spy_r is None:
            return result

        n = len(upst_r)
        result.n_observations = n
        result.unconditional_correlation = float(np.corrcoef(upst_r, spy_r)[0, 1])

        # ── Step 1: Univariate GARCH(1,1) ──
        upst_params, upst_h, upst_ok = self._fit_garch(upst_r)
        spy_params, spy_h, spy_ok = self._fit_garch(spy_r)

        result.upst_garch_converged = upst_ok
        result.spy_garch_converged = spy_ok

        if upst_ok:
            result.upst_omega, result.upst_alpha, result.upst_beta = upst_params
            result.upst_persistence = result.upst_alpha + result.upst_beta
        if spy_ok:
            result.spy_omega, result.spy_alpha, result.spy_beta = spy_params
            result.spy_persistence = result.spy_alpha + result.spy_beta

        if not (upst_ok and spy_ok):
            return result

        result.upst_cond_vol = np.sqrt(upst_h)
        result.spy_cond_vol = np.sqrt(spy_h)

        # Standardised residuals
        z_upst = upst_r / np.sqrt(upst_h)
        z_spy = spy_r / np.sqrt(spy_h)

        # ── Step 2: DCC estimation ──
        dcc_params, dcc_ok, dcc_ll = self._fit_dcc(z_upst, z_spy)
        result.dcc_converged = dcc_ok
        result.dcc_log_likelihood = dcc_ll

        if dcc_ok:
            result.dcc_a, result.dcc_b = dcc_params
            result.dcc_persistence = result.dcc_a + result.dcc_b
        else:
            # Fallback: use unconditional correlation as constant
            result.dcc_a = 0.0
            result.dcc_b = 0.0
            result.dcc_persistence = 0.0

        # ── Filtered correlation path ──
        rho_t = self._filter_correlation(z_upst, z_spy, result.dcc_a or 0.0, result.dcc_b or 0.0)
        result.correlation_series = rho_t
        result.current_correlation = float(rho_t[-1])
        result.mean_correlation = float(np.mean(rho_t))
        result.median_correlation = float(np.median(rho_t))
        result.min_correlation = float(np.min(rho_t))
        result.max_correlation = float(np.max(rho_t))
        result.correlation_std = float(np.std(rho_t))

        # ── Regime detection ──
        self._detect_regimes(rho_t, result)

        # ── Correlation forecasts ──
        self._forecast_correlation(z_upst, z_spy, result)

        # ── Conditional beta ──
        self._compute_conditional_beta(rho_t, upst_h, spy_h, result)

        # ── Correlation asymmetry ──
        self._compute_asymmetry(upst_r, spy_r, rho_t, result)

        return result

    # ------------------------------------------------------------------ #
    # Validation                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_inputs(
        upst: np.ndarray, spy: np.ndarray,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Validate and align return series."""
        if upst is None or spy is None:
            return None, None

        upst = np.asarray(upst, dtype=np.float64).ravel()
        spy = np.asarray(spy, dtype=np.float64).ravel()

        if len(upst) != len(spy):
            min_len = min(len(upst), len(spy))
            upst = upst[:min_len]
            spy = spy[:min_len]

        # Remove rows where either has NaN
        valid = ~(np.isnan(upst) | np.isnan(spy))
        upst = upst[valid]
        spy = spy[valid]

        if len(upst) < _MIN_OBSERVATIONS:
            return None, None

        return upst, spy

    # ------------------------------------------------------------------ #
    # Step 1: Univariate GARCH(1,1)                                      #
    # ------------------------------------------------------------------ #

    def _fit_garch(
        self, returns: np.ndarray,
    ) -> tuple[tuple[float, float, float], np.ndarray, bool]:
        """Fit GARCH(1,1) by MLE.

        Returns (omega, alpha, beta), conditional variance array, converged flag.
        """
        n = len(returns)
        var0 = float(np.var(returns))

        def neg_log_lik(params: np.ndarray) -> float:
            omega, alpha, beta = params
            if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1.0:
                return 1e12
            h = np.empty(n)
            h[0] = var0
            for t in range(1, n):
                h[t] = omega + alpha * returns[t - 1] ** 2 + beta * h[t - 1]
                if h[t] <= 0:
                    return 1e12
            ll = -0.5 * np.sum(np.log(2 * np.pi) + np.log(h) + returns**2 / h)
            return -ll

        x0 = np.array([_GARCH_OMEGA_INIT, _GARCH_ALPHA_INIT, _GARCH_BETA_INIT])
        bounds = [(1e-10, 1e-2), (1e-4, 0.5), (0.5, 0.9999)]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = minimize(
                    neg_log_lik, x0, method="L-BFGS-B", bounds=bounds,
                    options={"maxiter": _MAX_ITER, "ftol": _FTOL, "gtol": _GTOL},
                )
            except Exception:
                return (0.0, 0.0, 0.0), np.full(n, var0), False

        if not res.success and res.fun >= 1e11:
            return (0.0, 0.0, 0.0), np.full(n, var0), False

        omega, alpha, beta = res.x
        # Build conditional variance
        h = np.empty(n)
        h[0] = var0
        for t in range(1, n):
            h[t] = omega + alpha * returns[t - 1] ** 2 + beta * h[t - 1]

        return (float(omega), float(alpha), float(beta)), h, True

    # ------------------------------------------------------------------ #
    # Step 2: DCC estimation                                             #
    # ------------------------------------------------------------------ #

    def _fit_dcc(
        self, z1: np.ndarray, z2: np.ndarray,
    ) -> tuple[tuple[float, float], bool, float | None]:
        """Estimate DCC parameters (a, b) from standardised residuals.

        Returns (a, b), converged flag, log-likelihood.
        """
        n = len(z1)
        q_bar = float(np.mean(z1 * z2))  # unconditional covariance of std residuals
        s1_bar = float(np.mean(z1**2))
        s2_bar = float(np.mean(z2**2))

        # Q_bar as 2x2 unconditional correlation of z
        Q_bar_11 = s1_bar
        Q_bar_22 = s2_bar
        Q_bar_12 = q_bar

        def neg_log_lik(params: np.ndarray) -> float:
            a, b = params
            if a < 0 or b < 0 or a + b >= 1.0:
                return 1e12

            c = 1.0 - a - b
            q11 = Q_bar_11
            q22 = Q_bar_22
            q12 = Q_bar_12
            ll = 0.0

            for t in range(1, n):
                q11 = c * Q_bar_11 + a * z1[t - 1] ** 2 + b * q11
                q22 = c * Q_bar_22 + a * z2[t - 1] ** 2 + b * q22
                q12 = c * Q_bar_12 + a * z1[t - 1] * z2[t - 1] + b * q12

                denom = math.sqrt(q11 * q22)
                if denom <= 0:
                    return 1e12
                rho = q12 / denom
                rho = max(-0.9999, min(0.9999, rho))

                # DCC log-likelihood increment (conditional part only)
                det_R = 1.0 - rho**2
                if det_R <= 0:
                    return 1e12
                ll += math.log(det_R) + (z1[t] ** 2 + z2[t] ** 2 - 2 * rho * z1[t] * z2[t]) / det_R - z1[t] ** 2 - z2[t] ** 2

            return 0.5 * ll  # minimise positive quantity

        x0 = np.array([_DCC_A_INIT, _DCC_B_INIT])
        bounds = [(1e-6, 0.3), (0.5, 0.9999)]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = minimize(
                    neg_log_lik, x0, method="L-BFGS-B", bounds=bounds,
                    options={"maxiter": _MAX_ITER, "ftol": _FTOL, "gtol": _GTOL},
                )
            except Exception:
                return (0.0, 0.0), False, None

        if not res.success and res.fun >= 1e11:
            return (0.0, 0.0), False, None

        a_hat, b_hat = res.x
        return (float(a_hat), float(b_hat)), True, float(-res.fun)

    # ------------------------------------------------------------------ #
    # Filtered correlation path                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _filter_correlation(
        z1: np.ndarray, z2: np.ndarray, a: float, b: float,
    ) -> np.ndarray:
        """Run the DCC filter to produce time-varying correlation series."""
        n = len(z1)
        Q_bar_11 = float(np.mean(z1**2))
        Q_bar_22 = float(np.mean(z2**2))
        Q_bar_12 = float(np.mean(z1 * z2))
        c = 1.0 - a - b

        rho = np.empty(n)
        q11 = Q_bar_11
        q22 = Q_bar_22
        q12 = Q_bar_12

        # First observation: unconditional correlation
        denom0 = math.sqrt(Q_bar_11 * Q_bar_22)
        rho[0] = Q_bar_12 / denom0 if denom0 > 0 else 0.0

        for t in range(1, n):
            q11 = c * Q_bar_11 + a * z1[t - 1] ** 2 + b * q11
            q22 = c * Q_bar_22 + a * z2[t - 1] ** 2 + b * q22
            q12 = c * Q_bar_12 + a * z1[t - 1] * z2[t - 1] + b * q12

            denom = math.sqrt(q11 * q22)
            if denom > 0:
                rho[t] = q12 / denom
            else:
                rho[t] = rho[t - 1]

            # Clip to valid range
            rho[t] = max(-1.0, min(1.0, rho[t]))

        return rho

    # ------------------------------------------------------------------ #
    # Regime detection                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _detect_regimes(rho_t: np.ndarray, result: DCCResult) -> None:
        """Classify each observation into a correlation regime and detect events."""
        n = len(rho_t)
        abs_rho = np.abs(rho_t)

        regimes = np.empty(n, dtype=object)
        counts: dict[str, int] = {label: 0 for label in _REGIME_LABELS}

        for t in range(n):
            r = abs_rho[t]
            if r < _REGIME_DECORRELATED:
                regimes[t] = "decorrelated"
            elif r < _REGIME_MODERATE:
                regimes[t] = "moderate"
            elif r < _REGIME_HIGH:
                regimes[t] = "high"
            else:
                regimes[t] = "crisis"
            counts[regimes[t]] += 1

        result.regime_series = regimes
        result.regime_counts = counts
        result.regime_fractions = {k: v / n for k, v in counts.items()}
        result.current_regime = str(regimes[-1])

        # Detect correlation breakdowns and spikes
        # Breakdown: drop > 0.15 in a 5-day window
        # Spike: rise > 0.15 in a 5-day window
        window = 5
        for t in range(window, n):
            delta = rho_t[t] - rho_t[t - window]
            if delta < -0.15:
                result.correlation_breakdowns.append(t)
            elif delta > 0.15:
                result.correlation_spikes.append(t)

    # ------------------------------------------------------------------ #
    # Correlation forecasting                                            #
    # ------------------------------------------------------------------ #

    def _forecast_correlation(
        self, z1: np.ndarray, z2: np.ndarray, result: DCCResult,
    ) -> None:
        """Project correlation at t+1, t+5, t+21 using DCC mean reversion."""
        a = result.dcc_a or 0.0
        b = result.dcc_b or 0.0
        rho_current = result.current_correlation
        rho_bar = result.unconditional_correlation

        if rho_current is None or rho_bar is None:
            return

        persistence = a + b
        for label, h in _FORECAST_HORIZONS.items():
            if persistence > 0 and persistence < 1.0:
                # Mean-reverting forecast: rho_{t+h} = rho_bar + (a+b)^h * (rho_t - rho_bar)
                forecast = rho_bar + persistence**h * (rho_current - rho_bar)
            else:
                forecast = rho_current
            result.correlation_forecast[label] = float(max(-1.0, min(1.0, forecast)))

    # ------------------------------------------------------------------ #
    # Conditional beta                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_conditional_beta(
        rho_t: np.ndarray,
        upst_h: np.ndarray,
        spy_h: np.ndarray,
        result: DCCResult,
    ) -> None:
        """Compute time-varying beta: beta_t = rho_t * sigma_UPST_t / sigma_SPY_t."""
        sigma_upst = np.sqrt(upst_h)
        sigma_spy = np.sqrt(spy_h)

        # Avoid division by zero
        valid = sigma_spy > 0
        beta_t = np.where(valid, rho_t * sigma_upst / sigma_spy, 0.0)

        result.beta_series = beta_t
        result.current_beta = float(beta_t[-1])
        result.mean_beta = float(np.mean(beta_t))
        result.beta_std = float(np.std(beta_t))

    # ------------------------------------------------------------------ #
    # Correlation asymmetry                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_asymmetry(
        upst_r: np.ndarray,
        spy_r: np.ndarray,
        rho_t: np.ndarray,
        result: DCCResult,
    ) -> None:
        """Measure correlation asymmetry between up and down markets."""
        n = len(spy_r)
        if n < _MIN_OBSERVATIONS:
            return

        # Down-market vs up-market correlation
        down_mask = spy_r < 0
        up_mask = spy_r >= 0

        if np.sum(down_mask) > 20:
            result.corr_down_markets = float(np.mean(rho_t[down_mask]))
        if np.sum(up_mask) > 20:
            result.corr_up_markets = float(np.mean(rho_t[up_mask]))

        if result.corr_down_markets is not None and result.corr_up_markets is not None:
            if abs(result.corr_up_markets) > 1e-8:
                result.asymmetry_ratio = result.corr_down_markets / result.corr_up_markets

        # Exceedance correlations — correlation conditional on extreme SPY days
        spy_pct_1 = np.percentile(spy_r, 1)
        spy_pct_5 = np.percentile(spy_r, 5)

        mask_1 = spy_r <= spy_pct_1
        mask_5 = spy_r <= spy_pct_5

        if np.sum(mask_1) >= 5:
            # Use realised co-movement in the tail as exceedance correlation
            result.exceedance_corr_1pct = float(np.mean(rho_t[mask_1]))
        if np.sum(mask_5) >= 5:
            result.exceedance_corr_5pct = float(np.mean(rho_t[mask_5]))
