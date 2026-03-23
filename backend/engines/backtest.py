"""
Backtesting / Validation / Performance Attribution Engine — Phase 7
Walk-forward testing, signal backtests, regime-specific analysis.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class BacktestResult:
    """Full backtest output with performance metrics and attribution."""
    strategy_name: str
    ticker: str = "UPST"
    start_date: dt.date | None = None
    end_date: dt.date | None = None

    # Performance
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0

    # Trade stats
    total_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    payoff_ratio: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0

    # Beta decomposition
    alpha_vs_spy: float = 0.0
    beta_vs_spy: float = 0.0

    # Trades
    trades: list[dict] = field(default_factory=list)

    # Regime breakdown
    performance_by_regime: dict = field(default_factory=dict)

    # Equity curve
    equity_curve: list[float] = field(default_factory=list)
    drawdown_series: list[float] = field(default_factory=list)


class BacktestEngine:
    """Backtests trading signals against historical price data."""

    def run(
        self,
        df: pd.DataFrame,
        signals: list[dict],
        strategy_name: str = "default",
        initial_capital: float = 100_000.0,
        position_size_pct: float = 10.0,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float = 10.0,
        spy_df: pd.DataFrame | None = None,
        slippage_pct: float = 0.05,   # half-spread slippage per side, percent
        commission_per_trade: float = 1.0,  # flat $ per trade (entry + exit)
    ) -> BacktestResult:
        """
        df: OHLCV DataFrame indexed by datetime
        signals: list of {"date": str, "direction": "long"|"short", "strength": float}
        slippage_pct: one-way slippage as % of price (applied at entry and exit)
        commission_per_trade: total round-trip commission in $
        """
        result = BacktestResult(strategy_name=strategy_name)

        if df.empty or signals is None or (hasattr(signals, '__len__') and len(signals) == 0):
            return result

        close = df["close"].astype(float)
        result.start_date = df.index[0].date() if hasattr(df.index[0], 'date') else df.index[0]
        result.end_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else df.index[-1]

        capital = initial_capital
        equity = [capital]
        trades = []
        position = None  # {"entry_price", "direction", "entry_date", "size"}

        for i in range(1, len(close)):
            date = df.index[i]
            price = float(close.iloc[i])

            # Check exits
            if position is not None:
                pnl_pct = (price - position["entry_price"]) / position["entry_price"]
                if position["direction"] == "short":
                    pnl_pct = -pnl_pct

                if pnl_pct <= -stop_loss_pct / 100:
                    # Stop loss hit — apply exit slippage (adverse: longs get worse fill)
                    slip = slippage_pct / 100
                    exit_price = price * (1 - slip) if position["direction"] == "long" else price * (1 + slip)
                    pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"]
                    if position["direction"] == "short":
                        pnl_pct = -pnl_pct
                    pnl = position["size"] * pnl_pct - commission_per_trade / 2
                    capital += position["size"] + pnl
                    trades.append({
                        "entry_date": position["entry_date"],
                        "exit_date": date,
                        "direction": position["direction"],
                        "entry_price": position["entry_price"],
                        "exit_price": round(exit_price, 4),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct * 100, 2),
                        "exit_reason": "stop",
                    })
                    position = None
                elif pnl_pct >= take_profit_pct / 100:
                    slip = slippage_pct / 100
                    exit_price = price * (1 - slip) if position["direction"] == "long" else price * (1 + slip)
                    pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"]
                    if position["direction"] == "short":
                        pnl_pct = -pnl_pct
                    pnl = position["size"] * pnl_pct - commission_per_trade / 2
                    capital += position["size"] + pnl
                    trades.append({
                        "entry_date": position["entry_date"],
                        "exit_date": date,
                        "direction": position["direction"],
                        "entry_price": position["entry_price"],
                        "exit_price": round(exit_price, 4),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct * 100, 2),
                        "exit_reason": "target",
                    })
                    position = None

            # Check entries
            if position is None:
                date_str = str(date.date()) if hasattr(date, 'date') else str(date)
                matching = [s for s in signals if s.get("date") == date_str]
                if matching:
                    sig = matching[0]
                    size = capital * position_size_pct / 100
                    # Apply entry slippage: longs pay more, shorts receive less
                    slip = slippage_pct / 100
                    entry_price = price * (1 + slip) if sig["direction"] == "long" else price * (1 - slip)
                    # Deduct commission at entry (half of round-trip)
                    commission_entry = commission_per_trade / 2
                    capital -= commission_entry
                    position = {
                        "entry_price": entry_price,
                        "direction": sig["direction"],
                        "entry_date": date,
                        "size": size,
                    }
                    capital -= size

            # Track equity
            if position:
                mark_pnl = (price - position["entry_price"]) / position["entry_price"]
                if position["direction"] == "short":
                    mark_pnl = -mark_pnl
                equity.append(capital + position["size"] * (1 + mark_pnl))
            else:
                equity.append(capital)

        # Close any open position
        if position and len(close) > 0:
            final_price = float(close.iloc[-1])
            slip = slippage_pct / 100
            exit_price = final_price * (1 - slip) if position["direction"] == "long" else final_price * (1 + slip)
            pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"]
            if position["direction"] == "short":
                pnl_pct = -pnl_pct
            pnl = position["size"] * pnl_pct - commission_per_trade / 2
            trades.append({
                "entry_date": position["entry_date"],
                "exit_date": df.index[-1],
                "direction": position["direction"],
                "entry_price": position["entry_price"],
                "exit_price": round(exit_price, 4),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct * 100, 2),
                "exit_reason": "end_of_period",
            })

        # ── Compute Metrics ──
        result.trades = trades
        result.total_trades = len(trades)
        result.equity_curve = [round(e, 2) for e in equity]

        if not trades:
            return result

        pnls = [t["pnl_pct"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        result.total_return = round((equity[-1] / initial_capital - 1) * 100, 2)
        days = (result.end_date - result.start_date).days if result.start_date and result.end_date else 365
        # Guard against inflated annualized returns for very short backtests
        if days >= 20:
            result.annualized_return = round(((1 + result.total_return / 100) ** (365 / days) - 1) * 100, 2)
        else:
            result.annualized_return = result.total_return  # Too short to annualize meaningfully

        result.win_rate = round(len(wins) / len(trades) * 100, 2) if trades else 0
        result.avg_win = round(np.mean(wins), 2) if wins else 0
        result.avg_loss = round(np.mean(losses), 2) if losses else 0
        result.payoff_ratio = round(abs(result.avg_win / result.avg_loss), 2) if result.avg_loss != 0 else 999.99
        result.expectancy = round(np.mean(pnls), 2) if pnls else 0
        result.profit_factor = round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else 999.99

        # Sharpe / Sortino
        equity_returns = pd.Series(equity).pct_change().dropna()
        if len(equity_returns) > 1 and equity_returns.std() > 0:
            result.sharpe_ratio = round(
                float(equity_returns.mean() / equity_returns.std() * np.sqrt(252)), 2,
            )
            downside = equity_returns[equity_returns < 0]
            if len(downside) > 0 and downside.std() > 0:
                result.sortino_ratio = round(
                    float(equity_returns.mean() / downside.std() * np.sqrt(252)), 2,
                )

        # Max drawdown
        equity_series = pd.Series(equity)
        cummax = equity_series.cummax()
        dd = (equity_series / cummax - 1) * 100
        result.max_drawdown = round(float(dd.min()), 2)
        result.drawdown_series = [round(float(d), 2) for d in dd]

        if result.max_drawdown != 0:
            result.calmar_ratio = round(result.annualized_return / abs(result.max_drawdown), 2)

        # Performance by regime (bull / bear / neutral based on 50-day SMA)
        if len(close) >= 50:
            sma50 = close.rolling(50).mean()
            regime_trades = {"bull": [], "bear": [], "neutral": []}
            for t in trades:
                entry_date = t["entry_date"]
                # Find the SMA value at entry
                try:
                    if entry_date in df.index:
                        idx = df.index.get_loc(entry_date)
                    else:
                        idx = df.index.get_indexer([entry_date], method="nearest")[0]
                    sma_val = float(sma50.iloc[idx]) if pd.notna(sma50.iloc[idx]) else None
                    price_val = float(close.iloc[idx])
                    if sma_val is not None:
                        if price_val > sma_val * 1.02:
                            regime_trades["bull"].append(t["pnl_pct"])
                        elif price_val < sma_val * 0.98:
                            regime_trades["bear"].append(t["pnl_pct"])
                        else:
                            regime_trades["neutral"].append(t["pnl_pct"])
                except (KeyError, IndexError):
                    regime_trades["neutral"].append(t["pnl_pct"])

            for regime, pnls_list in regime_trades.items():
                if pnls_list:
                    result.performance_by_regime[regime] = {
                        "trades": len(pnls_list),
                        "avg_pnl": round(float(np.mean(pnls_list)), 2),
                        "win_rate": round(sum(1 for p in pnls_list if p > 0) / len(pnls_list) * 100, 2),
                        "total_pnl": round(sum(pnls_list), 2),
                    }

        # Alpha / Beta vs SPY
        if spy_df is not None and not spy_df.empty:
            spy_close = spy_df["close"].astype(float)
            spy_ret = spy_close.pct_change().dropna()
            min_len = min(len(equity_returns), len(spy_ret))
            if min_len > 10:
                slope, intercept, _, _, _ = stats.linregress(
                    spy_ret.tail(min_len).values, equity_returns.tail(min_len).values,
                )
                result.beta_vs_spy = round(slope, 4)
                result.alpha_vs_spy = round(intercept * 252, 4)

        return result

    def walk_forward(
        self,
        df: pd.DataFrame,
        signal_generator,
        train_window: int = 252,
        test_window: int = 63,
        **kwargs,
    ) -> list[BacktestResult]:
        """Walk-forward backtesting with rolling train/test splits.

        signal_generator: callable(train_df) -> list[dict] where each dict has
            at minimum {"date": str, "direction": "long"|"short", "strength": float}
        """
        if not callable(signal_generator):
            raise TypeError(
                f"signal_generator must be callable, got {type(signal_generator).__name__}"
            )

        results = []
        total_bars = len(df)

        for start in range(0, total_bars - train_window - test_window, test_window):
            train_df = df.iloc[start:start + train_window]
            test_df = df.iloc[start + train_window:start + train_window + test_window]

            signals = signal_generator(train_df)

            # Validate signal format
            if not isinstance(signals, list):
                signals = list(signals) if signals else []
            valid_signals = []
            for sig in signals:
                if isinstance(sig, dict) and "date" in sig and "direction" in sig:
                    if sig["direction"] in ("long", "short"):
                        valid_signals.append(sig)

            result = self.run(test_df, valid_signals, **kwargs)
            results.append(result)

        return results
