"""
Balance Sheet / Liquidity Stress Lab — Stress testing funding,
liquidity, and solvency under adverse scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StressScenario:
    name: str
    description: str
    funding_impact_pct: float = 0.0
    origination_impact_pct: float = 0.0
    revenue_impact_pct: float = 0.0
    cash_burn_months: float | None = None
    survives: bool = True
    severity: str = "moderate"  # mild | moderate | severe | extreme


@dataclass
class StressSnapshot:
    """Balance sheet stress test results."""
    # Current balance sheet
    cash_and_equivalents: float = 0.0  # $M
    total_debt: float = 0.0
    net_cash: float = 0.0
    current_ratio: float = 0.0
    quick_ratio: float = 0.0

    # Liquidity
    monthly_cash_burn: float = 0.0
    runway_months: float = 0.0
    liquidity_score: float = 50.0

    # Scenarios
    scenarios: list[StressScenario] = field(default_factory=list)

    # Survival analysis
    min_survival_months: float = 0.0
    worst_case_scenario: str = ""
    probability_of_distress: float = 0.0

    # Score
    balance_sheet_health_score: float = 50.0


class StressEngine:
    """Runs balance sheet and liquidity stress tests."""

    def analyze(self, balance_sheet: dict | None = None) -> StressSnapshot:
        snap = StressSnapshot()

        if not balance_sheet:
            balance_sheet = self._defaults()

        snap.cash_and_equivalents = balance_sheet.get("cash", 800)
        snap.total_debt = balance_sheet.get("total_debt", 200)
        snap.net_cash = snap.cash_and_equivalents - snap.total_debt
        snap.current_ratio = balance_sheet.get("current_ratio", 1.8)
        snap.quick_ratio = balance_sheet.get("quick_ratio", 1.5)
        snap.monthly_cash_burn = balance_sheet.get("monthly_cash_burn", 15)

        if snap.monthly_cash_burn > 0:
            snap.runway_months = round(snap.cash_and_equivalents / snap.monthly_cash_burn, 1)
        else:
            snap.runway_months = 999  # cash flow positive

        # Run stress scenarios
        scenarios = [
            ("Base Case", "No stress", 0, 0, 0, "mild"),
            ("Mild Funding Loss", "Lose 1 warehouse facility", -15, -10, -8, "moderate"),
            ("Moderate Funding Crisis", "Lose 2 facilities, spreads widen", -30, -25, -20, "severe"),
            ("Severe Liquidity Crisis", "No new ABS issuance for 6 months", -50, -40, -35, "extreme"),
            ("2022-Style Drawdown", "Replicate 2022 funding environment", -40, -50, -45, "extreme"),
            ("Rate Shock +200bp", "Sudden rate increase", -10, -20, -15, "moderate"),
            ("Credit Deterioration", "Delinquencies spike 3x", -20, -15, -25, "severe"),
            ("Combined Stress", "Rate shock + credit + funding", -45, -55, -50, "extreme"),
        ]

        for name, desc, fund_impact, orig_impact, rev_impact, severity in scenarios:
            adj_burn = snap.monthly_cash_burn * (1 - rev_impact / 100)
            if adj_burn > 0:
                survival = snap.cash_and_equivalents / adj_burn
            else:
                survival = 999
            snap.scenarios.append(StressScenario(
                name=name, description=desc,
                funding_impact_pct=fund_impact,
                origination_impact_pct=orig_impact,
                revenue_impact_pct=rev_impact,
                cash_burn_months=round(survival, 1),
                survives=survival > 12,
                severity=severity,
            ))

        # Survival analysis
        survivals = [s.cash_burn_months for s in snap.scenarios if s.cash_burn_months is not None]
        snap.min_survival_months = min(survivals) if survivals else 0
        worst = min(snap.scenarios, key=lambda s: s.cash_burn_months or 999)
        snap.worst_case_scenario = worst.name
        failed = sum(1 for s in snap.scenarios if not s.survives)
        snap.probability_of_distress = round(failed / len(snap.scenarios) * 100, 1) if snap.scenarios else 0

        snap.liquidity_score = self._liquidity_score(snap)
        snap.balance_sheet_health_score = self._health_score(snap)

        return snap

    def _liquidity_score(self, snap: StressSnapshot) -> float:
        score = 50.0
        score += min(20, snap.runway_months * 0.8)
        score += min(10, (snap.current_ratio - 1.0) * 20)
        score += min(10, snap.net_cash / 100)
        score -= snap.probability_of_distress * 0.3
        return round(max(0, min(100, score)), 2)

    def _health_score(self, snap: StressSnapshot) -> float:
        score = 50.0
        score += min(15, snap.runway_months * 0.5)
        score += min(10, snap.net_cash / 200)
        score -= snap.probability_of_distress * 0.4
        score += min(10, (snap.current_ratio - 1.0) * 15)
        return round(max(0, min(100, score)), 2)

    def _defaults(self) -> dict:
        return {
            "cash": 800,
            "total_debt": 200,
            "current_ratio": 1.8,
            "quick_ratio": 1.5,
            "monthly_cash_burn": 15,
        }
