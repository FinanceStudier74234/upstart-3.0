"""
News Intelligence Engine — Extends base news analysis with deep intelligence
features including CEO tracking, investor relations, social sentiment,
and market narrative analysis for UPST.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from backend.engines.news import NewsEngine, NewsItem, NewsSnapshot


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NewsIntelligenceItem:
    """Extended news item with richer metadata."""
    headline: str
    summary: str = ""
    source: str = "unknown"
    source_type: str = "news"  # news | social | ir | ceo | sec | analyst
    published: str = ""
    url: str = ""
    sentiment: float = 0.0  # -1 to +1
    relevance: float = 0.5
    category: str = "general"
    flags: dict = field(default_factory=dict)
    upst_transmission_score: float = 0.0  # how much this affects UPST specifically, -1 to +1
    confidence: float = 0.5


@dataclass
class CEOInsight:
    """Insight derived from CEO public activity and statements."""
    name: str = "Dave Girouard"
    recent_statements: list[str] = field(default_factory=list)
    sentiment: float = 0.0
    tone: str = "neutral"  # optimistic | cautious | neutral | defensive | aggressive
    topics: list[str] = field(default_factory=list)
    activity_level: str = "normal"  # high | normal | low | silent
    last_active: str = ""


@dataclass
class InvestorRelationsInsight:
    """Insight from investor relations releases and activity."""
    recent_releases: list[dict] = field(default_factory=list)
    release_frequency: str = "normal"  # high | normal | low
    themes: list[str] = field(default_factory=list)
    guidance_sentiment: float = 0.0
    capital_markets_activity: bool = False
    partnership_news: bool = False
    product_launches: list[str] = field(default_factory=list)


@dataclass
class SocialSentimentInsight:
    """Social media / retail investor sentiment analysis."""
    platforms: dict = field(default_factory=dict)  # platform_name -> sentiment_score
    retail_sentiment: float = 0.0
    retail_sentiment_label: str = "neutral"
    trending: bool = False
    mention_volume: str = "normal"  # high | normal | low
    top_topics: list[str] = field(default_factory=list)
    bull_bear_ratio: float = 1.0


@dataclass
class MarketNarrativeInsight:
    """The prevailing market narrative around UPST."""
    dominant_narrative: str = "neutral"
    narrative_shift: bool = False
    narrative_strength: float = 0.5
    competing_narratives: list[str] = field(default_factory=list)
    catalyst_proximity: str = "none"  # near | medium | far | none
    upcoming_catalysts: list[dict] = field(default_factory=list)


@dataclass
class NewsIntelligenceSnapshot:
    """Full news intelligence output combining all analysis layers."""
    timestamp: str = ""
    ticker: str = "UPST"

    # Base news analysis from NewsEngine
    base_news: NewsSnapshot = field(default_factory=NewsSnapshot)

    # Extended articles
    articles: list[NewsIntelligenceItem] = field(default_factory=list)
    total_article_count: int = 0
    source_breakdown: dict = field(default_factory=dict)  # source_type -> count

    # Intelligence layers
    ceo_insight: CEOInsight = field(default_factory=CEOInsight)
    ir_insight: InvestorRelationsInsight = field(default_factory=InvestorRelationsInsight)
    social_sentiment: SocialSentimentInsight = field(default_factory=SocialSentimentInsight)
    market_narrative: MarketNarrativeInsight = field(default_factory=MarketNarrativeInsight)

    # Aggregations
    category_breakdown: dict = field(default_factory=dict)  # category -> {count, avg_sentiment}
    key_headlines: list[str] = field(default_factory=list)  # top 5 most relevant headlines

    # Signals
    risk_summary: dict = field(default_factory=dict)
    opportunity_signals: list[str] = field(default_factory=list)
    threat_signals: list[str] = field(default_factory=list)

    # Master score
    news_intelligence_score: float = 50.0  # 0-100

    # Analyst commentary
    analysis_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Keywords used for classification
# ---------------------------------------------------------------------------

_OPTIMISTIC_WORDS = {
    "excited", "record", "growth", "momentum", "confident", "strong",
    "accelerating", "opportunity", "thrilled", "optimistic", "beat",
    "exceeded", "outperformed", "raised", "expanding",
}
_CAUTIOUS_WORDS = {
    "cautious", "prudent", "careful", "measured", "uncertain", "monitoring",
    "watching", "evaluating",
}
_DEFENSIVE_WORDS = {
    "challenge", "headwind", "difficult", "pressure", "tough", "defend",
    "navigating", "volatile", "risk",
}
_AGGRESSIVE_WORDS = {
    "disrupt", "dominate", "aggressive", "bold", "transform", "revolutionize",
    "massive", "game-changer",
}

_CAPITAL_MARKETS_KEYWORDS = {
    "abs", "warehouse", "securitization", "facility", "bond", "offering",
    "capital markets", "debt", "credit facility",
}

_CATALYST_KEYWORDS = {
    "earnings", "guidance", "conference", "investor day", "announcement",
    "launch", "release", "filing", "report", "fda", "ruling", "vote",
    "deadline", "approval",
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class NewsIntelligenceEngine:
    """Deep news intelligence engine that layers CEO, IR, social, and
    narrative analysis on top of the base NewsEngine."""

    def __init__(self) -> None:
        self._base_engine = NewsEngine()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def analyze(
        self,
        news_data: list[dict] | None = None,
        ir_data: list[dict] | None = None,
        social_data: list[dict] | None = None,
        ceo_data: list[dict] | None = None,
    ) -> NewsIntelligenceSnapshot:
        """Run full news intelligence analysis pipeline."""

        snap = NewsIntelligenceSnapshot(
            timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        )

        # 1. Base news analysis
        if not news_data:
            news_data = self._default_news()
        snap.base_news = self._base_engine.analyze(news_data)

        # 2. Build extended article list from ALL sources
        all_raw: list[dict] = []
        for item in news_data:
            item.setdefault("source_type", "news")
            all_raw.append(item)
        for item in (ir_data or self._default_ir()):
            item.setdefault("source_type", "ir")
            all_raw.append(item)
        for item in (social_data or self._default_social()):
            item.setdefault("source_type", "social")
            all_raw.append(item)
        for item in (ceo_data or self._default_ceo()):
            item.setdefault("source_type", "ceo")
            all_raw.append(item)

        articles: list[NewsIntelligenceItem] = []
        for item in all_raw:
            articles.append(NewsIntelligenceItem(
                headline=item.get("headline", ""),
                summary=item.get("summary", ""),
                source=item.get("source", "unknown"),
                source_type=item.get("source_type", "news"),
                published=item.get("published", ""),
                url=item.get("url", ""),
                sentiment=item.get("sentiment", 0.0),
                relevance=item.get("relevance", 0.5),
                category=item.get("category", "general"),
                flags=item.get("flags", {}),
                upst_transmission_score=item.get("upst_transmission_score", 0.0),
                confidence=item.get("confidence", 0.5),
            ))

        snap.articles = articles
        snap.total_article_count = len(articles)

        # Source breakdown
        breakdown: dict[str, int] = {}
        for a in articles:
            breakdown[a.source_type] = breakdown.get(a.source_type, 0) + 1
        snap.source_breakdown = breakdown

        # 3. CEO insight
        snap.ceo_insight = self._analyze_ceo(ceo_data)

        # 4. IR insight
        snap.ir_insight = self._analyze_ir(ir_data)

        # 5. Social sentiment
        snap.social_sentiment = self._analyze_social(social_data)

        # 6. Market narrative
        snap.market_narrative = self._build_narrative(
            articles, snap.ceo_insight, snap.ir_insight, snap.social_sentiment,
        )

        # 7. Category breakdown across ALL sources
        cat_map: dict[str, list[float]] = {}
        for a in articles:
            cat_map.setdefault(a.category, []).append(a.sentiment)
        snap.category_breakdown = {
            cat: {
                "count": len(sents),
                "avg_sentiment": round(sum(sents) / len(sents), 4),
            }
            for cat, sents in cat_map.items()
        }

        # 8. Key headlines — top 5 by relevance * |sentiment|
        scored = sorted(
            articles,
            key=lambda a: a.relevance * abs(a.sentiment),
            reverse=True,
        )
        snap.key_headlines = [a.headline for a in scored[:5]]

        # 9. Risk and opportunity signals
        snap.risk_summary, snap.threat_signals = self._identify_risks(snap)
        snap.opportunity_signals = self._identify_opportunities(snap)

        # 10. Master intelligence score
        snap.news_intelligence_score = self._compute_intelligence_score(snap)

        # 11. Analysis notes
        snap.analysis_notes = self._generate_analysis_notes(snap)

        return snap

    # ------------------------------------------------------------------
    # Private analysis helpers
    # ------------------------------------------------------------------

    def _analyze_ceo(self, ceo_data: list[dict] | None) -> CEOInsight:
        data = ceo_data or self._default_ceo()
        insight = CEOInsight()

        if not data:
            insight.activity_level = "silent"
            return insight

        # Extract statements
        insight.recent_statements = [
            d.get("headline", d.get("summary", "")) for d in data if d.get("headline") or d.get("summary")
        ]

        # Sentiment — average across items
        sentiments = [d.get("sentiment", 0.0) for d in data]
        insight.sentiment = round(sum(sentiments) / len(sentiments), 4) if sentiments else 0.0

        # Tone — keyword analysis on combined text
        combined = " ".join(s.lower() for s in insight.recent_statements)
        tone_scores: dict[str, int] = {
            "optimistic": sum(1 for w in _OPTIMISTIC_WORDS if w in combined),
            "cautious": sum(1 for w in _CAUTIOUS_WORDS if w in combined),
            "defensive": sum(1 for w in _DEFENSIVE_WORDS if w in combined),
            "aggressive": sum(1 for w in _AGGRESSIVE_WORDS if w in combined),
        }
        best_tone = max(tone_scores, key=tone_scores.get)  # type: ignore[arg-type]
        insight.tone = best_tone if tone_scores[best_tone] > 0 else "neutral"

        # Topics — unique categories mentioned
        insight.topics = list({d.get("category", "general") for d in data})

        # Activity level
        count = len(data)
        if count >= 5:
            insight.activity_level = "high"
        elif count >= 2:
            insight.activity_level = "normal"
        elif count >= 1:
            insight.activity_level = "low"
        else:
            insight.activity_level = "silent"

        # Last active
        dates = [d.get("published", "") for d in data if d.get("published")]
        if dates:
            insight.last_active = max(dates)

        return insight

    def _analyze_ir(self, ir_data: list[dict] | None) -> InvestorRelationsInsight:
        data = ir_data or self._default_ir()
        insight = InvestorRelationsInsight()

        if not data:
            insight.release_frequency = "low"
            return insight

        insight.recent_releases = data

        # Release frequency
        count = len(data)
        if count >= 5:
            insight.release_frequency = "high"
        elif count >= 2:
            insight.release_frequency = "normal"
        else:
            insight.release_frequency = "low"

        # Themes
        themes: set[str] = set()
        for d in data:
            cat = d.get("category", "")
            if cat:
                themes.add(cat)
            headline_lower = d.get("headline", "").lower()
            if any(kw in headline_lower for kw in ("partner", "collaboration", "alliance")):
                themes.add("partnerships")
            if any(kw in headline_lower for kw in ("launch", "product", "feature", "release")):
                themes.add("products")
        insight.themes = sorted(themes)

        # Guidance sentiment
        guidance_items = [
            d for d in data
            if any(kw in d.get("headline", "").lower() for kw in ("guidance", "outlook", "forecast", "raises", "raised"))
        ]
        if guidance_items:
            sents = [d.get("sentiment", 0.0) for d in guidance_items]
            insight.guidance_sentiment = round(sum(sents) / len(sents), 4)

        # Capital markets activity
        for d in data:
            text = (d.get("headline", "") + " " + d.get("summary", "")).lower()
            if any(kw in text for kw in _CAPITAL_MARKETS_KEYWORDS):
                insight.capital_markets_activity = True
                break

        # Partnership news
        for d in data:
            text = d.get("headline", "").lower()
            if any(kw in text for kw in ("partner", "collaboration", "alliance", "agreement")):
                insight.partnership_news = True
                break

        # Product launches
        for d in data:
            headline = d.get("headline", "")
            if any(kw in headline.lower() for kw in ("launch", "new product", "introduces", "rolls out")):
                insight.product_launches.append(headline)

        return insight

    def _analyze_social(self, social_data: list[dict] | None) -> SocialSentimentInsight:
        data = social_data or self._default_social()
        insight = SocialSentimentInsight()

        if not data:
            return insight

        # Platform breakdown
        platform_sents: dict[str, list[float]] = {}
        for d in data:
            platform = d.get("source", "unknown")
            platform_sents.setdefault(platform, []).append(d.get("sentiment", 0.0))

        insight.platforms = {
            p: round(sum(s) / len(s), 4) for p, s in platform_sents.items()
        }

        # Retail sentiment — average across all social items
        all_sents = [d.get("sentiment", 0.0) for d in data]
        insight.retail_sentiment = round(sum(all_sents) / len(all_sents), 4) if all_sents else 0.0

        # Retail sentiment label
        rs = insight.retail_sentiment
        if rs > 0.3:
            insight.retail_sentiment_label = "very_bullish"
        elif rs > 0.1:
            insight.retail_sentiment_label = "bullish"
        elif rs < -0.3:
            insight.retail_sentiment_label = "very_bearish"
        elif rs < -0.1:
            insight.retail_sentiment_label = "bearish"
        else:
            insight.retail_sentiment_label = "neutral"

        # Trending — high volume
        if len(data) >= 8:
            insight.trending = True
            insight.mention_volume = "high"
        elif len(data) >= 3:
            insight.mention_volume = "normal"
        else:
            insight.mention_volume = "low"

        # Top topics from categories
        topic_counts: dict[str, int] = {}
        for d in data:
            cat = d.get("category", "general")
            topic_counts[cat] = topic_counts.get(cat, 0) + 1
        insight.top_topics = sorted(topic_counts, key=topic_counts.get, reverse=True)[:5]  # type: ignore[arg-type]

        # Bull/bear ratio
        bulls = sum(1 for s in all_sents if s > 0.05)
        bears = sum(1 for s in all_sents if s < -0.05)
        insight.bull_bear_ratio = round(bulls / max(bears, 1), 2)

        return insight

    def _build_narrative(
        self,
        all_articles: list[NewsIntelligenceItem],
        ceo: CEOInsight,
        ir: InvestorRelationsInsight,
        social: SocialSentimentInsight,
    ) -> MarketNarrativeInsight:
        narrative = MarketNarrativeInsight()

        if not all_articles:
            return narrative

        # Dominant narrative — most frequent category weighted by relevance
        cat_weight: dict[str, float] = {}
        for a in all_articles:
            cat_weight[a.category] = cat_weight.get(a.category, 0.0) + a.relevance

        if cat_weight:
            dominant_cat = max(cat_weight, key=cat_weight.get)  # type: ignore[arg-type]
            # Translate category into narrative label
            avg_sent = sum(a.sentiment for a in all_articles) / len(all_articles)
            if avg_sent > 0.2:
                narrative.dominant_narrative = f"bullish_{dominant_cat}"
            elif avg_sent < -0.2:
                narrative.dominant_narrative = f"bearish_{dominant_cat}"
            else:
                narrative.dominant_narrative = f"mixed_{dominant_cat}"

        # Narrative strength — how consistent are sentiments
        sents = [a.sentiment for a in all_articles]
        if sents:
            mean = sum(sents) / len(sents)
            variance = sum((s - mean) ** 2 for s in sents) / len(sents)
            # Low variance = strong narrative, high variance = weak
            narrative.narrative_strength = round(max(0.0, min(1.0, 1.0 - variance)), 4)

        # Narrative shift — compare first-half vs second-half sentiment
        if len(all_articles) >= 4:
            mid = len(all_articles) // 2
            first_avg = sum(a.sentiment for a in all_articles[:mid]) / mid
            second_avg = sum(a.sentiment for a in all_articles[mid:]) / (len(all_articles) - mid)
            if abs(second_avg - first_avg) > 0.15:
                narrative.narrative_shift = True

        # Competing narratives — other top categories
        if cat_weight:
            sorted_cats = sorted(cat_weight, key=cat_weight.get, reverse=True)  # type: ignore[arg-type]
            narrative.competing_narratives = sorted_cats[1:4]

        # Upcoming catalysts — articles mentioning future events
        for a in all_articles:
            text = (a.headline + " " + a.summary).lower()
            if any(kw in text for kw in _CATALYST_KEYWORDS):
                catalyst_entry = {
                    "headline": a.headline,
                    "category": a.category,
                    "sentiment": a.sentiment,
                }
                narrative.upcoming_catalysts.append(catalyst_entry)

        # Catalyst proximity
        if narrative.upcoming_catalysts:
            count = len(narrative.upcoming_catalysts)
            if count >= 3:
                narrative.catalyst_proximity = "near"
            elif count >= 1:
                narrative.catalyst_proximity = "medium"
            else:
                narrative.catalyst_proximity = "far"
        else:
            narrative.catalyst_proximity = "none"

        return narrative

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_intelligence_score(self, snap: NewsIntelligenceSnapshot) -> float:
        """Weighted master intelligence score (0-100)."""

        # Base news sentiment score: 30%
        base_component = snap.base_news.news_sentiment_score * 0.30

        # CEO tone score: 15%
        ceo_tone_map = {
            "optimistic": 70,
            "aggressive": 65,
            "neutral": 50,
            "cautious": 35,
            "defensive": 25,
        }
        ceo_score = ceo_tone_map.get(snap.ceo_insight.tone, 50)
        ceo_component = ceo_score * 0.15

        # IR activity score: 15%
        ir_freq_map = {"high": 65, "normal": 50, "low": 35}
        ir_score = ir_freq_map.get(snap.ir_insight.release_frequency, 50)
        if snap.ir_insight.guidance_sentiment > 0.1:
            ir_score += 15
        elif snap.ir_insight.guidance_sentiment < -0.1:
            ir_score -= 15
        if snap.ir_insight.capital_markets_activity:
            ir_score += 5
        ir_score = max(0, min(100, ir_score))
        ir_component = ir_score * 0.15

        # Social sentiment score: 15%
        social_score = 50.0 + snap.social_sentiment.retail_sentiment * 30
        social_score = max(0, min(100, social_score))
        social_component = social_score * 0.15

        # Narrative strength: 10%
        narrative_score = snap.market_narrative.narrative_strength * 100
        if "bullish" in snap.market_narrative.dominant_narrative:
            narrative_score = min(100, narrative_score + 15)
        elif "bearish" in snap.market_narrative.dominant_narrative:
            narrative_score = max(0, narrative_score - 15)
        narrative_component = narrative_score * 0.10

        # Base total before adjustments
        score = base_component + ceo_component + ir_component + social_component + narrative_component

        # Normalize to approximate 0-100 range (components sum weights = 0.85 * ~50 = ~42.5 baseline)
        # The individual scores are already 0-100 and weights sum to 0.85, so max is 85.
        # Scale up so that neutral = ~50
        score = score / 0.85  # re-normalize to 0-100 range

        # Risk penalty: -15% for each major risk flag
        risk_flags = [
            snap.base_news.policy_risk,
            snap.base_news.world_risk,
            snap.base_news.regulatory_risk,
            snap.base_news.negative_funding_news,
        ]
        for flag in risk_flags:
            if flag:
                score -= 15

        # Opportunity bonus: +5% for each opportunity signal
        score += len(snap.opportunity_signals) * 5

        return round(max(0.0, min(100.0, score)), 2)

    # ------------------------------------------------------------------
    # Signal identification
    # ------------------------------------------------------------------

    def _identify_risks(self, snap: NewsIntelligenceSnapshot) -> tuple[dict, list[str]]:
        risk_summary: dict[str, bool] = {}
        threats: list[str] = []

        # Propagate base news risks
        if snap.base_news.policy_risk:
            risk_summary["policy_risk"] = True
            threats.append("Policy/regulatory headwinds detected in news flow")
        if snap.base_news.world_risk:
            risk_summary["world_risk"] = True
            threats.append("Geopolitical or macro risk events in headlines")
        if snap.base_news.regulatory_risk:
            risk_summary["regulatory_risk"] = True
            threats.append("Regulatory scrutiny flagged in recent articles")
        if snap.base_news.negative_funding_news:
            risk_summary["negative_funding"] = True
            threats.append("Negative funding/credit market signals")

        # CEO defensiveness
        if snap.ceo_insight.tone == "defensive":
            risk_summary["ceo_defensive"] = True
            threats.append("CEO tone appears defensive — potential undisclosed headwinds")

        # Bearish social
        if snap.social_sentiment.retail_sentiment < -0.2:
            risk_summary["retail_bearish"] = True
            threats.append("Retail investor sentiment skewing bearish")

        # Narrative shift
        if snap.market_narrative.narrative_shift:
            risk_summary["narrative_shift"] = True
            threats.append("Market narrative has shifted recently — increased uncertainty")

        return risk_summary, threats

    def _identify_opportunities(self, snap: NewsIntelligenceSnapshot) -> list[str]:
        opportunities: list[str] = []

        if snap.base_news.positive_funding_news:
            opportunities.append("Positive funding/capital markets activity")
        if snap.ceo_insight.tone == "optimistic":
            opportunities.append("CEO tone is optimistic — positive forward outlook")
        if snap.ir_insight.capital_markets_activity:
            opportunities.append("Active capital markets engagement (ABS/warehouse)")
        if snap.ir_insight.product_launches:
            opportunities.append(f"New product launches: {', '.join(snap.ir_insight.product_launches[:3])}")
        if snap.social_sentiment.retail_sentiment > 0.2:
            opportunities.append("Strong bullish retail sentiment")
        if snap.social_sentiment.trending:
            opportunities.append("UPST trending on social platforms — elevated visibility")
        if snap.market_narrative.catalyst_proximity == "near":
            opportunities.append("Multiple near-term catalysts identified")
        if snap.base_news.sentiment_trend == "improving":
            opportunities.append("News sentiment trend is improving")

        return opportunities

    # ------------------------------------------------------------------
    # Analysis notes
    # ------------------------------------------------------------------

    def _generate_analysis_notes(self, snap: NewsIntelligenceSnapshot) -> list[str]:
        """Generate 3-5 concise analyst-style commentary bullets."""
        notes: list[str] = []

        # 1. Dominant sentiment and trend
        label = snap.base_news.sentiment_label.replace("_", " ")
        trend = snap.base_news.sentiment_trend
        notes.append(
            f"Overall news sentiment is {label} with a {trend} trend "
            f"(score: {snap.base_news.news_sentiment_score}/100)."
        )

        # 2. CEO activity / tone
        ceo = snap.ceo_insight
        if ceo.activity_level != "normal" or ceo.tone != "neutral":
            activity_desc = (
                f"CEO activity is {ceo.activity_level}"
                if ceo.activity_level != "normal"
                else "CEO activity is normal"
            )
            tone_desc = f"tone reads as {ceo.tone}"
            notes.append(f"{activity_desc}; {tone_desc}.")

        # 3. Risk signals
        if snap.threat_signals:
            notes.append(
                f"Risk flags ({len(snap.threat_signals)}): {snap.threat_signals[0]}"
                + (f" and {len(snap.threat_signals) - 1} more." if len(snap.threat_signals) > 1 else ".")
            )

        # 4. Social vs institutional divergence
        retail = snap.social_sentiment.retail_sentiment
        institutional = snap.base_news.avg_sentiment
        divergence = abs(retail - institutional)
        if divergence > 0.2:
            direction = "more bullish" if retail > institutional else "more bearish"
            notes.append(
                f"Retail sentiment ({retail:+.2f}) diverges from institutional news "
                f"sentiment ({institutional:+.2f}) — retail is {direction}."
            )

        # 5. Upcoming catalysts
        if snap.market_narrative.upcoming_catalysts:
            count = len(snap.market_narrative.upcoming_catalysts)
            notes.append(
                f"{count} potential catalyst(s) identified; "
                f"catalyst proximity rated '{snap.market_narrative.catalyst_proximity}'."
            )

        return notes[:5]

    # ------------------------------------------------------------------
    # Default / fallback data
    # ------------------------------------------------------------------

    def _default_news(self) -> list[dict]:
        """Fallback news data — delegates to base engine's defaults."""
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

    def _default_ceo(self) -> list[dict]:
        return [
            {"headline": "Dave Girouard: 'We are excited about the momentum in auto and HELOC'",
             "source": "Earnings Call", "published": "2026-02-11", "sentiment": 0.6,
             "relevance": 0.9, "category": "earnings",
             "summary": "CEO highlights strong growth and expanding product lines."},
            {"headline": "Girouard at fintech conference: 'AI lending is at an inflection point'",
             "source": "Conference", "published": "2026-03-03", "sentiment": 0.5,
             "relevance": 0.7, "category": "fintech",
             "summary": "CEO expresses confidence in AI-driven underwriting opportunity."},
            {"headline": "Upstart CEO on credit cycle: 'Our models are built to navigate uncertainty'",
             "source": "CNBC Interview", "published": "2026-03-14", "sentiment": 0.2,
             "relevance": 0.8, "category": "macro",
             "summary": "CEO strikes measured tone on macro headwinds while defending model resilience."},
        ]

    def _default_ir(self) -> list[dict]:
        return [
            {"headline": "Upstart announces $400M warehouse facility with Goldman Sachs",
             "source": "PR Newswire", "published": "2026-03-12", "sentiment": 0.6,
             "relevance": 0.9, "category": "funding",
             "summary": "New warehouse facility expands funding capacity for personal loans."},
            {"headline": "Upstart raises full-year 2026 revenue guidance to $800M+",
             "source": "Company IR", "published": "2026-02-11", "sentiment": 0.7,
             "relevance": 0.95, "category": "earnings",
             "summary": "Guidance raised above consensus following strong Q4 beat."},
            {"headline": "Upstart launches small-dollar loan product for credit unions",
             "source": "Company PR", "published": "2026-03-08", "sentiment": 0.4,
             "relevance": 0.7, "category": "fintech",
             "summary": "New product launch targeting underserved segment."},
        ]

    def _default_social(self) -> list[dict]:
        return [
            {"headline": "UPST short squeeze potential discussed on Reddit",
             "source": "Reddit", "published": "2026-03-16", "sentiment": 0.3,
             "relevance": 0.4, "category": "general"},
            {"headline": "$UPST momentum building, bullish setup on the daily chart",
             "source": "Twitter", "published": "2026-03-17", "sentiment": 0.4,
             "relevance": 0.3, "category": "general"},
            {"headline": "Upstart deep dive: is AI lending finally working?",
             "source": "YouTube", "published": "2026-03-15", "sentiment": 0.2,
             "relevance": 0.5, "category": "fintech"},
            {"headline": "UPST added to my fintech watchlist, strong Q4 numbers",
             "source": "StockTwits", "published": "2026-03-13", "sentiment": 0.5,
             "relevance": 0.3, "category": "earnings"},
            {"headline": "Worried about UPST exposure to rising delinquencies",
             "source": "Reddit", "published": "2026-03-18", "sentiment": -0.3,
             "relevance": 0.4, "category": "macro"},
        ]
