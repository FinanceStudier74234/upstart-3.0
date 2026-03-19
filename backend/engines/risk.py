"""
Risk / Sizing / Portfolio Engine — Phase 7
Position sizing, risk budgeting, risk-of-ruin, survival analysis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class RiskMetrics:
    """Complete risk profile."""
    # VaR / CVaR
    var_95_1d: float | None = None
    var_99_1d: float | None = None
    cvar_95_1d: float | None = None  # Expected Shortfall
    var_95_1m: float | None = None

    # Drawdown
    max_drawdown: float | None = None
    current_drawdown: float | None = None
    avg_drawdown: float | None = None
    drawdown_duration_days: int | None = None

    # Risk of ruin
    risk_of_ruin_pct: float | None = None
    drawdown_threshold_pct: float = 20.0
    survival_probability: float | None = None

    # Position sizing
    vol_target_size_pct: float | None = None
    kelly_size_pct: float | None = None
    quarter_kelly_pct: float | None = None
    max_loss_size_pct: float | None = None
    recommended_size_pct: float | None = None

    # Tail risk
    skewness: float | None = None
    kurtosis: float | None = None
    tail_ratio: float | None = None  # 95th / 5th percentile returns

    # Risk budget
    risk_budget_used_pct: float = 0.0
    remaining_risk_budget_pct: float = 100.0


class RiskEngine:
    """Position sizing, risk metrics, and survival analysis."""

    def compute_risk(
        self,
        returns: np.ndarray,
        price: float,
        portfolio_value: float = 100_000.0,
        max_portfolio_loss_pct: float = 2.0,
        target_vol: float = 0.20,
        win_rate: float = 0.50,
        avg_win: float = 0.05,
        avg_loss: float = 0.03,
    ) -> RiskMetrics:
        """Compute full risk profile from return series."""
        rm = RiskMetrics()

        if len(returns) < 20:
            return rm

        # ── VaR / CVaR ──
        rm.var_95_1d = round(-float(np.percentile(returns, 5)) * price, 2)
        rm.var_99_1d = round(-float(np.percentile(returns, 1)) * price, 2)
        tail_5 = returns[returns <= np.percentile(returns, 5)]
        rm.cvar_95_1d = round(-float(np.mean(tail_5)) * price, 2) if len(tail_5) > 0 else rm.var_95_1d
        rm.var_95_1m = round(rm.var_95_1d * math.sqrt(21), 2) if rm.var_95_1d else None

        # ── Drawdown ──
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        dd = (cum_returns / running_max - 1) * 100
        rm.max_drawdown = round(float(np.min(dd)), 2)
        rm.current_drawdown = round(float(dd[-1]), 2)
        rm.avg_drawdown = round(float(np.mean(dd[dd < 0])), 2) if np.any(dd < 0) else 0.0

        # ── Distribution Properties ──
        rm.skewness = round(float(stats.skew(returns)), 4)
        rm.kurtosis = round(float(stats.kurtosis(returns)), 4)
        p95 = np.percentile(returns, 95)
        p5 = np.percentile(returns, 5)
        rm.tail_ratio = round(abs(p95 / p5), 4) if p5 != 0 else None

        # ── Position Sizing ──
        daily_vol = float(np.std(returns))
        annual_vol = daily_vol * math.sqrt(252)

        # 1. Volatility-targeted sizing
        if annual_vol > 0:
            rm.vol_target_size_pct = round(target_vol / annual_vol * 100, 2)
        else:
            rm.vol_target_size_pct = 100.0

        # 2. Kelly Criterion
        if avg_loss > 0:
            b = avg_win / avg_loss  # Payoff ratio
            kelly = (win_rate * (b + 1) - 1) / b if b > 0 else 0
            rm.kelly_size_pct = round(max(0, kelly * 100), 2)
            rm.quarter_kelly_pct = round(max(0, kelly * 25), 2)
        else:
            rm.kelly_size_pct = 0
            rm.quarter_kelly_pct = 0

        # 3. Max-loss sizing
        if daily_vol > 0:
            # Size such that max_portfolio_loss_pct is respected
            max_loss_per_unit = daily_vol * 2  # ~2 sigma daily
            rm.max_loss_size_pct = round(
                max_portfolio_loss_pct / (max_loss_per_unit * 100) * 100, 2,
            )
        else:
            rm.max_loss_size_pct = max_portfolio_loss_pct

        # 4. Recommended = minimum of approaches
        candidates = [rm.vol_target_size_pct, rm.quarter_kelly_pct, rm.max_loss_size_pct]
        rm.recommended_size_pct = round(min(c for c in candidates if c and c > 0), 2)

        # ── Risk of Ruin ──
        rm.risk_of_ruin_pct = self._risk_of_ruin(
            win_rate, avg_win, avg_loss, rm.drawdown_threshold_pct / 100,
        )
        rm.survival_probability = round(100 - (rm.risk_of_ruin_pct or 0), 2)

        return rm

    def _risk_of_ruin(
        self, win_rate: float, avg_win: float, avg_loss: float, max_dd: float,
    ) -> float:
        """
        Approximate risk of ruin using the classic formula:
        RoR = ((1 - edge) / (1 + edge)) ^ units_to_ruin
        where edge = win_rate * avg_win - (1 - win_rate) * avg_loss
        """
        edge = win_rate * avg_win - (1 - win_rate) * avg_loss
        if edge <= 0:
            return 100.0  # Negative expectancy = certain ruin

        avg_trade = win_rate * avg_win + (1 - win_rate) * (-avg_loss)
        if avg_trade == 0:
            return 100.0

        # Units of average trade to reach max drawdown
        units = max_dd / avg_trade if avg_trade > 0 else 1

        if edge >= 1:
            return 0.0
        ratio = (1 - edge) / (1 + edge)
        ror = ratio ** units * 100
        return round(max(0, min(100, ror)), 4)

    def stress_test(
        self,
        price: float,
        position_pct: float,
        portfolio_value: float,
        scenarios: dict[str, float],
    ) -> dict[str, dict]:
        """Run position through stress scenarios."""
        position_value = portfolio_value * position_pct / 100
        results = {}
        for name, shock_pct in scenarios.items():
            new_price = price * (1 + shock_pct / 100)
            pnl = position_value * shock_pct / 100
            results[name] = {
                "scenario": name,
                "shock_pct": shock_pct,
                "new_price": round(new_price, 2),
                "position_pnl": round(pnl, 2),
                "portfolio_impact_pct": round(pnl / portfolio_value * 100, 2),
                "survives": abs(pnl) < portfolio_value * 0.20,
            }
        return results

    def black_swan_scenarios(self, price: float) -> dict[str, dict]:
        """Pre-built extreme scenarios for UPST."""
        return self.stress_test(price, 10.0, 100_000, {
            "flash_crash_-20%": -20,
            "bear_market_-40%": -40,
            "funding_crisis_-50%": -50,
            "2022_style_-80%": -80,
            "squeeze_+50%": 50,
            "squeeze_+100%": 100,
            "earnings_miss_-25%": -25,
            "earnings_beat_+30%": 30,
            "fed_panic_-15%": -15,
            "macro_recovery_+40%": 40,
        })
