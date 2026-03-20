"""
News / Sentiment Analysis Engine — Processes news data into sentiment scores,
topic classification, and regime detection for UPST.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class NewsItem:
    headline: str
    source: str
    published: str
    sentiment: float = 0.0  # -1 to +1
    relevance: float = 0.5
    category: str = "general"  # earnings | funding | macro | fintech | regulatory | general
    flags: dict = field(default_factory=dict)


@dataclass
class NewsSnapshot:
    """News and sentiment analysis output."""
    # Articles
    articles: list[NewsItem] = field(default_factory=list)
    article_count: int = 0

    # Aggregate sentiment
    avg_sentiment: float = 0.0
    sentiment_label: str = "neutral"  # very_bearish | bearish | neutral | bullish | very_bullish
    sentiment_trend: str = "stable"  # improving | stable | deteriorating

    # Category breakdown
    earnings_sentiment: float = 0.0
    funding_sentiment: float = 0.0
    macro_sentiment: float = 0.0
    fintech_sentiment: float = 0.0

    # Risk flags
    policy_risk: bool = False
    world_risk: bool = False
    positive_funding_news: bool = False
    negative_funding_news: bool = False
    regulatory_risk: bool = False

    # Volume / intensity
    news_volume_ratio: float = 1.0  # vs 30d avg
    high_impact_count: int = 0

    # Score
    news_sentiment_score: float = 50.0  # 0-100


class NewsEngine:
    """Analyzes news data into sentiment regimes and scores."""

    def analyze(self, news_data: list[dict] | None = None) -> NewsSnapshot:
        snap = NewsSnapshot()

        if not news_data:
            news_data = self._default_news()

        articles = []
        for item in news_data:
            article = NewsItem(
                headline=item.get("headline", ""),
                source=item.get("source", "unknown"),
                published=item.get("published", ""),
                sentiment=item.get("sentiment", 0.0),
                relevance=item.get("relevance", 0.5),
                category=item.get("category", "general"),
                flags=item.get("flags", {}),
            )
            articles.append(article)

        snap.articles = articles
        snap.article_count = len(articles)

        if not articles:
            return snap

        # Weighted average sentiment (by relevance)
        total_weight = sum(a.relevance for a in articles) or 1
        snap.avg_sentiment = round(
            sum(a.sentiment * a.relevance for a in articles) / total_weight, 4
        )

        # Sentiment label
        if snap.avg_sentiment > 0.3:
            snap.sentiment_label = "very_bullish"
        elif snap.avg_sentiment > 0.1:
            snap.sentiment_label = "bullish"
        elif snap.avg_sentiment < -0.3:
            snap.sentiment_label = "very_bearish"
        elif snap.avg_sentiment < -0.1:
            snap.sentiment_label = "bearish"
        else:
            snap.sentiment_label = "neutral"

        # Category breakdowns
        for cat in ["earnings", "funding", "macro", "fintech"]:
            cat_articles = [a for a in articles if a.category == cat]
            if cat_articles:
                setattr(snap, f"{cat}_sentiment",
                        round(sum(a.sentiment for a in cat_articles) / len(cat_articles), 4))

        # Risk flags
        snap.policy_risk = any(a.flags.get("policy_risk") for a in articles)
        snap.world_risk = any(a.flags.get("world_risk") for a in articles)
        snap.positive_funding_news = any(
            a.category == "funding" and a.sentiment > 0.2 for a in articles)
        snap.negative_funding_news = any(
            a.category == "funding" and a.sentiment < -0.2 for a in articles)
        snap.regulatory_risk = any(a.category == "regulatory" for a in articles)

        # High impact articles
        snap.high_impact_count = sum(1 for a in articles if abs(a.sentiment) > 0.5 and a.relevance > 0.7)

        # Sentiment trend (compare first half vs second half)
        if len(articles) >= 4:
            mid = len(articles) // 2
            first_half = sum(a.sentiment for a in articles[:mid]) / mid
            second_half = sum(a.sentiment for a in articles[mid:]) / (len(articles) - mid)
            if second_half - first_half > 0.1:
                snap.sentiment_trend = "improving"
            elif second_half - first_half < -0.1:
                snap.sentiment_trend = "deteriorating"

        # Score
        snap.news_sentiment_score = self._compute_score(snap)

        return snap

    def _compute_score(self, snap: NewsSnapshot) -> float:
        score = 50.0 + snap.avg_sentiment * 30
        if snap.positive_funding_news:
            score += 5
        if snap.negative_funding_news:
            score -= 8
        if snap.policy_risk:
            score -= 5
        if snap.world_risk:
            score -= 5
        if snap.regulatory_risk:
            score -= 5
        if snap.sentiment_trend == "improving":
            score += 5
        elif snap.sentiment_trend == "deteriorating":
            score -= 5
        return round(max(0, min(100, score)), 2)

    def _default_news(self) -> list[dict]:
        return [
            {"headline": "Upstart beats Q4 revenue estimates, raises FY guidance",
             "source": "Reuters", "published": "2026-02-11", "sentiment": 0.7,
             "relevance": 0.95, "category": "earnings", "flags": {}},
            {"headline": "UPST expands auto lending to 5 new states",
             "source": "Bloomberg", "published": "2026-02-15", "sentiment": 0.5,
             "relevance": 0.8, "category": "funding", "flags": {}},
            {"headline": "Consumer delinquencies rise in January, credit tightening continues",
             "source": "WSJ", "published": "2026-03-01", "sentiment": -0.4,
             "relevance": 0.6, "category": "macro", "flags": {"policy_risk": True}},
            {"headline": "AI-powered lending under regulatory scrutiny ahead of CFPB review",
             "source": "FT", "published": "2026-03-05", "sentiment": -0.3,
             "relevance": 0.7, "category": "regulatory", "flags": {}},
            {"headline": "Fintech sector rally led by AI-native platforms",
             "source": "TechCrunch", "published": "2026-03-10", "sentiment": 0.4,
             "relevance": 0.5, "category": "fintech", "flags": {}},
            {"headline": "UPST closes new $400M warehouse facility with Goldman Sachs",
             "source": "SEC Filing", "published": "2026-03-12", "sentiment": 0.6,
             "relevance": 0.9, "category": "funding", "flags": {}},
            {"headline": "Fed signals patience on rate cuts, markets adjust expectations",
             "source": "CNBC", "published": "2026-03-15", "sentiment": -0.2,
             "relevance": 0.5, "category": "macro", "flags": {}},
            {"headline": "Upstart HELOC product gains traction, volumes up 40% MoM",
             "source": "Company PR", "published": "2026-03-18", "sentiment": 0.5,
             "relevance": 0.85, "category": "earnings", "flags": {}},
        ]
