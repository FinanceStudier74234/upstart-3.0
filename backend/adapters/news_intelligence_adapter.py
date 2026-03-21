"""Live news-intelligence adapter — fetches real news from multiple public web sources."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from html import unescape
from typing import Any
from urllib.parse import quote_plus

import httpx

from backend.adapters.base import BaseNewsAdapter, DataEnvelope

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/xml, text/html, */*"}
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_CACHE_TTL = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Keyword lists for sentiment / category scoring
# ---------------------------------------------------------------------------

_POSITIVE_KEYWORDS = [
    "beat", "beats", "exceeded", "exceeds", "surpass", "growth", "grew",
    "profit", "profitable", "upgrade", "upgraded", "outperform", "buy",
    "bullish", "strong", "record", "rally", "surge", "soar", "gain",
    "positive", "expansion", "raised", "raising", "approval", "approved",
    "partnership", "deal", "innovation", "milestone", "optimistic",
    "recovery", "rebound", "upside", "breakout", "momentum", "dividend",
]

_NEGATIVE_KEYWORDS = [
    "miss", "missed", "decline", "declined", "loss", "losses", "downgrade",
    "downgraded", "underperform", "sell", "bearish", "weak", "slump",
    "plunge", "drop", "fell", "negative", "contraction", "cut", "cuts",
    "layoff", "layoffs", "default", "delinquency", "delinquencies",
    "lawsuit", "investigation", "warning", "risk", "recession",
    "bankruptcy", "fraud", "probe", "shortfall", "disappointing",
]

_CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("earnings", ["earnings", "revenue", "eps", "quarter", "q1", "q2", "q3", "q4", "fiscal", "profit", "income"]),
    ("funding", ["funding", "raise", "capital", "ipo", "offering", "debt", "bond", "issuance"]),
    ("origination", ["origination", "loan", "lending", "underwriting", "approval rate", "conversion"]),
    ("macro", ["inflation", "gdp", "unemployment", "jobs", "payroll", "economic", "economy", "cpi", "ppi"]),
    ("fed", ["fed", "federal reserve", "fomc", "rate hike", "rate cut", "interest rate", "powell", "monetary"]),
    ("credit", ["credit", "fico", "delinquency", "charge-off", "default", "subprime", "credit score"]),
    ("fintech", ["fintech", "ai lending", "machine learning", "artificial intelligence", "automation", "platform"]),
    ("regulatory", ["sec", "regulation", "regulatory", "compliance", "cfpb", "enforcement", "filing"]),
    ("world", ["geopolitical", "war", "tariff", "trade", "global", "china", "europe", "emerging"]),
    ("peer", ["sofi", "lendingclub", "affirm", "prosper", "avant", "marlette", "oportun"]),
    ("leadership", ["ceo", "cfo", "executive", "appoint", "resign", "hire", "board", "director", "girouard"]),
    ("product", ["product", "launch", "feature", "auto loan", "heloc", "personal loan", "small business"]),
    ("partnership", ["partner", "partnership", "collaboration", "agreement", "alliance", "integration"]),
]


# ---------------------------------------------------------------------------
# Simple in-memory cache
# ---------------------------------------------------------------------------

class _SimpleCache:
    """Dict-based cache with per-key TTL."""

    def __init__(self, ttl: int = _CACHE_TTL) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)


_cache = _SimpleCache()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cache_key(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def _parse_rss_date(date_str: str) -> dt.datetime:
    """Best-effort parse of RSS date strings."""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return dt.datetime.strptime(date_str.strip(), fmt).replace(
                tzinfo=dt.timezone.utc
            ) if "%" not in fmt or "%z" not in fmt else dt.datetime.strptime(
                date_str.strip(), fmt
            ).astimezone(dt.timezone.utc)
        except (ValueError, TypeError):
            continue
    return dt.datetime.now(dt.timezone.utc)


def _parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    """Extract items/entries from RSS or Atom XML."""
    items: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS 2.0: <channel><item>…</item></channel>
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            items.append({"title": title, "link": link, "description": desc, "pubDate": pub})

    # Atom: <entry>…</entry>
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("atom:title", namespaces=ns) or entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        desc = (entry.findtext("{http://www.w3.org/2005/Atom}summary") or entry.findtext("{http://www.w3.org/2005/Atom}content") or "").strip()
        pub = (entry.findtext("{http://www.w3.org/2005/Atom}updated") or entry.findtext("{http://www.w3.org/2005/Atom}published") or "").strip()
        if title:
            items.append({"title": title, "link": link, "description": desc, "pubDate": pub})

    return items


def _headline_fingerprint(headline: str) -> str:
    """Normalised fingerprint for dedup."""
    h = re.sub(r"[^a-z0-9 ]", "", headline.lower())
    h = re.sub(r"\s+", " ", h).strip()
    return h


def _is_duplicate(h1: str, h2: str, threshold: float = 0.80) -> bool:
    return SequenceMatcher(None, _headline_fingerprint(h1), _headline_fingerprint(h2)).ratio() >= threshold


def _score_sentiment(headline: str, summary: str) -> float:
    """Keyword-based sentiment score in [-1.0, 1.0]."""
    text = f"{headline} {summary}".lower()
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def _classify_category(headline: str, summary: str) -> str:
    """Return the best-matching category for a news item."""
    text = f"{headline} {summary}".lower()
    best_cat = "general"
    best_score = 0
    for cat, keywords in _CATEGORY_PATTERNS:
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat


def _score_relevance(headline: str, ticker: str) -> float:
    """Score relevance to the ticker — higher when symbol/name appears directly."""
    text = headline.lower()
    ticker_lower = ticker.lower()
    score = 0.3  # baseline
    if ticker_lower in text:
        score += 0.4
    # Check for common company name references
    _TICKER_NAMES = {
        "upst": ["upstart"],
        "sofi": ["sofi"],
        "lc": ["lendingclub", "lending club"],
        "afrm": ["affirm"],
    }
    names = _TICKER_NAMES.get(ticker_lower, [])
    for name in names:
        if name in text:
            score += 0.25
            break
    return min(round(score, 2), 1.0)


def _deduplicate_articles(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles based on headline similarity."""
    unique: list[dict] = []
    for article in articles:
        is_dup = False
        for existing in unique:
            if _is_duplicate(article.get("headline", ""), existing.get("headline", "")):
                is_dup = True
                break
        if not is_dup:
            unique.append(article)
    return unique


