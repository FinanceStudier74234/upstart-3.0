"""
Bot 3: Short Squeeze Simulation Bot
Simulates short-cover cascades, gamma squeeze pressure, and upside acceleration.
"""

from __future__ import annotations

import math

import numpy as np

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class SqueezeBot(BaseBot):
    name = "short_squeeze_simulation"

    async def run(self, input: BotInput) -> BotOutput:
        price = input.current_price or 70.0
        params = input.scenario_params
        short_pct_float = params.get("short_pct_float", 15.0)
        days_to_cover = params.get("days_to_cover", 3.0)
        utilization = params.get("utilization", 70.0)
        call_oi_surge = params.get("call_oi_surge_pct", 0.0)
        trigger_pct = params.get("trigger_move_pct", 5.0)

        # Simulate squeeze cascade
        n_scenarios = 5
        scenarios = []

        for severity_label, cover_pct in [
            ("mild", 10), ("moderate", 25), ("strong", 50), ("extreme", 75), ("max", 95)
        ]:
            shares_covered = short_pct_float * cover_pct / 100
            # Price impact: each 1% of float covered adds ~0.5-2% to price (vol dependent)
            base_impact = shares_covered * 0.8  # 0.8% per 1% of float covered
            # Gamma amplifier
            gamma_mult = 1 + call_oi_surge / 100 * 0.5
            # Utilization amplifier (high utilization = more forced covering)
            util_mult = 1 + max(0, (utilization - 70)) / 30 * 0.5
            # Reflexivity: covering begets more covering
            reflexivity = 1 + (cover_pct / 100) ** 1.5

            total_impact = base_impact * gamma_mult * util_mult * reflexivity
            squeeze_price = round(price * (1 + total_impact / 100), 2)

            # Probability estimate
            if severity_label == "mild":
                prob = min(0.40, 0.15 + short_pct_float / 100)
            elif severity_label == "moderate":
                prob = min(0.25, 0.08 + short_pct_float / 150)
            elif severity_label == "strong":
                prob = min(0.12, 0.03 + short_pct_float / 300)
            elif severity_label == "extreme":
                prob = min(0.05, 0.01 + short_pct_float / 500)
            else:
                prob = min(0.02, 0.005 + short_pct_float / 1000)

            scenarios.append({
                "severity": severity_label,
                "shares_covered_pct": cover_pct,
                "price_impact_pct": round(total_impact, 2),
                "squeeze_price": squeeze_price,
                "probability": round(prob, 4),
                "cover_urgency": "high" if utilization > 85 else "moderate" if utilization > 60 else "low",
                "gamma_amplification": round(gamma_mult, 2),
            })

        # Do-not-short zones
        do_not_short_above = round(price * (1 + trigger_pct / 100), 2)

        # Probability-weighted expected squeeze outcome
        expected_squeeze = sum(
            s["squeeze_price"] * s["probability"] for s in scenarios
        )
        no_squeeze_prob = 1 - sum(s["probability"] for s in scenarios)
        expected_price = round(expected_squeeze + price * no_squeeze_prob, 2)

        # Monte Carlo squeeze simulation (500 paths)
        mc_n_paths = 500
        mc_steps = 20
        mc_paths_arr = np.zeros((mc_n_paths, mc_steps + 1))
        mc_paths_arr[:, 0] = price
        cover_prob = short_pct_float / 100 * utilization / 100

        for step in range(1, mc_steps + 1):
            # Determine which paths trigger covering at this step
            triggers = np.random.random(mc_n_paths) < cover_prob
            # Random price shock of 1-5% upward when covering triggers
            shocks = np.where(triggers, 1 + np.random.uniform(0.01, 0.05, mc_n_paths), 1.0)
            mc_paths_arr[:, step] = mc_paths_arr[:, step - 1] * shocks

        mc_final = mc_paths_arr[:, -1]
        mc_percentiles = {
            int(p): round(float(np.percentile(mc_final, p)), 2)
            for p in [5, 25, 50, 75, 95]
        }
        mc_sample_paths = [mc_paths_arr[i].tolist() for i in range(min(20, mc_n_paths))]

        return self._create_output(
            results={
                "scenarios": scenarios,
                "expected_price_with_squeeze_risk": expected_price,
                "do_not_short_above": do_not_short_above,
                "overall_squeeze_probability": round(sum(s["probability"] for s in scenarios), 4),
                "max_squeeze_price": max(s["squeeze_price"] for s in scenarios),
                "monte_carlo_squeeze_prices": mc_percentiles,
                "mc_paths": mc_sample_paths,
                "cover_urgency_zones": [
                    {"zone": "immediate_cover", "trigger": round(price * 1.05, 2)},
                    {"zone": "cautious_cover", "trigger": round(price * 1.10, 2)},
                    {"zone": "forced_cover", "trigger": round(price * 1.20, 2)},
                ],
            },
            tables=[{"name": "Squeeze Scenarios", "data": scenarios}],
            assumptions={
                "short_pct_float": short_pct_float, "days_to_cover": days_to_cover,
                "utilization": utilization, "call_oi_surge": call_oi_surge,
            },
            limitations=["Simplified cascade model", "Does not model real-time order book dynamics",
                          "Probability estimates are heuristic"],
            confidence=0.40,
            explanation=f"Squeeze simulation: {short_pct_float}% SI, {utilization}% util. Max squeeze to ${max(s['squeeze_price'] for s in scenarios)}",
        )
