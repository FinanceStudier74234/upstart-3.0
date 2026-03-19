"""
Origination Momentum Engine — Loan origination volume, growth trends,
product mix, conversion rates, partner expansion.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OriginationSnapshot:
    """Complete origination profile."""
    # Volume
    quarterly_volume: float | None = None  # $M
    monthly_run_rate: float | None = None
    volume_index: float = 50.0  # 0-100 vs historical range

    # Growth
    qoq_growth: float | None = None
    yoy_growth: float | None = None
    accelerating: bool = False

    # Product mix
    personal_pct: float | None = None
    auto_pct: float | None = None
    heloc_pct: float | None = None
    small_biz_pct: float | None = None
    product_count: int = 1

    # Conversion
    conversion_rate: float | None = None  # % of inquiries converted
    approval_rate: float | None = None

    # Partners
    bank_partner_count: int = 0
    auto_dealer_count: int = 0
    new_partners_quarter: int = 0
    partner_growth_trend: str = "stable"  # growing | stable | declining

    # Quality
    avg_loan_size: float | None = None
    weighted_avg_coupon: float | None = None
    credit_quality_trend: str = "stable"  # improving | stable | deteriorating

    # Guidance
    beat_guidance: bool | None = None
    guidance_vs_actual_pct: float | None = None

    # Score
    origination_momentum_score: float = 50.0


class OriginationAnalysisEngine:
    """Analyzes UPST's origination trends and momentum."""

    def analyze(self, data: dict | None = None) -> OriginationSnapshot:
        snap = OriginationSnapshot()

        if not data:
            data = self._defaults()

        for k, v in data.items():
            if hasattr(snap, k):
                setattr(snap, k, v)

        # Derived
        if snap.qoq_growth is not None and snap.yoy_growth is not None:
            snap.accelerating = snap.qoq_growth > 0 and snap.qoq_growth > (snap.yoy_growth / 4)

        products = [snap.personal_pct, snap.auto_pct, snap.heloc_pct, snap.small_biz_pct]
        snap.product_count = sum(1 for p in products if p and p > 0)

        snap.origination_momentum_score = self._compute_score(snap)
        return snap

    def _compute_score(self, snap: OriginationSnapshot) -> float:
        score = 50.0
        if snap.qoq_growth is not None:
            score += min(15, max(-15, snap.qoq_growth * 50))
        if snap.yoy_growth is not None:
            score += min(10, max(-10, snap.yoy_growth * 20))
        if snap.accelerating:
            score += 5
        score += min(5, snap.product_count * 1.5)
        if snap.beat_guidance:
            score += 5
        if snap.new_partners_quarter > 0:
            score += min(5, snap.new_partners_quarter)
        if snap.conversion_rate and snap.conversion_rate > 0.15:
            score += 5
        return round(max(0, min(100, score)), 2)

    def _defaults(self) -> dict:
        return {
            "quarterly_volume": 1800,
            "monthly_run_rate": 600,
            "volume_index": 65,
            "qoq_growth": 0.15,
            "yoy_growth": 0.35,
            "personal_pct": 60,
            "auto_pct": 25,
            "heloc_pct": 10,
            "small_biz_pct": 5,
            "conversion_rate": 0.22,
            "approval_rate": 0.75,
            "bank_partner_count": 100,
            "auto_dealer_count": 800,
            "new_partners_quarter": 12,
            "partner_growth_trend": "growing",
            "avg_loan_size": 12500,
            "weighted_avg_coupon": 0.24,
            "credit_quality_trend": "stable",
            "beat_guidance": True,
            "guidance_vs_actual_pct": 5.0,
        }
