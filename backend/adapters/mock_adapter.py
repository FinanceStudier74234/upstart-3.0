"""Mock adapter — generates realistic synthetic data for all provider interfaces.
Used when MOCK_MODE=true or when API keys are unavailable.
"""

from __future__ import annotations

import datetime as dt
import math
import random
import logging

import numpy as np

from backend.adapters.base import (
    BaseMarketAdapter, BaseMacroAdapter, BaseShortAdapter,
    BaseNewsAdapter, BaseFundamentalAdapter, DataEnvelope,
)

logger = logging.getLogger(__name__)

# Local RNG for reproducibility without polluting global state
_rng = random.Random(42)
_np_rng = np.random.RandomState(42)


def _gbm_path(s0: float, mu: float, sigma: float, days: int) -> list[float]:
    """Geometric Brownian Motion price path."""
    dt_val = 1 / 252
    prices = [s0]
    for _ in range(days):
        z = _np_rng.standard_normal()
        s = prices[-1] * math.exp((mu - 0.5 * sigma**2) * dt_val + sigma * math.sqrt(dt_val) * z)
        prices.append(round(s, 2))
    return prices


class MockMarketAdapter(BaseMarketAdapter):

    def __init__(self):
        self._base_price = 72.50  # Approximate recent UPST price
        self._spy_price = 520.0

    async def get_quote(self, ticker: str) -> DataEnvelope:
        base = self._base_price if ticker == "UPST" else self._spy_price
        jitter = base * _rng.uniform(-0.02, 0.02)
        price = round(base + jitter, 2)
        return DataEnvelope(
            data={
                "ticker": ticker, "price": price,
                "previous_close": round(price - _rng.uniform(-2, 2), 2),
                "market_cap": round(price * 85e6, 0) if ticker == "UPST" else None,
                "volume": _rng.randint(2_000_000, 8_000_000),
            },
            source="mock", source_label="mock", confidence=0.5,
            warnings=["Mock data — not real market data"],
        )

    async def get_bars(
        self, ticker: str, timeframe: str, start: dt.date, end: dt.date,
    ) -> DataEnvelope:
        base = self._base_price if ticker == "UPST" else self._spy_price
        sigma = 0.65 if ticker == "UPST" else 0.15  # UPST is high-vol
        days = (end - start).days
        if days <= 0:
            days = 30
        closes = _gbm_path(base, 0.0, sigma, days)
        records = []
        cur = start
        for i, c in enumerate(closes):
            if cur.weekday() < 5:  # Skip weekends
                h = round(c * _rng.uniform(1.0, 1.04), 2)
                l = round(c * _rng.uniform(0.96, 1.0), 2)
                o = round(_rng.uniform(l, h), 2)
                records.append({
                    "ticker": ticker, "timeframe": timeframe,
                    "bar_time": dt.datetime.combine(cur, dt.time(16, 0), tzinfo=dt.timezone.utc),
                    "open": o, "high": h, "low": l, "close": c,
                    "volume": _rng.randint(1_000_000, 10_000_000),
                    "vwap": round((h + l + c) / 3, 2),
                })
            cur += dt.timedelta(days=1)
        return DataEnvelope(
            data=records, source="mock", source_label="mock", confidence=0.5,
            warnings=["Mock GBM-generated price data"],
        )

    async def get_options_chain(self, ticker: str) -> DataEnvelope:
        price = self._base_price if ticker == "UPST" else self._spy_price
        contracts = []
        now = dt.date.today()
        for weeks_out in [1, 2, 4, 8, 12]:
            exp = now + dt.timedelta(weeks=weeks_out)
            for pct in [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]:
                strike = round(price * (1 + pct) / 2.5) * 2.5  # Round to nearest 2.50
                for opt_type in ["call", "put"]:
                    iv = round(_rng.uniform(0.50, 1.20), 4) if ticker == "UPST" else round(_rng.uniform(0.12, 0.25), 4)
                    mid = round(max(0.05, price * iv * math.sqrt(weeks_out / 52) * 0.4), 2)
                    contracts.append({
                        "ticker": ticker, "option_type": opt_type,
                        "strike": strike, "expiration": exp.isoformat(),
                        "bid": round(mid * 0.95, 2), "ask": round(mid * 1.05, 2),
                        "mark": mid, "last": mid,
                        "volume": _rng.randint(0, 5000),
                        "open_interest": _rng.randint(0, 20000),
                        "implied_volatility": iv,
                        "delta": round(_rng.uniform(-1, 1), 4),
                        "gamma": round(_rng.uniform(0, 0.1), 6),
                        "theta": round(-_rng.uniform(0, 0.5), 4),
                        "vega": round(_rng.uniform(0, 0.5), 4),
                        "in_the_money": (opt_type == "call" and strike < price) or (opt_type == "put" and strike > price),
                    })
        return DataEnvelope(
            data={"ticker": ticker, "underlying_price": price,
                  "expirations": [], "contracts": contracts},
            source="mock", source_label="mock", confidence=0.5,
        )


class MockMacroAdapter(BaseMacroAdapter):

    _MOCK_VALUES = {
        "FED_FUNDS": 5.25, "TREASURY_2Y": 4.65, "TREASURY_10Y": 4.30,
        "CPI_YOY": 3.1, "UNEMPLOYMENT": 4.0, "INITIAL_CLAIMS": 220,
        "HY_SPREAD": 350, "IG_SPREAD": 120, "VIX": 18.5,
        "FINANCIAL_CONDITIONS": -0.2, "RECESSION_PROB": 25.0,
        "CONSUMER_DELINQUENCY": 2.8, "CONSUMER_CREDIT": 5000,
        "LENDING_STANDARDS": 10.0, "PCE_YOY": 2.7,
    }

    async def get_indicator(self, indicator: str) -> DataEnvelope:
        base = self._MOCK_VALUES.get(indicator, 0.0)
        records = []
        today = dt.date.today()
        for i in range(252):
            d = today - dt.timedelta(days=i)
            jitter = base * _rng.uniform(-0.03, 0.03)
            records.append({
                "indicator": indicator,
                "observation_date": d.isoformat(),
                "value": round(base + jitter, 4),
            })
        return DataEnvelope(
            data=records, source="mock", source_label="mock", confidence=0.5,
            warnings=["Mock macro data"],
        )


