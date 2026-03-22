"""
Volatility Surface / SABR Model Engine
Full implied-volatility surface construction, SABR calibration (Hagan et al. 2002),
skew analytics, term structure, regime classification, and sticky-strike vs sticky-delta detection.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import interpolate, optimize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPS = 1e-12


def _safe_float(val: Any, default: float = float("nan")) -> float:
    """Coerce to float; return *default* on failure."""
    if val is None:
        return default
    try:
        v = float(val)
        return v if np.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _moneyness(strike: float, spot: float) -> float:
    """Log-moneyness: ln(K/S)."""
    if spot <= 0 or strike <= 0:
        return float("nan")
    return math.log(strike / spot)


def _years_to_expiry(expiration_str: str, ref_date: str | None = None) -> float:
    """Convert expiration date string (YYYY-MM-DD) to time-to-expiry in years."""
    import datetime as _dt

    try:
        exp = _dt.date.fromisoformat(expiration_str)
    except (ValueError, TypeError):
        return float("nan")
    if ref_date is not None:
        today = _dt.date.fromisoformat(ref_date)
    else:
        today = _dt.date.today()
    delta = (exp - today).days
    if delta <= 0:
        return float("nan")
    return delta / 365.25


# ---------------------------------------------------------------------------
# SABR closed-form (Hagan 2002)
# ---------------------------------------------------------------------------

def sabr_implied_vol(
    F: float,
    K: float,
    T: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> float:
    """
    Hagan et al. (2002) SABR closed-form implied volatility approximation.

    Parameters
    ----------
    F : forward price
    K : strike
    T : time to expiry (years)
    alpha : ATM vol level parameter
    beta : CEV exponent (fixed, e.g. 0.5 for equity)
    rho : correlation between asset and vol processes
    nu : vol-of-vol

    Returns
    -------
    Approximate Black implied volatility (annualised).
    """
    if T <= 0 or alpha <= 0 or F <= 0 or K <= 0:
        return float("nan")

    # Handle ATM case (K ≈ F)
    if abs(F - K) < _EPS * F:
        fmid = F
        fmid_beta = fmid ** (1.0 - beta)
        term1 = alpha / fmid_beta
        term2 = (
            ((1.0 - beta) ** 2 / 24.0) * alpha ** 2 / fmid ** (2.0 * (1.0 - beta))
            + 0.25 * rho * beta * nu * alpha / fmid_beta
            + (2.0 - 3.0 * rho ** 2) / 24.0 * nu ** 2
        )
        return term1 * (1.0 + term2 * T)

    fk = F * K
    fk_beta = fk ** ((1.0 - beta) / 2.0)
    log_fk = math.log(F / K)

    # z and x(z)
    z = (nu / alpha) * fk_beta * log_fk
    # Guard against division by zero in x(z)
    discriminant = 1.0 - 2.0 * rho * z + z ** 2
    if discriminant < 0:
        return float("nan")
    sqrt_disc = math.sqrt(discriminant)
    x_z_denom = sqrt_disc + z - rho
    if abs(x_z_denom) < _EPS:
        return float("nan")
    x_z = math.log((sqrt_disc + z - rho) / (1.0 - rho))
    if abs(x_z) < _EPS:
        return float("nan")

    # Prefactor
    one_minus_beta = 1.0 - beta
    fk_pow = fk ** (one_minus_beta / 2.0)
    denom = fk_pow * (
        1.0
        + one_minus_beta ** 2 / 24.0 * log_fk ** 2
        + one_minus_beta ** 4 / 1920.0 * log_fk ** 4
    )
    prefix = alpha / denom

    # Correction term
    term2 = (
        one_minus_beta ** 2 / 24.0 * alpha ** 2 / fk ** one_minus_beta
        + 0.25 * rho * beta * nu * alpha / fk_pow
        + (2.0 - 3.0 * rho ** 2) / 24.0 * nu ** 2
    )

    return prefix * (z / x_z) * (1.0 + term2 * T)


def _sabr_objective(params: np.ndarray, F: float, T: float, beta: float,
                    strikes: np.ndarray, market_vols: np.ndarray) -> float:
    """Sum-of-squared errors between SABR model vols and market vols."""
    alpha, rho, nu = params
    if alpha <= 0 or nu <= 0 or abs(rho) >= 1.0:
        return 1e12
    sse = 0.0
    for k, mv in zip(strikes, market_vols):
        model_v = sabr_implied_vol(F, k, T, alpha, beta, rho, nu)
        if not np.isfinite(model_v):
            sse += 1.0  # penalty
        else:
            sse += (model_v - mv) ** 2
    return sse


def calibrate_sabr(
    F: float,
    T: float,
    strikes: np.ndarray,
    market_vols: np.ndarray,
    beta: float = 0.5,
) -> dict[str, float]:
    """
    Calibrate SABR parameters (alpha, rho, nu) for a single expiry.

    Returns dict with keys: alpha, beta, rho, nu, fit_error.
    """
    if len(strikes) < 3 or T <= 0 or F <= 0:
        return {"alpha": float("nan"), "beta": beta, "rho": float("nan"),
                "nu": float("nan"), "fit_error": float("nan")}

    # Initial guess: alpha ≈ ATM vol * F^(1-beta), rho ~ 0, nu ~ 0.3
    atm_idx = int(np.argmin(np.abs(strikes - F)))
    atm_vol = market_vols[atm_idx]
    alpha0 = max(atm_vol * F ** (1.0 - beta), 1e-4)
    x0 = np.array([alpha0, -0.2, 0.3])

    bounds = [(1e-6, None), (-0.999, 0.999), (1e-4, 5.0)]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = optimize.minimize(
            _sabr_objective,
            x0,
            args=(F, T, beta, strikes, market_vols),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 500, "ftol": 1e-12},
        )

    alpha_fit, rho_fit, nu_fit = result.x
    return {
        "alpha": float(alpha_fit),
        "beta": beta,
        "rho": float(rho_fit),
        "nu": float(nu_fit),
        "fit_error": float(result.fun),
    }


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VolSurfaceResult:
    """Complete volatility surface analytics."""

    # Raw surface grid
    strikes: list[float] = field(default_factory=list)
    moneyness_grid: list[float] = field(default_factory=list)
    expiries: list[str] = field(default_factory=list)
    expiry_years: list[float] = field(default_factory=list)
    iv_matrix: list[list[float]] = field(default_factory=list)  # [expiry_idx][strike_idx]

    # SABR parameters per expiry
    sabr_params: list[dict[str, float]] = field(default_factory=list)

    # Skew metrics per expiry
    risk_reversal_25d: list[float] = field(default_factory=list)   # call_25d - put_25d
    butterfly_25d: list[float] = field(default_factory=list)       # (call_25d + put_25d)/2 - atm
    skew_slope: list[float] = field(default_factory=list)          # dIV/dMoneyness near ATM

    # Term structure
    atm_iv_term: list[float] = field(default_factory=list)         # ATM IV per expiry
    term_structure_slope: float = float("nan")                      # linear slope of ATM IV vs sqrt(T)
    term_structure_regime: str = "flat"                              # contango | backwardation | flat

    # Vol surface regime
    surface_regime: str = "normal_skew"  # normal_skew | steep_skew | smile | flat | inverted

    # Sticky strike vs sticky delta
    sticky_regime: str = "unknown"  # sticky_strike | sticky_delta | unknown

    # Diagnostics
    n_contracts: int = 0
    n_expiries: int = 0
    interpolation_method: str = "cubic_spline"
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class VolSurfaceEngine:
    """
    Builds and analyses the implied-volatility surface from options chain data.

    Usage
    -----
    >>> engine = VolSurfaceEngine()
    >>> result = engine.fit(contracts, spot=150.0)
    """

    def __init__(self, beta: float = 0.5, ref_date: str | None = None):
        """
        Parameters
        ----------
        beta : CEV exponent for SABR (0.5 typical for equity).
        ref_date : reference date (YYYY-MM-DD) for time-to-expiry calculation.
                   Defaults to today.
        """
        self.beta = beta
        self.ref_date = ref_date

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, contracts: list[dict], spot: float) -> VolSurfaceResult:
        """
        Fit a volatility surface from a list of option contracts.

        Parameters
        ----------
        contracts : list of dicts, each with keys
            strike, expiration (str YYYY-MM-DD), option_type ('call'/'put'),
            implied_volatility, delta (optional).
        spot : current underlying price.

        Returns
        -------
        VolSurfaceResult
        """
        result = VolSurfaceResult()

        if not contracts or spot <= 0:
            result.warnings.append("No contracts or invalid spot price.")
            return result

        # -- Parse and validate contracts --------------------------------
        parsed = self._parse_contracts(contracts, spot)
        if not parsed:
            result.warnings.append("No valid contracts after parsing.")
            return result

        result.n_contracts = len(parsed)

        # -- Group by expiry ---------------------------------------------
        by_expiry: dict[str, list[dict]] = {}
        for c in parsed:
            by_expiry.setdefault(c["expiration"], []).append(c)

        sorted_expiries = sorted(by_expiry.keys())
        result.expiries = sorted_expiries
        result.n_expiries = len(sorted_expiries)

        # -- Build per-expiry analytics ----------------------------------
        all_strikes_set: set[float] = set()
        for exp in sorted_expiries:
            for c in by_expiry[exp]:
                all_strikes_set.add(c["strike"])

        all_strikes_sorted = sorted(all_strikes_set)
        result.strikes = all_strikes_sorted
        result.moneyness_grid = [_moneyness(k, spot) for k in all_strikes_sorted]

        iv_matrix: list[list[float]] = []
        sabr_params_list: list[dict[str, float]] = []
        rr_list: list[float] = []
        bfly_list: list[float] = []
        slope_list: list[float] = []
        atm_iv_list: list[float] = []
        expiry_years_list: list[float] = []

        for exp in sorted_expiries:
            exp_contracts = by_expiry[exp]
            T = _years_to_expiry(exp, self.ref_date)
            expiry_years_list.append(T)

            # Collect strike -> IV mapping (average if both call and put)
            strike_iv: dict[float, list[float]] = {}
            call_ivs: dict[float, float] = {}
            put_ivs: dict[float, float] = {}
            deltas_calls: dict[float, float] = {}
            deltas_puts: dict[float, float] = {}

            for c in exp_contracts:
                k = c["strike"]
                iv = c["iv"]
                strike_iv.setdefault(k, []).append(iv)
                if c["option_type"] == "call":
                    call_ivs[k] = iv
                    if np.isfinite(c.get("delta", float("nan"))):
                        deltas_calls[k] = c["delta"]
                else:
                    put_ivs[k] = iv
                    if np.isfinite(c.get("delta", float("nan"))):
                        deltas_puts[k] = c["delta"]

            # Mean IV per strike
            strikes_exp = sorted(strike_iv.keys())
            ivs_exp = np.array([float(np.nanmean(strike_iv[k])) for k in strikes_exp])
            strikes_arr = np.array(strikes_exp)

            # Interpolate onto full strike grid via cubic spline
            iv_row = self._interpolate_iv(strikes_arr, ivs_exp, all_strikes_sorted)
            iv_matrix.append(iv_row)

            # ATM IV (closest strike to spot)
            atm_iv = self._atm_iv(strikes_arr, ivs_exp, spot)
            atm_iv_list.append(atm_iv)

            # SABR calibration
            if np.isfinite(T) and T > 0 and len(strikes_arr) >= 3:
                valid = np.isfinite(ivs_exp)
                sabr = calibrate_sabr(
                    spot, T, strikes_arr[valid], ivs_exp[valid], beta=self.beta
                )
            else:
                sabr = {"alpha": float("nan"), "beta": self.beta,
                        "rho": float("nan"), "nu": float("nan"),
                        "fit_error": float("nan")}
            sabr_params_list.append(sabr)

            # Skew metrics
            rr, bfly = self._skew_metrics(
                call_ivs, put_ivs, deltas_calls, deltas_puts, atm_iv, spot
            )
            rr_list.append(rr)
            bfly_list.append(bfly)

            # Skew slope (dIV / d_moneyness near ATM)
            slope = self._skew_slope(strikes_arr, ivs_exp, spot)
            slope_list.append(slope)

        result.iv_matrix = iv_matrix
        result.expiry_years = expiry_years_list
        result.sabr_params = sabr_params_list
        result.risk_reversal_25d = rr_list
        result.butterfly_25d = bfly_list
        result.skew_slope = slope_list
        result.atm_iv_term = atm_iv_list

        # -- Term structure -----------------------------------------------
        result.term_structure_slope, result.term_structure_regime = (
            self._term_structure(expiry_years_list, atm_iv_list)
        )

        # -- Surface regime -----------------------------------------------
        result.surface_regime = self._classify_surface_regime(
            slope_list, bfly_list, rr_list
        )

        # -- Sticky strike vs sticky delta --------------------------------
        result.sticky_regime = self._detect_sticky_regime(
            sabr_params_list, atm_iv_list
        )

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_contracts(self, contracts: list[dict], spot: float) -> list[dict]:
        """Validate and normalise raw contract dicts."""
        parsed: list[dict] = []
        for c in contracts:
            strike = _safe_float(c.get("strike"))
            iv = _safe_float(c.get("implied_volatility"))
            exp = c.get("expiration")
            otype = str(c.get("option_type", "")).lower().strip()
            if otype not in ("call", "put"):
                continue
            if not np.isfinite(strike) or strike <= 0:
                continue
            if not np.isfinite(iv) or iv <= 0:
                continue
            if not isinstance(exp, str) or len(exp) < 8:
                continue
            T = _years_to_expiry(exp, self.ref_date)
            if not np.isfinite(T) or T <= 0:
                continue
            delta = _safe_float(c.get("delta"))
            parsed.append({
                "strike": strike,
                "iv": iv,
                "expiration": exp,
                "option_type": otype,
                "delta": delta,
                "T": T,
            })
        return parsed

    @staticmethod
    def _interpolate_iv(
        strikes: np.ndarray,
        ivs: np.ndarray,
        target_strikes: list[float],
    ) -> list[float]:
        """Cubic-spline interpolation of IV across strikes, with flat extrapolation."""
        valid = np.isfinite(ivs)
        if valid.sum() < 2:
            return [float("nan")] * len(target_strikes)

        xs = strikes[valid]
        ys = ivs[valid]
        if len(xs) < 4:
            # Fall back to linear if too few points for cubic
            kind = "linear"
        else:
            kind = "cubic"

        try:
            interp_fn = interpolate.interp1d(
                xs, ys, kind=kind, bounds_error=False,
                fill_value=(float(ys[0]), float(ys[-1])),
            )
            return [float(interp_fn(k)) for k in target_strikes]
        except Exception:
            return [float("nan")] * len(target_strikes)

    @staticmethod
    def _atm_iv(strikes: np.ndarray, ivs: np.ndarray, spot: float) -> float:
        """ATM implied vol — closest strike to spot."""
        valid = np.isfinite(ivs)
        if not valid.any():
            return float("nan")
        idx = int(np.argmin(np.abs(strikes[valid] - spot)))
        return float(ivs[valid][idx])

    @staticmethod
    def _skew_metrics(
        call_ivs: dict[float, float],
        put_ivs: dict[float, float],
        deltas_calls: dict[float, float],
        deltas_puts: dict[float, float],
        atm_iv: float,
        spot: float,
    ) -> tuple[float, float]:
        """
        25-delta risk reversal and butterfly.

        Risk reversal = IV(25d call) - IV(25d put)
        Butterfly     = (IV(25d call) + IV(25d put)) / 2 - ATM IV
        """
        call_25d_iv = float("nan")
        put_25d_iv = float("nan")

        # Try delta-based selection first
        if deltas_calls and deltas_puts:
            # 25-delta call: delta ≈ 0.25
            best_c = min(deltas_calls.items(), key=lambda kv: abs(abs(kv[1]) - 0.25))
            if abs(abs(best_c[1]) - 0.25) < 0.15:
                call_25d_iv = call_ivs.get(best_c[0], float("nan"))
            # 25-delta put: delta ≈ -0.25
            best_p = min(deltas_puts.items(), key=lambda kv: abs(abs(kv[1]) - 0.25))
            if abs(abs(best_p[1]) - 0.25) < 0.15:
                put_25d_iv = put_ivs.get(best_p[0], float("nan"))

        # Fallback: approximate 25-delta via moneyness (~±0.07 log-moneyness for short expiry)
        if not np.isfinite(call_25d_iv) and call_ivs:
            otm_calls = {k: v for k, v in call_ivs.items() if k > spot * 1.03}
            if otm_calls:
                closest = min(otm_calls.keys(), key=lambda k: abs(k - spot * 1.07))
                call_25d_iv = otm_calls[closest]
        if not np.isfinite(put_25d_iv) and put_ivs:
            otm_puts = {k: v for k, v in put_ivs.items() if k < spot * 0.97}
            if otm_puts:
                closest = min(otm_puts.keys(), key=lambda k: abs(k - spot * 0.93))
                put_25d_iv = otm_puts[closest]

        rr = float("nan")
        bfly = float("nan")
        if np.isfinite(call_25d_iv) and np.isfinite(put_25d_iv):
            rr = call_25d_iv - put_25d_iv
            if np.isfinite(atm_iv):
                bfly = (call_25d_iv + put_25d_iv) / 2.0 - atm_iv
        return rr, bfly

    @staticmethod
    def _skew_slope(strikes: np.ndarray, ivs: np.ndarray, spot: float) -> float:
        """
        Linear slope of IV vs log-moneyness in a ±10% band around spot.
        Negative slope → normal put-skew; positive → inverted.
        """
        mask = (strikes > spot * 0.90) & (strikes < spot * 1.10) & np.isfinite(ivs)
        if mask.sum() < 2:
            return float("nan")
        moneyness = np.log(strikes[mask] / spot)
        vols = ivs[mask]
        try:
            coeffs = np.polyfit(moneyness, vols, 1)
            return float(coeffs[0])
        except Exception:
            return float("nan")

    @staticmethod
    def _term_structure(
        expiry_years: list[float], atm_ivs: list[float]
    ) -> tuple[float, str]:
        """
        Compute term-structure slope and classify contango / backwardation / flat.
        """
        valid = [
            (t, iv)
            for t, iv in zip(expiry_years, atm_ivs)
            if np.isfinite(t) and np.isfinite(iv) and t > 0
        ]
        if len(valid) < 2:
            return float("nan"), "flat"

        ts = np.array([v[0] for v in valid])
        ivs = np.array([v[1] for v in valid])

        # Regress ATM IV on sqrt(T) — natural time scaling
        sqrt_t = np.sqrt(ts)
        try:
            coeffs = np.polyfit(sqrt_t, ivs, 1)
        except Exception:
            return float("nan"), "flat"

        slope = float(coeffs[0])
        if slope > 0.005:
            regime = "contango"
        elif slope < -0.005:
            regime = "backwardation"
        else:
            regime = "flat"
        return slope, regime

    @staticmethod
    def _classify_surface_regime(
        skew_slopes: list[float],
        butterflies: list[float],
        risk_reversals: list[float],
    ) -> str:
        """
        Classify vol-surface regime:
          normal_skew  — moderate negative skew (typical equity)
          steep_skew   — very negative skew (crash fear)
          smile        — symmetric wings (FX-like)
          flat         — almost no skew
          inverted     — positive skew (unusual)
        """
        valid_slopes = [s for s in skew_slopes if np.isfinite(s)]
        valid_bfly = [b for b in butterflies if np.isfinite(b)]
        valid_rr = [r for r in risk_reversals if np.isfinite(r)]

        if not valid_slopes:
            return "flat"

        avg_slope = float(np.mean(valid_slopes))
        avg_bfly = float(np.mean(valid_bfly)) if valid_bfly else 0.0
        avg_rr = float(np.mean(valid_rr)) if valid_rr else 0.0

        # Smile: large positive butterfly + small risk-reversal magnitude
        if avg_bfly > 0.01 and abs(avg_rr) < 0.02:
            return "smile"

        if avg_slope < -1.0:
            return "steep_skew"
        if avg_slope < -0.1:
            return "normal_skew"
        if avg_slope > 0.1:
            return "inverted"
        return "flat"

    @staticmethod
    def _detect_sticky_regime(
        sabr_params: list[dict[str, float]],
        atm_ivs: list[float],
    ) -> str:
        """
        Heuristic: if rho is strongly negative across expiries the surface
        behaves more like sticky-delta (IV moves with spot); if rho ≈ 0 it
        is closer to sticky-strike (IV pinned to absolute strike levels).

        This is a simplified classifier — a full test requires two snapshots
        at different spot levels, which we may not have.
        """
        rhos = [p["rho"] for p in sabr_params if np.isfinite(p.get("rho", float("nan")))]
        if not rhos:
            return "unknown"

        avg_rho = float(np.mean(rhos))
        if avg_rho < -0.35:
            return "sticky_delta"
        if avg_rho > -0.10:
            return "sticky_strike"
        return "unknown"
