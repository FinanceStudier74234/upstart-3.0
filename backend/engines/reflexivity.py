"""
Reflexivity / Nonlinearity / Feedback Loop Engine — Detects self-reinforcing
dynamics, reflexive spirals, and nonlinear regime transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class FeedbackLoop:
    name: str
    type: str  # positive | negative
    trigger: str
    mechanism: str
    current_state: str  # dormant | activating | active | exhausting
    strength: float = 0.0  # 0-100


@dataclass
class ReflexivitySnapshot:
    """Reflexivity and nonlinearity analysis."""
    # Active feedback loops
    feedback_loops: list[FeedbackLoop] = field(default_factory=list)

    # Soros reflexivity indicators
    perception_reality_gap: float = 0.0  # how far narrative diverges from fundamentals
    reflexivity_score: float = 50.0  # 0-100, high = strong feedback effects

    # Nonlinearity detection
    return_autocorrelation: float | None = None
    volatility_clustering: float | None = None  # GARCH-like persistence
    jump_frequency: float | None = None  # large moves per month
    tail_thickness: float | None = None  # kurtosis excess

    # Regime transition risk
    regime_transition_probability: float = 0.0
    nearest_tipping_point: str = ""
    distance_to_tipping: float | None = None

    # Spiral risk
    bullish_spiral_risk: float = 0.0
    bearish_spiral_risk: float = 0.0

    # Herding
    herding_score: float = 50.0  # correlation with crowd behavior


class ReflexivityEngine:
    """Detects reflexive dynamics and nonlinear regime risks."""

    def analyze(
        self,
        returns: np.ndarray | None = None,
        short_data: dict | None = None,
        options_data: dict | None = None,
        price: float = 0.0,
    ) -> ReflexivitySnapshot:
        snap = ReflexivitySnapshot()

        # Feedback loops for UPST
        snap.feedback_loops = self._identify_loops(short_data, options_data, price)

        if returns is not None and len(returns) > 30:
            # Autocorrelation
            snap.return_autocorrelation = round(float(np.corrcoef(returns[:-1], returns[1:])[0, 1]), 4)

            # Volatility clustering (simplified GARCH check)
            sq_ret = returns ** 2
            if len(sq_ret) > 1:
                snap.volatility_clustering = round(float(np.corrcoef(sq_ret[:-1], sq_ret[1:])[0, 1]), 4)

            # Jump frequency (moves > 3 sigma)
            std = np.std(returns)
            if std > 0:
                jumps = np.sum(np.abs(returns) > 3 * std)
                snap.jump_frequency = round(jumps / len(returns) * 21, 2)  # per month

            # Tail thickness
            from scipy import stats as sp_stats
            snap.tail_thickness = round(float(sp_stats.kurtosis(returns)), 2)

        # Reflexivity score
        snap.reflexivity_score = self._compute_reflexivity_score(snap)

        # Spiral risks
        snap.bullish_spiral_risk = self._bullish_spiral_risk(short_data, options_data)
        snap.bearish_spiral_risk = self._bearish_spiral_risk(short_data, options_data)

        # Regime transition
        snap.regime_transition_probability = self._regime_transition_prob(snap)
        snap.nearest_tipping_point = self._nearest_tipping(snap, price)

        # Herding
        snap.herding_score = self._herding_score(short_data, options_data)

        return snap

    def _identify_loops(self, short_data, options_data, price) -> list[FeedbackLoop]:
        loops = []

        # Short squeeze loop
        si = (short_data or {}).get("short_pct_float", 0)
        squeeze_state = "active" if si > 20 else ("activating" if si > 15 else "dormant")
        loops.append(FeedbackLoop(
            name="Short Squeeze Spiral",
            type="positive",
            trigger=f"SI at {si:.0f}% of float",
            mechanism="Price rise → margin calls → forced covering → more price rise",
            current_state=squeeze_state,
            strength=min(100, si * 4),
        ))

        # Funding confidence loop
        loops.append(FeedbackLoop(
            name="Funding Confidence Loop",
            type="positive",
            trigger="Stock price decline",
            mechanism="Price drop → partner concern → facility stress → origination drop → more price drop",
            current_state="dormant" if price > 50 else "activating",
            strength=max(0, min(100, (70 - price) * 2)) if price > 0 else 0,
        ))

        # AI narrative loop
        loops.append(FeedbackLoop(
            name="AI Narrative Momentum",
            type="positive",
            trigger="AI sector sentiment shift",
            mechanism="AI hype → multiple expansion → price rise → more AI coverage → more hype",
            current_state="active",
            strength=65,
        ))

        # Options gamma loop
        oi = (options_data or {}).get("total_oi", 0)
        loops.append(FeedbackLoop(
            name="Gamma Squeeze / Pin",
            type="positive",
            trigger="Concentrated options OI",
            mechanism="Price approaches strike → dealer hedging → amplified move",
            current_state="activating" if oi > 100000 else "dormant",
            strength=min(100, oi / 2000) if oi else 30,
        ))

        return loops

    def _compute_reflexivity_score(self, snap: ReflexivitySnapshot) -> float:
        score = 50.0
        active_loops = sum(1 for l in snap.feedback_loops if l.current_state in ("active", "activating"))
        score += active_loops * 8
        if snap.volatility_clustering and snap.volatility_clustering > 0.3:
            score += 10
        if snap.return_autocorrelation and abs(snap.return_autocorrelation) > 0.1:
            score += 5
        if snap.jump_frequency and snap.jump_frequency > 1:
            score += 10
        return round(max(0, min(100, score)), 2)

    def _bullish_spiral_risk(self, short_data, options_data) -> float:
        risk = 20.0
        si = (short_data or {}).get("short_pct_float", 0)
        risk += min(30, si * 1.5)
        ctb = (short_data or {}).get("cost_to_borrow", 0)
        risk += min(20, ctb * 0.5)
        pc_ratio = (options_data or {}).get("put_call_volume_ratio", 1.0)
        if pc_ratio and pc_ratio > 1.5:
            risk += 10
        return round(max(0, min(100, risk)), 2)

    def _bearish_spiral_risk(self, short_data, options_data) -> float:
        risk = 15.0
        iv = (options_data or {}).get("atm_iv", 0.5)
        if iv and iv > 0.8:
            risk += 15
        return round(max(0, min(100, risk)), 2)

    def _regime_transition_prob(self, snap: ReflexivitySnapshot) -> float:
        prob = 10.0
        active = sum(1 for l in snap.feedback_loops if l.current_state == "active")
        prob += active * 10
        if snap.volatility_clustering and snap.volatility_clustering > 0.4:
            prob += 10
        return round(max(0, min(100, prob)), 2)

    def _nearest_tipping(self, snap: ReflexivitySnapshot, price: float) -> str:
        for loop in snap.feedback_loops:
            if loop.current_state in ("active", "activating"):
                return loop.name
        return "None detected"

    def _herding_score(self, short_data, options_data) -> float:
        score = 40.0
        si = (short_data or {}).get("short_pct_float", 0)
        if si > 15:
            score += 15
        pc = (options_data or {}).get("put_call_volume_ratio", 1.0)
        if pc and (pc > 1.5 or pc < 0.5):
            score += 10
        return round(max(0, min(100, score)), 2)
