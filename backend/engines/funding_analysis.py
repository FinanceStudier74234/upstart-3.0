"""
Funding Analysis Engine — Warehouse facility tracking, maturity analysis,
capacity monitoring, concentration risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields


@dataclass
class FundingFacility:
    name: str
    partner: str
    committed_amount: float  # $M
    drawn_amount: float
    maturity_date: str  # ISO date
    months_to_maturity: int
    renewal_probability: float  # 0-1
    status: str = "active"  # active | maturing | expired | at_risk
    has_covenant_issues: bool = False
    waiver_active: bool = False


@dataclass
class FundingSnapshot:
    """Complete funding profile."""
    facilities: list[FundingFacility] = field(default_factory=list)

    # Capacity
    total_committed: float = 0.0  # $B
    total_drawn: float = 0.0
    available_capacity: float = 0.0
    utilization_pct: float = 0.0

    # Coverage
    months_coverage: float = 0.0  # months of origination funded
    coverage_ratio: float = 0.0

    # Concentration
    partner_count: int = 0
    hhi_concentration: float = 0.0  # Herfindahl index 0-10000
    top_partner_pct: float = 0.0

    # Maturity
    avg_months_to_maturity: float = 0.0
    facilities_maturing_6mo: int = 0
    maturity_wall_risk: bool = False  # >30% maturing in 6 months

    # Quality
    avg_renewal_prob: float = 0.0
    has_covenant_issues: bool = False
    waivers_active: int = 0

    # Score
    funding_strength_score: float = 50.0


class FundingAnalysisEngine:
    """Analyzes UPST's warehouse funding facilities."""

    def analyze(self, funding_data: dict | None = None) -> FundingSnapshot:
        snap = FundingSnapshot()

        if not funding_data:
            funding_data = self._default_funding()

        facilities = []
        for f in funding_data.get("facilities", []):
            _valid = {fld.name for fld in fields(FundingFacility)}
            fac = FundingFacility(**{k: v for k, v in f.items() if k in _valid})
            facilities.append(fac)
        snap.facilities = facilities

        if not facilities:
            return snap

        # Capacity
        snap.total_committed = round(sum(f.committed_amount for f in facilities) / 1000, 2)  # $B
        snap.total_drawn = round(sum(f.drawn_amount for f in facilities) / 1000, 2)
        snap.available_capacity = round(snap.total_committed - snap.total_drawn, 2)
        snap.utilization_pct = round(snap.total_drawn / snap.total_committed * 100, 1) if snap.total_committed > 0 else 0

        # Coverage
        monthly_origination = funding_data.get("monthly_origination", 150)  # $M
        snap.months_coverage = round(snap.available_capacity * 1000 / monthly_origination, 1) if monthly_origination > 0 else 0
        snap.coverage_ratio = round(snap.total_committed * 1000 / (monthly_origination * 12), 2) if monthly_origination > 0 else 0

        # Concentration
        snap.partner_count = len(set(f.partner for f in facilities))
        amounts = [f.committed_amount for f in facilities]
        total_amt = sum(amounts)
        if total_amt > 0:
            shares = [a / total_amt for a in amounts]
            snap.hhi_concentration = round(sum(s ** 2 for s in shares) * 10000, 0)
            snap.top_partner_pct = round(max(shares) * 100, 1)

        # Maturity
        maturities = [f.months_to_maturity for f in facilities if f.months_to_maturity > 0]
        snap.avg_months_to_maturity = round(sum(maturities) / len(maturities), 1) if maturities else 0
        snap.facilities_maturing_6mo = sum(1 for f in facilities if f.months_to_maturity <= 6)
        snap.maturity_wall_risk = snap.facilities_maturing_6mo / len(facilities) > 0.3 if facilities else False

        # Quality
        probs = [f.renewal_probability for f in facilities]
        snap.avg_renewal_prob = round(sum(probs) / len(probs), 2) if probs else 0
        snap.has_covenant_issues = any(f.has_covenant_issues for f in facilities)
        snap.waivers_active = sum(1 for f in facilities if f.waiver_active)

        # Score
        snap.funding_strength_score = self._compute_score(snap)

        return snap

    def _compute_score(self, snap: FundingSnapshot) -> float:
        score = 50.0
        # Capacity bonus
        score += min(15, snap.total_committed * 5)
        # Coverage bonus
        score += min(10, snap.months_coverage * 0.8)
        # Diversification
        score += min(10, snap.partner_count * 2)
        # Maturity
        score += min(10, snap.avg_months_to_maturity * 0.4)
        # Renewal
        score += (snap.avg_renewal_prob - 0.5) * 20
        # Penalties
        if snap.has_covenant_issues:
            score -= 15
        if snap.maturity_wall_risk:
            score -= 10
        if snap.hhi_concentration > 3000:
            score -= 5
        return round(max(0, min(100, score)), 2)

    def _default_funding(self) -> dict:
        return {
            "monthly_origination": 150,
            "facilities": [
                {"name": "Warehouse A", "partner": "Goldman Sachs", "committed_amount": 500,
                 "drawn_amount": 300, "maturity_date": "2026-12-15", "months_to_maturity": 9,
                 "renewal_probability": 0.85, "status": "active"},
                {"name": "Warehouse B", "partner": "JP Morgan", "committed_amount": 400,
                 "drawn_amount": 250, "maturity_date": "2027-06-30", "months_to_maturity": 15,
                 "renewal_probability": 0.90, "status": "active"},
                {"name": "Warehouse C", "partner": "Citi", "committed_amount": 350,
                 "drawn_amount": 200, "maturity_date": "2026-09-30", "months_to_maturity": 6,
                 "renewal_probability": 0.75, "status": "active"},
                {"name": "Warehouse D", "partner": "Barclays", "committed_amount": 300,
                 "drawn_amount": 150, "maturity_date": "2027-03-31", "months_to_maturity": 12,
                 "renewal_probability": 0.80, "status": "active"},
                {"name": "ABS Shelf", "partner": "Multi-bank", "committed_amount": 600,
                 "drawn_amount": 400, "maturity_date": "2027-12-31", "months_to_maturity": 21,
                 "renewal_probability": 0.95, "status": "active"},
                {"name": "Forward Flow 1", "partner": "Castle Lake", "committed_amount": 200,
                 "drawn_amount": 180, "maturity_date": "2026-06-30", "months_to_maturity": 3,
                 "renewal_probability": 0.70, "status": "maturing"},
            ],
        }
