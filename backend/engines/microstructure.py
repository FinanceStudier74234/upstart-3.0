"""
Market Microstructure Engine
Kyle's lambda, Amihud illiquidity, VPIN, Roll spread, Corwin-Schultz spread,
order-flow toxicity, intraday volatility signature, and effective spread decomposition.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats as sp_stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPS = 1e-12


def _safe_float(val: Any, default: float = float("nan")) -> float:
    if val is None:
        return default
    try:
        v = float(val)
        return v if np.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _returns(prices: np.ndarray) -> np.ndarray:
    """Simple returns from a price series, length n-1."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = np.diff(prices) / prices[:-1]
    ret[~np.isfinite(ret)] = 0.0
    return ret


def _log_returns(prices: np.ndarray) -> np.ndarray:
    """Log returns, length n-1."""
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.diff(np.log(prices))
    lr[~np.isfinite(lr)] = 0.0
    return lr


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class MicrostructureResult:
    """Complete market microstructure analytics."""

    # Kyle's Lambda
    kyle_lambda: float = float("nan")
    kyle_lambda_t_stat: float = float("nan")
    kyle_lambda_r2: float = float("nan")

    # Amihud illiquidity
    amihud_illiquidity: float = float("nan")
    amihud_series: list[float] = field(default_factory=list)

    # VPIN
    vpin: float = float("nan")
    vpin_series: list[float] = field(default_factory=list)
    vpin_threshold: float = 0.7  # above this -> toxic flow

    # Roll spread
    roll_spread: float = float("nan")
    roll_effective_spread_bps: float = float("nan")

    # Corwin-Schultz spread
    cs_spread: float = float("nan")
    cs_spread_bps: float = float("nan")

    # Order flow toxicity
    toxicity_score: float = float("nan")  # 0..1 composite
    toxic_flow: bool = False

    # Intraday volatility signature
    vol_signature: list[dict[str, float]] = field(default_factory=list)
    # each entry: {"sampling_freq": n_bars, "realized_vol": rv}
    noise_ratio: float = float("nan")  # RV(1-bar)/RV(5-bar) -- >1 => noise

    # Effective spread decomposition
    permanent_impact: float = float("nan")   # information component
    temporary_impact: float = float("nan")   # liquidity / transient component
    permanent_share: float = float("nan")    # fraction of total spread

    # Diagnostics
    n_bars: int = 0
    n_trades: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MicrostructureEngine:
    """
    Analyses market microstructure from bar data and (optionally) tick-level trades.

    Usage
    -----
    >>> engine = MicrostructureEngine()
    >>> result = engine.analyze(bars, trades=trades)
    """

    def __init__(
        self,
        vpin_n_buckets: int = 50,
        amihud_window: int = 20,
        toxicity_weights: dict[str, float] | None = None,
    ):
        self.vpin_n_buckets = vpin_n_buckets
        self.amihud_window = amihud_window
        self.toxicity_weights = toxicity_weights or {
            "vpin": 0.40, "lambda": 0.35, "amihud": 0.25,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        bars: list[dict],
        trades: list[dict] | None = None,
    ) -> MicrostructureResult:
        """
        Run full microstructure analysis.

        Parameters
        ----------
        bars : list of dicts with keys open, high, low, close, volume.
        trades : optional list of dicts with keys price, volume, timestamp.

        Returns
        -------
        MicrostructureResult
        """
        result = MicrostructureResult()

        if not bars:
            result.warnings.append("No bar data provided.")
            return result

        # -- Parse bars ---------------------------------------------------
        opens, highs, lows, closes, volumes = self._parse_bars(bars)
        n = len(closes)
        result.n_bars = n
        if n < 5:
            result.warnings.append("Fewer than 5 bars -- most metrics unreliable.")

        # -- Parse trades -------------------------------------------------
        trade_prices: np.ndarray | None = None
        trade_volumes: np.ndarray | None = None
        if trades:
            trade_prices, trade_volumes = self._parse_trades(trades)
            result.n_trades = len(trade_prices) if trade_prices is not None else 0

        # -- Kyle's Lambda ------------------------------------------------
        lam, t_stat, r2 = self._kyle_lambda(closes, volumes)
        result.kyle_lambda = lam
        result.kyle_lambda_t_stat = t_stat
        result.kyle_lambda_r2 = r2

        # -- Amihud -------------------------------------------------------
        result.amihud_illiquidity, result.amihud_series = self._amihud(
            closes, volumes, self.amihud_window
        )

        # -- VPIN ---------------------------------------------------------
        vpin_val, vpin_series = self._vpin(closes, volumes, self.vpin_n_buckets)
        result.vpin = vpin_val
        result.vpin_series = vpin_series

        # -- Roll spread --------------------------------------------------
        result.roll_spread, result.roll_effective_spread_bps = self._roll_spread(closes)

        # -- Corwin-Schultz -----------------------------------------------
        result.cs_spread, result.cs_spread_bps = self._corwin_schultz(highs, lows, closes)

        # -- Volatility signature -----------------------------------------
        result.vol_signature, result.noise_ratio = self._volatility_signature(closes)

        # -- Effective spread decomposition --------------------------------
        if trade_prices is not None and trade_volumes is not None and len(trade_prices) >= 10:
            perm, temp, share = self._spread_decomposition(trade_prices, trade_volumes)
        else:
            # Fallback: use bar close prices
            perm, temp, share = self._spread_decomposition(closes, volumes)
        result.permanent_impact = perm
        result.temporary_impact = temp
        result.permanent_share = share

        # -- Toxicity score -----------------------------------------------
        result.toxicity_score, result.toxic_flow = self._toxicity_score(
            result.vpin, result.kyle_lambda, result.amihud_illiquidity
        )

        return result

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_bars(
        bars: list[dict],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        opens = np.array([_safe_float(b.get("open")) for b in bars])
        highs = np.array([_safe_float(b.get("high")) for b in bars])
        lows = np.array([_safe_float(b.get("low")) for b in bars])
        closes = np.array([_safe_float(b.get("close")) for b in bars])
        volumes = np.array([_safe_float(b.get("volume"), 0.0) for b in bars])
        # Replace NaN closes with previous valid
        for i in range(1, len(closes)):
            if not np.isfinite(closes[i]):
                closes[i] = closes[i - 1]
        return opens, highs, lows, closes, volumes

    @staticmethod
    def _parse_trades(
        trades: list[dict],
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        if not trades:
            return None, None
        prices = np.array([_safe_float(t.get("price")) for t in trades])
        vols = np.array([_safe_float(t.get("volume"), 0.0) for t in trades])
        valid = np.isfinite(prices) & (prices > 0)
        if valid.sum() < 2:
            return None, None
        return prices[valid], vols[valid]

    # ------------------------------------------------------------------
    # Kyle's Lambda
    # ------------------------------------------------------------------

    @staticmethod
    def _kyle_lambda(
        closes: np.ndarray, volumes: np.ndarray
    ) -> tuple[float, float, float]:
        """
        Kyle (1985) price-impact coefficient.

        Regress: dP_t = lambda * SignedVolume_t + epsilon

        Signed volume approximated via tick rule on close prices.
        """
        n = len(closes)
        if n < 10:
            return float("nan"), float("nan"), float("nan")

        dp = np.diff(closes)
        # Tick rule: sign of price change determines buy/sell
        signs = np.sign(dp)
        signs[signs == 0] = 1.0  # no-change treated as continuation

        # Signed volume (use volumes[1:] aligned with dp)
        sv = signs * volumes[1:n]

        # Guard: need variance in signed volume
        if np.std(sv) < _EPS:
            return float("nan"), float("nan"), float("nan")

        # OLS: dp = alpha + lambda * sv
        X = np.column_stack([np.ones(len(sv)), sv])
        try:
            beta, residuals, _, _ = np.linalg.lstsq(X, dp, rcond=None)
        except np.linalg.LinAlgError:
            return float("nan"), float("nan"), float("nan")

        lam = float(beta[1])

        # t-statistic and R-squared
        dp_hat = X @ beta
        ss_res = float(np.sum((dp - dp_hat) ** 2))
        ss_tot = float(np.sum((dp - np.mean(dp)) ** 2))
        r2 = 1.0 - ss_res / max(ss_tot, _EPS)
        r2 = max(0.0, min(r2, 1.0))

        dof = len(sv) - 2
        if dof > 0 and ss_res > 0:
            mse = ss_res / dof
            xtx_inv = np.linalg.inv(X.T @ X)
            se_lam = math.sqrt(max(mse * xtx_inv[1, 1], 0.0))
            t_stat = lam / max(se_lam, _EPS)
        else:
            t_stat = float("nan")

        return lam, float(t_stat), r2

    # ------------------------------------------------------------------
    # Amihud illiquidity
    # ------------------------------------------------------------------

    @staticmethod
    def _amihud(
        closes: np.ndarray, volumes: np.ndarray, window: int = 20
    ) -> tuple[float, list[float]]:
        """
        Amihud (2002) illiquidity ratio: mean(|r_t| / dollar_volume_t).
        """
        n = len(closes)
        if n < 2:
            return float("nan"), []

        rets = np.abs(_returns(closes))
        # Dollar volume aligned with returns (use volumes[1:])
        dvol = closes[1:] * volumes[1:n]

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(dvol > _EPS, rets / dvol, float("nan"))

        # Rolling window
        series: list[float] = []
        for i in range(len(ratio)):
            start = max(0, i - window + 1)
            chunk = ratio[start : i + 1]
            valid = chunk[np.isfinite(chunk)]
            series.append(float(np.mean(valid)) if len(valid) > 0 else float("nan"))

        # Overall mean
        valid_all = ratio[np.isfinite(ratio)]
        overall = float(np.mean(valid_all)) if len(valid_all) > 0 else float("nan")

        return overall, series

    # ------------------------------------------------------------------
    # VPIN
    # ------------------------------------------------------------------

    @staticmethod
    def _vpin(
        closes: np.ndarray,
        volumes: np.ndarray,
        n_buckets: int = 50,
    ) -> tuple[float, list[float]]:
        """
        Volume-Synchronized Probability of Informed Trading (Easley et al. 2012).

        Uses Bulk Volume Classification (BVC): fraction of bar volume classified
        as buy/sell based on normalised price change within the bar.
        """
        n = len(closes)
        if n < n_buckets + 1:
            # Not enough bars for even one full bucket window
            n_buckets = max(5, n // 2)

        dp = np.diff(closes)
        # BVC: approximate buy fraction via CDF of normalised price change
        sigma = np.std(dp)
        if sigma < _EPS:
            sigma = 1.0

        from scipy.stats import norm

        z = dp / sigma
        buy_frac = norm.cdf(z)  # probability bar is buy-initiated

        buy_vol = buy_frac * volumes[1:n]
        sell_vol = (1.0 - buy_frac) * volumes[1:n]
        total_vol = volumes[1:n]

        # Volume buckets: aggregate bars until bucket reaches target volume
        total_volume = float(np.nansum(total_vol))
        if total_volume <= 0:
            return float("nan"), []

        bucket_vol_target = total_volume / n_buckets

        bucket_buy: list[float] = []
        bucket_sell: list[float] = []
        cum_buy = 0.0
        cum_sell = 0.0
        cum_vol = 0.0

        for i in range(len(buy_vol)):
            bv = float(buy_vol[i]) if np.isfinite(buy_vol[i]) else 0.0
            sv = float(sell_vol[i]) if np.isfinite(sell_vol[i]) else 0.0
            tv = float(total_vol[i]) if np.isfinite(total_vol[i]) else 0.0
            cum_buy += bv
            cum_sell += sv
            cum_vol += tv

            if cum_vol >= bucket_vol_target and bucket_vol_target > 0:
                bucket_buy.append(cum_buy)
                bucket_sell.append(cum_sell)
                cum_buy = 0.0
                cum_sell = 0.0
                cum_vol = 0.0

        # Flush remainder
        if cum_buy + cum_sell > 0:
            bucket_buy.append(cum_buy)
            bucket_sell.append(cum_sell)

        if not bucket_buy:
            return float("nan"), []

        bucket_buy_arr = np.array(bucket_buy)
        bucket_sell_arr = np.array(bucket_sell)
        bucket_total = bucket_buy_arr + bucket_sell_arr

        with np.errstate(divide="ignore", invalid="ignore"):
            oi = np.abs(bucket_buy_arr - bucket_sell_arr) / np.where(
                bucket_total > _EPS, bucket_total, float("nan")
            )

        # VPIN = rolling mean of order imbalance over last n_buckets buckets
        vpin_window = min(n_buckets, len(oi))
        vpin_series: list[float] = []
        for i in range(len(oi)):
            start = max(0, i - vpin_window + 1)
            chunk = oi[start : i + 1]
            valid = chunk[np.isfinite(chunk)]
            vpin_series.append(float(np.mean(valid)) if len(valid) > 0 else float("nan"))

        current_vpin = vpin_series[-1] if vpin_series else float("nan")
        return current_vpin, vpin_series

    # ------------------------------------------------------------------
    # Roll spread
    # ------------------------------------------------------------------

    @staticmethod
    def _roll_spread(closes: np.ndarray) -> tuple[float, float]:
        """
        Roll (1984) effective spread estimator:
        spread = 2 * sqrt(-Cov(dP_t, dP_{t-1}))  when autocovariance is negative.
        """
        dp = np.diff(closes)
        if len(dp) < 3:
            return float("nan"), float("nan")

        cov = float(np.cov(dp[:-1], dp[1:])[0, 1])

        if cov >= 0:
            # Positive autocovariance -- Roll spread undefined, set to 0
            return 0.0, 0.0

        spread = 2.0 * math.sqrt(-cov)
        mid = float(np.mean(closes))
        bps = (spread / max(mid, _EPS)) * 10_000 if mid > 0 else float("nan")
        return spread, bps

    # ------------------------------------------------------------------
    # Corwin-Schultz spread
    # ------------------------------------------------------------------

    @staticmethod
    def _corwin_schultz(
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
    ) -> tuple[float, float]:
        """
        Corwin & Schultz (2012) high-low spread estimator.

        Uses adjacent-period highs and lows to separate spread from volatility.
        """
        n = len(highs)
        if n < 3:
            return float("nan"), float("nan")

        valid = (
            np.isfinite(highs)
            & np.isfinite(lows)
            & (highs > _EPS)
            & (lows > _EPS)
            & (highs >= lows)
        )
        if valid.sum() < 3:
            return float("nan"), float("nan")

        h = highs[valid]
        lo = lows[valid]

        spreads: list[float] = []
        for i in range(len(h) - 1):
            # Single-period beta
            beta_single_1 = (math.log(h[i] / lo[i])) ** 2
            beta_single_2 = (math.log(h[i + 1] / lo[i + 1])) ** 2
            beta_sum = beta_single_1 + beta_single_2

            # Two-period high/low
            h2 = max(h[i], h[i + 1])
            l2 = min(lo[i], lo[i + 1])
            gamma = (math.log(h2 / l2)) ** 2

            # alpha calculation
            if beta_sum < _EPS:
                continue

            k1 = 3.0 - 2.0 * math.sqrt(2.0)
            if abs(k1) < _EPS:
                continue

            alpha = (math.sqrt(gamma) - math.sqrt(beta_sum)) / (
                k1 * math.sqrt(beta_sum)
            )

            # Spread = 2(e^alpha - 1) / (1 + e^alpha)
            if alpha > 10:
                s = 2.0  # cap at 200%
            elif alpha < -10:
                s = 0.0
            else:
                ea = math.exp(alpha)
                s = 2.0 * (ea - 1.0) / (1.0 + ea)
            spreads.append(max(s, 0.0))

        if not spreads:
            return float("nan"), float("nan")

        avg_spread = float(np.mean(spreads))
        bps = avg_spread * 10_000  # already in fractional terms
        return avg_spread, bps

    # ------------------------------------------------------------------
    # Volatility signature
    # ------------------------------------------------------------------

    @staticmethod
    def _volatility_signature(
        closes: np.ndarray,
    ) -> tuple[list[dict[str, float]], float]:
        """
        Realized-vol as a function of sampling frequency.

        If RV(1-bar) >> RV(5-bar), microstructure noise dominates.
        """
        n = len(closes)
        if n < 10:
            return [], float("nan")

        log_p = np.log(closes[np.isfinite(closes) & (closes > 0)])
        if len(log_p) < 10:
            return [], float("nan")

        freqs = [1, 2, 5, 10, 15, 20, 30]
        signature: list[dict[str, float]] = []
        rv_at: dict[int, float] = {}

        for freq in freqs:
            if freq >= len(log_p):
                break
            sampled = log_p[::freq]
            if len(sampled) < 3:
                continue
            lr = np.diff(sampled)
            rv = float(np.sqrt(np.sum(lr ** 2)))
            signature.append({"sampling_freq": freq, "realized_vol": rv})
            rv_at[freq] = rv

        noise_ratio = float("nan")
        if 1 in rv_at and 5 in rv_at and rv_at[5] > _EPS:
            noise_ratio = rv_at[1] / rv_at[5]

        return signature, noise_ratio

    # ------------------------------------------------------------------
    # Effective spread decomposition
    # ------------------------------------------------------------------

    @staticmethod
    def _spread_decomposition(
        prices: np.ndarray, volumes: np.ndarray
    ) -> tuple[float, float, float]:
        """
        Decompose effective spread into permanent (information) and temporary
        (liquidity) price impact following Huang & Stoll (1996).

        Permanent impact: how much of the price change persists.
        Temporary impact: mean-reverting component.
        """
        n = len(prices)
        if n < 10:
            return float("nan"), float("nan"), float("nan")

        dp = np.diff(prices)
        signs = np.sign(dp)
        signs[signs == 0] = 1.0

        if len(signs) < 3:
            return float("nan"), float("nan"), float("nan")

        # 5-period forward price change as permanent component
        lookforward = min(5, len(prices) - 2)
        perm_impacts: list[float] = []
        temp_impacts: list[float] = []

        for i in range(len(signs) - lookforward):
            immediate_impact = abs(dp[i])
            future_change = prices[i + 1 + lookforward] - prices[i + 1]
            # Permanent = portion of immediate impact that persists
            if immediate_impact > _EPS:
                perm = signs[i] * future_change
                perm_impacts.append(perm)
                temp_impacts.append(immediate_impact - max(perm, 0.0))

        if not perm_impacts:
            return float("nan"), float("nan"), float("nan")

        perm = max(float(np.nanmean(perm_impacts)), 0.0)
        temp = max(float(np.nanmean(temp_impacts)), 0.0)
        total = perm + temp
        share = perm / max(total, _EPS) if total > 0 else float("nan")

        return perm, temp, share

    # ------------------------------------------------------------------
    # Order flow toxicity (composite)
    # ------------------------------------------------------------------

    def _toxicity_score(
        self,
        vpin: float,
        kyle_lambda: float,
        amihud: float,
    ) -> tuple[float, bool]:
        """
        Composite toxicity score (0-1) combining VPIN, Kyle's lambda, and
        Amihud illiquidity.  Each component is rank-normalised to [0,1]
        using a sigmoid mapping, then weighted.

        toxic_flow = True if score > toxicity threshold.
        """

        def _sigmoid_norm(x: float, center: float, scale: float) -> float:
            """Map x to (0, 1) via logistic function centred at *center*."""
            if not np.isfinite(x):
                return 0.5  # agnostic
            z = (x - center) / max(scale, _EPS)
            z = max(min(z, 20.0), -20.0)  # clamp to avoid overflow
            return 1.0 / (1.0 + math.exp(-z))

        w = self.toxicity_weights

        # VPIN: already in [0,1], higher = more toxic
        vpin_score = float(np.clip(vpin, 0.0, 1.0)) if np.isfinite(vpin) else 0.5

        # Lambda: positive = price impact; normalise around typical equity values
        lambda_score = _sigmoid_norm(kyle_lambda, center=0.0, scale=0.001)

        # Amihud: log-scale normalisation (typical daily Amihud for liquid stock ~1e-10)
        if np.isfinite(amihud) and amihud > 0:
            log_amihud = math.log10(amihud + _EPS)
            amihud_score = _sigmoid_norm(log_amihud, center=-9.0, scale=2.0)
        else:
            amihud_score = 0.5

        total_w = sum(w.values())
        score = (
            w.get("vpin", 0.4) * vpin_score
            + w.get("lambda", 0.35) * lambda_score
            + w.get("amihud", 0.25) * amihud_score
        ) / max(total_w, _EPS)

        score = float(np.clip(score, 0.0, 1.0))
        toxic = score > 0.7
        return score, toxic
