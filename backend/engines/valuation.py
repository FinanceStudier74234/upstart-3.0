"""
Valuation Engine — Fair value estimation, peer comparison, historical percentiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValuationSnapshot:
    """Complete valuation profile."""
    # Core multiples
    price_to_sales: float | None = None
    ev_revenue: float | None = None
    ev_ebitda: float | None = None
    price_to_book: float | None = None
    price_to_earnings: float | None = None

    # Historical context
    ps_median_3y: float | None = None
    ps_percentile: float | None = None  # where current P/S sits vs 3y range
    ev_rev_percentile: float | None = None

    # Growth-adjusted
    growth_rate: float | None = None  # revenue YoY %
    peg_like_ratio: float | None = None  # P/S / growth
    fcf_yield: float | None = None

    # Fair value scenarios
    fair_value_bull: float | None = None
    fair_value_base: float | None = None
    fair_value_bear: float | None = None
    upside_to_fair: float | None = None  # % from current to base fair value

    # Peer comparison
    peer_multiples: list[dict] = field(default_factory=list)
    vs_peer_median: float | None = None  # premium/discount %

    # DCF simplified
    dcf_value: float | None = None
    wacc: float = 0.12

    # Score
    valuation_attractiveness_score: float = 50.0


class ValuationEngine:
    """Estimates fair value through multiple methods."""

    def analyze(
        self,
        fundamentals: dict | None = None,
        price: float = 0.0,
        market_cap: float | None = None,
    ) -> ValuationSnapshot:
        snap = ValuationSnapshot()
        if not fundamentals:
            fundamentals = self._default_fundamentals()

        revenue = fundamentals.get("revenue_ttm", 600_000_000)
        ebitda = fundamentals.get("ebitda_ttm", 50_000_000)
        shares = fundamentals.get("shares_outstanding", 87_000_000)
        book_value = fundamentals.get("book_value", 1_500_000_000)
        fcf = fundamentals.get("fcf_ttm", 30_000_000)
        growth = fundamentals.get("revenue_growth_yoy", 0.25)

        if not market_cap and price > 0 and shares > 0:
            market_cap = price * shares

        ev = (market_cap or 0) + fundamentals.get("net_debt", 0)

        # Core multiples
        if revenue > 0:
            snap.price_to_sales = round((market_cap or 0) / revenue, 2)
            snap.ev_revenue = round(ev / revenue, 2)
        if ebitda > 0:
            snap.ev_ebitda = round(ev / ebitda, 2)
        if book_value > 0:
            snap.price_to_book = round((market_cap or 0) / book_value, 2)
        if shares > 0 and fundamentals.get("net_income_ttm", 0) > 0:
            eps = fundamentals["net_income_ttm"] / shares
            snap.price_to_earnings = round(price / eps, 2) if eps > 0 else None

        # Historical context
        snap.ps_median_3y = fundamentals.get("ps_median_3y", 8.0)
        if snap.price_to_sales and snap.ps_median_3y:
            ps_min = fundamentals.get("ps_min_3y", 2.0)
            ps_max = fundamentals.get("ps_max_3y", 15.0)
            rng = ps_max - ps_min
            snap.ps_percentile = round((snap.price_to_sales - ps_min) / rng * 100, 1) if rng > 0 else 50.0

        # Growth-adjusted
        snap.growth_rate = round(growth * 100, 1)
        if snap.price_to_sales and growth > 0:
            snap.peg_like_ratio = round(snap.price_to_sales / (growth * 100), 2)
        if market_cap and market_cap > 0:
            snap.fcf_yield = round(fcf / market_cap * 100, 2)

        # Fair value scenarios
        rev_next = revenue * (1 + growth)
        snap.fair_value_bull = round(rev_next * 10 / shares, 2) if shares else None  # 10x P/S
        snap.fair_value_base = round(rev_next * 7 / shares, 2) if shares else None   # 7x P/S
        snap.fair_value_bear = round(rev_next * 4 / shares, 2) if shares else None   # 4x P/S

        if snap.fair_value_base and price > 0:
            snap.upside_to_fair = round((snap.fair_value_base - price) / price * 100, 1)

        # Peer comparison
        snap.peer_multiples = self._peer_multiples()
        peer_ps = [p["ps"] for p in snap.peer_multiples if p.get("ps")]
        if peer_ps and snap.price_to_sales:
            median_ps = sorted(peer_ps)[len(peer_ps) // 2]
            snap.vs_peer_median = round((snap.price_to_sales / median_ps - 1) * 100, 1)

        # Simplified DCF
        snap.dcf_value = self._simple_dcf(fcf, growth, snap.wacc, shares)

        # Score
        snap.valuation_attractiveness_score = self._compute_score(snap, price)

        return snap

    def _default_fundamentals(self) -> dict:
        return {
            "revenue_ttm": 600_000_000,
            "ebitda_ttm": 50_000_000,
            "net_income_ttm": -20_000_000,
            "fcf_ttm": 30_000_000,
            "shares_outstanding": 87_000_000,
            "book_value": 1_500_000_000,
            "net_debt": -400_000_000,
            "revenue_growth_yoy": 0.25,
            "ps_median_3y": 8.0,
            "ps_min_3y": 2.0,
            "ps_max_3y": 15.0,
        }

    def _peer_multiples(self) -> list[dict]:
        return [
            {"ticker": "SOFI", "ps": 4.5, "ev_rev": 5.0},
            {"ticker": "LC", "ps": 2.0, "ev_rev": 2.5},
            {"ticker": "AFRM", "ps": 7.0, "ev_rev": 7.5},
            {"ticker": "HOOD", "ps": 6.0, "ev_rev": 6.5},
            {"ticker": "PYPL", "ps": 3.0, "ev_rev": 3.2},
            {"ticker": "MQ", "ps": 3.5, "ev_rev": 4.0},
            {"ticker": "LPRO", "ps": 1.5, "ev_rev": 2.0},
        ]

    def _simple_dcf(self, fcf: float, growth: float, wacc: float, shares: int) -> float | None:
        if shares <= 0 or fcf <= 0:
            return None
        total = 0.0
        cf = fcf
        for year in range(1, 11):
            g = growth if year <= 5 else growth * 0.5
            cf *= (1 + g)
            total += cf / (1 + wacc) ** year
        terminal = cf * (1 + 0.03) / (wacc - 0.03)
        total += terminal / (1 + wacc) ** 10
        return round(total / shares, 2)

    def _compute_score(self, snap: ValuationSnapshot, price: float) -> float:
        score = 50.0
        if snap.upside_to_fair is not None:
            score += min(25, max(-25, snap.upside_to_fair * 0.5))
        if snap.ps_percentile is not None:
            score += (50 - snap.ps_percentile) * 0.2
        if snap.vs_peer_median is not None:
            score -= snap.vs_peer_median * 0.15
        if snap.fcf_yield is not None:
            score += snap.fcf_yield * 2
        return round(max(0, min(100, score)), 2)
