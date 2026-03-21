"""
News Intelligence Service — orchestrates news intelligence gathering,
analysis, and caching for the UPST Quant Finance Hub.

Fetches from news intelligence adapters concurrently, runs the analysis
engine, and manages a cached result with periodic refresh support.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import asdict
from typing import Any

logger = logging.getLogger(__name__)


class NewsIntelligenceService:
    """Orchestrates news intelligence gathering, analysis, and caching."""

    def __init__(self):
        # Import and initialize the adapters and engine
        # Use lazy imports to avoid circular dependencies
        self._cache: dict = {}
        self._cache_ttl: int = 300  # 5 minutes
        self._last_refresh: dt.datetime | None = None
        self._history: list[dict] = []  # Rolling history of snapshots for trend detection
        self._max_history: int = 100

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def get_full_intelligence(
        self, ticker: str = "UPST", force_refresh: bool = False
    ) -> dict:
        """Gather news intelligence from all adapters, run analysis engine,
        and return the full result dict.

        1. Check cache -- return cached if fresh and not force_refresh.
        2. Fetch from all adapters concurrently.
        3. Extract data from DataEnvelopes.
        4. Run NewsIntelligenceEngine.analyze().
        5. Convert snapshot to dict.
        6. Store in cache with timestamp.
        7. Append summary to history.
        8. Return the full dict result.
        """
        # 1. Cache check
        if not force_refresh and self._is_cache_fresh() and self._cache:
            logger.debug("Returning cached news intelligence for %s", ticker)
            return self._cache

        logger.info("Fetching fresh news intelligence for %s ...", ticker)

        # Lazy imports to avoid circular / startup issues
        from backend.adapters.news_intelligence_adapter import (
            NewsIntelligenceAdapter, InvestorRelationsAdapter,
            SocialSentimentAdapter, CEOTracker,
        )
        from backend.engines.news_intelligence import NewsIntelligenceEngine

        # 2. Fetch from all adapters concurrently
        try:
            news_env, ir_env, social_env, ceo_env = await asyncio.gather(
                NewsIntelligenceAdapter().get_news(ticker, limit=50),
                InvestorRelationsAdapter().get_ir_releases(limit=20),
                SocialSentimentAdapter().get_social_sentiment(ticker),
                CEOTracker().get_ceo_activity(),
            )
        except Exception as exc:
            logger.error("Adapter fetch failed: %s", exc, exc_info=True)
            return self._cache or {"error": str(exc)}

        # 3. Extract data from DataEnvelopes
        news_data = news_env.data if news_env and news_env.data else []
        ir_data = ir_env.data if ir_env and ir_env.data else []
        social_data = social_env.data if social_env and social_env.data else {}
        ceo_data = ceo_env.data if ceo_env and ceo_env.data else {}

        # 4. Run analysis engine
        try:
            engine = NewsIntelligenceEngine()
            snapshot = engine.analyze(news_data, ir_data, social_data, ceo_data)
        except Exception as exc:
            logger.error("NewsIntelligenceEngine failed: %s", exc, exc_info=True)
            return self._cache or {"error": str(exc)}

        # 5. Convert snapshot to dict
        result = self._snapshot_to_dict(snapshot)
        result["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
        result["ticker"] = ticker

        # 6. Store in cache with timestamp
        self._cache = result
        self._last_refresh = dt.datetime.now(dt.timezone.utc)

        # 7. Append summary to history (rolling window)
        summary = {
            "timestamp": result["timestamp"],
            "ticker": ticker,
            "overall_sentiment": result.get("overall_sentiment"),
            "news_intelligence_score": result.get("news_intelligence_score"),
            "risk_flags_count": len(result.get("risk_flags", [])),
            "opportunity_signals_count": len(result.get("opportunity_signals", [])),
        }
        self._history.append(summary)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info("News intelligence updated for %s", ticker)

        # 8. Return the full dict result
        return result

    # ------------------------------------------------------------------
    # Quick / partial endpoints
    # ------------------------------------------------------------------

    async def get_latest_headlines(
        self, ticker: str = "UPST", limit: int = 10
    ) -> list[dict]:
        """Return the top headlines sorted by relevance and recency.

        Uses cached data if available, otherwise fetches fresh data.
        """
        intel = self._cache if self._is_cache_fresh() and self._cache else (
            await self.get_full_intelligence(ticker)
        )

        headlines = intel.get("headlines", intel.get("top_headlines", []))
        # Sort by relevance (descending) then recency (descending)
        try:
            headlines = sorted(
                headlines,
                key=lambda h: (
                    h.get("relevance", 0),
                    h.get("published", h.get("published_at", "")),
                ),
                reverse=True,
            )
        except Exception:
            pass
        return headlines[:limit]

    async def get_sentiment_summary(self, ticker: str = "UPST") -> dict:
        """Return a compact sentiment summary."""
        intel = self._cache if self._is_cache_fresh() and self._cache else (
            await self.get_full_intelligence(ticker)
        )

        return {
            "overall_sentiment": intel.get("overall_sentiment"),
            "sentiment_label": intel.get("sentiment_label"),
            "sentiment_trend": intel.get("sentiment_trend"),
            "ceo_tone": intel.get("ceo_tone"),
            "social_sentiment": intel.get("social_sentiment"),
            "ir_sentiment": intel.get("ir_sentiment"),
            "risk_flags": intel.get("risk_flags", []),
            "opportunity_signals": intel.get("opportunity_signals", []),
            "news_intelligence_score": intel.get("news_intelligence_score"),
        }

    async def get_ceo_tracker(self, ceo_name: str = "Dave Girouard") -> dict:
        """Return CEO-specific intelligence."""
        intel = self._cache if self._is_cache_fresh() and self._cache else (
            await self.get_full_intelligence()
        )

        return {
            "ceo_name": ceo_name,
            "ceo_tone": intel.get("ceo_tone"),
            "ceo_activity": intel.get("ceo_activity", {}),
            "ceo_mentions": intel.get("ceo_mentions", []),
            "ceo_sentiment": intel.get("ceo_sentiment"),
            "last_updated": intel.get("timestamp"),
        }

    async def get_ir_tracker(self) -> dict:
        """Return investor relations intelligence."""
        intel = self._cache if self._is_cache_fresh() and self._cache else (
            await self.get_full_intelligence()
        )

        return {
            "ir_releases": intel.get("ir_releases", []),
            "ir_sentiment": intel.get("ir_sentiment"),
            "ir_topics": intel.get("ir_topics", []),
            "upcoming_events": intel.get("upcoming_events", []),
            "last_updated": intel.get("timestamp"),
        }

    async def get_social_pulse(self, ticker: str = "UPST") -> dict:
        """Return social sentiment intelligence."""
        intel = self._cache if self._is_cache_fresh() and self._cache else (
            await self.get_full_intelligence(ticker)
        )

        return {
            "ticker": ticker,
            "social_sentiment": intel.get("social_sentiment"),
            "social_volume": intel.get("social_volume"),
            "social_momentum": intel.get("social_momentum"),
            "trending_topics": intel.get("trending_topics", []),
            "platform_breakdown": intel.get("platform_breakdown", {}),
            "last_updated": intel.get("timestamp"),
        }

    async def get_narrative_analysis(self, ticker: str = "UPST") -> dict:
        """Return market narrative analysis."""
        intel = self._cache if self._is_cache_fresh() and self._cache else (
            await self.get_full_intelligence(ticker)
        )

        return {
            "ticker": ticker,
            "dominant_narrative": intel.get("dominant_narrative"),
            "narrative_shift": intel.get("narrative_shift"),
            "narrative_strength": intel.get("narrative_strength"),
            "competing_narratives": intel.get("competing_narratives", []),
            "media_framing": intel.get("media_framing", {}),
            "last_updated": intel.get("timestamp"),
        }

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> list[dict]:
        """Return recent intelligence history for trend analysis."""
        return self._history[-limit:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_cache_fresh(self) -> bool:
        """Check if cache is within TTL."""
        if self._last_refresh is None:
            return False
        age = (dt.datetime.now(dt.timezone.utc) - self._last_refresh).total_seconds()
        return age < self._cache_ttl

    def _snapshot_to_dict(self, obj: Any) -> dict:
        """Convert dataclass snapshots to dicts (same pattern as orchestrator)."""
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for key, value in asdict(obj).items():
                if value is None:
                    result[key] = None
                elif hasattr(value, "tolist"):
                    arr = value.tolist()
                    if isinstance(arr, list):
                        if len(arr) <= 500:
                            result[key] = arr
                    else:
                        result[key] = arr
                else:
                    result[key] = value
            return result
        if isinstance(obj, dict):
            return obj
        return vars(obj) if hasattr(obj, "__dict__") else {}


# Singleton
news_intelligence_service = NewsIntelligenceService()
