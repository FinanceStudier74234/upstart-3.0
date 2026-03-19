"""
Bot 2: Options Reaction Bot
Simulates options chain repricing under different scenarios.
"""

from __future__ import annotations

import math

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class OptionsReactionBot(BaseBot):
    name = "options_reaction"

    async def run(self, input: BotInput) -> BotOutput:
        price = input.current_price or 70.0
        params = input.scenario_params
        price_change_pct = params.get("price_change_pct", 0.0)
        iv_change_pct = params.get("iv_change_pct", 0.0)
        days_elapsed = params.get("days_elapsed", 7)
        base_iv = params.get("base_iv", 0.70)

        new_price = price * (1 + price_change_pct / 100)
        new_iv = base_iv * (1 + iv_change_pct / 100)

        # Simulate repricing for sample strikes
        strikes = [round(price * mult, 2) for mult in [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]]
        dte_base = 30
        dte_new = max(1, dte_base - days_elapsed)

        results_calls = []
        results_puts = []

        for strike in strikes:
            # Simplified Black-Scholes-like estimation
            for opt_type in ["call", "put"]:
                base_price_opt = self._approx_option_price(price, strike, base_iv, dte_base / 365, opt_type)
                new_price_opt = self._approx_option_price(new_price, strike, new_iv, dte_new / 365, opt_type)
                change = new_price_opt - base_price_opt
                change_pct = (change / base_price_opt * 100) if base_price_opt > 0.01 else 0

                entry = {
                    "strike": strike,
                    "base_price": round(base_price_opt, 2),
                    "new_price": round(new_price_opt, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 1),
                    "dte_remaining": dte_new,
                }
                if opt_type == "call":
                    results_calls.append(entry)
                else:
                    results_puts.append(entry)

        # Best structures
        best_bullish = "long_calls" if iv_change_pct <= 0 else "call_debit_spread"
        best_bearish = "long_puts" if iv_change_pct <= 0 else "put_debit_spread"

        return self._create_output(
            results={
                "calls": results_calls,
                "puts": results_puts,
                "best_bullish_structure": best_bullish,
                "best_bearish_structure": best_bearish,
                "iv_impact": "Elevated IV favors selling premium" if new_iv > 0.8 else "Lower IV favors buying premium",
                "theta_impact": f"{days_elapsed} days of decay applied",
            },
            tables=[{"name": "Call Repricing", "data": results_calls}, {"name": "Put Repricing", "data": results_puts}],
            assumptions={"base_price": price, "new_price": round(new_price, 2), "base_iv": base_iv, "new_iv": round(new_iv, 4)},
            limitations=["Simplified BS model", "Does not model skew changes", "No dividend adjustment"],
            confidence=0.50,
            explanation=f"Options repricing for UPST ${price}→${new_price:.2f}, IV {base_iv:.0%}→{new_iv:.0%}",
        )

    def _approx_option_price(self, s, k, vol, t, opt_type):
        """Simplified Black-Scholes approximation."""
        if t <= 0 or vol <= 0:
            if opt_type == "call":
                return max(0, s - k)
            return max(0, k - s)

        d1 = (math.log(s / k) + (0.05 + vol**2 / 2) * t) / (vol * math.sqrt(t))
        d2 = d1 - vol * math.sqrt(t)

        from scipy.stats import norm
        if opt_type == "call":
            return max(0.01, s * norm.cdf(d1) - k * math.exp(-0.05 * t) * norm.cdf(d2))
        else:
            return max(0.01, k * math.exp(-0.05 * t) * norm.cdf(-d2) - s * norm.cdf(-d1))
