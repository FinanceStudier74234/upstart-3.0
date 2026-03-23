"""
Bot 6: Options Strategy Bot
Compares P/L curves, risk/reward across bullish/bearish structures.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from backend.bots.base_bot import BaseBot, BotInput, BotOutput


class StrategyBot(BaseBot):
    name = "options_strategy"

    async def run(self, input: BotInput) -> BotOutput:
        price = max(0.01, input.current_price or 70.0)
        params = input.scenario_params
        iv = max(0.01, min(params.get("iv", 0.70), 5.0))
        dte = max(1, min(params.get("dte", 30), 730))
        direction = params.get("direction", "bearish")  # bullish | bearish | neutral
        self._rfr = max(-0.05, min(params.get("risk_free_rate", 0.05), 0.30))

        strategies = []

        if direction == "bullish":
            strategies = self._bullish_strategies(price, iv, dte)
        elif direction == "bearish":
            strategies = self._bearish_strategies(price, iv, dte)
        else:
            strategies = self._neutral_strategies(price, iv, dte)

        # Generate P/L surface for each strategy
        price_range = np.linspace(price * 0.7, price * 1.3, 25)
        for strat in strategies:
            strat["pl_curve"] = self._compute_pl_curve(strat, price_range, price)

        # Rank by risk-adjusted return
        ranked = sorted(strategies, key=lambda s: s.get("expected_value", 0), reverse=True)
        best = ranked[0]["name"] if ranked else "none"

        return self._create_output(
            results={
                "strategies": strategies,
                "best_strategy": best,
                "direction": direction,
                "iv_environment": "high" if iv > 0.6 else "low" if iv < 0.3 else "normal",
                "recommendation": self._recommend(direction, iv, strategies),
            },
            tables=[{"name": f"{direction.title()} Strategies", "data": [
                {k: v for k, v in s.items() if k != "pl_curve"} for s in strategies
            ]}],
            assumptions={"price": price, "iv": iv, "dte": dte},
            limitations=["Assumes constant IV", "No early exercise modeling"],
            confidence=0.50,
            explanation=f"{direction.title()} strategy comparison at ${price}, IV={iv:.0%}, {dte} DTE",
        )

    def _bullish_strategies(self, price, iv, dte):
        t = dte / 365
        call_strike = round(price * 1.05 / 2.5) * 2.5
        spread_long = round(price * 0.95 / 2.5) * 2.5
        spread_short = round(price * 1.05 / 2.5) * 2.5
        # Guard: ensure strikes differ by at least one tick
        if spread_short <= spread_long:
            spread_short = spread_long + 2.5

        call_price = self._bs_price(price, call_strike, iv, t, "call")
        spread_debit = self._bs_price(price, spread_long, iv, t, "call") - self._bs_price(price, spread_short, iv, t, "call")

        return [
            {
                "name": "Long Stock",
                "type": "equity", "max_risk": f"${price}", "max_reward": "unlimited",
                "breakeven": price, "cost": price,
                "expected_value": round(price * 0.02, 2),  # Assume 2% expected return
            },
            {
                "name": f"Long {call_strike} Call",
                "type": "long_call", "strike": call_strike,
                "max_risk": f"${call_price:.2f}", "max_reward": "unlimited",
                "breakeven": round(call_strike + call_price, 2), "cost": round(call_price, 2),
                "pct_move_to_breakeven": round((call_strike + call_price - price) / price * 100, 1),
                "expected_value": round(call_price * -0.1, 2),  # Negative due to theta
            },
            {
                "name": f"{spread_long}/{spread_short} Call Spread",
                "type": "call_spread", "long_strike": spread_long, "short_strike": spread_short,
                "max_risk": f"${spread_debit:.2f}", "max_reward": f"${spread_short - spread_long - spread_debit:.2f}",
                "breakeven": round(spread_long + spread_debit, 2), "cost": round(max(0.1, spread_debit), 2),
                "expected_value": round(max(0.1, spread_debit) * 0.3, 2),
            },
        ]

    def _bearish_strategies(self, price, iv, dte):
        t = dte / 365
        put_strike = round(price * 0.95 / 2.5) * 2.5
        spread_long = round(price * 0.95 / 2.5) * 2.5   # Buy higher-strike put (more valuable)
        spread_short = round(price * 0.85 / 2.5) * 2.5  # Sell lower-strike put
        # Guard: ensure long strike > short strike for bear put spread
        if spread_long <= spread_short:
            spread_long = spread_short + 2.5

        put_price = self._bs_price(price, put_strike, iv, t, "put")
        spread_debit = self._bs_price(price, spread_long, iv, t, "put") - self._bs_price(price, spread_short, iv, t, "put")

        return [
            {
                "name": "Short Stock",
                "type": "short_equity", "max_risk": "unlimited", "max_reward": f"${price}",
                "breakeven": price, "cost": 0,
                "squeeze_exposure": "high",
                "expected_value": round(price * 0.02, 2),
            },
            {
                "name": f"Long {put_strike} Put",
                "type": "long_put", "strike": put_strike,
                "max_risk": f"${put_price:.2f}", "max_reward": f"${put_strike - put_price:.2f}",
                "breakeven": round(put_strike - put_price, 2), "cost": round(put_price, 2),
                "squeeze_exposure": "none",
                "expected_value": round(put_price * -0.1, 2),
            },
            {
                "name": f"{spread_long}/{spread_short} Put Spread",
                "type": "put_spread", "long_strike": spread_long, "short_strike": spread_short,
                "max_risk": f"${max(0.1, spread_debit):.2f}",
                "max_reward": f"${spread_long - spread_short - max(0.1, spread_debit):.2f}",
                "breakeven": round(spread_long - max(0.1, spread_debit), 2),
                "cost": round(max(0.1, spread_debit), 2),
                "squeeze_exposure": "none",
                "expected_value": round(max(0.1, spread_debit) * 0.3, 2),
            },
        ]

    def _neutral_strategies(self, price, iv, dte):
        return [{"name": "No trade", "type": "cash", "max_risk": "$0", "expected_value": 0}]

    def _bs_price(self, s, k, vol, t, opt_type):
        if t <= 0 or vol <= 0 or s <= 0 or k <= 0:
            return max(0, s - k) if opt_type == "call" else max(0, k - s)
        rfr = getattr(self, "_rfr", 0.05)
        d1 = (math.log(s / k) + (rfr + vol**2 / 2) * t) / (vol * math.sqrt(t))
        d2 = d1 - vol * math.sqrt(t)
        if opt_type == "call":
            return max(0.01, s * norm.cdf(d1) - k * math.exp(-rfr * t) * norm.cdf(d2))
        return max(0.01, k * math.exp(-rfr * t) * norm.cdf(-d2) - s * norm.cdf(-d1))

    def _compute_pl_curve(self, strat, price_range, current_price):
        result = []
        stype = strat.get("type", "")
        for p in price_range:
            if stype == "equity":
                pnl = (p - current_price) / current_price * 100
            elif stype == "short_equity":
                pnl = (current_price - p) / current_price * 100
            elif stype == "long_call":
                pnl = (max(0, p - strat["strike"]) - strat["cost"]) / strat["cost"] * 100
            elif stype == "long_put":
                pnl = (max(0, strat["strike"] - p) - strat["cost"]) / strat["cost"] * 100
            elif stype == "call_spread":
                pnl = (min(strat["short_strike"] - strat["long_strike"], max(0, p - strat["long_strike"])) - strat["cost"]) / strat["cost"] * 100
            elif stype == "put_spread":
                pnl = (min(strat["long_strike"] - strat["short_strike"], max(0, strat["long_strike"] - p)) - strat["cost"]) / strat["cost"] * 100
            else:
                pnl = 0
            result.append({"price": round(p, 2), "pnl": round(pnl, 1)})
        return result

    def _recommend(self, direction, iv, strategies):
        if iv > 0.8:
            return f"High IV favors selling premium. Consider spreads over outright {'calls' if direction == 'bullish' else 'puts'}."
        elif iv < 0.3:
            return f"Low IV favors buying premium. Outright {'calls' if direction == 'bullish' else 'puts'} are attractive."
        return f"Normal IV. Spreads offer best risk/reward for {direction} thesis."
