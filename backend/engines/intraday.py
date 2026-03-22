"""
Intraday Analysis Engine — VWAP bands, ORB, regime classification,
volume profile, intraday momentum, gap analysis, session segmentation,
stop-run detection, auction theory signals.

All computations use numpy only (no pandas/scipy dependencies).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Session time boundaries (US Eastern)
# ---------------------------------------------------------------------------
_SESSION_BOUNDS: list[tuple[str, dt.time, dt.time]] = [
    ("pre_market", dt.time(4, 0), dt.time(9, 30)),
    ("open", dt.time(9, 30), dt.time(10, 0)),
    ("morning", dt.time(10, 0), dt.time(12, 0)),
    ("midday", dt.time(12, 0), dt.time(14, 0)),
    ("power_hour", dt.time(14, 0), dt.time(15, 0)),
    ("close", dt.time(15, 0), dt.time(16, 0)),
    ("after_hours", dt.time(16, 0), dt.time(20, 0)),
]


# ---------------------------------------------------------------------------
# Dataclass — every field produced by the engine
# ---------------------------------------------------------------------------
@dataclass
class IntradaySnapshot:
    """Complete intraday analysis at a point in time."""

    # --- VWAP ---
    vwap: float | None = None
    vwap_upper_1: float | None = None  # +1 sigma
    vwap_lower_1: float | None = None  # -1 sigma
    vwap_upper_2: float | None = None  # +2 sigma
    vwap_lower_2: float | None = None  # -2 sigma
    price_vs_vwap: str = "unknown"  # above | below | at_vwap
    vwap_cross_detected: bool = False
    vwap_cross_direction: str | None = None  # bullish | bearish

    # --- Opening Range Breakout ---
    orb_15_high: float | None = None
    orb_15_low: float | None = None
    orb_30_high: float | None = None
    orb_30_low: float | None = None
    orb_15_status: str = "unknown"  # above | below | inside | not_formed
    orb_30_status: str = "unknown"  # above | below | inside | not_formed
    orb_15_breakout_probability: float | None = None
    orb_30_breakout_probability: float | None = None

    # --- Intraday regime ---
    intraday_regime: str = "unknown"  # trend | range | chop
    regime_confidence: float | None = None
    rolling_autocorrelation: float | None = None

    # --- Volume profile ---
    point_of_control: float | None = None  # price with highest volume
    value_area_high: float | None = None
    value_area_low: float | None = None
    high_volume_nodes: list[float] = field(default_factory=list)
    low_volume_gaps: list[tuple[float, float]] = field(default_factory=list)

    # --- Intraday momentum ---
    rsi_5min: float | None = None
    rsi_15min: float | None = None
    momentum_oscillator_5min: float | None = None
    momentum_oscillator_15min: float | None = None
    intraday_ob_os: str = "neutral"  # overbought | oversold | neutral

    # --- Gap analysis ---
    gap_size_pct: float | None = None
    gap_direction: str | None = None  # up | down | none
    gap_fill_probability: float | None = None
    gap_fill_pct: float | None = None  # how much of the gap has been filled (0-100)
    gap_filled: bool = False

    # --- Session segmentation ---
    current_session: str = "unknown"
    session_volume: dict[str, float] = field(default_factory=dict)
    session_range_pct: dict[str, float] = field(default_factory=dict)
    highest_edge_session: str | None = None

    # --- Stop-run detection ---
    stop_run_detected: bool = False
    stop_run_direction: str | None = None  # long_squeeze | short_squeeze
    stop_run_price: float | None = None
    stop_run_reversal_magnitude: float | None = None

    # --- Auction theory ---
    single_prints: list[float] = field(default_factory=list)
    poor_high: bool = False
    poor_low: bool = False
    excess_high: bool = False
    excess_low: bool = False

    # --- Meta ---
    n_bars: int = 0
    last_bar_time: dt.datetime | None = None
    last_price: float | None = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class IntradayEngine:
    """Intraday analysis from minute-bar data."""

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------
    def analyze(
        self,
        minute_bars: list[dict],
        daily_atr: float | None = None,
        prev_close: float | None = None,
    ) -> IntradaySnapshot:
        snap = IntradaySnapshot()

        if minute_bars is None or len(minute_bars) < 2:
            return snap

        # -- extract arrays ------------------------------------------------
        times: list[dt.datetime] = [b["bar_time"] for b in minute_bars]
        opens = np.array([b["open"] for b in minute_bars], dtype=np.float64)
        highs = np.array([b["high"] for b in minute_bars], dtype=np.float64)
        lows = np.array([b["low"] for b in minute_bars], dtype=np.float64)
        closes = np.array([b["close"] for b in minute_bars], dtype=np.float64)
        volumes = np.array([b["volume"] for b in minute_bars], dtype=np.float64)

        snap.n_bars = len(closes)
        snap.last_bar_time = times[-1]
        snap.last_price = float(closes[-1])

        # -- run all sub-analyses ------------------------------------------
        self._vwap(snap, highs, lows, closes, volumes)
        self._opening_range(snap, times, highs, lows, closes, daily_atr)
        self._regime(snap, closes)
        self._volume_profile(snap, highs, lows, closes, volumes)
        self._momentum(snap, closes)
        self._gap(snap, opens, highs, lows, closes, times)
        self._sessions(snap, times, highs, lows, closes, volumes)
        self._stop_run(snap, opens, highs, lows, closes, volumes)
        self._auction(snap, highs, lows, closes, volumes)

        return snap

    # -----------------------------------------------------------------------
    # 1. VWAP with standard-deviation bands
    # -----------------------------------------------------------------------
    def _vwap(
        self,
        snap: IntradaySnapshot,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
    ) -> None:
        typical = (highs + lows + closes) / 3.0
        cum_vol = np.cumsum(volumes)
        cum_tp_vol = np.cumsum(typical * volumes)

        if cum_vol[-1] == 0:
            return

        safe_cum_vol = np.where(cum_vol == 0, 1.0, cum_vol)
        vwap_arr = cum_tp_vol / safe_cum_vol
        snap.vwap = float(vwap_arr[-1])

        # Volume-weighted variance of typical price around VWAP
        cum_tp2_vol = np.cumsum((typical ** 2) * volumes)
        variance = cum_tp2_vol / safe_cum_vol - vwap_arr ** 2
        variance = np.maximum(variance, 0.0)
        std = float(np.sqrt(variance[-1]))

        snap.vwap_upper_1 = snap.vwap + std
        snap.vwap_lower_1 = snap.vwap - std
        snap.vwap_upper_2 = snap.vwap + 2.0 * std
        snap.vwap_lower_2 = snap.vwap - 2.0 * std

        price = float(closes[-1])
        eps = abs(snap.vwap) * 1e-6
        if price > snap.vwap + eps:
            snap.price_vs_vwap = "above"
        elif price < snap.vwap - eps:
            snap.price_vs_vwap = "below"
        else:
            snap.price_vs_vwap = "at_vwap"

        # Cross detection on last two bars
        if len(closes) >= 2 and len(vwap_arr) >= 2:
            prev_diff = closes[-2] - vwap_arr[-2]
            curr_diff = closes[-1] - vwap_arr[-1]
            if prev_diff <= 0 < curr_diff:
                snap.vwap_cross_detected = True
                snap.vwap_cross_direction = "bullish"
            elif prev_diff >= 0 > curr_diff:
                snap.vwap_cross_detected = True
                snap.vwap_cross_direction = "bearish"

    # -----------------------------------------------------------------------
    # 2. Opening Range Breakout
    # -----------------------------------------------------------------------
    def _opening_range(
        self,
        snap: IntradaySnapshot,
        times: list[dt.datetime],
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        daily_atr: float | None,
    ) -> None:
        # Find the first regular-session bar (>= 9:30)
        open_idx: int | None = None
        for i, t in enumerate(times):
            bar_time = t.time() if hasattr(t, "time") else t
            if bar_time >= dt.time(9, 30):
                open_idx = i
                break

        if open_idx is None:
            snap.orb_15_status = "not_formed"
            snap.orb_30_status = "not_formed"
            return

        open_time = times[open_idx]

        # Collect bar indices for 15-min and 30-min windows
        idx_15: list[int] = []
        idx_30: list[int] = []
        for i in range(open_idx, len(times)):
            delta_sec = (times[i] - open_time).total_seconds()
            if delta_sec < 15 * 60:
                idx_15.append(i)
            if delta_sec < 30 * 60:
                idx_30.append(i)

        price = float(closes[-1])

        # 15-min ORB
        if idx_15:
            snap.orb_15_high = float(np.max(highs[idx_15]))
            snap.orb_15_low = float(np.min(lows[idx_15]))
            if price > snap.orb_15_high:
                snap.orb_15_status = "above"
            elif price < snap.orb_15_low:
                snap.orb_15_status = "below"
            else:
                snap.orb_15_status = "inside"
            if daily_atr and daily_atr > 0:
                ratio = (snap.orb_15_high - snap.orb_15_low) / daily_atr
                snap.orb_15_breakout_probability = float(
                    np.clip(1.0 - ratio, 0.15, 0.90)
                )
        else:
            snap.orb_15_status = "not_formed"

        # 30-min ORB
        if idx_30:
            snap.orb_30_high = float(np.max(highs[idx_30]))
            snap.orb_30_low = float(np.min(lows[idx_30]))
            if price > snap.orb_30_high:
                snap.orb_30_status = "above"
            elif price < snap.orb_30_low:
                snap.orb_30_status = "below"
            else:
                snap.orb_30_status = "inside"
            if daily_atr and daily_atr > 0:
                ratio = (snap.orb_30_high - snap.orb_30_low) / daily_atr
                snap.orb_30_breakout_probability = float(
                    np.clip(1.0 - ratio, 0.10, 0.85)
                )
        else:
            snap.orb_30_status = "not_formed"

    # -----------------------------------------------------------------------
    # 3. Intraday regime classification
    # -----------------------------------------------------------------------
    def _regime(
        self,
        snap: IntradaySnapshot,
        closes: np.ndarray,
    ) -> None:
        step = 5  # 5-minute rolling returns
        if len(closes) < step + 20:
            snap.intraday_regime = "unknown"
            return

        # 5-bar log returns
        with np.errstate(divide="ignore", invalid="ignore"):
            rets = np.log(closes[step:] / closes[:-step])
        rets = rets[np.isfinite(rets)]
        if len(rets) < 10:
            snap.intraday_regime = "unknown"
            return

        # Lag-1 autocorrelation
        mean_r = np.mean(rets)
        centered = rets - mean_r
        var = float(np.dot(centered, centered))
        if var == 0:
            autocorr = 0.0
        else:
            autocorr = float(np.dot(centered[:-1], centered[1:]) / var)
        snap.rolling_autocorrelation = autocorr

        # Directional consistency: fraction of returns with same sign as net move
        net = float(np.sum(rets))
        if net > 0:
            consistency = float(np.mean(rets > 0))
        elif net < 0:
            consistency = float(np.mean(rets < 0))
        else:
            consistency = 0.5

        abs_ac = abs(autocorr)
        if autocorr > 0.15 and consistency > 0.55:
            snap.intraday_regime = "trend"
            snap.regime_confidence = float(np.clip(autocorr * 2 + consistency * 0.5, 0, 1))
        elif autocorr < -0.15:
            snap.intraday_regime = "range"
            snap.regime_confidence = float(np.clip(abs_ac * 2, 0, 1))
        else:
            snap.intraday_regime = "chop"
            snap.regime_confidence = float(
                np.clip(1.0 - abs_ac * 3 - abs(consistency - 0.5), 0, 1)
            )

    # -----------------------------------------------------------------------
    # 4. Volume profile
    # -----------------------------------------------------------------------
    def _volume_profile(
        self,
        snap: IntradaySnapshot,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
    ) -> None:
        total_vol = float(np.sum(volumes))
        if total_vol == 0 or len(closes) < 5:
            return

        price_low = float(np.min(lows))
        price_high = float(np.max(highs))
        if price_high <= price_low:
            return

        n_bins = max(30, min(100, len(closes) // 2))
        bin_edges = np.linspace(price_low, price_high, n_bins + 1)
        bin_width = float(bin_edges[1] - bin_edges[0])
        bin_vol = np.zeros(n_bins, dtype=np.float64)

        # Distribute each bar's volume across the price bins it spans
        for i in range(len(closes)):
            bar_lo = float(lows[i])
            bar_hi = float(highs[i])
            bar_v = float(volumes[i])
            if bar_v <= 0:
                continue
            if bar_hi <= bar_lo:
                # Single-tick bar: place all volume in the close's bin
                idx = int((float(closes[i]) - price_low) / bin_width)
                idx = max(0, min(idx, n_bins - 1))
                bin_vol[idx] += bar_v
                continue
            lo_idx = int((bar_lo - price_low) / bin_width)
            hi_idx = int((bar_hi - price_low) / bin_width)
            lo_idx = max(0, min(lo_idx, n_bins - 1))
            hi_idx = max(0, min(hi_idx, n_bins - 1))
            span = hi_idx - lo_idx + 1
            per_bin = bar_v / span
            bin_vol[lo_idx: hi_idx + 1] += per_bin

        bin_mids = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        # Point of control
        poc_idx = int(np.argmax(bin_vol))
        snap.point_of_control = float(bin_mids[poc_idx])

        # Value area: 70% of total volume centred around POC
        target_vol = total_vol * 0.70
        va_lo = poc_idx
        va_hi = poc_idx
        accumulated = float(bin_vol[poc_idx])
        while accumulated < target_vol and (va_lo > 0 or va_hi < n_bins - 1):
            expand_lo = float(bin_vol[va_lo - 1]) if va_lo > 0 else -1.0
            expand_hi = float(bin_vol[va_hi + 1]) if va_hi < n_bins - 1 else -1.0
            if expand_lo >= expand_hi and va_lo > 0:
                va_lo -= 1
                accumulated += float(bin_vol[va_lo])
            elif va_hi < n_bins - 1:
                va_hi += 1
                accumulated += float(bin_vol[va_hi])
            else:
                break
        snap.value_area_high = float(bin_edges[va_hi + 1])
        snap.value_area_low = float(bin_edges[va_lo])

        # High-volume nodes: bins with volume > 1.5x mean
        mean_vol = float(np.mean(bin_vol))
        if mean_vol > 0:
            hvn_mask = bin_vol > 1.5 * mean_vol
            snap.high_volume_nodes = [float(m) for m in bin_mids[hvn_mask]]

            # Low-volume gaps: consecutive bins with volume < 0.3x mean
            lvn_mask = bin_vol < 0.3 * mean_vol
            gap_start: int | None = None
            for j in range(n_bins):
                if lvn_mask[j]:
                    if gap_start is None:
                        gap_start = j
                else:
                    if gap_start is not None:
                        snap.low_volume_gaps.append(
                            (float(bin_edges[gap_start]), float(bin_edges[j]))
                        )
                        gap_start = None
            if gap_start is not None:
                snap.low_volume_gaps.append(
                    (float(bin_edges[gap_start]), float(bin_edges[n_bins]))
                )

    # -----------------------------------------------------------------------
    # 5. Intraday momentum (RSI + momentum oscillator)
    # -----------------------------------------------------------------------
    def _momentum(
        self,
        snap: IntradaySnapshot,
        closes: np.ndarray,
    ) -> None:
        snap.rsi_5min = self._rsi(closes, 5)
        snap.rsi_15min = self._rsi(closes, 15)
        snap.momentum_oscillator_5min = self._momentum_osc(closes, 5)
        snap.momentum_oscillator_15min = self._momentum_osc(closes, 15)

        # OB/OS classification using 5-min RSI as primary signal
        if snap.rsi_5min is not None:
            if snap.rsi_5min >= 80:
                snap.intraday_ob_os = "overbought"
            elif snap.rsi_5min <= 20:
                snap.intraday_ob_os = "oversold"
            else:
                snap.intraday_ob_os = "neutral"

    @staticmethod
    def _rsi(closes: np.ndarray, period: int) -> float | None:
        """Wilder-smoothed RSI."""
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + float(gains[i])) / period
            avg_loss = (avg_loss * (period - 1) + float(losses[i])) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - 100.0 / (1.0 + rs))

    @staticmethod
    def _momentum_osc(closes: np.ndarray, period: int) -> float | None:
        """Rate of change as percentage."""
        if len(closes) <= period:
            return None
        prev = float(closes[-period - 1])
        if prev == 0:
            return None
        return float((closes[-1] - prev) / prev * 100.0)

    # -----------------------------------------------------------------------
    # 6. Gap analysis
    # -----------------------------------------------------------------------
    def _gap(
        self,
        snap: IntradaySnapshot,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        times: list[dt.datetime],
    ) -> None:
        # Find the first regular-session bar (>= 9:30)
        rth_idx: int | None = None
        for i, t in enumerate(times):
            if hasattr(t, "time") and t.time() >= dt.time(9, 30):
                rth_idx = i
                break

        if rth_idx is None or rth_idx == 0:
            snap.gap_direction = "none"
            return

        # Previous close is the last bar before the RTH open
        prev_close = float(closes[rth_idx - 1])
        rth_open = float(opens[rth_idx])

        if prev_close == 0:
            snap.gap_direction = "none"
            return

        gap_pct = (rth_open - prev_close) / prev_close * 100.0
        snap.gap_size_pct = gap_pct

        if abs(gap_pct) < 0.05:
            snap.gap_direction = "none"
            return

        if gap_pct > 0:
            snap.gap_direction = "up"
            gap_total = rth_open - prev_close
            if gap_total > 0:
                rth_lows = lows[rth_idx:]
                lowest = float(np.min(rth_lows))
                filled_amount = rth_open - lowest
                snap.gap_fill_pct = float(np.clip(filled_amount / gap_total, 0, 1) * 100)
                snap.gap_filled = lowest <= prev_close
        else:
            snap.gap_direction = "down"
            gap_total = prev_close - rth_open
            if gap_total > 0:
                rth_highs = highs[rth_idx:]
                highest = float(np.max(rth_highs))
                filled_amount = highest - rth_open
                snap.gap_fill_pct = float(np.clip(filled_amount / gap_total, 0, 1) * 100)
                snap.gap_filled = highest >= prev_close

        # Empirical gap-fill probability estimate based on gap magnitude
        abs_gap = abs(gap_pct)
        if abs_gap < 0.5:
            snap.gap_fill_probability = 0.80
        elif abs_gap < 1.0:
            snap.gap_fill_probability = 0.65
        elif abs_gap < 2.0:
            snap.gap_fill_probability = 0.45
        elif abs_gap < 4.0:
            snap.gap_fill_probability = 0.30
        else:
            snap.gap_fill_probability = 0.15

    # -----------------------------------------------------------------------
    # 7. Session segmentation
    # -----------------------------------------------------------------------
    def _sessions(
        self,
        snap: IntradaySnapshot,
        times: list[dt.datetime],
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
    ) -> None:
        session_vols: dict[str, float] = {}
        session_highs: dict[str, float] = {}
        session_lows: dict[str, float] = {}

        for i, t in enumerate(times):
            bar_time = t.time() if hasattr(t, "time") else t
            name = self._classify_session(bar_time)

            session_vols[name] = session_vols.get(name, 0.0) + float(volumes[i])
            if name not in session_highs:
                session_highs[name] = float(highs[i])
                session_lows[name] = float(lows[i])
            else:
                session_highs[name] = max(session_highs[name], float(highs[i]))
                session_lows[name] = min(session_lows[name], float(lows[i]))

        snap.session_volume = session_vols

        # Range percentage per session
        for name in session_highs:
            lo = session_lows[name]
            if lo > 0:
                snap.session_range_pct[name] = (session_highs[name] - lo) / lo * 100.0
            else:
                snap.session_range_pct[name] = 0.0

        # Current session
        if times:
            last_time = times[-1].time() if hasattr(times[-1], "time") else times[-1]
            snap.current_session = self._classify_session(last_time)

        # Highest edge = session with the largest price range (most opportunity)
        if snap.session_range_pct:
            best_session: str | None = None
            best_score = -1.0
            for name, rng in snap.session_range_pct.items():
                if rng > best_score:
                    best_score = rng
                    best_session = name
            snap.highest_edge_session = best_session

    @staticmethod
    def _classify_session(bar_time: dt.time) -> str:
        for name, start, end in _SESSION_BOUNDS:
            if start <= bar_time < end:
                return name
        return "after_hours"

    # -----------------------------------------------------------------------
    # 8. Stop-run detection
    # -----------------------------------------------------------------------
    def _stop_run(
        self,
        snap: IntradaySnapshot,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
    ) -> None:
        n = len(closes)
        if n < 20:
            return

        window = 20
        avg_vol = float(np.mean(volumes[-window:]))
        if avg_vol <= 0:
            return

        # Compute rolling high/low *excluding* the bars being tested so a bar
        # does not trivially match its own extreme.
        boundary = max(0, n - window - 3)
        lookback_highs = highs[boundary: max(boundary, n - 3)]
        lookback_lows = lows[boundary: max(boundary, n - 3)]
        if len(lookback_highs) == 0:
            return
        recent_high = float(np.max(lookback_highs))
        recent_low = float(np.min(lookback_lows))

        # Scan the last 3 bars for a stop-run pattern:
        # spike beyond S/R on volume surge, then close reversing > 50% of bar range.
        for offset in range(min(3, n - 1)):
            idx = n - 1 - offset
            if idx < 1:
                break

            bar_vol = float(volumes[idx])
            vol_surge = bar_vol > 1.8 * avg_vol
            bar_range = float(highs[idx] - lows[idx])
            if bar_range <= 0 or not vol_surge:
                continue

            bar_close = float(closes[idx])
            bar_mid = (float(highs[idx]) + float(lows[idx])) / 2.0

            # Upside stop-run (short squeeze then fail): new high but close below midpoint
            if float(highs[idx]) >= recent_high and bar_close < bar_mid:
                reversal = float(highs[idx]) - bar_close
                if reversal / bar_range > 0.5:
                    snap.stop_run_detected = True
                    snap.stop_run_direction = "short_squeeze"
                    snap.stop_run_price = float(highs[idx])
                    snap.stop_run_reversal_magnitude = reversal
                    return

            # Downside stop-run (long squeeze then fail): new low but close above midpoint
            if float(lows[idx]) <= recent_low and bar_close > bar_mid:
                reversal = bar_close - float(lows[idx])
                if reversal / bar_range > 0.5:
                    snap.stop_run_detected = True
                    snap.stop_run_direction = "long_squeeze"
                    snap.stop_run_price = float(lows[idx])
                    snap.stop_run_reversal_magnitude = reversal
                    return

    # -----------------------------------------------------------------------
    # 9. Auction theory signals
    # -----------------------------------------------------------------------
    def _auction(
        self,
        snap: IntradaySnapshot,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
    ) -> None:
        n = len(closes)
        if n < 10:
            return

        price_low = float(np.min(lows))
        price_high = float(np.max(highs))
        if price_high <= price_low:
            return

        n_levels = 100
        tick_size = (price_high - price_low) / n_levels
        if tick_size <= 0:
            return

        level_prices = np.linspace(price_low, price_high, n_levels)
        tpo_count = np.zeros(n_levels, dtype=np.int32)

        for i in range(n):
            lo_idx = int((float(lows[i]) - price_low) / tick_size)
            hi_idx = int((float(highs[i]) - price_low) / tick_size)
            lo_idx = max(0, min(lo_idx, n_levels - 1))
            hi_idx = max(0, min(hi_idx, n_levels - 1))
            tpo_count[lo_idx: hi_idx + 1] += 1

        # Single prints: price levels visited exactly once (one-time framing)
        single_mask = tpo_count == 1
        if np.any(single_mask):
            snap.single_prints = [float(p) for p in level_prices[single_mask]]

        # Poor high / poor low: 1-2 TPOs at the extreme traded level
        nonzero = np.nonzero(tpo_count)[0]
        if len(nonzero) == 0:
            return

        top_level = int(nonzero[-1])
        bottom_level = int(nonzero[0])

        if tpo_count[top_level] <= 2:
            snap.poor_high = True
        if tpo_count[bottom_level] <= 2:
            snap.poor_low = True

        # Excess at edges: strong rejection (5+ TPOs concentrated in the top/bottom 3 levels)
        if top_level >= 2:
            edge_tpo = int(np.sum(tpo_count[top_level - 2: top_level + 1]))
            if edge_tpo >= 5:
                snap.excess_high = True
        if bottom_level + 2 < n_levels:
            edge_tpo = int(np.sum(tpo_count[bottom_level: bottom_level + 3]))
            if edge_tpo >= 5:
                snap.excess_low = True
