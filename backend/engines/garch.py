"""
GARCH Volatility Modeling Engine — Conditional Variance Analysis
GARCH(1,1), EGARCH, GJR-GARCH with volatility term structure,
regime classification, vol-of-vol, and shock half-life analytics.
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

_HORIZON_MAP: dict[str, int] = {
    "1d": 1,
    "1w": 5,
    "1m": 21,
    "3m": 63,
    "6m": 126,
}

_REGIME_LABELS: list[str] = ["low_vol", "normal_vol", "high_vol", "crisis_vol"]
_REGIME_QUANTILES: list[float] = [0.25, 0.75, 0.95]

# MLE optimiser settings
_MAX_ITER = 500
_FTOL = 1e-12
_GTOL = 1e-8


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GARCHResult:
    """Complete GARCH volatility analysis output."""

    # ── GARCH(1,1) parameters ──
    omega: float | None = None
    alpha: float | None = None
    beta: float | None = None
    garch_converged: bool = False
    garch_log_likelihood: float | None = None

    # ── EGARCH parameters ──
    egarch_omega: float | None = None
    egarch_alpha: float | None = None
    egarch_gamma: float | None = None          # leverage coefficient
    egarch_beta: float | None = None
    egarch_converged: bool = False
    egarch_log_likelihood: float | None = None

    # ── GJR-GARCH parameters ──
    gjr_omega: float | None = None
    gjr_alpha: float | None = None
    gjr_gamma: float | None = None             # asymmetric threshold coefficient
    gjr_beta: float | None = None
    gjr_converged: bool = False
    gjr_log_likelihood: float | None = None

    # ── Conditional variance series (from best model) ──
    conditional_variance: np.ndarray | None = None
    conditional_volatility: np.ndarray | None = None

    # ── Volatility term structure ──
    vol_term_structure: dict[str, float] = field(default_factory=dict)

    # ── Forecasting ──
    forecast_horizon_days: int = 21
    forecast_variance: np.ndarray | None = None
    forecast_volatility: np.ndarray | None = None
    forecast_annualized_vol: float | None = None

    # ── Regime classification ──
    current_regime: str = "normal_vol"
    regime_series: np.ndarray | None = None
    regime_thresholds: dict[str, float] = field(default_factory=dict)

    # ── Vol-of-vol ──
    vol_of_vol: float | None = None
    vol_of_vol_annualized: float | None = None

    # ── Shock dynamics ──
    persistence: float | None = None           # alpha + beta
    is_stationary: bool | None = None          # persistence < 1
    half_life_days: float | None = None        # ln(2) / ln(alpha + beta)
    unconditional_variance: float | None = None
    unconditional_volatility: float | None = None

    # ── Diagnostics ──
    n_observations: int = 0
    best_model: str = "garch"                  # garch | egarch | gjr_garch


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class GARCHEngine:
    """GARCH family volatility modeling with MLE estimation.

    Fits GARCH(1,1), EGARCH, and GJR-GARCH models to a return series,
    selects the best specification by log-likelihood, and produces
    volatility forecasts, term structure, regime labels, and shock
    dynamics analytics.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def fit(self, returns: np.ndarray, horizon_days: int = 21) -> GARCHResult:
        """Fit GARCH models and produce full volatility analytics.

        Parameters
        ----------
        returns : np.ndarray
            1-D array of simple or log returns (daily).
        horizon_days : int
            Number of days for the primary volatility forecast.

        Returns
        -------
        GARCHResult
            Populated result dataclass.
        """
        result = GARCHResult(forecast_horizon_days=horizon_days)
        returns = self._validate_returns(returns)
        if returns is None:
            return result

        result.n_observations = len(returns)
        variance_init = float(np.var(returns))

        # ── Fit all three models ──
        self._fit_garch(returns, variance_init, result)
        self._fit_egarch(returns, variance_init, result)
        self._fit_gjr_garch(returns, variance_init, result)

        # ── Select best model by log-likelihood ──
        self._select_best_model(result)

        # ── Build conditional variance from best model ──
        cond_var = self._build_conditional_variance(returns, result)
        if cond_var is not None:
            result.conditional_variance = cond_var
            result.conditional_volatility = np.sqrt(cond_var)

        # ── Forecasting ──
        if result.garch_converged:
            self._forecast(returns, horizon_days, result)
            self._build_term_structure(returns, result)

        # ── Persistence / half-life ──
        self._compute_shock_dynamics(result)

        # ── Regime classification ──
        if result.conditional_variance is not None and len(result.conditional_variance) > 0:
            self._classify_regimes(result)

        # ── Vol-of-vol ──
        if result.conditional_volatility is not None and len(result.conditional_volatility) > 1:
            self._compute_vol_of_vol(result)

        return result

    # ------------------------------------------------------------------ #
    # Validation                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_returns(returns: np.ndarray) -> np.ndarray | None:
        """Validate and clean the return series."""
        if returns is None or len(returns) < _MIN_OBSERVATIONS:
            return None

        returns = np.asarray(returns, dtype=np.float64).ravel()

        # Strip leading/trailing NaNs, then fill interior NaNs with 0
        first_valid = 0
        while first_valid < len(returns) and np.isnan(returns[first_valid]):
            first_valid += 1
        last_valid = len(returns) - 1
        while last_valid >= 0 and np.isnan(returns[last_valid]):
            last_valid -= 1
        if last_valid - first_valid + 1 < _MIN_OBSERVATIONS:
            return None

        returns = returns[first_valid: last_valid + 1]
        nan_mask = np.isnan(returns)
        if nan_mask.any():
            returns[nan_mask] = 0.0

        # Reject series with zero variance (e.g. constant price)
        if np.var(returns) < 1e-20:
            return None

        return returns

    # ------------------------------------------------------------------ #
    # GARCH(1,1) MLE                                                      #
    # ------------------------------------------------------------------ #

    def _fit_garch(
        self, returns: np.ndarray, var_init: float, result: GARCHResult,
    ) -> None:
        """Maximum-likelihood estimation of GARCH(1,1).

        sigma_t^2 = omega + alpha * eps_{t-1}^2 + beta * sigma_{t-1}^2
        """
        eps2 = returns ** 2

        def neg_log_lik(params: np.ndarray) -> float:
            omega, alpha, beta = params
            n = len(eps2)
            sigma2 = np.empty(n, dtype=np.float64)
            sigma2[0] = var_init
            for t in range(1, n):
                sigma2[t] = omega + alpha * eps2[t - 1] + beta * sigma2[t - 1]
                if sigma2[t] < 1e-20:
                    sigma2[t] = 1e-20
            # Gaussian log-likelihood (drop constant)
            ll = -0.5 * np.sum(np.log(sigma2) + eps2 / sigma2)
            if not np.isfinite(ll):
                return 1e10
            return -ll

        x0 = np.array([var_init * 0.05, 0.08, 0.88])
        bounds = [(1e-10, var_init * 10), (1e-6, 0.9999), (1e-6, 0.9999)]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = minimize(
                neg_log_lik, x0, method="L-BFGS-B", bounds=bounds,
                options={"maxiter": _MAX_ITER, "ftol": _FTOL, "gtol": _GTOL},
            )

        if res.success or res.fun < 1e9:
            omega, alpha, beta = res.x
            # Enforce stationarity bound softly: allow up to 1.0 but flag
            result.omega = float(omega)
            result.alpha = float(alpha)
            result.beta = float(beta)
            result.garch_converged = True
            result.garch_log_likelihood = float(-res.fun)

    # ------------------------------------------------------------------ #
    # EGARCH — Nelson (1991)                                               #
    # ------------------------------------------------------------------ #

    def _fit_egarch(
        self, returns: np.ndarray, var_init: float, result: GARCHResult,
    ) -> None:
        """MLE of EGARCH(1,1).

        ln(sigma_t^2) = omega + alpha * (|z_{t-1}| - E|z|) + gamma * z_{t-1}
                        + beta * ln(sigma_{t-1}^2)

        where z_t = eps_t / sigma_t, E|z| = sqrt(2/pi) for Gaussian.
        """
        n = len(returns)
        e_abs_z = math.sqrt(2.0 / math.pi)
        log_var_init = math.log(max(var_init, 1e-20))

        def neg_log_lik(params: np.ndarray) -> float:
            omega, alpha, gamma, beta = params
            log_s2 = np.empty(n, dtype=np.float64)
            log_s2[0] = log_var_init
            for t in range(1, n):
                s2_prev = math.exp(log_s2[t - 1])
                if s2_prev < 1e-20:
                    s2_prev = 1e-20
                z = returns[t - 1] / math.sqrt(s2_prev)
                log_s2[t] = (
                    omega
                    + alpha * (abs(z) - e_abs_z)
                    + gamma * z
                    + beta * log_s2[t - 1]
                )
                # Clamp to avoid overflow
                if log_s2[t] > 20.0:
                    log_s2[t] = 20.0
                elif log_s2[t] < -40.0:
                    log_s2[t] = -40.0

            sigma2 = np.exp(log_s2)
            ll = -0.5 * np.sum(log_s2 + returns ** 2 / sigma2)
            if not np.isfinite(ll):
                return 1e10
            return -ll

        x0 = np.array([log_var_init * 0.01, 0.15, -0.05, 0.95])
        bounds = [(-5.0, 5.0), (-1.0, 1.0), (-1.0, 1.0), (0.0, 0.9999)]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = minimize(
                neg_log_lik, x0, method="L-BFGS-B", bounds=bounds,
                options={"maxiter": _MAX_ITER, "ftol": _FTOL, "gtol": _GTOL},
            )

        if res.success or res.fun < 1e9:
            omega, alpha, gamma, beta = res.x
            result.egarch_omega = float(omega)
            result.egarch_alpha = float(alpha)
            result.egarch_gamma = float(gamma)
            result.egarch_beta = float(beta)
            result.egarch_converged = True
            result.egarch_log_likelihood = float(-res.fun)

    # ------------------------------------------------------------------ #
    # GJR-GARCH — Glosten, Jagannathan & Runkle (1993)                    #
    # ------------------------------------------------------------------ #

    def _fit_gjr_garch(
        self, returns: np.ndarray, var_init: float, result: GARCHResult,
    ) -> None:
        """MLE of GJR-GARCH(1,1).

        sigma_t^2 = omega + alpha * eps_{t-1}^2
                     + gamma * eps_{t-1}^2 * I(eps_{t-1} < 0)
                     + beta * sigma_{t-1}^2
        """
        eps2 = returns ** 2
        indicator = (returns < 0).astype(np.float64)
        n = len(returns)

        def neg_log_lik(params: np.ndarray) -> float:
            omega, alpha, gamma, beta = params
            sigma2 = np.empty(n, dtype=np.float64)
            sigma2[0] = var_init
            for t in range(1, n):
                sigma2[t] = (
                    omega
                    + alpha * eps2[t - 1]
                    + gamma * eps2[t - 1] * indicator[t - 1]
                    + beta * sigma2[t - 1]
                )
                if sigma2[t] < 1e-20:
                    sigma2[t] = 1e-20

            ll = -0.5 * np.sum(np.log(sigma2) + eps2 / sigma2)
            if not np.isfinite(ll):
                return 1e10
            return -ll

        x0 = np.array([var_init * 0.05, 0.05, 0.05, 0.88])
        bounds = [
            (1e-10, var_init * 10),
            (1e-6, 0.9999),
            (0.0, 0.9999),
            (1e-6, 0.9999),
        ]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = minimize(
                neg_log_lik, x0, method="L-BFGS-B", bounds=bounds,
                options={"maxiter": _MAX_ITER, "ftol": _FTOL, "gtol": _GTOL},
            )

        if res.success or res.fun < 1e9:
            omega, alpha, gamma, beta = res.x
            result.gjr_omega = float(omega)
            result.gjr_alpha = float(alpha)
            result.gjr_gamma = float(gamma)
            result.gjr_beta = float(beta)
            result.gjr_converged = True
            result.gjr_log_likelihood = float(-res.fun)

    # ------------------------------------------------------------------ #
    # Model selection                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _select_best_model(result: GARCHResult) -> None:
        """Pick the best-fitting model by log-likelihood."""
        candidates: list[tuple[str, float]] = []
        if result.garch_converged and result.garch_log_likelihood is not None:
            candidates.append(("garch", result.garch_log_likelihood))
        if result.egarch_converged and result.egarch_log_likelihood is not None:
            candidates.append(("egarch", result.egarch_log_likelihood))
        if result.gjr_converged and result.gjr_log_likelihood is not None:
            candidates.append(("gjr_garch", result.gjr_log_likelihood))

        if candidates:
            best = max(candidates, key=lambda c: c[1])
            result.best_model = best[0]
        else:
            result.best_model = "garch"

    # ------------------------------------------------------------------ #
    # Conditional variance reconstruction                                  #
    # ------------------------------------------------------------------ #

    def _build_conditional_variance(
        self, returns: np.ndarray, result: GARCHResult,
    ) -> np.ndarray | None:
        """Reconstruct conditional variance from the best model."""
        n = len(returns)
        var_init = float(np.var(returns))

        if result.best_model == "egarch" and result.egarch_converged:
            return self._egarch_variance(
                returns, n, var_init,
                result.egarch_omega, result.egarch_alpha,
                result.egarch_gamma, result.egarch_beta,
            )
        elif result.best_model == "gjr_garch" and result.gjr_converged:
            return self._gjr_variance(
                returns, n, var_init,
                result.gjr_omega, result.gjr_alpha,
                result.gjr_gamma, result.gjr_beta,
            )
        elif result.garch_converged:
            return self._garch_variance(
                returns, n, var_init,
                result.omega, result.alpha, result.beta,
            )
        return None

    @staticmethod
    def _garch_variance(
        returns: np.ndarray, n: int, var_init: float,
        omega: float, alpha: float, beta: float,
    ) -> np.ndarray:
        eps2 = returns ** 2
        sigma2 = np.empty(n, dtype=np.float64)
        sigma2[0] = var_init
        for t in range(1, n):
            sigma2[t] = omega + alpha * eps2[t - 1] + beta * sigma2[t - 1]
            if sigma2[t] < 1e-20:
                sigma2[t] = 1e-20
        return sigma2

    @staticmethod
    def _egarch_variance(
        returns: np.ndarray, n: int, var_init: float,
        omega: float, alpha: float, gamma: float, beta: float,
    ) -> np.ndarray:
        e_abs_z = math.sqrt(2.0 / math.pi)
        log_s2 = np.empty(n, dtype=np.float64)
        log_s2[0] = math.log(max(var_init, 1e-20))
        for t in range(1, n):
            s2_prev = math.exp(log_s2[t - 1])
            if s2_prev < 1e-20:
                s2_prev = 1e-20
            z = returns[t - 1] / math.sqrt(s2_prev)
            log_s2[t] = (
                omega
                + alpha * (abs(z) - e_abs_z)
                + gamma * z
                + beta * log_s2[t - 1]
            )
            if log_s2[t] > 20.0:
                log_s2[t] = 20.0
            elif log_s2[t] < -40.0:
                log_s2[t] = -40.0
        return np.exp(log_s2)

    @staticmethod
    def _gjr_variance(
        returns: np.ndarray, n: int, var_init: float,
        omega: float, alpha: float, gamma: float, beta: float,
    ) -> np.ndarray:
        eps2 = returns ** 2
        indicator = (returns < 0).astype(np.float64)
        sigma2 = np.empty(n, dtype=np.float64)
        sigma2[0] = var_init
        for t in range(1, n):
            sigma2[t] = (
                omega
                + alpha * eps2[t - 1]
                + gamma * eps2[t - 1] * indicator[t - 1]
                + beta * sigma2[t - 1]
            )
            if sigma2[t] < 1e-20:
                sigma2[t] = 1e-20
        return sigma2

    # ------------------------------------------------------------------ #
    # Forecasting (GARCH(1,1) analytic h-step-ahead)                       #
    # ------------------------------------------------------------------ #

    def _forecast(
        self, returns: np.ndarray, horizon: int, result: GARCHResult,
    ) -> None:
        """Analytic h-step-ahead variance forecast from GARCH(1,1).

        h-step: sigma^2_{t+h|t} = V_L + (alpha + beta)^{h-1} * (sigma^2_{t+1|t} - V_L)
        where V_L = omega / (1 - alpha - beta) is unconditional variance.
        """
        if not result.garch_converged:
            return

        omega = result.omega
        alpha = result.alpha
        beta = result.beta
        persistence = alpha + beta

        # One-step-ahead from last observation
        var_init = float(np.var(returns))
        sigma2 = self._garch_variance(returns, len(returns), var_init, omega, alpha, beta)
        last_var = float(sigma2[-1])
        last_eps2 = float(returns[-1] ** 2)
        one_step = omega + alpha * last_eps2 + beta * last_var

        # Unconditional variance
        if persistence < 1.0:
            v_long = omega / (1.0 - persistence)
        else:
            v_long = one_step  # fallback for near-unit-root

        forecast = np.empty(horizon, dtype=np.float64)
        for h in range(horizon):
            if persistence < 1.0:
                forecast[h] = v_long + (persistence ** h) * (one_step - v_long)
            else:
                forecast[h] = one_step  # flat for IGARCH

        result.forecast_variance = forecast
        result.forecast_volatility = np.sqrt(forecast)

        # Annualised vol from average forecast variance
        avg_daily_var = float(np.mean(forecast))
        result.forecast_annualized_vol = round(
            math.sqrt(avg_daily_var) * _ANNUALIZATION_FACTOR, 6,
        )

    # ------------------------------------------------------------------ #
    # Volatility term structure                                            #
    # ------------------------------------------------------------------ #

    def _build_term_structure(
        self, returns: np.ndarray, result: GARCHResult,
    ) -> None:
        """Annualised vol forecasts at standard horizons."""
        if not result.garch_converged:
            return

        omega = result.omega
        alpha = result.alpha
        beta = result.beta
        persistence = alpha + beta

        var_init = float(np.var(returns))
        sigma2 = self._garch_variance(returns, len(returns), var_init, omega, alpha, beta)
        last_var = float(sigma2[-1])
        last_eps2 = float(returns[-1] ** 2)
        one_step = omega + alpha * last_eps2 + beta * last_var

        if persistence < 1.0:
            v_long = omega / (1.0 - persistence)
        else:
            v_long = one_step

        term_structure: dict[str, float] = {}
        for label, days in _HORIZON_MAP.items():
            # Average variance over horizon
            if abs(persistence - 1.0) < 1e-12:
                avg_var = one_step
            else:
                # sum of geometric: sum_{h=0}^{H-1} p^h = (1 - p^H) / (1 - p)
                geo_sum = (1.0 - persistence ** days) / (1.0 - persistence)
                avg_var = v_long + (one_step - v_long) * geo_sum / days
            annualized_vol = math.sqrt(max(avg_var, 0.0)) * _ANNUALIZATION_FACTOR
            term_structure[label] = round(annualized_vol, 6)

        result.vol_term_structure = term_structure

    # ------------------------------------------------------------------ #
    # Shock dynamics                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_shock_dynamics(result: GARCHResult) -> None:
        """Persistence, half-life, unconditional variance."""
        if not result.garch_converged:
            return

        alpha = result.alpha
        beta = result.beta
        omega = result.omega
        persistence = alpha + beta
        result.persistence = round(persistence, 8)
        result.is_stationary = persistence < 1.0

        # Half-life: time for shock to decay to 50%
        if 0.0 < persistence < 1.0:
            result.half_life_days = round(
                math.log(2.0) / (-math.log(persistence)), 4,
            )
        else:
            result.half_life_days = None  # IGARCH → infinite half-life

        # Unconditional variance
        if persistence < 1.0:
            uv = omega / (1.0 - persistence)
            result.unconditional_variance = round(uv, 10)
            result.unconditional_volatility = round(math.sqrt(uv), 8)

    # ------------------------------------------------------------------ #
    # Regime classification                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _classify_regimes(result: GARCHResult) -> None:
        """Label each observation's volatility regime using quantile thresholds
        on the conditional variance series.

        Buckets:
            [0, q25)        → low_vol
            [q25, q75)      → normal_vol
            [q75, q95)      → high_vol
            [q95, ∞)        → crisis_vol
        """
        cv = result.conditional_variance
        q25, q75, q95 = np.quantile(cv, _REGIME_QUANTILES)
        result.regime_thresholds = {
            "low_vol_upper": round(float(q25), 10),
            "normal_vol_upper": round(float(q75), 10),
            "high_vol_upper": round(float(q95), 10),
        }

        regimes = np.empty(len(cv), dtype="<U10")
        regimes[:] = "normal_vol"
        regimes[cv < q25] = "low_vol"
        regimes[(cv >= q75) & (cv < q95)] = "high_vol"
        regimes[cv >= q95] = "crisis_vol"
        result.regime_series = regimes

        # Current regime = last observation
        result.current_regime = str(regimes[-1])

    # ------------------------------------------------------------------ #
    # Vol-of-vol                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_vol_of_vol(result: GARCHResult) -> None:
        """Second-order volatility: standard deviation of the
        conditional volatility series."""
        cv = result.conditional_volatility
        if cv is None or len(cv) < 2:
            return
        vov = float(np.std(cv, ddof=1))
        result.vol_of_vol = round(vov, 10)
        result.vol_of_vol_annualized = round(vov * _ANNUALIZATION_FACTOR, 6)
