"""
Short-Selling / Squeeze Intelligence Engine — Domain C
Complete institutional-grade short analysis, squeeze risk, and short-decision system.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ShortSnapshot:
    """Complete short/squeeze intelligence at a point in time."""
    ticker: str
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    # Short interest data
    short_interest: int | None = None
    shares_float: int | None = None
    short_pct_float: float | None = None
    days_to_cover: float | None = None
    short_interest_trend: str = "stable"  # rising | stable | falling
    short_change_pct: float | None = None

    # Stock loan
    cost_to_borrow: float | None = None
    utilization: float | None = None
    shares_available: int | None = None
    lendable_shares: int | None = None
    borrow_fee_trend: str = "stable"  # rising | stable | falling
    borrow_tightening: bool = False

    # Crowding
    crowding_score: float | None = None  # 0-100
    crowding_change: str = "stable"  # increasing | stable | decreasing

    # Squeeze risk
    squeeze_risk_score: float = 50.0  # 0-100
    gamma_squeeze_risk: float | None = None
    forced_cover_probability: float | None = None
    do_not_short_flag: bool = False
    do_not_short_reasons: list[str] = field(default_factory=list)

    # Short structure analysis
    short_entry_zones: list[tuple[float, float]] = field(default_factory=list)
    short_add_zones: list[tuple[float, float]] = field(default_factory=list)
    cover_zones: list[tuple[float, float]] = field(default_factory=list)
    short_invalidation_level: float | None = None

    # Setup detection
    failed_rally_setup: bool = False
    breakdown_setup: bool = False
    lower_high_confirmed: bool = False
    momentum_breakdown: bool = False

    # Bearish structure comparison
    best_bearish_vehicle: str = "none"  # short_stock | puts | put_spread | bear_call_spread | none
    bearish_comparison: dict = field(default_factory=dict)

    # Short timeframe analysis
    timeframe_analysis: dict = field(default_factory=dict)

    # Scores
    short_opportunity_score: float = 50.0  # 0-100
    positioning_crowdedness_score: float = 50.0
    bearish_structure_score: float = 50.0
    direct_short_feasibility_score: float = 50.0

    # Short thesis factors
    thesis_factors: list[dict] = field(default_factory=list)

    # Decision
    short_decision: str = "no_action"
    # short_now | short_rally | short_breakdown | add_short | cover_short |
    # avoid_short | use_puts | use_spreads | no_bearish_trade | no_action
    short_decision_explanation: str = ""
    downside_targets: list[dict] = field(default_factory=list)


class ShortEngine:
    """Analyzes short interest, stock loan, squeeze risk, and short setups."""

    def analyze(
        self,
        short_data: dict | None,
        loan_data: dict | None,
        technical_snap: dict | None = None,
        options_snap: dict | None = None,
        price: float = 0.0,
    ) -> ShortSnapshot:
        snap = ShortSnapshot(ticker="UPST")

        # ── Populate short interest ──
        if short_data:
            snap.short_interest = short_data.get("short_interest")
            snap.shares_float = short_data.get("shares_float")
            snap.short_pct_float = short_data.get("short_pct_float")
            snap.days_to_cover = short_data.get("days_to_cover")
            # Short change % (from previous report if available)
            prev_si = short_data.get("previous_short_interest")
            if prev_si and snap.short_interest and prev_si > 0:
                snap.short_change_pct = round((snap.short_interest - prev_si) / prev_si * 100, 2)
            elif snap.short_pct_float is not None:
                # No previous SI available — default to zero change
                snap.short_change_pct = 0.0
            # Short interest trend
            if snap.short_change_pct is not None:
                if snap.short_change_pct > 5:
                    snap.short_interest_trend = "rising"
                elif snap.short_change_pct < -5:
                    snap.short_interest_trend = "falling"

        # ── Populate stock loan ──
        if loan_data:
            snap.cost_to_borrow = loan_data.get("cost_to_borrow")
            snap.utilization = loan_data.get("utilization")
            snap.shares_available = loan_data.get("shares_available")
            snap.lendable_shares = loan_data.get("lendable_shares")
            snap.borrow_fee_trend = loan_data.get("borrow_fee_trend", "stable")
            snap.borrow_tightening = snap.borrow_fee_trend == "rising"

        # ── Crowding Score ──
        snap.crowding_score = self._compute_crowding(snap)

        # ── Crowding Change ──
        if snap.short_change_pct is not None:
            if snap.short_change_pct > 3:
                snap.crowding_change = "increasing"
            elif snap.short_change_pct < -3:
                snap.crowding_change = "decreasing"
            else:
                snap.crowding_change = "stable"

        # ── Squeeze Risk Score ──
        snap.squeeze_risk_score = self._compute_squeeze_risk(snap, options_snap)

        # ── Gamma Squeeze Risk ──
        if options_snap:
            snap.gamma_squeeze_risk = self._estimate_gamma_squeeze(options_snap)

        # ── Forced Cover Probability ──
        snap.forced_cover_probability = self._estimate_forced_cover(snap)

        # ── Do-Not-Short Flag ──
        self._check_do_not_short(snap)

        # ── Short Opportunity Score ──
        snap.short_opportunity_score = self._compute_short_opportunity(snap, technical_snap)

        # ── Setup Detection (requires technical data) ──
        if technical_snap:
            self._detect_setups(snap, technical_snap, price)

        # ── Short Zones ──
        if price > 0:
            self._compute_zones(snap, technical_snap, price)

        # ── Bearish Vehicle Comparison ──
        snap.bearish_comparison = self._compare_bearish_vehicles(snap, options_snap, price)
        snap.best_bearish_vehicle = snap.bearish_comparison.get("best", "none")

        # ── Positioning Scores ──
        snap.positioning_crowdedness_score = snap.crowding_score or 50
        snap.direct_short_feasibility_score = self._compute_feasibility(snap)
        snap.bearish_structure_score = self._compute_bearish_structure_score(snap, technical_snap)

        # ── Short Thesis Factors ──
        snap.thesis_factors = self._build_thesis(snap, technical_snap, options_snap)

        # ── Decision ──
        snap.short_decision, snap.short_decision_explanation = self._decide(snap, technical_snap)

        # ── Downside Targets ──
        if price > 0:
            snap.downside_targets = self._compute_downside_targets(snap, technical_snap, price)

        # ── Timeframe Analysis ──
        snap.timeframe_analysis = self._timeframe_analysis(snap, technical_snap)

        return snap

    def _compute_crowding(self, snap: ShortSnapshot) -> float:
        """Crowdedness Score (0-100). High = very crowded short."""
        score = 50.0
        if snap.short_pct_float is not None:
            if snap.short_pct_float > 30: score += 25
            elif snap.short_pct_float > 20: score += 15
            elif snap.short_pct_float > 10: score += 5
            elif snap.short_pct_float < 5: score -= 15
        if snap.days_to_cover is not None:
            if snap.days_to_cover > 5: score += 15
            elif snap.days_to_cover > 3: score += 8
            elif snap.days_to_cover < 1.5: score -= 10
        if snap.utilization is not None:
            if snap.utilization > 90: score += 15
            elif snap.utilization > 70: score += 8
            elif snap.utilization < 30: score -= 10
        return round(max(0, min(100, score)), 2)

    def _compute_squeeze_risk(self, snap: ShortSnapshot, options_snap: dict | None) -> float:
        """
        Squeeze Risk Score (0-100):
        - Short crowding: 30%
        - Borrow conditions: 25%
        - Call flow / gamma: 25%
        - Days to cover: 20%
        """
        score = 0.0
        # Crowding component
        if snap.crowding_score:
            score += snap.crowding_score * 0.30
        # Borrow conditions
        borrow_score = 50.0
        if snap.cost_to_borrow is not None:
            if snap.cost_to_borrow > 10: borrow_score = 85
            elif snap.cost_to_borrow > 5: borrow_score = 70
            elif snap.cost_to_borrow < 1: borrow_score = 20
        if snap.borrow_tightening:
            borrow_score += 10
        score += borrow_score * 0.25
        # Call flow / gamma proxy
        call_score = 50.0
        if options_snap:
            pc_ratio = options_snap.get("put_call_volume_ratio")
            if pc_ratio is not None and pc_ratio < 0.5:
                call_score = 80  # Heavy call flow = squeeze fuel
            elif pc_ratio is not None and pc_ratio > 1.5:
                call_score = 20
        score += call_score * 0.25
        # Days to cover
        dtc_score = 50.0
        if snap.days_to_cover is not None:
            if snap.days_to_cover > 5: dtc_score = 85
            elif snap.days_to_cover > 3: dtc_score = 70
            elif snap.days_to_cover < 1: dtc_score = 15
        score += dtc_score * 0.20
        return round(max(0, min(100, score)), 2)

    def _estimate_gamma_squeeze(self, options_snap: dict | None) -> float:
        if not options_snap:
            return 0.0
        net_gamma = options_snap.get("net_gamma_exposure", 0)
        if net_gamma and net_gamma > 0:
            return min(100, abs(net_gamma) / 1_000_000 * 10)
        return 0.0

    def _estimate_forced_cover(self, snap: ShortSnapshot) -> float:
        prob = 0.1  # Base 10%
        if snap.squeeze_risk_score > 75:
            prob += 0.3
        elif snap.squeeze_risk_score > 50:
            prob += 0.1
        if snap.borrow_tightening:
            prob += 0.15
        if snap.utilization and snap.utilization > 90:
            prob += 0.1
        return round(min(1.0, prob), 4)

    def _check_do_not_short(self, snap: ShortSnapshot):
        reasons = []
        if snap.squeeze_risk_score > 75:
            reasons.append("Squeeze risk score > 75")
        if snap.utilization and snap.utilization > 95:
            reasons.append("Utilization > 95%")
        if snap.cost_to_borrow and snap.cost_to_borrow > 20:
            reasons.append("Cost to borrow > 20%")
        if snap.forced_cover_probability and snap.forced_cover_probability > 0.4:
            reasons.append("Forced-cover probability > 40%")
        if reasons:
            snap.do_not_short_flag = True
            snap.do_not_short_reasons = reasons

    def _compute_short_opportunity(self, snap: ShortSnapshot, tech: dict | None) -> float:
        """
        Short Opportunity Score (0-100):
        - Technical weakness: 30%
        - Crowding inverse: 20% (less crowded = better short opportunity)
        - Squeeze risk inverse: 25%
        - Borrow feasibility: 25%
        """
        score = 50.0
        # Technical weakness (higher = more bearish = better short)
        if tech:
            tech_score = tech.get("technical_strength_score", 50)
            score += (50 - tech_score) * 0.30 * 2  # Invert: weak tech = good short

        # Crowding inverse
        if snap.crowding_score:
            score -= (snap.crowding_score - 50) * 0.20 * 2  # Crowded = worse short

        # Squeeze risk inverse
        score -= (snap.squeeze_risk_score - 50) * 0.25 * 2

        # Borrow feasibility
        if snap.cost_to_borrow is not None:
            if snap.cost_to_borrow < 2:
                score += 10
            elif snap.cost_to_borrow > 10:
                score -= 10

        return round(max(0, min(100, score)), 2)

    def _detect_setups(self, snap: ShortSnapshot, tech: dict, price: float):
        trend = tech.get("trend_direction", "neutral")
        momentum = tech.get("momentum_regime", "neutral")
        rsi = tech.get("rsi")

        if trend == "down" and momentum in ("down", "strong_down"):
            snap.momentum_breakdown = True

        if trend == "down" and rsi and rsi < 45:
            snap.breakdown_setup = True

        # Failed rally: uptrend weakening, RSI diverging
        if trend == "neutral" and rsi and rsi < 50 and momentum == "down":
            snap.failed_rally_setup = True

        # Lower high confirmed: price below resistance and downtrend
        resistance = tech.get("resistance_levels", [])
        recent_high = resistance[0] if resistance else None
        if recent_high and price > 0 and price < recent_high * 0.95 and trend == "down":
            snap.lower_high_confirmed = True

    def _compute_zones(self, snap: ShortSnapshot, tech: dict | None, price: float):
        # Short entry near resistance
        if tech and tech.get("resistance_levels"):
            for r in tech["resistance_levels"][:2]:
                snap.short_entry_zones.append((round(r * 0.99, 2), round(r * 1.01, 2)))

        # Cover near support
        if tech and tech.get("support_levels"):
            for s in tech["support_levels"][:2]:
                snap.cover_zones.append((round(s * 0.99, 2), round(s * 1.01, 2)))

        # Short add zones: between entry zones and cover zones (mid-range)
        if snap.short_entry_zones and snap.cover_zones:
            entry_low = min(z[0] for z in snap.short_entry_zones)
            cover_high = max(z[1] for z in snap.cover_zones)
            mid = (entry_low + cover_high) / 2
            snap.short_add_zones.append((round(mid * 0.98, 2), round(mid * 1.02, 2)))
        elif price > 0:
            # Fallback: add zone near current price if trending down
            snap.short_add_zones.append((round(price * 0.95, 2), round(price * 1.00, 2)))

        # Invalidation = above highest resistance + ATR
        resistance = tech.get("resistance_levels", []) if tech else []
        atr = tech.get("atr") if tech else None
        if resistance and atr:
            snap.short_invalidation_level = round(
                resistance[-1] + atr * 1.5, 2,
            )

    def _compare_bearish_vehicles(self, snap: ShortSnapshot, options: dict | None, price: float) -> dict:
        """Compare direct short vs puts vs spreads."""
        comparison = {
            "short_stock": {
                "vehicle": "short_stock",
                "max_risk": "unlimited",
                "breakeven": price,
                "squeeze_exposure": "high",
                "cost_to_borrow_drag": snap.cost_to_borrow or 0,
                "feasibility": "high" if not snap.do_not_short_flag else "low",
            },
            "long_puts": {
                "vehicle": "long_puts",
                "max_risk": "premium_paid",
                "breakeven": "strike - premium",
                "squeeze_exposure": "none",
                "iv_sensitivity": "high — loses if IV drops",
                "feasibility": "high",
            },
            "put_debit_spread": {
                "vehicle": "put_debit_spread",
                "max_risk": "net_debit",
                "breakeven": "long_strike - net_debit",
                "squeeze_exposure": "none",
                "iv_sensitivity": "reduced",
                "feasibility": "high",
            },
            "bear_call_spread": {
                "vehicle": "bear_call_spread",
                "max_risk": "width - credit",
                "breakeven": "short_strike + credit",
                "squeeze_exposure": "capped",
                "iv_sensitivity": "benefits from IV drop",
                "feasibility": "high",
            },
        }

        # Determine best
        if snap.do_not_short_flag:
            if options and options.get("iv_regime") == "elevated":
                best = "bear_call_spread"  # Sell premium in high IV
            else:
                best = "put_debit_spread"
        elif snap.squeeze_risk_score > 60:
            best = "put_debit_spread"
        elif snap.cost_to_borrow and snap.cost_to_borrow > 5:
            best = "long_puts"
        else:
            best = "short_stock"

        comparison["best"] = best
        return comparison

    def _compute_feasibility(self, snap: ShortSnapshot) -> float:
        score = 80.0
        if snap.do_not_short_flag:
            score -= 40
        if snap.cost_to_borrow and snap.cost_to_borrow > 10:
            score -= 20
        if snap.shares_available and snap.shares_available < 100_000:
            score -= 20
        if snap.utilization and snap.utilization > 90:
            score -= 15
        return round(max(0, min(100, score)), 2)

    def _compute_bearish_structure_score(self, snap: ShortSnapshot, tech: dict | None) -> float:
        score = 50.0
        if snap.failed_rally_setup: score += 15
        if snap.breakdown_setup: score += 15
        if snap.momentum_breakdown: score += 10
        if tech and tech.get("trend_direction") == "down": score += 10
        if snap.short_pct_float and snap.short_pct_float > 15:
            score += 5  # Others agree on short
        return round(max(0, min(100, score)), 2)

    def _build_thesis(self, snap, tech, options) -> list[dict]:
        factors = []
        if tech and tech.get("trend_direction") == "down":
            factors.append({"factor": "technical_breakdown", "strength": 0.8, "direction": "bearish"})
        if snap.short_pct_float and snap.short_pct_float > 15:
            factors.append({"factor": "high_short_interest", "strength": 0.6, "direction": "bearish"})
        if options and options.get("put_call_volume_ratio", 0) > 1.2:
            factors.append({"factor": "bearish_options_flow", "strength": 0.7, "direction": "bearish"})
        if snap.squeeze_risk_score > 65:
            factors.append({"factor": "squeeze_risk", "strength": 0.9, "direction": "caution"})
        return factors

    def _decide(self, snap: ShortSnapshot, tech: dict | None) -> tuple[str, str]:
        if snap.do_not_short_flag:
            if snap.bearish_structure_score > 60:
                return "use_puts", "Bearish thesis intact but squeeze risk too high for direct short. Use puts/spreads."
            return "avoid_short", f"Do-not-short conditions met: {'; '.join(snap.do_not_short_reasons)}"

        if snap.short_opportunity_score > 70 and snap.squeeze_risk_score < 50:
            if snap.breakdown_setup:
                return "short_breakdown", "Strong breakdown setup with manageable squeeze risk."
            if snap.failed_rally_setup:
                return "short_rally", "Failed rally setup detected. Short the bounce."
            return "short_now", "High short opportunity with low squeeze risk."

        if snap.short_opportunity_score < 30:
            return "no_bearish_trade", "Short opportunity score too low."

        return "no_action", "No clear short signal. Monitoring."

    def _compute_downside_targets(self, snap, tech, price) -> list[dict]:
        targets = []
        if tech and tech.get("support_levels"):
            for i, s in enumerate(tech["support_levels"][:3]):
                targets.append({
                    "level": s,
                    "pct_move": round((s - price) / price * 100, 2),
                    "label": f"Support {i+1}",
                    "probability": round(0.6 - i * 0.15, 2),
                    "timeframe": "1-4 weeks",
                })
        return targets

    def _timeframe_analysis(self, snap, tech) -> dict:
        result = {}
        for tf in ["intraday", "daily", "weekly", "monthly"]:
            result[tf] = {
                "bearish": snap.short_opportunity_score > 55,
                "shortable": not snap.do_not_short_flag and snap.short_opportunity_score > 55,
                "squeeze_risk": snap.squeeze_risk_score,
            }
        return result
