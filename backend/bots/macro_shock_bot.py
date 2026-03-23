"""
Bot 5: Macro Shock Bot
Simulates SPY drawdowns, rate changes, recession, credit stress on UPST.
"""

from __future__ import annotations

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class MacroShockBot(BaseBot):
    name = "macro_shock"

    async def run(self, input: BotInput) -> BotOutput:
        price = max(0.01, input.current_price or 70.0)
        params = input.scenario_params
        beta = max(-5.0, min(params.get("beta", 1.5), 5.0))

        scenarios = []

        # Pre-built macro scenarios
        macro_scenarios = [
            {
                "name": "Mild Correction (SPY -5%)",
                "spy_return": -5, "rate_change_bps": 0, "credit_spread_bps": 50,
                "unemployment_change": 0.2, "probability": 0.25,
            },
            {
                "name": "Bear Market (SPY -20%)",
                "spy_return": -20, "rate_change_bps": -50, "credit_spread_bps": 200,
                "unemployment_change": 1.0, "probability": 0.10,
            },
            {
                "name": "Recession (SPY -30%)",
                "spy_return": -30, "rate_change_bps": -150, "credit_spread_bps": 400,
                "unemployment_change": 2.5, "probability": 0.05,
            },
            {
                "name": "Rate Hike Shock (+100bps)",
                "spy_return": -8, "rate_change_bps": 100, "credit_spread_bps": 100,
                "unemployment_change": 0.3, "probability": 0.08,
            },
            {
                "name": "Rate Cut Rally (-100bps)",
                "spy_return": 10, "rate_change_bps": -100, "credit_spread_bps": -50,
                "unemployment_change": -0.1, "probability": 0.15,
            },
            {
                "name": "Credit Crisis",
                "spy_return": -15, "rate_change_bps": -25, "credit_spread_bps": 500,
                "unemployment_change": 1.5, "probability": 0.03,
            },
            {
                "name": "Goldilocks (Soft Landing)",
                "spy_return": 15, "rate_change_bps": -75, "credit_spread_bps": -100,
                "unemployment_change": -0.3, "probability": 0.20,
            },
            {
                "name": "Stagflation",
                "spy_return": -10, "rate_change_bps": 50, "credit_spread_bps": 200,
                "unemployment_change": 1.0, "probability": 0.05,
            },
        ]

        for ms in macro_scenarios:
            # UPST impact calculation
            spy_impact = ms["spy_return"] * beta
            rate_impact = -ms["rate_change_bps"] / 25 * 2  # Each 25bps = ~2% for UPST
            credit_impact = -ms["credit_spread_bps"] / 100 * 3  # Credit-sensitive
            unemp_impact = -ms["unemployment_change"] * 5  # Labor market effect on lending

            total_impact = spy_impact + rate_impact + credit_impact + unemp_impact
            new_price = round(max(0.01, price * (1 + total_impact / 100)), 2)

            # Attractiveness changes
            long_attractive = total_impact > 5
            short_attractive = total_impact < -10

            scenarios.append({
                **ms,
                "upst_impact_pct": round(total_impact, 1),
                "projected_price": new_price,
                "spy_component": round(spy_impact, 1),
                "rate_component": round(rate_impact, 1),
                "credit_component": round(credit_impact, 1),
                "unemployment_component": round(unemp_impact, 1),
                "long_attractiveness": "high" if long_attractive else "low",
                "short_attractiveness": "high" if short_attractive else "low",
                "regime_transition": self._regime_from_scenario(ms),
            })

        return self._create_output(
            results={
                "scenarios": scenarios,
                "most_likely": max(scenarios, key=lambda x: x["probability"])["name"],
                "worst_case_price": min(s["projected_price"] for s in scenarios),
                "best_case_price": max(s["projected_price"] for s in scenarios),
                "expected_price": round(sum(s["projected_price"] * s["probability"] for s in scenarios) /
                                       max(0.01, sum(s["probability"] for s in scenarios)), 2),
            },
            tables=[{"name": "Macro Shock Scenarios", "data": scenarios}],
            assumptions={"beta": beta, "rate_sensitivity": "high", "credit_sensitivity": "high"},
            limitations=["Linear factor model", "Does not capture nonlinear stress dynamics",
                          "Probabilities are subjective"],
            confidence=0.45,
            explanation=f"Macro shock analysis across {len(scenarios)} scenarios, beta={beta}",
        )

    def _regime_from_scenario(self, ms):
        if ms["spy_return"] < -15:
            return "risk_off"
        if ms["spy_return"] > 10:
            return "risk_on"
        if ms["credit_spread_bps"] > 300:
            return "credit_stress"
        return "transitional"