class MockShortAdapter(BaseShortAdapter):

    async def get_short_interest(self, ticker: str) -> DataEnvelope:
        si_pct = round(_rng.uniform(8, 25), 2)
        shares_float = 75_000_000
        si = int(shares_float * si_pct / 100)
        return DataEnvelope(
            data={
                "ticker": ticker,
                "report_date": dt.date.today().isoformat(),
                "short_interest": si,
                "shares_float": shares_float,
                "short_pct_float": si_pct,
                "days_to_cover": round(_rng.uniform(1.5, 6.0), 2),
                "avg_volume_30d": _rng.randint(3_000_000, 8_000_000),
            },
            source="mock", source_label="mock", confidence=0.5,
        )

    async def get_stock_loan(self, ticker: str) -> DataEnvelope:
        return DataEnvelope(
            data={
                "ticker": ticker,
                "snapshot_date": dt.date.today().isoformat(),
                "cost_to_borrow": round(_rng.uniform(1.0, 15.0), 2),
                "utilization": round(_rng.uniform(40, 95), 1),
                "shares_available": _rng.randint(100_000, 2_000_000),
                "lendable_shares": _rng.randint(5_000_000, 20_000_000),
                "borrow_fee_trend": _rng.choice(["rising", "stable", "falling"]),
            },
            source="mock", source_label="mock", confidence=0.5,
        )


class MockNewsAdapter(BaseNewsAdapter):

    _HEADLINES = [
        "Upstart Reports Record Origination Volume in Latest Quarter",
        "Fed Signals Potential Rate Cut Path, Fintech Stocks Rally",
        "Upstart Announces New Bank Partnership for Auto Lending",
        "Consumer Credit Delinquencies Rise, Pressuring Lending Stocks",
        "Upstart AI Model Approval Rates Improve Year-Over-Year",
        "Short Sellers Increase Bets Against Fintech Lenders",
        "Upstart Completes $400M ABS Securitization",
        "Macro Uncertainty Weighs on Growth Stocks",
        "Upstart Expands HELOC Product to New States",
        "SPY Drops 2% on Recession Fears, UPST Falls 5%",
    ]

    async def get_news(self, ticker: str, limit: int = 50) -> DataEnvelope:
        items = []
        now = dt.datetime.now(dt.timezone.utc)
        for i in range(min(limit, len(self._HEADLINES))):
            items.append({
                "ticker": ticker,
                "published_at": (now - dt.timedelta(hours=i * 8)).isoformat(),
                "headline": self._HEADLINES[i],
                "summary": f"Mock summary for: {self._HEADLINES[i]}",
                "source_name": _rng.choice(["Reuters", "Bloomberg", "CNBC", "MarketWatch"]),
                "category": _rng.choice(["earnings", "funding", "macro", "fintech", "general"]),
                "sentiment_score": round(_rng.uniform(-0.8, 0.8), 3),
                "relevance_score": round(_rng.uniform(0.3, 1.0), 3),
            })
        return DataEnvelope(data=items, source="mock", source_label="mock", confidence=0.5)


class MockFundamentalAdapter(BaseFundamentalAdapter):

    async def get_financials(self, ticker: str) -> DataEnvelope:
        quarters = []
        base_rev = 150_000_000  # ~$150M quarterly
        for q in range(8):
            growth = 1 + 0.05 * (8 - q)  # Decelerating growth going back
            rev = round(base_rev * growth)
            quarters.append({
                "ticker": ticker,
                "period_type": f"Q{(4 - q % 4)}",
                "fiscal_year": 2025 - q // 4,
                "revenue": rev,
                "fee_revenue": round(rev * 0.85),
                "gross_margin": round(_rng.uniform(0.70, 0.80), 4),
                "operating_margin": round(_rng.uniform(-0.10, 0.10), 4),
                "ebitda": round(rev * _rng.uniform(-0.05, 0.15)),
                "adjusted_ebitda": round(rev * _rng.uniform(0.0, 0.20)),
                "eps_diluted": round(_rng.uniform(-0.50, 0.30), 2),
                "cash_and_equivalents": round(_rng.uniform(400e6, 900e6)),
                "total_debt": round(_rng.uniform(500e6, 1500e6)),
                "shares_outstanding": 85_000_000,
            })
        return DataEnvelope(data=quarters, source="mock", source_label="mock", confidence=0.5)

    async def get_earnings(self, ticker: str) -> DataEnvelope:
        releases = []
        for q in range(8):
            d = dt.date.today() - dt.timedelta(days=q * 91)
            implied = round(_rng.uniform(0.08, 0.18), 4)
            realized = round(_rng.uniform(0.05, 0.25), 4)
            releases.append({
                "ticker": ticker, "report_date": d.isoformat(),
                "eps_estimate": round(_rng.uniform(-0.30, 0.20), 2),
                "eps_actual": round(_rng.uniform(-0.20, 0.30), 2),
                "revenue_estimate": round(_rng.uniform(130e6, 180e6)),
                "revenue_actual": round(_rng.uniform(130e6, 200e6)),
                "implied_move": implied, "realized_move": realized,
            })
        return DataEnvelope(data=releases, source="mock", source_label="mock", confidence=0.5)
