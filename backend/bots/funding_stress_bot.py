"""
Bot 4: Funding Stress Bot
Simulates funding loss, renewal failure, facility reduction scenarios.
"""

from __future__ import annotations

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class FundingStressBot(BaseBot):
    name = "funding_stress"

    async def run(self, input: BotInput) -> BotOutput:
        price = input.current_price or 70.0
        params = input.scenario_params

        total_capacity = params.get("total_capacity_mm", 5000)
        facility_count = params.get("facility_count", 8)
        avg_maturity_months = params.get("avg_maturity_months", 18)
        quarterly_origination = params.get("quarterly_origination_mm", 2000)

        scenarios = []

        # Scenario 1: Single facility non-renewal
        lost_pct = 1 / max(facility_count, 1) * 100
        remaining = total_capacity * (1 - lost_pct / 100)
        months_coverage = remaining / (quarterly_origination / 3) if quarterly_origination > 0 else 0
        price_impact = -lost_pct * 0.4  # 0.4x multiplier
        scenarios.append({
            "name": "Single Facility Non-Renewal",
            "capacity_loss_pct": round(lost_pct, 1),
            "remaining_capacity_mm": round(remaining),
            "months_origination_support": round(months_coverage, 1),
            "price_impact_pct": round(price_impact, 1),
            "projected_price": round(price * (1 + price_impact / 100), 2),
            "short_thesis_impact": "strengthens" if price_impact < -5 else "neutral",
            "probability": 0.15,
        })

        # Scenario 2: 25% capacity reduction
        for loss_pct, label, prob in [
            (25, "Moderate Funding Stress (-25%)", 0.10),
            (50, "Severe Funding Stress (-50%)", 0.05),
            (75, "Critical Funding Crisis (-75%)", 0.02),
        ]:
            remaining = total_capacity * (1 - loss_pct / 100)
            months_coverage = remaining / (quarterly_origination / 3) if quarterly_origination > 0 else 0
            # Nonlinear price impact: larger losses hurt more
            price_impact = -loss_pct * 0.6 * (1 + loss_pct / 100)
            origination_impact = -min(loss_pct * 1.2, 90)  # Origination drops faster than capacity

            scenarios.append({
                "name": label,
                "capacity_loss_pct": loss_pct,
                "remaining_capacity_mm": round(remaining),
                "months_origination_support": round(months_coverage, 1),
                "origination_impact_pct": round(origination_impact, 1),
                "price_impact_pct": round(price_impact, 1),
                "projected_price": round(price * (1 + price_impact / 100), 2),
                "multiple_compression": round(loss_pct * 0.3, 1),
                "short_thesis_impact": "strongly_strengthens",
                "probability": prob,
            })

        # Scenario 3: New funding secured
        for gain_pct, label, prob in [
            (15, "New Funding Partner (+15%)", 0.20),
            (30, "Major Funding Expansion (+30%)", 0.10),
        ]:
            new_cap = total_capacity * (1 + gain_pct / 100)
            price_impact = gain_pct * 0.3
            scenarios.append({
                "name": label,
                "capacity_change_pct": gain_pct,
                "new_capacity_mm": round(new_cap),
                "price_impact_pct": round(price_impact, 1),
                "projected_price": round(price * (1 + price_impact / 100), 2),
                "short_thesis_impact": "weakens",
                "probability": prob,
            })

        return self._create_output(
            results={
                "scenarios": scenarios,
                "current_capacity_mm": total_capacity,
                "current_months_coverage": round(total_capacity / (quarterly_origination / 3), 1) if quarterly_origination > 0 else 0,
                "funding_cliff_months": avg_maturity_months,
                "concentration_risk": "high" if facility_count < 5 else "moderate" if facility_count < 8 else "low",
            },
            tables=[{"name": "Funding Stress Scenarios", "data": scenarios}],
            assumptions={
                "total_capacity": total_capacity,
                "facility_count": facility_count,
                "quarterly_origination": quarterly_origination,
            },
            limitations=["Linear approximation of nonlinear effects", "Does not model covenant triggers"],
            confidence=0.45,
            explanation=f"Funding stress analysis: ${total_capacity}M capacity across {facility_count} facilities",
        )