# ---------------------------------------------------------------------------
# 1. NewsIntelligenceAdapter
# ---------------------------------------------------------------------------

class NewsIntelligenceAdapter(BaseNewsAdapter):
    """Fetches real news from multiple public RSS / web sources."""

    def __init__(self) -> None:
        self._sources = [
            {
                "name": "yahoo_finance",
                "url_template": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
                "parser": self._parse_generic_rss,
            },
            {
                "name": "google_news",
                "url_template": "https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en",
                "parser": self._parse_generic_rss,
            },
            {
                "name": "sec_edgar",
                "url_template": "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start}&enddt={end}&forms=10-K,10-Q,8-K",
                "parser": self._parse_edgar_rss,
            },
            {
                "name": "marketwatch",
                "url_template": "https://www.marketwatch.com/search?q={ticker}&m=Keyword&rpp=20&mp=0&bd=false&rs=true",
                "parser": self._parse_generic_rss,
            },
            {
                "name": "seeking_alpha",
                "url_template": "https://seekingalpha.com/api/sa/combined/{ticker}.xml",
                "parser": self._parse_generic_rss,
            },
        ]

    async def get_news(self, ticker: str, limit: int = 50) -> DataEnvelope:
        cache_key = _make_cache_key("news_intel", ticker, str(limit))
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for news_intel:%s", ticker)
            return cached

        now = dt.datetime.now(dt.timezone.utc)
        start_date = (now - dt.timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            tasks = []
            for src in self._sources:
                url = src["url_template"].format(
                    ticker=quote_plus(ticker),
                    start=start_date,
                    end=end_date,
                )
                tasks.append(self._fetch_source(client, src["name"], url, src["parser"], ticker))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles: list[dict] = []
        warnings: list[str] = []
        for i, result in enumerate(results):
            src_name = self._sources[i]["name"]
            if isinstance(result, Exception):
                logger.warning("Source %s failed: %s", src_name, result)
                warnings.append(f"{src_name}: {result}")
            elif isinstance(result, list):
                all_articles.extend(result)

        # Deduplicate and sort
        all_articles = _deduplicate_articles(all_articles)
        all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        all_articles = all_articles[:limit]

        envelope = DataEnvelope(
            data=all_articles,
            source="news_intelligence",
            source_label="official",
            confidence=0.8,
            quality_score=min(1.0, len(all_articles) / max(limit * 0.3, 1)),
            warnings=warnings,
        )
        _cache.set(cache_key, envelope)
        return envelope

    async def _fetch_source(
        self,
        client: httpx.AsyncClient,
        source_name: str,
        url: str,
        parser: Any,
        ticker: str,
    ) -> list[dict]:
        logger.info("Fetching %s: %s", source_name, url)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return parser(resp.text, source_name, ticker)
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP %s from %s: %s", exc.response.status_code, source_name, url)
            return []
        except Exception as exc:
            logger.warning("Error fetching %s: %s", source_name, exc)
            return []

    # ---- Parsers -----------------------------------------------------------

    def _parse_generic_rss(self, text: str, source_name: str, ticker: str) -> list[dict]:
        items = _parse_rss_items(text)
        articles: list[dict] = []
        for item in items:
            headline = _strip_html(item["title"])
            summary = _strip_html(item["description"])[:500]
            articles.append({
                "ticker": ticker,
                "published_at": _parse_rss_date(item["pubDate"]).isoformat(),
                "headline": headline,
                "summary": summary,
                "url": item["link"],
                "source_name": source_name,
                "category": _classify_category(headline, summary),
                "sentiment_score": _score_sentiment(headline, summary),
                "relevance_score": _score_relevance(headline, ticker),
            })
        return articles

    def _parse_edgar_rss(self, text: str, source_name: str, ticker: str) -> list[dict]:
        """Parse SEC EDGAR search results (Atom feed or HTML fallback)."""
        items = _parse_rss_items(text)
        articles: list[dict] = []
        for item in items:
            headline = _strip_html(item["title"])
            summary = _strip_html(item["description"])[:500]
            articles.append({
                "ticker": ticker,
                "published_at": _parse_rss_date(item["pubDate"]).isoformat(),
                "headline": headline,
                "summary": summary,
                "url": item["link"] or f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}",
                "source_name": "sec_edgar",
                "category": "regulatory",
                "sentiment_score": 0.0,
                "relevance_score": 0.9,
            })
        return articles


