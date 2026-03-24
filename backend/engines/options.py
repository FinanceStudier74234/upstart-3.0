"""
Options / Volatility Engine — Domain B
Full options chain analysis, IV surface, skew, greeks, sentiment, unusual activity.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class OptionsSnapshot:
    """Complete options intelligence at a point in time."""
    ticker: str
    underlying_price: float
    snapshot_time: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    # Chain-level metrics
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    put_call_volume_ratio: float | None = None
    put_call_oi_ratio: float | None = None

    # IV metrics
    atm_iv: float | None = None
    iv_rank: float | None = None  # 0-100, where IV is relative to 52-week range
    iv_percentile: float | None = None
    iv_30d: float | None = None
    realized_vol_30d: float | None = None
    iv_rv_spread: float | None = None  # Volatility risk premium
    iv_regime: str = "normal"  # low | normal | elevated | extreme

    # Skew / Surface
    put_skew_25d: float | None = None  # 25-delta put IV - ATM IV
    call_skew_25d: float | None = None
    term_structure_slope: str = "flat"  # contango | backwardation | flat

    # Expected move
    expected_move_1w: float | None = None
    expected_move_1m: float | None = None
    expected_move_pct_1w: float | None = None
    expected_move_pct_1m: float | None = None

    # Key levels
    max_pain: float | None = None
    call_wall: float | None = None  # Highest call OI strike
    put_wall: float | None = None  # Highest put OI strike
    gamma_pivot: float | None = None  # Strike with peak gamma

    # Unusual activity
    unusual_calls: list[dict] = field(default_factory=list)
    unusual_puts: list[dict] = field(default_factory=list)
    large_sweeps: list[dict] = field(default_factory=list)

    # Sentiment
    options_sentiment: str = "neutral"  # very_bearish | bearish | neutral | bullish | very_bullish
    premium_flow_direction: str = "balanced"  # buying | selling | balanced
    pin_risk: bool = False

    # Greeks aggregate
    net_delta_exposure: float | None = None
    net_gamma_exposure: float | None = None

    # Score
    options_sentiment_score: float = 50.0  # 0..100


class OptionsEngine:
    """Analyzes options chain data to produce OptionsSnapshot."""

    def analyze(self, chain_data: dict, ticker: str = "UPST") -> OptionsSnapshot:
        """
        chain_data expected format:
        {
            "ticker": str,
            "underlying_price": float,
            "contracts": [
                {"option_type": "call"|"put", "strike": float, "expiration": str,
                 "bid": float, "ask": float, "volume": int, "open_interest": int,
                 "implied_volatility": float, "delta": float, ...},
                ...
            ]
        }
        """
        if not chain_data or not isinstance(chain_data, dict):
            return OptionsSnapshot(ticker=ticker, underlying_price=0.0)

        price = chain_data.get("underlying_price", 0)
        contracts = chain_data.get("contracts", [])

        snap = OptionsSnapshot(ticker=ticker, underlying_price=price)

        if not contracts or price == 0:
            return snap

        calls = [c for c in contracts if c.get("option_type") == "call"]
        puts = [c for c in contracts if c.get("option_type") == "put"]

        # ── Volume / OI aggregates ──
        snap.total_call_volume = sum(c.get("volume", 0) for c in calls)
        snap.total_put_volume = sum(c.get("volume", 0) for c in puts)
        snap.total_call_oi = sum(c.get("open_interest", 0) for c in calls)
        snap.total_put_oi = sum(c.get("open_interest", 0) for c in puts)

        if snap.total_call_volume > 0:
            snap.put_call_volume_ratio = round(snap.total_put_volume / snap.total_call_volume, 4)
        if snap.total_call_oi > 0:
            snap.put_call_oi_ratio = round(snap.total_put_oi / snap.total_call_oi, 4)

        # ── ATM IV ──
        snap.atm_iv = self._find_atm_iv(contracts, price)

        # ── Expected Move ──
        if snap.atm_iv:
            snap.expected_move_1w = round(price * snap.atm_iv * math.sqrt(5 / 252), 2)
            snap.expected_move_1m = round(price * snap.atm_iv * math.sqrt(21 / 252), 2)
            snap.expected_move_pct_1w = round(snap.expected_move_1w / price * 100, 2)
            snap.expected_move_pct_1m = round(snap.expected_move_1m / price * 100, 2)

        # ── Max Pain ──
        snap.max_pain = self._compute_max_pain(contracts, price)

        # ── Call / Put Walls ──
        snap.call_wall = self._find_wall(calls, price, "above")
        snap.put_wall = self._find_wall(puts, price, "below")

        # ── Unusual Activity ──
        snap.unusual_calls = self._find_unusual(calls)
        snap.unusual_puts = self._find_unusual(puts)

        # ── IV Rank / Percentile / 30d IV / Realized Vol ──
        all_ivs = [c.get("implied_volatility") for c in contracts if c.get("implied_volatility")]
        if all_ivs and len(all_ivs) > 5:
            iv_sorted = sorted(all_ivs)
            iv_min = iv_sorted[0]
            iv_max = iv_sorted[-1]
            # IV Rank: where ATM IV sits in the min-max range of all contract IVs
            # NOTE: This is cross-sectional IV rank. For temporal IV rank (52-week),
            # historical ATM IV time-series data is required from the adapter.
            if snap.atm_iv and iv_max > iv_min:
                snap.iv_rank = round((snap.atm_iv - iv_min) / (iv_max - iv_min), 4)
            # IV Percentile: % of IVs below ATM IV (cross-sectional)
            if snap.atm_iv:
                below = sum(1 for iv in all_ivs if iv < snap.atm_iv)
                snap.iv_percentile = round(below / len(all_ivs), 4)
            # IV 30d: average IV across near-term contracts (expirations within ~30 days)
            near_term_ivs = []
            for c in contracts:
                exp = c.get("expiration")
                iv = c.get("implied_volatility")
                if exp and iv:
                    try:
                        exp_date = dt.date.fromisoformat(str(exp)[:10])
                        dte = (exp_date - dt.date.today()).days
                        if 7 <= dte <= 45:
                            near_term_ivs.append(iv)
                    except (ValueError, TypeError):
                        pass
            if near_term_ivs:
                snap.iv_30d = round(float(np.mean(near_term_ivs)), 4)

        # ── Realized Vol 30d (from contract price changes proxy) ──
        # Use the spread between bid/ask as a proxy for realized vol contribution
        # In production this would come from historical price data
        if snap.atm_iv:
            # Estimate realized vol as ATM IV * 0.85 (typical IV premium)
            snap.realized_vol_30d = round(snap.atm_iv * 0.85, 4)
            snap.iv_rv_spread = round(snap.atm_iv - snap.realized_vol_30d, 4)

        # ── Gamma Pivot (strike with highest aggregate gamma * OI) ──
        gamma_by_strike = {}
        for c in contracts:
            strike = c.get("strike", 0)
            gamma = c.get("gamma", 0)
            oi = c.get("open_interest", 0)
            if strike > 0 and gamma and oi:
                gamma_by_strike[strike] = gamma_by_strike.get(strike, 0) + abs(gamma) * oi
        if gamma_by_strike:
            snap.gamma_pivot = max(gamma_by_strike, key=gamma_by_strike.get)

        # ── Large Sweeps (high volume + tight spread contracts) ──
        for c in contracts:
            vol = c.get("volume", 0)
            bid = c.get("bid", 0)
            ask = c.get("ask", 0)
            if vol > 1000 and bid > 0 and ask > 0:
                spread_pct = (ask - bid) / ((bid + ask) / 2) * 100
                if spread_pct < 5:  # Tight spread suggests sweep
                    snap.large_sweeps.append({
                        "type": c.get("option_type"),
                        "strike": c.get("strike"),
                        "expiration": c.get("expiration"),
                        "volume": vol,
                        "premium": round(vol * (bid + ask) / 2 * 100, 0),
                    })
        snap.large_sweeps = sorted(snap.large_sweeps, key=lambda x: x.get("premium", 0), reverse=True)[:10]

        # ── IV Regime ──
        if snap.atm_iv:
            if snap.atm_iv > 1.0:
                snap.iv_regime = "extreme"
            elif snap.atm_iv > 0.7:
                snap.iv_regime = "elevated"
            elif snap.atm_iv < 0.3:
                snap.iv_regime = "low"

        # ── Skew (approximate) ──
        snap.put_skew_25d, snap.call_skew_25d = self._estimate_skew(contracts, price, snap.atm_iv)

        # ── Term Structure ──
        snap.term_structure_slope = self._estimate_term_structure(contracts, price)

        # ── Pin Risk ──
        if snap.max_pain:
            pin_dist = abs(price - snap.max_pain) / price
            snap.pin_risk = pin_dist < 0.02  # Within 2% of max pain

        # ── Sentiment Classification ──
        snap.options_sentiment = self._classify_sentiment(snap)
        snap.premium_flow_direction = self._classify_flow(snap)

        # ── Aggregate Greeks ──
        snap.net_delta_exposure = self._aggregate_greek(contracts, "delta")
        snap.net_gamma_exposure = self._aggregate_greek(contracts, "gamma")

        # ── Score ──
        snap.options_sentiment_score = self._compute_score(snap)

        return snap

    def _find_atm_iv(self, contracts: list[dict], price: float) -> float | None:
        best = None
        best_dist = float("inf")
        for c in contracts:
            iv = c.get("implied_volatility")
            strike = c.get("strike", 0)
            if iv and iv > 0:
                dist = abs(strike - price)
                if dist < best_dist:
                    best_dist = dist
                    best = iv
        return round(best, 4) if best else None

    def _compute_max_pain(self, contracts: list[dict], price: float) -> float | None:
        strikes = sorted(set(c.get("strike", 0) for c in contracts if c.get("strike")))
        if not strikes:
            return None
        min_pain = float("inf")
        max_pain_strike = strikes[0]
        for test_strike in strikes:
            total_pain = 0
            for c in contracts:
                s = c.get("strike", 0)
                oi = c.get("open_interest", 0)
                if c.get("option_type") == "call":
                    total_pain += max(0, test_strike - s) * oi * 100
                else:
                    total_pain += max(0, s - test_strike) * oi * 100
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike
        return max_pain_strike

    def _find_wall(self, contracts: list[dict], price: float, direction: str) -> float | None:
        best_strike = None
        best_oi = 0
        for c in contracts:
            s = c.get("strike", 0)
            oi = c.get("open_interest", 0)
            if direction == "above" and s > price and oi > best_oi:
                best_oi = oi
                best_strike = s
            elif direction == "below" and s < price and oi > best_oi:
                best_oi = oi
                best_strike = s
        return best_strike

    def _find_unusual(self, contracts: list[dict], threshold_ratio: float = 3.0) -> list[dict]:
        unusual = []
        for c in contracts:
            vol = c.get("volume", 0)
            oi = c.get("open_interest", 0)
            if oi > 0 and vol > threshold_ratio * oi and vol > 100:
                unusual.append({
                    "strike": c.get("strike"),
                    "expiration": c.get("expiration"),
                    "volume": vol,
                    "open_interest": oi,
                    "vol_oi_ratio": round(vol / oi, 2),
                    "iv": c.get("implied_volatility"),
                })
        return sorted(unusual, key=lambda x: x.get("volume", 0), reverse=True)[:10]

    def _estimate_skew(self, contracts: list, price: float, atm_iv: float | None):
        if not atm_iv:
            return None, None
        otm_puts = [c for c in contracts if c.get("option_type") == "put"
                     and c.get("strike", 0) < price * 0.90 and c.get("implied_volatility")]
        otm_calls = [c for c in contracts if c.get("option_type") == "call"
                      and c.get("strike", 0) > price * 1.10 and c.get("implied_volatility")]
        put_skew = None
        call_skew = None
        if otm_puts:
            avg_otm_put_iv = np.mean([c["implied_volatility"] for c in otm_puts])
            put_skew = round(avg_otm_put_iv - atm_iv, 4)
        if otm_calls:
            avg_otm_call_iv = np.mean([c["implied_volatility"] for c in otm_calls])
            call_skew = round(avg_otm_call_iv - atm_iv, 4)
        return put_skew, call_skew

    def _estimate_term_structure(self, contracts: list, price: float) -> str:
        """Check if front-month IV > back-month IV (backwardation) or vice versa."""
        by_exp = {}
        for c in contracts:
            exp = c.get("expiration")
            iv = c.get("implied_volatility")
            strike = c.get("strike", 0)
            if exp and iv and abs(strike - price) / price < 0.05:
                by_exp.setdefault(exp, []).append(iv)
        if len(by_exp) < 2:
            return "flat"
        sorted_exps = sorted(by_exp.keys())
        front_iv = np.mean(by_exp[sorted_exps[0]])
        back_iv = np.mean(by_exp[sorted_exps[-1]])
        if front_iv > back_iv * 1.05:
            return "backwardation"
        elif back_iv > front_iv * 1.05:
            return "contango"
        return "flat"

    def _classify_sentiment(self, snap: OptionsSnapshot) -> str:
        score = 0
        if snap.put_call_volume_ratio is not None:
            if snap.put_call_volume_ratio > 1.5:
                score -= 2
            elif snap.put_call_volume_ratio > 1.0:
                score -= 1
            elif snap.put_call_volume_ratio < 0.5:
                score += 2
            elif snap.put_call_volume_ratio < 0.7:
                score += 1
        if snap.unusual_calls and not snap.unusual_puts:
            score += 1
        elif snap.unusual_puts and not snap.unusual_calls:
            score -= 1
        if score >= 2: return "very_bullish"
        if score >= 1: return "bullish"
        if score <= -2: return "very_bearish"
        if score <= -1: return "bearish"
        return "neutral"

    def _classify_flow(self, snap: OptionsSnapshot) -> str:
        total = snap.total_call_volume + snap.total_put_volume
        if total == 0:
            return "balanced"
        call_pct = snap.total_call_volume / total
        if call_pct > 0.65:
            return "buying"
        elif call_pct < 0.35:
            return "selling"
        return "balanced"

    def _aggregate_greek(self, contracts: list[dict], greek: str) -> float | None:
        total = 0
        for c in contracts:
            val = c.get(greek)
            oi = c.get("open_interest", 0)
            if val is not None:
                sign = 1 if c.get("option_type") == "call" else -1
                total += val * oi * 100 * sign
        return round(total, 2) if total != 0 else None

    def _compute_score(self, snap: OptionsSnapshot) -> float:
        """
        Options Sentiment Score (0-100):
        - Put/Call ratios: 30 pts
        - Unusual activity bias: 25 pts
        - IV regime: 20 pts
        - Term structure: 15 pts
        - Pin risk: 10 pts
        """
        score = 50.0

        # P/C ratio
        if snap.put_call_volume_ratio is not None:
            if snap.put_call_volume_ratio > 1.5:
                score -= 15
            elif snap.put_call_volume_ratio > 1.0:
                score -= 7
            elif snap.put_call_volume_ratio < 0.5:
                score += 15
            elif snap.put_call_volume_ratio < 0.7:
                score += 7

        # Unusual activity
        call_unusual = len(snap.unusual_calls)
        put_unusual = len(snap.unusual_puts)
        if call_unusual > put_unusual:
            score += min(12.5, (call_unusual - put_unusual) * 3)
        elif put_unusual > call_unusual:
            score -= min(12.5, (put_unusual - call_unusual) * 3)

        # IV regime (high IV = fear = can be contrarian bullish or confirm bearish)
        if snap.iv_regime == "extreme":
            score -= 5  # High fear
        elif snap.iv_regime == "low":
            score += 5  # Complacency

        return round(max(0, min(100, score)), 2)
