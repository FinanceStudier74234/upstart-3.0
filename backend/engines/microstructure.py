"""
Market Microstructure Engine — Kyle lambda, Amihud illiquidity, VPIN,
Roll/Corwin-Schultz spreads, order-flow toxicity.

References:
  Kyle (1985), Amihud (2002), Easley et al. (2012) VPIN,
  Roll (1984), Corwin & Schultz (2012)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class MicrostructureResult:
    """Complete microstructure analysis."""

    # Kyle's lambda (price impact coefficient)
    kyle_lambda: float | None = None
    kyle_lambda_t_stat: float | None = None

    # Amihud illiquidity ratio
    amihud_illiquidity: float | None = None
    amihud_illiquidity_20d: float | None = None

    # VPIN (Volume-synchronized Probability of Informed Trading)
    vpin: float | None = None
    vpin_series: list[float] = field(default_factory=list)

    # Roll (1984) spread estimator
    roll_spread: float | None = None

    # Corwin-Schultz (2012) high-low spread
    corwin_schultz_spread: float | None = None

    # Effective spread decomposition
    permanent_impact_pct: float | None = None  # information component
    temporary_impact_pct: float | None = None  # liquidity component

    # Order flow toxicity
    flow_toxicity_score: float | None = None  # 0-100
    flow_toxicity_regime: str = "normal"  # normal | elevated | toxic

    # Noise-to-signal
    microstructure_noise: float | None = None

    # Summary
    liquidity_score: float = 50.0  # 0-100, higher = more liquid
    n_observations: int = 0


class MicrostructureEngine:
    """Computes market microstructure metrics from OHLCV bar data."""

    def analyze(
        self,
        bars: list[dict],
        trades: list[dict] | None = None,
    ) -> MicrostructureResult:
        result = MicrostructureResult()

        if not bars or len(bars) < 20:
            return result

        # Extract arrays
        closes = np.array([b.get("close", 0) for b in bars], dtype=float)
        highs = np.array([b.get("high", 0) for b in bars], dtype=float)
        lows = np.array([b.get("low", 0) for b in bars], dtype=float)
        volumes = np.array([b.get("volume", 0) for b in bars], dtype=float)

        # Filter zeros
        mask = (closes > 0) & (highs > 0) & (lows > 0) & (volumes > 0)
        closes = closes[mask]
        highs = highs[mask]
        lows = lows[mask]
        volumes = volumes[mask]

        if len(closes) < 20:
            return result

        result.n_observations = len(closes)
        returns = np.diff(np.log(closes))

        # ── Kyle's Lambda ──
        result.kyle_lambda, result.kyle_lambda_t_stat = self._kyle_lambda(
            returns, volumes[1:]
        )

        # ── Amihud Illiquidity ──
        result.amihud_illiquidity = self._amihud(returns, closes[1:], volumes[1:])
        if len(returns) >= 20:
            result.amihud_illiquidity_20d = self._amihud(
                returns[-20:], closes[-20:], volumes[-20:]
            )

        # ── VPIN ──
        vpin_val, vpin_series = self._vpin(returns, volumes[1:])
        result.vpin = vpin_val
        result.vpin_series = vpin_series

        # ── Roll Spread ──
        result.roll_spread = self._roll_spread(returns)

        # ── Corwin-Schultz Spread ──
        result.corwin_schultz_spread = self._corwin_schultz(highs, lows)

        # ── Effective Spread Decomposition ──
        perm, temp = self._spread_decomposition(returns)
        result.permanent_impact_pct = perm
        result.temporary_impact_pct = temp

        # ── Microstructure Noise ──
        result.microstructure_noise = self._noise_ratio(returns)

        # ── Flow Toxicity ──
        result.flow_toxicity_score, result.flow_toxicity_regime = (
            self._flow_toxicity(result)
        )

        # ── Liquidity Score ──
        result.liquidity_score = self._liquidity_score(result)

        return result

    # ────────────────────────── Kyle's Lambda ──────────────────────────

    def _kyle_lambda(
        self, returns: np.ndarray, volumes: np.ndarray
    ) -> tuple[float | None, float | None]:
        """
        Price impact = lambda * signed_volume + epsilon
        Estimate lambda via OLS of |return| on sqrt(volume).
        """
        if len(returns) < 20 or len(volumes) < 20:
            return None, None

        min_len = min(len(returns), len(volumes))
        ret = returns[:min_len]
        vol = volumes[:min_len]

        # Sign volume by return direction (BVC approximation)
        signed_vol = np.sign(ret) * np.sqrt(vol)
        abs_ret = np.abs(ret)

        # Filter zeros
        nonzero = signed_vol != 0
        if nonzero.sum() < 10:
            return None, None

        x = signed_vol[nonzero]
        y = abs_ret[nonzero]

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        if std_err > 0:
            t_stat = slope / std_err
        else:
            t_stat = None

        return round(abs(slope), 10), round(t_stat, 4) if t_stat else None

    # ────────────────────────── Amihud Illiquidity ──────────────────────

    def _amihud(
        self, returns: np.ndarray, prices: np.ndarray, volumes: np.ndarray
    ) -> float | None:
        """Amihud (2002): average( |return| / dollar_volume )."""
        min_len = min(len(returns), len(prices), len(volumes))
        ret = returns[:min_len]
        p = prices[:min_len]
        v = volumes[:min_len]

        dollar_vol = p * v
        mask = dollar_vol > 0
        if mask.sum() < 5:
            return None

        illiq = np.mean(np.abs(ret[mask]) / dollar_vol[mask])
        return round(float(illiq), 14)

    # ────────────────────────── VPIN ──────────────────────────────────

    def _vpin(
        self, returns: np.ndarray, volumes: np.ndarray, n_buckets: int = 50
    ) -> tuple[float | None, list[float]]:
        """
        Volume-Synchronized Probability of Informed Trading.
        Uses BVC (Bulk Volume Classification) to classify each bar's
        volume as buy or sell.
        """
        if len(returns) < n_buckets or len(volumes) < n_buckets:
            return None, []

        min_len = min(len(returns), len(volumes))
        ret = returns[:min_len]
        vol = volumes[:min_len]

        # BVC: classify volume by CDF of standardized return
        sigma = np.std(ret)
        if sigma <= 0:
            return None, []

        z = ret / sigma
        buy_pct = stats.norm.cdf(z)
        buy_vol = vol * buy_pct
        sell_vol = vol * (1.0 - buy_pct)

        # Compute VPIN in rolling buckets
        total_vol = np.sum(vol)
        bucket_size = total_vol / n_buckets

        vpin_values = []
        cum_buy = 0.0
        cum_sell = 0.0
        cum_vol = 0.0

        for i in range(min_len):
            cum_buy += buy_vol[i]
            cum_sell += sell_vol[i]
            cum_vol += vol[i]

            if cum_vol >= bucket_size and cum_vol > 0:
                oi = abs(cum_buy - cum_sell) / cum_vol
                vpin_values.append(round(float(oi), 6))
                cum_buy = 0.0
                cum_sell = 0.0
                cum_vol = 0.0

        if not vpin_values:
            return None, []

        current_vpin = round(float(np.mean(vpin_values[-min(10, len(vpin_values)):])), 4)
        return current_vpin, vpin_values[-100:]  # Keep last 100

    # ────────────────────────── Roll Spread ──────────────────────────

    def _roll_spread(self, returns: np.ndarray) -> float | None:
        """
        Roll (1984): effective spread = 2 * sqrt( -cov(dp_t, dp_{t-1}) )
        Only valid when autocovariance is negative.
        """
        if len(returns) < 20:
            return None

        price_changes = returns  # log returns ≈ price changes
        if len(price_changes) < 2:
            return None

        autocov = np.cov(price_changes[:-1], price_changes[1:])[0, 1]

        if autocov >= 0:
            return 0.0  # No Roll spread detectable

        spread = 2.0 * math.sqrt(-autocov)
        return round(float(spread), 8)

    # ────────────────────────── Corwin-Schultz ──────────────────────

    def _corwin_schultz(
        self, highs: np.ndarray, lows: np.ndarray
    ) -> float | None:
        """
        Corwin & Schultz (2012) high-low spread estimator.
        Uses adjacent bars' high and low prices.
        """
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Beta: average sum of squared log(H/L) over pairs
        log_hl = np.log(highs / lows)
        log_hl_sq = log_hl ** 2

        # Single-period beta
        beta_vals = []
        for i in range(1, len(highs)):
            # 2-period high/low
            h2 = max(highs[i - 1], highs[i])
            l2 = min(lows[i - 1], lows[i])
            if h2 <= 0 or l2 <= 0 or h2 <= l2:
                continue
            gamma = np.log(h2 / l2) ** 2
            beta = log_hl_sq[i - 1] + log_hl_sq[i]
            beta_vals.append((gamma, beta))

        if len(beta_vals) < 5:
            return None

        gamma_arr = np.array([x[0] for x in beta_vals])
        beta_arr = np.array([x[1] for x in beta_vals])

        gamma_mean = np.mean(gamma_arr)
        beta_mean = np.mean(beta_arr)

        k = 2.0 * math.sqrt(2.0) - 1.0
        denom = 3.0 - 2.0 * math.sqrt(2.0)

        alpha_val = (
            math.sqrt(2.0 * beta_mean) - math.sqrt(beta_mean)
        ) / denom - math.sqrt(gamma_mean / denom)

        # Clamp negative
        alpha_val = max(0.0, alpha_val)
        spread = 2.0 * (math.exp(alpha_val) - 1.0) / (1.0 + math.exp(alpha_val))

        return round(float(spread), 8)

    # ────────────────────────── Spread Decomposition ──────────────────

    def _spread_decomposition(
        self, returns: np.ndarray
    ) -> tuple[float | None, float | None]:
        """
        Decompose effective spread into permanent (information) and
        temporary (liquidity) components using return autocorrelation.
        """
        if len(returns) < 30:
            return None, None

        # Variance ratio: permanent = long-run variance / short-run
        var_1 = np.var(returns)
        if var_1 <= 0:
            return None, None

        # 5-day returns
        n5 = len(returns) // 5
        if n5 < 5:
            return None, None

        ret_5d = np.array([
            np.sum(returns[i * 5:(i + 1) * 5]) for i in range(n5)
        ])
        var_5 = np.var(ret_5d) / 5.0

        vr = var_5 / var_1 if var_1 > 0 else 1.0
        # VR > 1: momentum (permanent dominates), VR < 1: reversal (temporary dominates)
        permanent = round(min(1.0, max(0.0, vr)) * 100, 2)
        temporary = round(100.0 - permanent, 2)

        return permanent, temporary

    # ────────────────────────── Microstructure Noise ──────────────────

    def _noise_ratio(self, returns: np.ndarray) -> float | None:
        """
        Estimate microstructure noise from first-order negative
        autocorrelation in returns (bid-ask bounce).
        """
        if len(returns) < 30:
            return None

        ac1 = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        if np.isnan(ac1):
            return None

        # Negative autocorrelation = more noise
        noise = max(0.0, -ac1)
        return round(float(noise), 6)

    # ────────────────────────── Flow Toxicity ──────────────────────────

    def _flow_toxicity(
        self, result: MicrostructureResult
    ) -> tuple[float, str]:
        """Combined toxicity score from VPIN + lambda + Amihud."""
        score = 0.0
        count = 0

        if result.vpin is not None:
            # VPIN > 0.5 is concerning, > 0.7 is toxic
            score += min(100, result.vpin * 130)
            count += 1

        if result.kyle_lambda is not None:
            # Normalize lambda (higher = more impact = more toxic)
            # Typical lambda for liquid stocks: 1e-8 to 1e-6
            log_lambda = math.log10(max(result.kyle_lambda, 1e-12))
            toxicity_from_lambda = min(100, max(0, (log_lambda + 8) * 20))
            score += toxicity_from_lambda
            count += 1

        if result.amihud_illiquidity is not None and result.amihud_illiquidity > 0:
            log_amihud = math.log10(max(result.amihud_illiquidity, 1e-15))
            toxicity_from_amihud = min(100, max(0, (log_amihud + 12) * 12))
            score += toxicity_from_amihud
            count += 1

        if count == 0:
            return 50.0, "normal"

        avg = round(score / count, 2)

        if avg > 70:
            regime = "toxic"
        elif avg > 45:
            regime = "elevated"
        else:
            regime = "normal"

        return avg, regime

    # ────────────────────────── Liquidity Score ──────────────────────

    def _liquidity_score(self, result: MicrostructureResult) -> float:
        """Higher = more liquid. Inverted toxicity + spread metrics."""
        base = 50.0

        if result.flow_toxicity_score is not None:
            base += (50 - result.flow_toxicity_score) * 0.4

        if result.roll_spread is not None:
            # Lower spread = more liquid
            spread_penalty = min(20, result.roll_spread * 1000)
            base += (20 - spread_penalty) * 0.3

        if result.corwin_schultz_spread is not None:
            cs_penalty = min(20, result.corwin_schultz_spread * 500)
            base += (20 - cs_penalty) * 0.3

        return round(max(0, min(100, base)), 2)
