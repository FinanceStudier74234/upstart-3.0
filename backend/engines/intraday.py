"""
Intraday Analysis Engine — VWAP bands, opening range breakout, volume profile,
gap analysis, session segmentation, stop-run detection, intraday regime.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class IntradaySnapshot:
    """Complete intraday analysis output."""

    # VWAP
    vwap: float | None = None
    vwap_upper_1sd: float | None = None
    vwap_lower_1sd: float | None = None
    vwap_upper_2sd: float | None = None
    vwap_lower_2sd: float | None = None
    price_vs_vwap: str = "at"  # above | below | at

    # Opening Range Breakout
    orb_15m_high: float | None = None
    orb_15m_low: float | None = None
    orb_30m_high: float | None = None
    orb_30m_low: float | None = None
    orb_status: str = "inside"  # above | below | inside
    orb_breakout_probability: float | None = None

    # Intraday regime
    intraday_regime: str = "unknown"  # trend | range | chop
    regime_confidence: float = 0.0

    # Volume profile
    point_of_control: float | None = None  # price with highest volume
    value_area_high: float | None = None
    value_area_low: float | None = None
    high_volume_nodes: list[float] = field(default_factory=list)
    low_volume_gaps: list[tuple[float, float]] = field(default_factory=list)

    # Intraday momentum
    rsi_5m: float | None = None
    rsi_15m: float | None = None
    momentum_5m: float | None = None
    intraday_overbought: bool = False
    intraday_oversold: bool = False

    # Gap analysis
    gap_size_pct: float | None = None
    gap_direction: str = "none"  # up | down | none
    gap_filled: bool = False
    gap_fill_pct: float | None = None

    # Session analysis
    current_session: str = "unknown"
    session_volume_pct: dict[str, float] = field(default_factory=dict)
    best_edge_session: str = ""

    # Stop-run detection
    stop_run_detected: bool = False
    stop_run_direction: str = "none"  # up | down | none
    stop_run_level: float | None = None

    # Summary
    n_bars: int = 0
    bar_interval: str = ""  # 1m, 5m, etc.


class IntradayEngine:
    """Analyzes intraday minute-bar data for UPST."""

    # Session boundaries (ET)
    SESSIONS = {
        "pre_market": (4, 0, 9, 30),
        "open": (9, 30, 10, 0),
        "morning": (10, 0, 12, 0),
        "midday": (12, 0, 14, 0),
        "power_hour": (14, 0, 15, 0),
        "close": (15, 0, 16, 0),
        "after_hours": (16, 0, 20, 0),
    }

    def analyze(
        self,
        minute_bars: list[dict],
        daily_atr: float | None = None,
        prev_close: float | None = None,
    ) -> IntradaySnapshot:
        snap = IntradaySnapshot()

        if not minute_bars or len(minute_bars) < 5:
            return snap

        # Parse bars
        times = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        for bar in minute_bars:
            bt = bar.get("bar_time")
            if isinstance(bt, str):
                try:
                    bt = dt.datetime.fromisoformat(bt)
                except (ValueError, TypeError):
                    bt = None
            times.append(bt)
            opens.append(float(bar.get("open", 0)))
            highs.append(float(bar.get("high", 0)))
            lows.append(float(bar.get("low", 0)))
            closes.append(float(bar.get("close", 0)))
            volumes.append(float(bar.get("volume", 0)))

        c = np.array(closes)
        h = np.array(highs)
        lo = np.array(lows)
        o = np.array(opens)
        v = np.array(volumes)
        snap.n_bars = len(c)

        price = c[-1] if len(c) > 0 else 0.0

        # ── VWAP ──
        self._compute_vwap(snap, c, h, lo, v, price)

        # ── Opening Range Breakout ──
        self._compute_orb(snap, times, h, lo, c, daily_atr, price)

        # ── Intraday Regime ──
        self._compute_regime(snap, c)

        # ── Volume Profile ──
        self._compute_volume_profile(snap, c, v)

        # ── Intraday Momentum ──
        self._compute_momentum(snap, c)

        # ── Gap Analysis ──
        if prev_close and prev_close > 0 and o[0] > 0:
            self._compute_gap(snap, prev_close, o[0], lo, h, price)

        # ── Session Analysis ──
        self._compute_sessions(snap, times, v, c)

        # ── Stop-Run Detection ──
        self._detect_stop_run(snap, h, lo, c, v)

        return snap

    def _compute_vwap(self, snap, closes, highs, lows, volumes, price):
        """Compute VWAP and standard deviation bands."""
        typical = (highs + lows + closes) / 3.0
        cum_tpv = np.cumsum(typical * volumes)
        cum_vol = np.cumsum(volumes)

        mask = cum_vol > 0
        if not mask.any():
            return

        vwap_series = np.where(mask, cum_tpv / cum_vol, typical)
        snap.vwap = round(float(vwap_series[-1]), 4)

        # Deviation bands
        sq_diff = (typical - vwap_series) ** 2
        cum_sq_diff = np.cumsum(sq_diff * volumes)
        variance = np.where(mask, cum_sq_diff / cum_vol, 0)
        std = np.sqrt(variance)

        if std[-1] > 0:
            snap.vwap_upper_1sd = round(snap.vwap + float(std[-1]), 4)
            snap.vwap_lower_1sd = round(snap.vwap - float(std[-1]), 4)
            snap.vwap_upper_2sd = round(snap.vwap + 2 * float(std[-1]), 4)
            snap.vwap_lower_2sd = round(snap.vwap - 2 * float(std[-1]), 4)

        if price > snap.vwap * 1.001:
            snap.price_vs_vwap = "above"
        elif price < snap.vwap * 0.999:
            snap.price_vs_vwap = "below"
        else:
            snap.price_vs_vwap = "at"

    def _compute_orb(self, snap, times, highs, lows, closes, atr, price):
        """Opening range breakout detection."""
        # Find first 15 and 30 bars (assuming 1-min bars)
        n = len(highs)
        if n < 15:
            return

        snap.orb_15m_high = round(float(np.max(highs[:15])), 4)
        snap.orb_15m_low = round(float(np.min(lows[:15])), 4)

        if n >= 30:
            snap.orb_30m_high = round(float(np.max(highs[:30])), 4)
            snap.orb_30m_low = round(float(np.min(lows[:30])), 4)

        # Status
        if snap.orb_15m_high and snap.orb_15m_low:
            if price > snap.orb_15m_high:
                snap.orb_status = "above"
            elif price < snap.orb_15m_low:
                snap.orb_status = "below"
            else:
                snap.orb_status = "inside"

        # Breakout probability (range width vs ATR)
        if atr and atr > 0 and snap.orb_15m_high and snap.orb_15m_low:
            range_width = snap.orb_15m_high - snap.orb_15m_low
            ratio = range_width / atr
            # Narrow range (< 0.5 ATR) → high breakout prob
            # Wide range (> 1.5 ATR) → low breakout prob
            snap.orb_breakout_probability = round(
                max(0.1, min(0.9, 1.0 - ratio * 0.5)), 4
            )

    def _compute_regime(self, snap, closes):
        """Classify intraday regime: trend, range, or chop."""
        if len(closes) < 20:
            return

        # 5-bar rolling returns
        ret_5 = []
        for i in range(5, len(closes)):
            ret_5.append((closes[i] - closes[i - 5]) / closes[i - 5])
        ret_5 = np.array(ret_5)

        if len(ret_5) < 10:
            return

        # Autocorrelation of 5-bar returns
        if np.std(ret_5) > 0:
            ac1 = float(np.corrcoef(ret_5[:-1], ret_5[1:])[0, 1])
        else:
            ac1 = 0.0

        # Directional bias
        total_move = abs(closes[-1] - closes[0])
        total_path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))

        if total_path > 0:
            efficiency = total_move / total_path
        else:
            efficiency = 0.0

        # Classification
        if efficiency > 0.5 and ac1 > 0.1:
            snap.intraday_regime = "trend"
            snap.regime_confidence = round(min(1.0, efficiency + ac1 * 0.5), 4)
        elif ac1 < -0.15:
            snap.intraday_regime = "range"
            snap.regime_confidence = round(min(1.0, abs(ac1)), 4)
        else:
            snap.intraday_regime = "chop"
            snap.regime_confidence = round(max(0.1, 1.0 - efficiency), 4)

    def _compute_volume_profile(self, snap, closes, volumes):
        """Build volume profile: POC, value area, HVN/LVN."""
        if len(closes) < 10 or np.sum(volumes) == 0:
            return

        # Create price bins
        price_min = float(np.min(closes))
        price_max = float(np.max(closes))
        if price_max <= price_min:
            return

        n_bins = min(50, max(10, len(closes) // 5))
        bin_edges = np.linspace(price_min, price_max, n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        # Accumulate volume in each bin
        vol_profile = np.zeros(n_bins)
        for i in range(len(closes)):
            bin_idx = min(n_bins - 1, max(0, int((closes[i] - price_min) / (price_max - price_min) * n_bins)))
            vol_profile[bin_idx] += volumes[i]

        # Point of Control (highest volume price)
        poc_idx = int(np.argmax(vol_profile))
        snap.point_of_control = round(float(bin_centers[poc_idx]), 4)

        # Value Area (70% of volume)
        total_vol = np.sum(vol_profile)
        if total_vol > 0:
            sorted_idx = np.argsort(vol_profile)[::-1]
            cum_vol = 0.0
            va_bins = []
            for idx in sorted_idx:
                cum_vol += vol_profile[idx]
                va_bins.append(idx)
                if cum_vol >= total_vol * 0.70:
                    break
            if va_bins:
                va_bins.sort()
                snap.value_area_low = round(float(bin_edges[va_bins[0]]), 4)
                snap.value_area_high = round(float(bin_edges[va_bins[-1] + 1]), 4)

        # High volume nodes (top 3 bins)
        top_bins = np.argsort(vol_profile)[-3:]
        snap.high_volume_nodes = [round(float(bin_centers[i]), 4) for i in sorted(top_bins)]

        # Low volume gaps (bins with < 10% of POC volume)
        poc_vol = vol_profile[poc_idx]
        if poc_vol > 0:
            for i in range(n_bins):
                if vol_profile[i] < poc_vol * 0.1:
                    snap.low_volume_gaps.append((
                        round(float(bin_edges[i]), 4),
                        round(float(bin_edges[i + 1]), 4),
                    ))

    def _compute_momentum(self, snap, closes):
        """Intraday RSI and momentum."""
        if len(closes) < 15:
            return

        # 5-bar RSI
        snap.rsi_5m = self._rsi(closes, 5)

        # 14-bar RSI
        snap.rsi_15m = self._rsi(closes, 14)

        # 5-bar momentum
        if len(closes) > 5:
            snap.momentum_5m = round(
                (closes[-1] - closes[-6]) / closes[-6] * 100, 4
            )

        # Overbought/oversold
        if snap.rsi_5m is not None:
            snap.intraday_overbought = snap.rsi_5m > 80
            snap.intraday_oversold = snap.rsi_5m < 20

    def _rsi(self, closes, period):
        """Compute RSI over given period."""
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-period - 1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - 100 / (1 + rs), 2)

    def _compute_gap(self, snap, prev_close, today_open, lows, highs, price):
        """Analyze opening gap."""
        gap = (today_open - prev_close) / prev_close * 100
        snap.gap_size_pct = round(gap, 4)

        if gap > 0.2:
            snap.gap_direction = "up"
            # Gap fill = price dropped below prev_close
            low_of_day = float(np.min(lows))
            if low_of_day <= prev_close:
                snap.gap_filled = True
                snap.gap_fill_pct = 100.0
            else:
                filled_pct = max(0, (today_open - low_of_day) / (today_open - prev_close) * 100)
                snap.gap_fill_pct = round(min(100, filled_pct), 2)
        elif gap < -0.2:
            snap.gap_direction = "down"
            high_of_day = float(np.max(highs))
            if high_of_day >= prev_close:
                snap.gap_filled = True
                snap.gap_fill_pct = 100.0
            else:
                filled_pct = max(0, (high_of_day - today_open) / (prev_close - today_open) * 100)
                snap.gap_fill_pct = round(min(100, filled_pct), 2)

    def _compute_sessions(self, snap, times, volumes, closes):
        """Segment volume by trading session."""
        total_vol = float(np.sum(volumes))
        if total_vol == 0 or not any(times):
            return

        session_vols = {s: 0.0 for s in self.SESSIONS}
        session_returns = {s: [] for s in self.SESSIONS}

        for i, t in enumerate(times):
            if t is None:
                continue
            h, m = t.hour, t.minute
            mins = h * 60 + m
            for sname, (sh, sm, eh, em) in self.SESSIONS.items():
                start_mins = sh * 60 + sm
                end_mins = eh * 60 + em
                if start_mins <= mins < end_mins:
                    session_vols[sname] += volumes[i]
                    if i > 0:
                        session_returns[sname].append(
                            (closes[i] - closes[i - 1]) / closes[i - 1]
                        )
                    break

        # Volume percentages
        snap.session_volume_pct = {
            s: round(v / total_vol * 100, 2) if total_vol > 0 else 0
            for s, v in session_vols.items()
        }

        # Best edge session (highest avg absolute return)
        best = ""
        best_edge = 0
        for s, rets in session_returns.items():
            if rets:
                edge = abs(np.mean(rets))
                if edge > best_edge:
                    best_edge = edge
                    best = s
        snap.best_edge_session = best

        # Current session
        if times[-1]:
            h, m = times[-1].hour, times[-1].minute
            mins = h * 60 + m
            for sname, (sh, sm, eh, em) in self.SESSIONS.items():
                if sh * 60 + sm <= mins < eh * 60 + em:
                    snap.current_session = sname
                    break

    def _detect_stop_run(self, snap, highs, lows, closes, volumes):
        """Detect potential stop-hunting: spike beyond range then quick reversal."""
        if len(closes) < 10:
            return

        # Look at last 10 bars for stop-run pattern
        recent_h = highs[-10:]
        recent_l = lows[-10:]
        recent_c = closes[-10:]
        recent_v = volumes[-10:]

        avg_vol = float(np.mean(volumes))
        if avg_vol == 0:
            return

        for i in range(2, len(recent_c)):
            # Volume surge (> 2x average)
            if recent_v[i] < avg_vol * 2:
                continue

            # Upside stop-run: spike high then close below
            bar_range = recent_h[i] - recent_l[i]
            if bar_range > 0:
                upper_wick = recent_h[i] - max(recent_c[i], recent_c[i] if i == 0 else recent_c[i - 1])
                if upper_wick > bar_range * 0.6:
                    snap.stop_run_detected = True
                    snap.stop_run_direction = "up"
                    snap.stop_run_level = round(float(recent_h[i]), 4)
                    break

                lower_wick = min(recent_c[i], recent_c[i] if i == 0 else recent_c[i - 1]) - recent_l[i]
                if lower_wick > bar_range * 0.6:
                    snap.stop_run_detected = True
                    snap.stop_run_direction = "down"
                    snap.stop_run_level = round(float(recent_l[i]), 4)
                    break
