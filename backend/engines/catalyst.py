"""
Catalyst / Event Analytics Engine — Earnings, product launches,
regulatory events, macro catalysts, and their expected impact.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class Catalyst:
    name: str
    date: str  # ISO date or "TBD"
    category: str  # earnings | product | regulatory | macro | funding | partnership
    expected_impact: str  # bullish | bearish | neutral | uncertain
    magnitude: str  # low | medium | high | extreme
    probability: float = 0.5  # 0-1
    description: str = ""
    historical_reaction: float | None = None  # avg % move on similar events


@dataclass
class CatalystSnapshot:
    """Upcoming and recent catalysts."""
    upcoming: list[Catalyst] = field(default_factory=list)
    recent: list[Catalyst] = field(default_factory=list)

    # Earnings
    next_earnings_date: str | None = None
    days_to_earnings: int | None = None
    earnings_expected_move: float | None = None  # % implied by options
    earnings_beat_streak: int = 0
    historical_earnings_reaction: float | None = None  # avg absolute move

    # Catalyst density
    catalysts_next_30d: int = 0
    catalyst_density_score: float = 50.0  # high = many catalysts coming

    # Net catalyst sentiment
    net_catalyst_sentiment: float = 0.0  # -100 to +100
    dominant_catalyst_type: str = ""

    # Binary event risk
    binary_event_risk: float = 0.0  # 0-100, high = large move likely


class CatalystEngine:
    """Tracks and assesses upcoming catalysts."""

    def analyze(self, events: dict | None = None) -> CatalystSnapshot:
        snap = CatalystSnapshot()

        if not events:
            events = self._default_events()

        today = dt.date.today()

        for evt in events.get("upcoming", []):
            cat = Catalyst(**{k: v for k, v in evt.items() if k in Catalyst.__dataclass_fields__})
            snap.upcoming.append(cat)
            try:
                evt_date = dt.date.fromisoformat(cat.date)
                if (evt_date - today).days <= 30:
                    snap.catalysts_next_30d += 1
            except (ValueError, TypeError):
                pass

        for evt in events.get("recent", []):
            cat = Catalyst(**{k: v for k, v in evt.items() if k in Catalyst.__dataclass_fields__})
            snap.recent.append(cat)

        # Earnings
        snap.next_earnings_date = events.get("next_earnings_date", "2026-05-06")
        if snap.next_earnings_date:
            try:
                earn_date = dt.date.fromisoformat(snap.next_earnings_date)
                snap.days_to_earnings = (earn_date - today).days
            except (ValueError, TypeError):
                pass
        snap.earnings_expected_move = events.get("earnings_expected_move", 15.0)
        snap.earnings_beat_streak = events.get("earnings_beat_streak", 4)
        snap.historical_earnings_reaction = events.get("historical_earnings_reaction", 18.0)

        # Sentiment
        bullish = sum(1 for c in snap.upcoming if c.expected_impact == "bullish")
        bearish = sum(1 for c in snap.upcoming if c.expected_impact == "bearish")
        total = len(snap.upcoming) or 1
        snap.net_catalyst_sentiment = round((bullish - bearish) / total * 100, 1)

        # Dominant type
        categories = [c.category for c in snap.upcoming]
        if categories:
            snap.dominant_catalyst_type = max(set(categories), key=categories.count)

        # Density score
        snap.catalyst_density_score = min(100, snap.catalysts_next_30d * 15)

        # Binary event risk
        snap.binary_event_risk = self._binary_risk(snap)

        return snap

    def _binary_risk(self, snap: CatalystSnapshot) -> float:
        risk = 20.0
        if snap.days_to_earnings is not None and snap.days_to_earnings <= 14:
            risk += 30
        high_impact = sum(1 for c in snap.upcoming if c.magnitude in ("high", "extreme"))
        risk += high_impact * 10
        if snap.earnings_expected_move and snap.earnings_expected_move > 15:
            risk += 10
        return round(min(100, risk), 1)

    def _default_events(self) -> dict:
        return {
            "next_earnings_date": "2026-05-06",
            "earnings_expected_move": 15.0,
            "earnings_beat_streak": 4,
            "historical_earnings_reaction": 18.0,
            "upcoming": [
                {"name": "Q1 2026 Earnings", "date": "2026-05-06", "category": "earnings",
                 "expected_impact": "uncertain", "magnitude": "extreme", "probability": 1.0,
                 "description": "Revenue and origination volume guidance key"},
                {"name": "Auto Lending Expansion", "date": "2026-04-15", "category": "product",
                 "expected_impact": "bullish", "magnitude": "medium", "probability": 0.7,
                 "description": "Expected new auto lending partnerships"},
                {"name": "Fed Meeting", "date": "2026-03-26", "category": "macro",
                 "expected_impact": "uncertain", "magnitude": "medium", "probability": 1.0,
                 "description": "Rate decision — hold expected"},
                {"name": "ABS Deal", "date": "2026-04-01", "category": "funding",
                 "expected_impact": "bullish", "magnitude": "medium", "probability": 0.8,
                 "description": "Next securitization expected"},
                {"name": "CFPB Ruling", "date": "TBD", "category": "regulatory",
                 "expected_impact": "uncertain", "magnitude": "high", "probability": 0.4,
                 "description": "Potential AI lending regulations"},
            ],
            "recent": [
                {"name": "Q4 2025 Earnings Beat", "date": "2026-02-11", "category": "earnings",
                 "expected_impact": "bullish", "magnitude": "high", "probability": 1.0,
                 "description": "Beat on revenue and origination, raised guidance"},
                {"name": "HELOC Launch", "date": "2026-01-20", "category": "product",
                 "expected_impact": "bullish", "magnitude": "medium", "probability": 1.0,
                 "description": "Home equity product launched in 5 states"},
            ],
        }
