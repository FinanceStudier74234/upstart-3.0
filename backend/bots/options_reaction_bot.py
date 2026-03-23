"""
Bot 2: Options Reaction Bot
Simulates options chain repricing under different scenarios.
"""

from __future__ import annotations

import math

from scipy.stats import norm

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class OptionsReactionBot(BaseBot):
    name = "options_reaction"

    async def run(self, input: BotInput) -> BotOutput:
        price = max(0.01, input.current_price or 70.0)
        params = input.scenario_params
        price_change_pct = max(-99, min(params.get("price_change_pct", 0.0), 500))
        iv_change_pct = max(-95, min(params.get("iv_change_pct", 0.0), 500))
        days_elapsed = max(0, min(params.get("days_elapsed", 7), 365))
        base_iv = max(0.01, params.get("base_iv", 0.70))
        self._rfr = params.get("risk_free_rate", 0.05)  # configurable risk-free rate

        new_price = max(0.01, price * (1 + price_change_pct / 100))
        new_iv = max(0.01, base_iv * (1 + iv_change_pct / 100))

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

        # Greeks summary for ATM strike
        s = new_price
        vol = new_iv
        t = dte_new / 365
        atm_strike = min(strikes, key=lambda k: abs(k - s))
        if t > 0 and vol > 0:
            d1 = (math.log(s / atm_strike) + (self._rfr + vol**2 / 2) * t) / (vol * math.sqrt(t))
            delta_call = round(norm.cdf(d1), 4)
            delta_put = round(delta_call - 1, 4)
            gamma = round(norm.pdf(d1) / (s * vol * math.sqrt(t)), 6)
            vega = round(s * norm.pdf(d1) * math.sqrt(t) / 100, 4)
            theta = round(-(s * norm.pdf(d1) * vol) / (2 * math.sqrt(t)) / 365, 4)
        else:
            delta_call, delta_put, gamma, vega, theta = 0, 0, 0, 0, 0

        greeks_summary = {
            "atm_strike": atm_strike,
            "delta_call": delta_call,
            "delta_put": delta_put,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
        }

        # 2D P/L surface: price changes × IV changes for ATM call
        price_shifts = [-10, -5, 0, 5, 10]  # percent
        iv_shifts = [-20, -10, 0, 10, 20]  # percent
        atm_call_base = self._approx_option_price(price, atm_strike, base_iv, dte_base / 365, "call")
        pl_surface = []
        for ps in price_shifts:
            row = {"price_change_pct": ps}
            for ivs in iv_shifts:
                scenario_price = price * (1 + ps / 100)
                scenario_iv = base_iv * (1 + ivs / 100)
                scenario_opt = self._approx_option_price(scenario_price, atm_strike, scenario_iv, dte_new / 365, "call")
                pl = round(scenario_opt - atm_call_base, 2)
                row[f"iv_change_{ivs}pct"] = pl
            pl_surface.append(row)

        # Best structures
        best_bullish = "long_calls" if iv_change_pct <= 0 else "call_debit_spread"
        best_bearish = "long_puts" if iv_change_pct <= 0 else "put_debit_spread"

        return self._create_output(
            results={
                "calls": results_calls,
                "puts": results_puts,
                "greeks_summary": greeks_summary,
                "pl_surface": pl_surface,
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
        """Black-Scholes option pricing with configurable risk-free rate."""
        if t <= 0 or vol <= 0 or s <= 0 or k <= 0:
            if opt_type == "call":
                return max(0, s - k)
            return max(0, k - s)

        rfr = getattr(self, "_rfr", 0.05)
        d1 = (math.log(s / k) + (rfr + vol**2 / 2) * t) / (vol * math.sqrt(t))
        d2 = d1 - vol * math.sqrt(t)

        if opt_type == "call":
            return max(0.01, s * norm.cdf(d1) - k * math.exp(-rfr * t) * norm.cdf(d2))
        else:
            return max(0.01, k * math.exp(-rfr * t) * norm.cdf(-d2) - s * norm.cdf(-d1))
