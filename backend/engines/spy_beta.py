"""
SPY / Beta / Market-Relationship Engine
Core system variable — models UPST's relationship to SPY and the broad market.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from backend.config.constants import ROLLING_BETA_WINDOW, ROLLING_CORR_WINDOW


@dataclass
class SPYRelationship:
    """Complete UPST-vs-SPY relationship snapshot."""
    # Current estimates
    beta: float | None = None
    correlation: float | None = None
    alpha_annualized: float | None = None

    # Rolling series (recent values)
    rolling_beta_latest: float | None = None
    rolling_corr_latest: float | None = None
    rolling_beta_mean: float | None = None
    rolling_beta_std: float | None = None

    # Capture ratios
    upside_capture: float | None = None
    downside_capture: float | None = None
    capture_ratio: float | None = None  # upside / downside

    # UPST/SPY ratio
    price_ratio: float | None = None
    ratio_sma20: float | None = None
    ratio_trend: str = "neutral"  # strengthening | weakening | neutral

    # Decomposition
    market_return_component: float | None = None  # beta * SPY_return
    idiosyncratic_return: float | None = None  # actual - market_return_component
    pct_market_driven: float | None = None  # R² from regression

    # Regime classification
    is_beta_vehicle: bool = False  # Trading as market-beta or idiosyncratic story?
    regime: str = "mixed"  # market_driven | idiosyncratic | mixed

    # Drawdown transmission
    spy_drawdown_current: float | None = None
    upst_drawdown_current: float | None = None
    drawdown_amplification: float | None = None  # UPST_dd / SPY_dd

    # Relative strength
    relative_strength_score: float = 50.0  # 0..100

    # For scenario engine
    beta_for_scenarios: float = 1.5  # Used to propagate SPY shocks to UPST


class SPYBetaEngine:
    """Computes all SPY/market relationship metrics."""

    def analyze(
        self, upst_df: pd.DataFrame, spy_df: pd.DataFrame,
    ) -> SPYRelationship:
        """
        Expects DataFrames with 'close' column indexed by datetime.
        """
        rel = SPYRelationship()
        if upst_df.empty or spy_df.empty:
            return rel

        # Align on common dates
        merged = pd.DataFrame({
            "upst": upst_df["close"],
            "spy": spy_df["close"],
        }).dropna()

        if len(merged) < 30:
            return rel

        upst_ret = merged["upst"].pct_change().dropna()
        spy_ret = merged["spy"].pct_change().dropna()

        # Align lengths
        min_len = min(len(upst_ret), len(spy_ret))
        upst_ret = upst_ret.tail(min_len)
        spy_ret = spy_ret.tail(min_len)

        # ── Full-sample OLS regression ──
        slope, intercept, r_value, _, _ = stats.linregress(spy_ret.values, upst_ret.values)
        if np.isnan(slope) or np.isnan(r_value):
            return rel  # Return defaults if regression fails
        rel.beta = round(float(slope), 4)
        rel.correlation = round(float(r_value), 4)
        rel.alpha_annualized = round(float(intercept) * 252, 4)
        rel.pct_market_driven = round(float(r_value ** 2) * 100, 2)
        rel.beta_for_scenarios = rel.beta

        # ── Rolling beta & correlation ──
        if len(spy_ret) >= ROLLING_BETA_WINDOW:
            rolling_betas = []
            rolling_corrs = []
            for i in range(ROLLING_BETA_WINDOW, len(spy_ret) + 1):
                window_spy = spy_ret.iloc[i - ROLLING_BETA_WINDOW:i]
                window_upst = upst_ret.iloc[i - ROLLING_BETA_WINDOW:i]
                s, _, r, _, _ = stats.linregress(window_spy.values, window_upst.values)
                rolling_betas.append(s)
                rolling_corrs.append(r)

            rel.rolling_beta_latest = round(float(rolling_betas[-1]), 4)
            rel.rolling_corr_latest = round(float(rolling_corrs[-1]), 4)
            rel.rolling_beta_mean = round(float(np.mean(rolling_betas)), 4)
            rel.rolling_beta_std = round(float(np.std(rolling_betas)), 4)

        # ── Upside / Downside capture ──
        up_days = spy_ret > 0
        down_days = spy_ret < 0

        if up_days.sum() > 5:
            upst_up_mean = upst_ret[up_days].mean()
            spy_up_mean = spy_ret[up_days].mean()
            rel.upside_capture = round(float(upst_up_mean / spy_up_mean * 100), 2) if spy_up_mean != 0 else None

        if down_days.sum() > 5:
            upst_down_mean = upst_ret[down_days].mean()
            spy_down_mean = spy_ret[down_days].mean()
            rel.downside_capture = round(float(upst_down_mean / spy_down_mean * 100), 2) if spy_down_mean != 0 else None

        if rel.upside_capture and rel.downside_capture and rel.downside_capture != 0:
            rel.capture_ratio = round(rel.upside_capture / rel.downside_capture, 4)

        # ── UPST/SPY ratio ──
        ratio = merged["upst"] / merged["spy"]
        rel.price_ratio = round(float(ratio.iloc[-1]), 6)
        if len(ratio) >= 20:
            rel.ratio_sma20 = round(float(ratio.rolling(20).mean().iloc[-1]), 6)
            if rel.price_ratio > rel.ratio_sma20:
                rel.ratio_trend = "strengthening"
            elif rel.price_ratio < rel.ratio_sma20:
                rel.ratio_trend = "weakening"

        # ── Market vs Idiosyncratic decomposition (latest period) ──
        if rel.beta is not None:
            spy_latest = float(spy_ret.iloc[-1])
            upst_latest = float(upst_ret.iloc[-1])
            rel.market_return_component = round(rel.beta * spy_latest, 6)
            rel.idiosyncratic_return = round(upst_latest - rel.market_return_component, 6)

        # ── Regime classification ──
        if rel.pct_market_driven is not None:
            if rel.pct_market_driven > 40:
                rel.regime = "market_driven"
                rel.is_beta_vehicle = True
            elif rel.pct_market_driven < 15:
                rel.regime = "idiosyncratic"
                rel.is_beta_vehicle = False
            else:
                rel.regime = "mixed"
                rel.is_beta_vehicle = False

        # ── Drawdown transmission ──
        spy_cummax = merged["spy"].cummax()
        spy_dd = (merged["spy"] / spy_cummax - 1)
        upst_cummax = merged["upst"].cummax()
        upst_dd = (merged["upst"] / upst_cummax - 1)
        rel.spy_drawdown_current = round(float(spy_dd.iloc[-1]) * 100, 2)
        rel.upst_drawdown_current = round(float(upst_dd.iloc[-1]) * 100, 2)
        if rel.spy_drawdown_current and rel.spy_drawdown_current != 0:
            rel.drawdown_amplification = round(
                rel.upst_drawdown_current / rel.spy_drawdown_current, 2,
            )

        # ── Relative Strength Score ──
        rel.relative_strength_score = self._compute_relative_strength_score(
            upst_ret, spy_ret, rel,
        )

        # ── Kalman Filter Time-Varying Beta (if available) ──
        try:
            from backend.engines.kalman_beta import KalmanBetaEngine
            kalman = KalmanBetaEngine()
            kalman_result = kalman.filter(upst_ret.values, spy_ret.values)
            if kalman_result.current_beta is not None:
                rel.beta_for_scenarios = kalman_result.current_beta
                # Use Kalman beta as rolling latest if available (more accurate)
                rel.rolling_beta_latest = round(kalman_result.current_beta, 4)
        except Exception:
            pass

        return rel

    def _compute_relative_strength_score(
        self, upst_ret: pd.Series, spy_ret: pd.Series, rel: SPYRelationship,
    ) -> float:
        """
        Relative Strength vs SPY Score (0-100):
        - Recent relative return (20d): 30 pts
        - Capture ratio: 25 pts
        - Ratio trend: 20 pts
        - Rolling beta stability: 15 pts
        - Idiosyncratic strength: 10 pts
        """
        score = 50.0

        # Recent relative return
        if len(upst_ret) >= 20 and len(spy_ret) >= 20:
            rel_ret = upst_ret.tail(20).sum() - spy_ret.tail(20).sum()
            score += min(15, max(-15, rel_ret * 100))

        # Capture ratio bonus
        if rel.capture_ratio is not None:
            if rel.capture_ratio > 1.2:
                score += 10
            elif rel.capture_ratio > 1.0:
                score += 5
            elif rel.capture_ratio < 0.8:
                score -= 10

        # Ratio trend
        if rel.ratio_trend == "strengthening":
            score += 10
        elif rel.ratio_trend == "weakening":
            score -= 10

        return round(max(0, min(100, score)), 2)

    def propagate_spy_shock(
        self, rel: SPYRelationship, spy_return_pct: float,
    ) -> dict:
        """Given a hypothetical SPY return, estimate UPST impact."""
        beta = rel.beta_for_scenarios
        expected_upst_return = beta * spy_return_pct
        # Add nonlinearity for large moves (convexity)
        if abs(spy_return_pct) > 3:
            convexity_factor = 1 + 0.1 * (abs(spy_return_pct) - 3)
            expected_upst_return *= convexity_factor

        return {
            "spy_return_pct": spy_return_pct,
            "expected_upst_return_pct": round(expected_upst_return, 2),
            "beta_used": beta,
            "convexity_adjusted": abs(spy_return_pct) > 3,
            "confidence": "high" if rel.pct_market_driven and rel.pct_market_driven > 30 else "moderate",
        }
