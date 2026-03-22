"""
Yield Curve Modeling Engine — Rate Sensitivity Analysis for UPST
Nelson-Siegel fitting, shape classification, rate shock scenarios,
duration/convexity proxy, forward rate extraction, and Fed funds path.
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

_MIN_TENORS = 4  # minimum number of points to fit Nelson-Siegel

# Standard tenor labels → maturity in years
_TENOR_MAP: dict[str, float] = {
    "1m": 1.0 / 12,
    "2m": 2.0 / 12,
    "3m": 3.0 / 12,
    "6m": 6.0 / 12,
    "1y": 1.0,
    "2y": 2.0,
    "3y": 3.0,
    "5y": 5.0,
    "7y": 7.0,
    "10y": 10.0,
    "20y": 20.0,
    "30y": 30.0,
}

# Smooth curve output grid (years)
_CURVE_GRID: list[float] = [
    1 / 12, 2 / 12, 3 / 12, 6 / 12,
    1, 2, 3, 5, 7, 10, 15, 20, 25, 30,
]

# Rate shock scenarios (basis points)
_PARALLEL_SHOCKS: list[int] = [-200, -100, -50, -25, 25, 50, 100, 200]

# Optimiser settings
_MAX_ITER = 1000
_FTOL = 1e-14


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class YieldCurveResult:
    """Complete yield curve analysis output."""

    # ── Nelson-Siegel parameters ──
    beta0: float | None = None                    # long-term level
    beta1: float | None = None                    # slope
    beta2: float | None = None                    # curvature
    tau: float | None = None                      # decay factor
    ns_converged: bool = False
    ns_rmse: float | None = None                  # fit quality (bps)

    # ── Fitted curve ──
    fitted_maturities: np.ndarray | None = None   # years
    fitted_yields: np.ndarray | None = None       # percent

    # ── Shape classification ──
    curve_shape: str = "unknown"                  # normal | flat | inverted | humped
    spread_2s10s: float | None = None             # bps
    spread_3m10y: float | None = None             # bps

    # ── Rate shock scenarios ──
    # dict keyed by scenario name → dict of curve or sensitivity
    shock_scenarios: dict[str, dict] = field(default_factory=dict)

    # ── Duration and convexity proxy ──
    effective_duration: float | None = None        # %UPST / 100bps rate change
    effective_convexity: float | None = None       # second-order term
    duration_r_squared: float | None = None        # regression fit quality

    # ── Forward rates ──
    forward_1y1y: float | None = None             # 1-year rate, 1 year forward
    forward_1y2y: float | None = None             # 2-year rate, 1 year forward
    forward_2y3y: float | None = None             # 3-year rate, 2 years forward

    # ── Fed funds path ──
    fed_funds_rate: float | None = None           # current FF rate (from 3m or input)
    prob_next_cut: float | None = None
    prob_next_hike: float | None = None
    cuts_priced_in: float | None = None           # number of 25bp cuts priced in
    two_year_ff_spread: float | None = None       # 2y yield minus FF rate (bps)

    # ── Diagnostics ──
    n_tenors_input: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class YieldCurveEngine:
    """Yield curve modeling and UPST rate sensitivity analysis.

    Fits a Nelson-Siegel model to observed treasury yields, classifies the
    curve shape, runs rate shock scenarios, estimates UPST's effective
    duration from historical data, extracts forward rates, and infers Fed
    funds path expectations.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        treasury_rates: dict[str, float],
        upst_returns: np.ndarray | None = None,
        rate_changes: np.ndarray | None = None,
    ) -> YieldCurveResult:
        """Run full yield curve analysis.

        Parameters
        ----------
        treasury_rates : dict[str, float]
            Observed yields keyed by tenor label (e.g. ``{"3m": 4.5, "10y": 3.7}``).
            Values in percent (e.g. 4.5 means 4.5%).
        upst_returns : np.ndarray, optional
            Daily UPST returns for duration/convexity estimation.
        rate_changes : np.ndarray, optional
            Daily changes in a reference rate (e.g. 10y yield) aligned with
            ``upst_returns``. If supplied, used for duration regression.

        Returns
        -------
        YieldCurveResult
            Populated result dataclass.
        """
        result = YieldCurveResult()
        maturities, yields = self._parse_rates(treasury_rates)
        result.n_tenors_input = len(maturities)

        if len(maturities) < _MIN_TENORS:
            return result

        # ── Nelson-Siegel fit ──
        self._fit_nelson_siegel(maturities, yields, result)

        # ── Smooth fitted curve ──
        if result.ns_converged:
            grid = np.array(_CURVE_GRID)
            result.fitted_maturities = grid
            result.fitted_yields = self._ns_curve(
                grid, result.beta0, result.beta1, result.beta2, result.tau,
            )

        # ── Shape classification ──
        self._classify_shape(treasury_rates, result)

        # ── Rate shock scenarios ──
        if result.ns_converged:
            self._run_shocks(result)

        # ── Duration / convexity proxy ──
        if upst_returns is not None and rate_changes is not None:
            self._estimate_duration(upst_returns, rate_changes, result)

        # ── Forward rates ──
        if result.ns_converged:
            self._extract_forwards(result)

        # ── Fed funds path ──
        self._fed_funds_path(treasury_rates, result)

        return result

    # ------------------------------------------------------------------ #
    # Input parsing                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_rates(
        treasury_rates: dict[str, float],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Convert tenor labels to maturities in years and yields in percent."""
        maturities: list[float] = []
        yields: list[float] = []

        for tenor, rate in treasury_rates.items():
            tenor_lower = tenor.lower().strip()
            if tenor_lower in _TENOR_MAP:
                maturities.append(_TENOR_MAP[tenor_lower])
                yields.append(float(rate))

        # Sort by maturity
        order = np.argsort(maturities)
        return np.array(maturities)[order], np.array(yields)[order]

    # ------------------------------------------------------------------ #
    # Nelson-Siegel model                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ns_curve(
        m: np.ndarray,
        beta0: float,
        beta1: float,
        beta2: float,
        tau: float,
    ) -> np.ndarray:
        """Evaluate Nelson-Siegel yield at maturities m (years).

        y(m) = beta0 + beta1 * [(1 - exp(-m/tau)) / (m/tau)]
                     + beta2 * [(1 - exp(-m/tau)) / (m/tau) - exp(-m/tau)]
        """
        x = m / tau
        # Guard against division by zero for very small m
        with np.errstate(divide="ignore", invalid="ignore"):
            factor1 = np.where(x > 1e-10, (1.0 - np.exp(-x)) / x, 1.0)
            factor2 = factor1 - np.exp(-x)

        return beta0 + beta1 * factor1 + beta2 * factor2

    def _fit_nelson_siegel(
        self,
        maturities: np.ndarray,
        yields: np.ndarray,
        result: YieldCurveResult,
    ) -> None:
        """Fit Nelson-Siegel parameters via least-squares minimisation."""

        def objective(params: np.ndarray) -> float:
            b0, b1, b2, tau = params
            if tau <= 0.01:
                return 1e12
            fitted = self._ns_curve(maturities, b0, b1, b2, tau)
            return float(np.sum((fitted - yields) ** 2))

        # Initial guesses from observable curve features
        long_rate = float(yields[-1])
        short_rate = float(yields[0])
        mid_rate = float(yields[len(yields) // 2])

        b0_init = long_rate
        b1_init = short_rate - long_rate
        b2_init = 2.0 * mid_rate - short_rate - long_rate
        tau_init = 1.5

        x0 = np.array([b0_init, b1_init, b2_init, tau_init])
        bounds = [
            (0.0, 20.0),        # beta0
            (-15.0, 15.0),      # beta1
            (-15.0, 15.0),      # beta2
            (0.1, 30.0),        # tau
        ]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = minimize(
                    objective, x0, method="L-BFGS-B", bounds=bounds,
                    options={"maxiter": _MAX_ITER, "ftol": _FTOL},
                )
            except Exception:
                return

        if not res.success and res.fun >= 1e10:
            return

        b0, b1, b2, tau = res.x
        result.beta0 = float(b0)
        result.beta1 = float(b1)
        result.beta2 = float(b2)
        result.tau = float(tau)
        result.ns_converged = True

        fitted = self._ns_curve(maturities, b0, b1, b2, tau)
        rmse_pct = float(np.sqrt(np.mean((fitted - yields) ** 2)))
        result.ns_rmse = rmse_pct * 100  # in basis points

    # ------------------------------------------------------------------ #
    # Shape classification                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _classify_shape(
        treasury_rates: dict[str, float],
        result: YieldCurveResult,
    ) -> None:
        """Classify curve shape using 2s10s and 3m10y spreads."""
        rates_lower = {k.lower().strip(): v for k, v in treasury_rates.items()}

        y2 = rates_lower.get("2y")
        y10 = rates_lower.get("10y")
        y3m = rates_lower.get("3m")

        if y2 is not None and y10 is not None:
            result.spread_2s10s = (y10 - y2) * 100  # bps
        if y3m is not None and y10 is not None:
            result.spread_3m10y = (y10 - y3m) * 100  # bps

        # Classification logic
        spread = result.spread_2s10s
        if spread is None and result.spread_3m10y is not None:
            spread = result.spread_3m10y

        if spread is None:
            result.curve_shape = "unknown"
            return

        # Check for humped shape: short end and long end close, belly higher
        is_humped = False
        y5 = rates_lower.get("5y")
        if y2 is not None and y10 is not None and y5 is not None:
            belly_premium_short = (y5 - y2) * 100
            belly_premium_long = (y5 - y10) * 100
            if belly_premium_short > 15 and belly_premium_long > 15:
                is_humped = True

        if is_humped:
            result.curve_shape = "humped"
        elif spread < -25:
            result.curve_shape = "inverted"
        elif spread > 25:
            result.curve_shape = "normal"
        else:
            result.curve_shape = "flat"

    # ------------------------------------------------------------------ #
    # Rate shock scenarios                                               #
    # ------------------------------------------------------------------ #

    def _run_shocks(self, result: YieldCurveResult) -> None:
        """Generate yield curves under various shock scenarios."""
        if result.fitted_maturities is None or result.fitted_yields is None:
            return

        grid = result.fitted_maturities
        base_curve = result.fitted_yields.copy()
        b0, b1, b2, tau = result.beta0, result.beta1, result.beta2, result.tau

        # Parallel shifts
        for bps in _PARALLEL_SHOCKS:
            shift_pct = bps / 100.0
            shocked_curve = base_curve + shift_pct
            label = f"parallel_{'+' if bps > 0 else ''}{bps}bps"
            result.shock_scenarios[label] = {
                "type": "parallel",
                "shift_bps": bps,
                "curve": shocked_curve.tolist(),
                "maturities": grid.tolist(),
                "change_10y_bps": bps,
            }

        # Steepening: short end down 50bps, long end up 50bps (linear interpolation)
        steep_shift = np.interp(grid, [grid[0], grid[-1]], [-0.5, 0.5])
        result.shock_scenarios["steepening"] = {
            "type": "steepening",
            "curve": (base_curve + steep_shift).tolist(),
            "maturities": grid.tolist(),
            "short_end_change_bps": -50,
            "long_end_change_bps": 50,
        }

        # Flattening: short end up 50bps, long end down 50bps
        flat_shift = np.interp(grid, [grid[0], grid[-1]], [0.5, -0.5])
        result.shock_scenarios["flattening"] = {
            "type": "flattening",
            "curve": (base_curve + flat_shift).tolist(),
            "maturities": grid.tolist(),
            "short_end_change_bps": 50,
            "long_end_change_bps": -50,
        }

        # Twist: belly up 50bps, wings unchanged
        belly_idx = len(grid) // 2
        twist_shift = np.zeros_like(grid)
        for i in range(len(grid)):
            # Triangle shape: peak at belly
            dist_from_belly = abs(i - belly_idx) / max(belly_idx, len(grid) - 1 - belly_idx)
            twist_shift[i] = 0.5 * (1.0 - dist_from_belly)
        result.shock_scenarios["twist"] = {
            "type": "twist",
            "curve": (base_curve + twist_shift).tolist(),
            "maturities": grid.tolist(),
            "belly_change_bps": 50,
        }

    # ------------------------------------------------------------------ #
    # Duration and convexity proxy                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estimate_duration(
        upst_returns: np.ndarray,
        rate_changes: np.ndarray,
        result: YieldCurveResult,
    ) -> None:
        """Estimate effective duration by regressing UPST returns on rate changes.

        Duration = -dP/P / dy ≈ negative coefficient of regression
        r_UPST = alpha + beta1 * Δy + beta2 * (Δy)^2 + eps

        effective_duration = -beta1 (per 1% rate change → expressed per 100bps)
        effective_convexity = beta2
        """
        upst_r = np.asarray(upst_returns, dtype=np.float64).ravel()
        dr = np.asarray(rate_changes, dtype=np.float64).ravel()

        min_len = min(len(upst_r), len(dr))
        upst_r = upst_r[:min_len]
        dr = dr[:min_len]

        # Remove NaN rows
        valid = ~(np.isnan(upst_r) | np.isnan(dr))
        upst_r = upst_r[valid]
        dr = dr[valid]

        if len(upst_r) < 30:
            return

        # Rate changes should be in percent (e.g. 0.01 = 1bp).
        # Build design matrix: [1, Δy, (Δy)^2]
        X = np.column_stack([np.ones(len(dr)), dr, dr**2])

        # OLS
        try:
            XtX = X.T @ X
            XtX_inv = np.linalg.inv(XtX)
            beta_hat = XtX_inv @ (X.T @ upst_r)
        except np.linalg.LinAlgError:
            return

        alpha, b1, b2 = beta_hat

        # Duration: negative of linear coefficient (per 1% = 100bps)
        # If rate_changes are in percentage points (e.g. 0.01 = 1bp),
        # then b1 is returns per percentage-point change.
        result.effective_duration = float(-b1)
        result.effective_convexity = float(b2)

        # R-squared
        y_hat = X @ beta_hat
        ss_res = np.sum((upst_r - y_hat) ** 2)
        ss_tot = np.sum((upst_r - np.mean(upst_r)) ** 2)
        if ss_tot > 0:
            result.duration_r_squared = float(1.0 - ss_res / ss_tot)

    # ------------------------------------------------------------------ #
    # Forward rate extraction                                            #
    # ------------------------------------------------------------------ #

    def _extract_forwards(self, result: YieldCurveResult) -> None:
        """Compute implied forward rates from the fitted Nelson-Siegel curve.

        Forward rate f(t1, t2) from spot rates:
        f(t1, t2) = [y(t2)*t2 - y(t1)*t1] / (t2 - t1)
        """
        b0, b1, b2, tau = result.beta0, result.beta1, result.beta2, result.tau

        def spot(m: float) -> float:
            return float(self._ns_curve(np.array([m]), b0, b1, b2, tau)[0])

        def forward(t1: float, t2: float) -> float:
            y1 = spot(t1)
            y2 = spot(t2)
            return (y2 * t2 - y1 * t1) / (t2 - t1)

        result.forward_1y1y = forward(1.0, 2.0)    # 1-year rate, 1 year forward
        result.forward_1y2y = forward(1.0, 3.0)    # 2-year rate, 1 year forward
        result.forward_2y3y = forward(2.0, 5.0)    # 3-year rate, 2 years forward

    # ------------------------------------------------------------------ #
    # Fed funds path                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fed_funds_path(
        treasury_rates: dict[str, float],
        result: YieldCurveResult,
    ) -> None:
        """Infer Fed funds rate expectations from the short end of the curve.

        Uses the 2y-FF spread to estimate number of cuts priced in and
        directional probability of next move.
        """
        rates_lower = {k.lower().strip(): v for k, v in treasury_rates.items()}

        # Approximate FF rate from the shortest tenor available
        ff_rate: float | None = None
        for tenor in ("ff", "fed_funds", "1m", "3m"):
            if tenor in rates_lower:
                ff_rate = rates_lower[tenor]
                break

        if ff_rate is None:
            return

        result.fed_funds_rate = ff_rate

        y2 = rates_lower.get("2y")
        if y2 is None:
            return

        spread_pct = y2 - ff_rate             # in percentage points
        spread_bps = spread_pct * 100         # in basis points
        result.two_year_ff_spread = spread_bps

        # Number of 25bp cuts priced in (negative spread → cuts expected)
        # Each 25bp of negative spread ≈ one cut priced over the 2y horizon
        # Positive spread ≈ hikes priced in (negative cuts)
        result.cuts_priced_in = float(-spread_bps / 25.0)

        # Probability of next move being a cut vs hike
        # Use logistic-like mapping from the 2y-FF spread
        # Large negative spread → high prob of cut, large positive → hike
        # At zero spread: 50/50
        # Scale factor: 50bps spread → ~88% probability
        k = 0.04  # logistic steepness per bp
        prob_cut = 1.0 / (1.0 + math.exp(k * spread_bps))
        result.prob_next_cut = float(prob_cut)
        result.prob_next_hike = float(1.0 - prob_cut)
