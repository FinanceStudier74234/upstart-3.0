"""
Execution / Microstructure / Liquidity Engine — Bid-ask spread analysis,
market depth, execution quality, slippage estimation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ExecutionSnapshot:
    """Market microstructure and execution quality."""
    # Spread
    bid_ask_spread: float | None = None  # $
    spread_pct: float | None = None
    spread_percentile: float | None = None  # vs 90-day history

    # Volume / Liquidity
    avg_daily_volume: float | None = None
    relative_volume: float | None = None  # today vs avg
    volume_profile_skew: str = "normal"  # front_loaded | back_loaded | normal
    dark_pool_pct: float | None = None

    # Market depth
    bid_depth_dollars: float | None = None
    ask_depth_dollars: float | None = None
    depth_imbalance: float | None = None  # positive = more bid support

    # Execution estimates
    est_slippage_100k: float | None = None  # $ for $100k order
    est_slippage_500k: float | None = None
    est_slippage_1m: float | None = None
    market_impact_model: str = "sqrt"  # linear | sqrt | almgren_chriss

    # Optimal execution
    optimal_algo: str = "TWAP"  # TWAP | VWAP | IS | MOC
    optimal_urgency: str = "medium"  # low | medium | high
    optimal_participation_rate: float = 0.05  # 5% of volume

    # Intraday patterns
    best_execution_window: str = "10:00-11:00"
    worst_execution_window: str = "15:30-16:00"

    # Gap analysis
    gap_fill_probability: float | None = None  # 0-1
    gap_direction: str | None = None  # "up" | "down" | None
    gap_size_pct: float | None = None

    # Chop vs trend
    chop_trend_regime: str = "unknown"  # chop | trend | transition
    chop_index: float | None = None  # 0-100, high = choppy

    # Stop-run / liquidity grab
    stop_run_risk: str = "low"  # low | medium | high
    stop_run_proximity_pct: float | None = None  # distance to likely stop cluster

    # Score
    liquidity_score: float = 50.0


class ExecutionEngine:
    """Analyzes execution quality and market microstructure."""

    def analyze(
        self,
        quote: dict | None = None,
        volume_data: dict | None = None,
        price: float = 0.0,
        bars: list[dict] | None = None,
    ) -> ExecutionSnapshot:
        snap = ExecutionSnapshot()

        if not quote:
            quote = self._default_quote(price)
        if not volume_data:
            volume_data = self._default_volume()

        bid = quote.get("bid", price * 0.999)
        ask = quote.get("ask", price * 1.001)
        snap.bid_ask_spread = round(ask - bid, 4)
        if price > 0:
            snap.spread_pct = round(snap.bid_ask_spread / price * 100, 4)

        snap.avg_daily_volume = volume_data.get("adv_30", 8_000_000)
        today_vol = volume_data.get("today_volume", 6_000_000)
        if snap.avg_daily_volume and snap.avg_daily_volume > 0:
            snap.relative_volume = round(today_vol / snap.avg_daily_volume, 2)

        snap.dark_pool_pct = volume_data.get("dark_pool_pct", 35)

        # Market depth
        snap.bid_depth_dollars = volume_data.get("bid_depth", 500_000)
        snap.ask_depth_dollars = volume_data.get("ask_depth", 450_000)
        if snap.bid_depth_dollars and snap.ask_depth_dollars:
            total = snap.bid_depth_dollars + snap.ask_depth_dollars
            snap.depth_imbalance = round((snap.bid_depth_dollars - snap.ask_depth_dollars) / total, 4) if total > 0 else 0

        # Slippage estimation (square-root model)
        adv_dollars = (snap.avg_daily_volume or 1) * price
        if adv_dollars > 0:
            snap.est_slippage_100k = round(self._sqrt_impact(100_000, adv_dollars, price), 4)
            snap.est_slippage_500k = round(self._sqrt_impact(500_000, adv_dollars, price), 4)
            snap.est_slippage_1m = round(self._sqrt_impact(1_000_000, adv_dollars, price), 4)

        # Spread percentile vs historical (simulate 90-day history)
        if snap.spread_pct is not None:
            # Estimate: UPST typical spread range 0.02% - 0.25%
            # Map current spread to a percentile within that range
            spread_min, spread_max = 0.02, 0.25
            if snap.spread_pct <= spread_min:
                snap.spread_percentile = 5.0
            elif snap.spread_pct >= spread_max:
                snap.spread_percentile = 95.0
            else:
                snap.spread_percentile = round(
                    (snap.spread_pct - spread_min) / (spread_max - spread_min) * 100, 1)

        # Volume profile skew detection
        if volume_data:
            morning_vol = volume_data.get("morning_volume", 0)
            afternoon_vol = volume_data.get("afternoon_volume", 0)
            if morning_vol and afternoon_vol:
                if morning_vol > afternoon_vol * 1.3:
                    snap.volume_profile_skew = "front_loaded"
                elif afternoon_vol > morning_vol * 1.3:
                    snap.volume_profile_skew = "back_loaded"
            elif today_vol and snap.avg_daily_volume:
                # Proxy: if current volume is high relative to expected pace, likely front-loaded
                if snap.relative_volume and snap.relative_volume > 1.3:
                    snap.volume_profile_skew = "front_loaded"
                elif snap.relative_volume and snap.relative_volume < 0.7:
                    snap.volume_profile_skew = "back_loaded"

        # Optimal execution
        if snap.avg_daily_volume and snap.avg_daily_volume > 5_000_000:
            snap.optimal_algo = "VWAP"
            snap.optimal_urgency = "low"
        else:
            snap.optimal_algo = "TWAP"
            snap.optimal_urgency = "medium"

        # Gap fill analysis
        self._analyze_gap(snap, bars, price)

        # Chop vs trend classification
        self._classify_chop_trend(snap, bars)

        # Stop-run / liquidity grab detection
        self._detect_stop_run(snap, bars, price)

        snap.liquidity_score = self._compute_score(snap)
        return snap

    def _sqrt_impact(self, order_dollars: float, adv_dollars: float, price: float) -> float:
        participation = order_dollars / adv_dollars
        impact_pct = 0.1 * np.sqrt(participation) * 100  # simplified Almgren model
        return impact_pct * price / 100

    def _compute_score(self, snap: ExecutionSnapshot) -> float:
        score = 50.0
        if snap.avg_daily_volume:
            if snap.avg_daily_volume > 10_000_000:
                score += 20
            elif snap.avg_daily_volume > 5_000_000:
                score += 10
            elif snap.avg_daily_volume < 1_000_000:
                score -= 15
        if snap.spread_pct is not None:
            if snap.spread_pct < 0.05:
                score += 10
            elif snap.spread_pct > 0.20:
                score -= 10
        if snap.depth_imbalance and snap.depth_imbalance > 0.1:
            score += 5
        return round(max(0, min(100, score)), 2)

    def _analyze_gap(self, snap: ExecutionSnapshot, bars: list[dict] | None, price: float):
        """Detect opening gaps and estimate fill probability."""
        if not bars or len(bars) < 2:
            return
        prev = bars[-2]
        curr = bars[-1]
        prev_close = prev.get("close", 0)
        curr_open = curr.get("open", 0)
        if prev_close <= 0 or curr_open <= 0:
            return
        gap_pct = (curr_open - prev_close) / prev_close * 100
        if abs(gap_pct) < 0.3:
            return  # no meaningful gap
        snap.gap_direction = "up" if gap_pct > 0 else "down"
        snap.gap_size_pct = round(abs(gap_pct), 2)
        # Gap fill probability: smaller gaps fill more often; UPST empirical ~65% fill
        base_fill = 0.70
        size_penalty = min(0.4, abs(gap_pct) * 0.04)  # larger gaps less likely to fill
        snap.gap_fill_probability = round(max(0.1, base_fill - size_penalty), 2)

    def _classify_chop_trend(self, snap: ExecutionSnapshot, bars: list[dict] | None):
        """Classify intraday/recent regime as chop or trend using a Choppiness Index proxy."""
        if not bars or len(bars) < 14:
            snap.chop_trend_regime = "unknown"
            return
        recent = bars[-14:]
        highs = [b.get("high", 0) for b in recent]
        lows = [b.get("low", 0) for b in recent]
        closes = [b.get("close", 0) for b in recent]
        if not all(highs) or not all(lows) or not all(closes):
            return
        # ATR sum
        atr_sum = sum(h - l for h, l in zip(highs, lows))
        # Range
        highest = max(highs)
        lowest = min(lows)
        total_range = highest - lowest
        if total_range <= 0 or atr_sum <= 0:
            return
        # Choppiness Index = 100 * LOG10(ATR_sum / range) / LOG10(14)
        import math
        ci = 100 * math.log10(atr_sum / total_range) / math.log10(14)
        snap.chop_index = round(max(0, min(100, ci)), 1)
        if ci > 61.8:
            snap.chop_trend_regime = "chop"
        elif ci < 38.2:
            snap.chop_trend_regime = "trend"
        else:
            snap.chop_trend_regime = "transition"

    def _detect_stop_run(self, snap: ExecutionSnapshot, bars: list[dict] | None, price: float):
        """Detect proximity to likely stop clusters (round numbers, recent lows/highs)."""
        if not bars or len(bars) < 5 or price <= 0:
            return
        recent_lows = sorted(b.get("low", 0) for b in bars[-20:] if b.get("low"))
        recent_highs = sorted((b.get("high", 0) for b in bars[-20:] if b.get("high")), reverse=True)
        # Round-number stop clusters
        round_below = int(price) if price % 1 > 0.5 else int(price) - 1
        round_above = int(price) + 1 if price % 1 < 0.5 else int(price) + 2
        # Closest stop cluster: recent swing low or round number below
        stop_levels = []
        if recent_lows:
            stop_levels.append(recent_lows[0])  # lowest recent low
        stop_levels.append(float(round_below))
        closest_stop = max(s for s in stop_levels if s < price) if any(s < price for s in stop_levels) else None
        if closest_stop and price > 0:
            dist_pct = (price - closest_stop) / price * 100
            snap.stop_run_proximity_pct = round(dist_pct, 2)
            if dist_pct < 1.0:
                snap.stop_run_risk = "high"
            elif dist_pct < 2.5:
                snap.stop_run_risk = "medium"
            else:
                snap.stop_run_risk = "low"

    def _default_quote(self, price: float) -> dict:
        return {"bid": price * 0.999, "ask": price * 1.001}

    def _default_volume(self) -> dict:
        return {
            "adv_30": 8_000_000,
            "today_volume": 6_500_000,
            "dark_pool_pct": 35,
            "bid_depth": 500_000,
            "ask_depth": 450_000,
        }
