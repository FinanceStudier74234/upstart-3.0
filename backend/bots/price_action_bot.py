"""
Bot 1: Price Action Simulation Bot
Simulates future price paths using technical/vol/SPY regimes + Monte Carlo.
"""

from __future__ import annotations

import math

import numpy as np

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class PriceActionBot(BaseBot):
    name = "price_action_simulation"

    async def run(self, input: BotInput) -> BotOutput:
        price = input.current_price or 70.0
        params = input.scenario_params
        n_paths = params.get("n_paths", 1000)
        horizon = params.get("horizon_days", 63)
        mu = params.get("drift", 0.0)
        sigma = params.get("volatility", 0.65)
        beta = params.get("beta", 1.5)
        spy_scenario = params.get("spy_return_pct", 0.0)

        # Adjust drift for SPY scenario
        adj_mu = mu + beta * spy_scenario / 100 * 252 / horizon

        dt_val = 1 / 252
        paths = np.zeros((n_paths, horizon + 1))
        paths[:, 0] = price

        for t in range(1, horizon + 1):
            z = np.random.standard_normal(n_paths)
            paths[:, t] = paths[:, t-1] * np.exp(
                (adj_mu - 0.5 * sigma**2) * dt_val + sigma * math.sqrt(dt_val) * z
            )

        final = paths[:, -1]
        percentiles = {p: round(float(np.percentile(final, p)), 2) for p in [5, 10, 25, 50, 75, 90, 95]}

        # Support/resistance migration
        supports = [percentiles[25], percentiles[10], percentiles[5]]
        resistances = [percentiles[75], percentiles[90], percentiles[95]]

        return self._create_output(
            results={
                "percentiles": percentiles,
                "probability_above_current": round(float(np.mean(final > price)), 4),
                "probability_below_current": round(float(np.mean(final < price)), 4),
                "expected_price": round(float(np.mean(final)), 2),
                "price_std": round(float(np.std(final)), 2),
                "projected_supports": supports,
                "projected_resistances": resistances,
                "max_path": round(float(np.max(paths)), 2),
                "min_path": round(float(np.min(paths)), 2),
            },
            paths=[paths[i].tolist() for i in range(min(50, n_paths))],  # Sample paths for chart
            assumptions={"drift": mu, "volatility": sigma, "beta": beta, "spy_scenario": spy_scenario},
            limitations=["Assumes log-normal returns", "Does not model jumps or regime changes within horizon"],
            confidence=0.55,
            explanation=f"Simulated {n_paths} paths over {horizon} days. Median target: ${percentiles[50]}",
        )