# ---------------------------------------------------------------------------
# 2. InvestorRelationsAdapter
# ---------------------------------------------------------------------------

class InvestorRelationsAdapter:
    """Fetches press releases from Upstart's IR page."""

    _IR_URL = "https://ir.upstart.com/news-and-events/news-releases/"
    _IR_RSS_URL = "https://ir.upstart.com/rss/news-releases.xml"

    async def get_ir_releases(self, limit: int = 20) -> DataEnvelope:
        cache_key = _make_cache_key("ir_releases", str(limit))
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for ir_releases")
            return cached

        articles: list[dict] = []
        warnings: list[str] = []

        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            # Try RSS first, fall back to scraping the HTML page
            for url in (self._IR_RSS_URL, self._IR_URL):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    articles = self._parse_ir(resp.text)
                    if articles:
                        break
                except Exception as exc:
                    logger.warning("IR fetch failed for %s: %s", url, exc)
                    warnings.append(f"ir_fetch:{url} — {exc}")

        articles = articles[:limit]

        envelope = DataEnvelope(
            data=articles,
            source="ir_upstart",
            source_label="official",
            confidence=0.95,
            quality_score=1.0 if articles else 0.0,
            warnings=warnings,
        )
        _cache.set(cache_key, envelope)
        return envelope

    @staticmethod
    def _parse_ir(text: str) -> list[dict]:
        """Parse RSS or basic HTML from IR page."""
        # Try RSS parse first
        items = _parse_rss_items(text)
        if items:
            articles: list[dict] = []
            for item in items:
                headline = _strip_html(item["title"])
                summary = _strip_html(item["description"])[:500]
                articles.append({
                    "ticker": "UPST",
                    "published_at": _parse_rss_date(item["pubDate"]).isoformat(),
                    "headline": headline,
                    "summary": summary,
                    "url": item["link"] or "https://ir.upstart.com/news-and-events/news-releases/",
                    "source_name": "ir_upstart",
                    "category": "ir_release",
                    "sentiment_score": _score_sentiment(headline, summary),
                    "relevance_score": 0.95,
                })
            return articles

        # HTML fallback: look for <a> tags inside press-release listings
        articles = []
        for match in re.finditer(
            r'<a[^>]+href="(/news-and-events/news-releases/[^"]+)"[^>]*>(.*?)</a>',
            text,
            re.DOTALL,
        ):
            path, title_raw = match.groups()
            headline = _strip_html(title_raw)
            if not headline:
                continue
            articles.append({
                "ticker": "UPST",
                "published_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "headline": headline,
                "summary": "",
                "url": f"https://ir.upstart.com{path}",
                "source_name": "ir_upstart",
                "category": "ir_release",
                "sentiment_score": _score_sentiment(headline, ""),
                "relevance_score": 0.95,
            })
        return articles


