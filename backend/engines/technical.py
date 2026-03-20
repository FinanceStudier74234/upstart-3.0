"""
Technical Analysis Engine — Domain A
Full price-action, technicals, support/resistance, regime detection.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backend.config.constants import (
    MA_PERIODS, RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ATR_PERIOD, BOLLINGER_PERIOD, BOLLINGER_STD, ADX_PERIOD,
)


@dataclass
class TechnicalSnapshot:
    """Complete technical state at a point in time."""
    ticker: str
    timestamp: dt.datetime
    price: float
    # Moving averages
    sma: dict[int, float] = field(default_factory=dict)
    ema: dict[int, float] = field(default_factory=dict)
    # Oscillators
    rsi: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    stochastic_k: float | None = None
    stochastic_d: float | None = None
    # Volatility
    atr: float | None = None
    atr_pct: float | None = None
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None
    bollinger_pct_b: float | None = None
    bollinger_bandwidth: float | None = None
    # Trend
    adx: float | None = None
    trend_direction: str = "neutral"  # up | down | neutral
    trend_strength: str = "weak"  # weak | moderate | strong
    # Levels
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    # VWAP
    vwap: float | None = None
    vwap_deviation: float | None = None
    # Regime
    volatility_regime: str = "normal"  # compressed | normal | expanded
    momentum_regime: str = "neutral"  # strong_up | up | neutral | down | strong_down
    range_regime: str = "ranging"  # trending | ranging | breakout | breakdown
    # Zones
    buy_zones: list[tuple[float, float]] = field(default_factory=list)
    sell_zones: list[tuple[float, float]] = field(default_factory=list)
    short_zones: list[tuple[float, float]] = field(default_factory=list)
    cover_zones: list[tuple[float, float]] = field(default_factory=list)
    invalidation_level: float | None = None
    # Gaps
    gap_up: bool = False
    gap_down: bool = False
    gap_fill_probability: float | None = None
    # Score
    technical_strength_score: float = 50.0  # 0..100


class TechnicalEngine:
    """Computes full technical analysis from OHLCV data."""

    def analyze(self, df: pd.DataFrame, ticker: str = "UPST") -> TechnicalSnapshot:
        """
        Analyze a DataFrame with columns: open, high, low, close, volume.
        Index should be datetime.
        """
        if df.empty or len(df) < 50:
            return TechnicalSnapshot(
                ticker=ticker, timestamp=dt.datetime.now(dt.timezone.utc), price=0.0,
            )

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)
        price = float(close.iloc[-1])
        ts = df.index[-1] if isinstance(df.index[-1], dt.datetime) else dt.datetime.now(dt.timezone.utc)

        snap = TechnicalSnapshot(ticker=ticker, timestamp=ts, price=price)

        # ── Moving Averages ──
        for p in MA_PERIODS:
            if len(close) >= p:
                snap.sma[p] = round(float(close.rolling(p).mean().iloc[-1]), 4)
                snap.ema[p] = round(float(close.ewm(span=p, adjust=False).mean().iloc[-1]), 4)

        # ── RSI ──
        snap.rsi = self._rsi(close, RSI_PERIOD)

        # ── MACD ──
        snap.macd_line, snap.macd_signal, snap.macd_histogram = self._macd(
            close, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
        )

        # ── ATR ──
        snap.atr = self._atr(high, low, close, ATR_PERIOD)
        if snap.atr and price > 0:
            snap.atr_pct = round(snap.atr / price * 100, 4)

        # ── Bollinger Bands ──
        if len(close) >= BOLLINGER_PERIOD:
            sma = close.rolling(BOLLINGER_PERIOD).mean()
            std = close.rolling(BOLLINGER_PERIOD).std()
            snap.bollinger_upper = round(float(sma.iloc[-1] + BOLLINGER_STD * std.iloc[-1]), 4)
            snap.bollinger_lower = round(float(sma.iloc[-1] - BOLLINGER_STD * std.iloc[-1]), 4)
            bw = snap.bollinger_upper - snap.bollinger_lower
            if bw > 0:
                snap.bollinger_pct_b = round((price - snap.bollinger_lower) / bw, 4)
                snap.bollinger_bandwidth = round(bw / float(sma.iloc[-1]) * 100, 4)

        # ── ADX ──
        snap.adx = self._adx(high, low, close, ADX_PERIOD)

        # ── Stochastic ──
        snap.stochastic_k, snap.stochastic_d = self._stochastic(high, low, close)

        # ── VWAP ──
        if "vwap" in df.columns and pd.notna(df["vwap"].iloc[-1]):
            snap.vwap = float(df["vwap"].iloc[-1])
        else:
            typical = (high + low + close) / 3
            snap.vwap = round(float((typical * volume).sum() / volume.sum()), 4) if volume.sum() > 0 else price
        if snap.vwap and snap.vwap > 0:
            snap.vwap_deviation = round((price - snap.vwap) / snap.vwap * 100, 4)

        # ── Support / Resistance ──
        snap.support_levels, snap.resistance_levels = self._find_levels(high, low, close, price)

        # ── Regime Detection ──
        snap.volatility_regime = self._vol_regime(close)
        snap.momentum_regime = self._momentum_regime(snap.rsi, snap.macd_histogram, snap.adx)
        snap.trend_direction, snap.trend_strength = self._trend_classification(snap)
        snap.range_regime = self._range_regime(snap)

        # ── Gap Detection ──
        if len(df) >= 2:
            prev_close = float(close.iloc[-2])
            today_open = float(df["open"].iloc[-1])
            gap_pct = (today_open - prev_close) / prev_close * 100
            if gap_pct > 1.0:
                snap.gap_up = True
                snap.gap_fill_probability = self._empirical_gap_fill_prob(df, direction="up")
            elif gap_pct < -1.0:
                snap.gap_down = True
                snap.gap_fill_probability = self._empirical_gap_fill_prob(df, direction="down")

        # ── Zones ──
        snap.buy_zones = self._compute_buy_zones(snap)
        snap.sell_zones = self._compute_sell_zones(snap)
        snap.short_zones = self._compute_short_zones(snap)
        snap.cover_zones = self._compute_cover_zones(snap)

        # ── Technical Strength Score ──
        snap.technical_strength_score = self._compute_score(snap)

        return snap

    # ── Indicator Implementations ──

    def _rsi(self, close: pd.Series, period: int) -> float | None:
        if len(close) < period + 1:
            return None
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return round(float(val), 2) if pd.notna(val) else None

    def _macd(self, close: pd.Series, fast: int, slow: int, signal: int):
        if len(close) < slow + signal:
            return None, None, None
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return (
            round(float(macd_line.iloc[-1]), 4),
            round(float(signal_line.iloc[-1]), 4),
            round(float(histogram.iloc[-1]), 4),
        )

    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> float | None:
        if len(close) < period + 1:
            return None
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        val = atr.iloc[-1]
        return round(float(val), 4) if pd.notna(val) else None

    def _adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> float | None:
        if len(close) < 2 * period:
            return None
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        tr = pd.concat([
            high - low, (high - close.shift()).abs(), (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        adx = dx.rolling(period).mean()
        val = adx.iloc[-1]
        return round(float(val), 2) if pd.notna(val) else None

    def _stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3):
        if len(close) < k_period + d_period:
            return None, None
        lowest = low.rolling(k_period).min()
        highest = high.rolling(k_period).max()
        k = 100 * (close - lowest) / (highest - lowest)
        d = k.rolling(d_period).mean()
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]
        return (
            round(float(k_val), 2) if pd.notna(k_val) else None,
            round(float(d_val), 2) if pd.notna(d_val) else None,
        )

    def _find_levels(self, high: pd.Series, low: pd.Series, close: pd.Series, price: float):
        supports = []
        resistances = []
        # Use local minima/maxima from last 60 bars
        window = min(60, len(close))
        recent_low = low.tail(window)
        recent_high = high.tail(window)
        for i in range(2, len(recent_low) - 2):
            if recent_low.iloc[i] < recent_low.iloc[i-1] and recent_low.iloc[i] < recent_low.iloc[i-2] \
               and recent_low.iloc[i] < recent_low.iloc[i+1] and recent_low.iloc[i] < recent_low.iloc[i+2]:
                lvl = round(float(recent_low.iloc[i]), 2)
                if lvl < price:
                    supports.append(lvl)
            if recent_high.iloc[i] > recent_high.iloc[i-1] and recent_high.iloc[i] > recent_high.iloc[i-2] \
               and recent_high.iloc[i] > recent_high.iloc[i+1] and recent_high.iloc[i] > recent_high.iloc[i+2]:
                lvl = round(float(recent_high.iloc[i]), 2)
                if lvl > price:
                    resistances.append(lvl)
        supports = sorted(set(supports), reverse=True)[:5]
        resistances = sorted(set(resistances))[:5]
        return supports, resistances

    def _empirical_gap_fill_prob(
        self, df: pd.DataFrame, direction: str, lookback: int = 252,
    ) -> float:
        """
        Estimate gap fill probability from historical data.
        A gap is 'filled' if the close returns to the prior day's close
        within the same session (for gap ups: low <= prev close,
        for gap downs: high >= prev close).
        Falls back to 0.65 (up) / 0.70 (down) if insufficient data.
        """
        close = df["close"].astype(float)
        opens = df["open"].astype(float)
        highs = df["high"].astype(float)
        lows = df["low"].astype(float)

        window = min(lookback, len(df) - 1)
        if window < 30:
            return 0.65 if direction == "up" else 0.70

        gaps_found = 0
        gaps_filled = 0

        for i in range(-window, -1):
            prev_c = float(close.iloc[i - 1])
            open_i = float(opens.iloc[i])
            gap_pct = (open_i - prev_c) / prev_c * 100

            if direction == "up" and gap_pct > 1.0:
                gaps_found += 1
                if float(lows.iloc[i]) <= prev_c:
                    gaps_filled += 1
            elif direction == "down" and gap_pct < -1.0:
                gaps_found += 1
                if float(highs.iloc[i]) >= prev_c:
                    gaps_filled += 1

        if gaps_found < 5:
            return 0.65 if direction == "up" else 0.70

        return round(gaps_filled / gaps_found, 2)

    def _vol_regime(self, close: pd.Series) -> str:
        if len(close) < 63:
            return "normal"
        returns = close.pct_change().dropna()
        vol_21 = returns.tail(21).std() * np.sqrt(252)
        vol_63 = returns.tail(63).std() * np.sqrt(252)
        ratio = vol_21 / vol_63 if vol_63 > 0 else 1.0
        if ratio < 0.7:
            return "compressed"
        elif ratio > 1.3:
            return "expanded"
        return "normal"

    def _momentum_regime(self, rsi, macd_hist, adx) -> str:
        score = 0
        if rsi is not None:
            if rsi > 70: score += 2
            elif rsi > 55: score += 1
            elif rsi < 30: score -= 2
            elif rsi < 45: score -= 1
        if macd_hist is not None:
            if macd_hist > 0: score += 1
            else: score -= 1
        if score >= 3: return "strong_up"
        if score >= 1: return "up"
        if score <= -3: return "strong_down"
        if score <= -1: return "down"
        return "neutral"

    def _trend_classification(self, snap: TechnicalSnapshot) -> tuple[str, str]:
        above_count = 0
        total = 0
        for p in [20, 50, 200]:
            if p in snap.sma:
                total += 1
                if snap.price > snap.sma[p]:
                    above_count += 1
        if total == 0:
            return "neutral", "weak"
        ratio = above_count / total
        if ratio >= 0.8:
            direction = "up"
        elif ratio <= 0.2:
            direction = "down"
        else:
            direction = "neutral"
        strength = "strong" if snap.adx and snap.adx > 25 else ("moderate" if snap.adx and snap.adx > 15 else "weak")
        return direction, strength

    def _range_regime(self, snap: TechnicalSnapshot) -> str:
        if snap.bollinger_bandwidth is not None and snap.bollinger_bandwidth < 8:
            return "ranging"  # compressed = likely breakout coming
        if snap.adx and snap.adx > 25 and snap.trend_direction in ("up", "down"):
            if snap.trend_direction == "up":
                return "breakout"
            return "breakdown"
        return "ranging" if (snap.adx and snap.adx < 20) else "trending"

    def _compute_buy_zones(self, snap: TechnicalSnapshot) -> list[tuple[float, float]]:
        zones = []
        if snap.support_levels:
            s = snap.support_levels[0]
            zones.append((round(s * 0.99, 2), round(s * 1.01, 2)))
        if snap.vwap and snap.vwap < snap.price:
            zones.append((round(snap.vwap * 0.99, 2), round(snap.vwap * 1.01, 2)))
        if snap.bollinger_lower:
            zones.append((round(snap.bollinger_lower * 0.99, 2), round(snap.bollinger_lower * 1.01, 2)))
        return zones

    def _compute_sell_zones(self, snap: TechnicalSnapshot) -> list[tuple[float, float]]:
        zones = []
        if snap.resistance_levels:
            r = snap.resistance_levels[0]
            zones.append((round(r * 0.99, 2), round(r * 1.01, 2)))
        if snap.bollinger_upper:
            zones.append((round(snap.bollinger_upper * 0.99, 2), round(snap.bollinger_upper * 1.01, 2)))
        return zones

    def _compute_short_zones(self, snap: TechnicalSnapshot) -> list[tuple[float, float]]:
        zones = []
        if snap.resistance_levels and snap.trend_direction == "down":
            r = snap.resistance_levels[0]
            zones.append((round(r * 0.99, 2), round(r * 1.01, 2)))
        return zones

    def _compute_cover_zones(self, snap: TechnicalSnapshot) -> list[tuple[float, float]]:
        zones = []
        if snap.support_levels:
            s = snap.support_levels[0]
            zones.append((round(s * 0.99, 2), round(s * 1.01, 2)))
        return zones

    def _compute_score(self, snap: TechnicalSnapshot) -> float:
        """
        Technical Strength Score (0-100):
        - Trend alignment (SMA positioning): 25 pts
        - Momentum (RSI, MACD): 25 pts
        - Volatility regime: 15 pts
        - VWAP position: 15 pts
        - Support proximity: 10 pts
        - ADX trend strength: 10 pts
        """
        score = 50.0  # Neutral base

        # Trend alignment: +/- 12.5
        above_count = sum(1 for p in [20, 50, 200] if p in snap.sma and snap.price > snap.sma[p])
        below_count = sum(1 for p in [20, 50, 200] if p in snap.sma and snap.price < snap.sma[p])
        score += (above_count - below_count) * 4.17

        # RSI: +/- 12.5
        if snap.rsi is not None:
            if snap.rsi > 70:
                score += 8  # Overbought but bullish momentum
            elif snap.rsi > 55:
                score += 5
            elif snap.rsi < 30:
                score -= 8
            elif snap.rsi < 45:
                score -= 5

        # MACD: +/- 12.5
        if snap.macd_histogram is not None:
            if snap.macd_histogram > 0:
                score += min(12.5, snap.macd_histogram * 100)
            else:
                score += max(-12.5, snap.macd_histogram * 100)

        # VWAP: +/- 7.5
        if snap.vwap_deviation is not None:
            if snap.vwap_deviation > 0:
                score += min(7.5, snap.vwap_deviation * 2)
            else:
                score += max(-7.5, snap.vwap_deviation * 2)

        # ADX
        if snap.adx is not None and snap.adx > 25:
            if snap.trend_direction == "up":
                score += 5
            elif snap.trend_direction == "down":
                score -= 5

        return round(max(0, min(100, score)), 2)