# ---------------------------------------------------------------------------
# 3. SocialSentimentAdapter
# ---------------------------------------------------------------------------

class SocialSentimentAdapter:
    """Fetches social-media sentiment from public, auth-free sources."""

    _REDDIT_SUBS = ["wallstreetbets", "stocks", "investing"]
    _STOCKTWITS_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

    async def get_social_sentiment(self, ticker: str) -> DataEnvelope:
        cache_key = _make_cache_key("social_sentiment", ticker)
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for social_sentiment:%s", ticker)
            return cached

        all_items: list[dict] = []
        warnings: list[str] = []

        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            tasks: list = []
            # Reddit RSS feeds
            for sub in self._REDDIT_SUBS:
                url = f"https://old.reddit.com/r/{sub}/search.rss?q={quote_plus(ticker)}&restrict_sr=on&sort=new&t=week"
                tasks.append(self._fetch_reddit(client, url, sub, ticker))
            # StockTwits public API
            tasks.append(self._fetch_stocktwits(client, ticker))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                warnings.append(str(result))
            elif isinstance(result, list):
                all_items.extend(result)

        all_items = _deduplicate_articles(all_items)
        all_items.sort(key=lambda a: a.get("published_at", ""), reverse=True)

        envelope = DataEnvelope(
            data=all_items,
            source="social_sentiment",
            source_label="estimated",
            confidence=0.5,
            quality_score=0.6 if all_items else 0.0,
            warnings=warnings,
        )
        _cache.set(cache_key, envelope)
        return envelope

    async def _fetch_reddit(
        self, client: httpx.AsyncClient, url: str, subreddit: str, ticker: str,
    ) -> list[dict]:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            items = _parse_rss_items(resp.text)
            articles: list[dict] = []
            for item in items:
                headline = _strip_html(item["title"])
                summary = _strip_html(item["description"])[:500]
                articles.append({
                    "ticker": ticker,
                    "published_at": _parse_rss_date(item["pubDate"]).isoformat(),
                    "headline": headline,
                    "summary": summary,
                    "url": item["link"],
                    "source_name": f"reddit_r/{subreddit}",
                    "category": _classify_category(headline, summary),
                    "sentiment_score": _score_sentiment(headline, summary),
                    "relevance_score": _score_relevance(headline, ticker),
                })
            return articles
        except Exception as exc:
            logger.warning("Reddit %s fetch failed: %s", subreddit, exc)
            return []

    async def _fetch_stocktwits(self, client: httpx.AsyncClient, ticker: str) -> list[dict]:
        url = self._STOCKTWITS_URL.format(ticker=quote_plus(ticker))
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [])
            articles: list[dict] = []
            for msg in messages:
                body = msg.get("body", "")
                created = msg.get("created_at", "")
                st_sentiment = msg.get("entities", {}).get("sentiment", {})
                if st_sentiment and st_sentiment.get("basic"):
                    raw = st_sentiment["basic"].lower()
                    sent = 0.5 if raw == "bullish" else (-0.5 if raw == "bearish" else 0.0)
                else:
                    sent = _score_sentiment(body, "")
                articles.append({
                    "ticker": ticker,
                    "published_at": created or dt.datetime.now(dt.timezone.utc).isoformat(),
                    "headline": body[:120],
                    "summary": body[:500],
                    "url": f"https://stocktwits.com/symbol/{ticker}",
                    "source_name": "stocktwits",
                    "category": _classify_category(body, ""),
                    "sentiment_score": sent,
                    "relevance_score": _score_relevance(body, ticker),
                })
            return articles
        except Exception as exc:
            logger.warning("StockTwits fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 4. CEOTracker
# ---------------------------------------------------------------------------

class CEOTracker:
    """Tracks CEO activity via public Google News RSS."""

    async def get_ceo_activity(self, ceo_name: str = "Dave Girouard") -> DataEnvelope:
        cache_key = _make_cache_key("ceo_tracker", ceo_name)
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for ceo_tracker:%s", ceo_name)
            return cached

        url = (
            f"https://news.google.com/rss/search?"
            f"q={quote_plus(ceo_name)}+Upstart&hl=en-US&gl=US&ceid=US:en"
        )
        articles: list[dict] = []
        warnings: list[str] = []

        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                items = _parse_rss_items(resp.text)
                for item in items:
                    headline = _strip_html(item["title"])
                    summary = _strip_html(item["description"])[:500]
                    articles.append({
                        "ticker": "UPST",
                        "published_at": _parse_rss_date(item["pubDate"]).isoformat(),
                        "headline": headline,
                        "summary": summary,
                        "url": item["link"],
                        "source_name": "google_news_ceo",
                        "category": "leadership",
                        "sentiment_score": _score_sentiment(headline, summary),
                        "relevance_score": 0.85,
                    })
            except Exception as exc:
                logger.warning("CEO tracker fetch failed: %s", exc)
                warnings.append(f"ceo_tracker: {exc}")

        envelope = DataEnvelope(
            data=articles,
            source="ceo_tracker",
            source_label="estimated",
            confidence=0.65,
            quality_score=0.7 if articles else 0.0,
            warnings=warnings,
        )
        _cache.set(cache_key, envelope)
        return envelope


# ---------------------------------------------------------------------------
# Convenience aggregator
# ---------------------------------------------------------------------------

async def fetch_all_news_intelligence(ticker: str = "UPST", limit: int = 50) -> dict:
    """Fetch from all intelligence sources and merge into a unified result."""
    news_adapter = NewsIntelligenceAdapter()
    ir_adapter = InvestorRelationsAdapter()
    social_adapter = SocialSentimentAdapter()
    ceo_tracker = CEOTracker()

    results = await asyncio.gather(
        news_adapter.get_news(ticker, limit=limit),
        ir_adapter.get_ir_releases(limit=20),
        social_adapter.get_social_sentiment(ticker),
        ceo_tracker.get_ceo_activity(),
        return_exceptions=True,
    )

    all_articles: list[dict] = []
    source_breakdown: dict[str, int] = {}
    warnings: list[str] = []

    for result in results:
        if isinstance(result, Exception):
            logger.error("Intelligence source failed: %s", result)
            warnings.append(str(result))
            continue
        if not isinstance(result, DataEnvelope):
            continue
        items = result.data if isinstance(result.data, list) else []
        for item in items:
            src = item.get("source_name", result.source)
            source_breakdown[src] = source_breakdown.get(src, 0) + 1
        all_articles.extend(items)
        warnings.extend(result.warnings)

    # Deduplicate across all sources
    all_articles = _deduplicate_articles(all_articles)

    # Sort by published_at descending
    all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)

    # Trim to limit
    all_articles = all_articles[:limit]

    # Recompute source breakdown after dedup
    source_breakdown = {}
    for article in all_articles:
        src = article.get("source_name", "unknown")
        source_breakdown[src] = source_breakdown.get(src, 0) + 1

    now = dt.datetime.now(dt.timezone.utc)
    freshness = "unknown"
    if all_articles:
        try:
            newest = dt.datetime.fromisoformat(all_articles[0]["published_at"])
            delta = now - newest
            if delta.total_seconds() < 3600:
                freshness = f"{int(delta.total_seconds() / 60)}m ago"
            elif delta.total_seconds() < 86400:
                freshness = f"{int(delta.total_seconds() / 3600)}h ago"
            else:
                freshness = f"{int(delta.total_seconds() / 86400)}d ago"
        except (ValueError, KeyError):
            freshness = "unknown"

    return {
        "articles": all_articles,
        "source_breakdown": source_breakdown,
        "total_count": len(all_articles),
        "freshness": freshness,
        "warnings": warnings,
    }
