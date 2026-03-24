"""
Scheduler Service — Periodic data refresh + real-time Polygon WebSocket streaming.
Uses asyncio tasks for lightweight scheduling without APScheduler dependency.
"""

from __future__ import annotations

import asyncio
import logging
import datetime as dt

logger = logging.getLogger(__name__)


class SchedulerService:
    """Lightweight async scheduler for periodic data refresh + streaming."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._last_run: dict[str, str] = {}
        self._streaming_client = None
        self._latest_trades: dict[str, dict] = {}  # ticker -> latest trade
        self._latest_quotes: dict[str, dict] = {}  # ticker -> latest quote

    async def start(self, orchestrator):
        """Start all scheduled refresh tasks + streaming."""
        from backend.config.settings import settings

        if not settings.scheduler_enabled:
            logger.info("Scheduler disabled")
            return

        self._running = True
        self._orchestrator = orchestrator
        logger.info("Starting scheduler...")

        self._tasks["market_data"] = asyncio.create_task(
            self._periodic(
                "market_data",
                settings.market_data_refresh_seconds,
                orchestrator.run_full_analysis,
            )
        )

        # News intelligence refresh
        if settings.news_intelligence_enabled:
            async def _refresh_news_intel():
                from backend.services.news_intelligence_service import news_intelligence_service
                await news_intelligence_service.get_full_intelligence(force_refresh=True)

            self._tasks["news_intelligence"] = asyncio.create_task(
                self._periodic(
                    "news_intelligence",
                    settings.news_intelligence_refresh_seconds,
                    _refresh_news_intel,
                )
            )

        # DB retention cleanup — run daily (every 24h)
        self._tasks["db_retention"] = asyncio.create_task(
            self._periodic("db_retention", 86400, self._run_retention_cleanup)
        )

        # Polygon real-time streaming (if configured)
        if settings.has_polygon() and settings.polygon_plan != "basic":
            self._tasks["polygon_streaming"] = asyncio.create_task(
                self._start_streaming()
            )

        logger.info("Scheduler started with %d tasks", len(self._tasks))

    async def _start_streaming(self):
        """Connect to Polygon WebSocket for real-time UPST + SPY data."""
        try:
            from backend.adapters.polygon_adapter import PolygonStreamingClient
            from backend.services.websocket_manager import ws_manager

            client = PolygonStreamingClient()
            self._streaming_client = client

            def on_trade(data):
                self._latest_trades[data["ticker"]] = data
                # Push to frontend via WebSocket
                asyncio.create_task(ws_manager.broadcast({
                    "type": "price_update",
                    "ticker": data["ticker"],
                    "price": data["price"],
                    "size": data["size"],
                    "timestamp": data["timestamp"],
                }))

            def on_quote(data):
                self._latest_quotes[data["ticker"]] = data

            def on_aggregate(data):
                # Minute aggregates — trigger intraday analysis
                asyncio.create_task(ws_manager.broadcast({
                    "type": "aggregate",
                    "ticker": data["ticker"],
                    "close": data["close"],
                    "volume": data["volume"],
                    "vwap": data["vwap"],
                }))

            client.on_trade = on_trade
            client.on_quote = on_quote
            client.on_aggregate = on_aggregate

            # Subscribe to UPST and SPY channels
            await client.subscribe([
                "T.UPST", "Q.UPST", "AM.UPST",
                "T.SPY", "Q.SPY", "AM.SPY",
            ])

            logger.info("Polygon streaming started for UPST + SPY")
            await client.connect()

        except ImportError:
            logger.info("Polygon streaming not available (aiohttp not installed)")
        except Exception as e:
            logger.error("Polygon streaming failed: %s", e)

    @staticmethod
    async def _run_retention_cleanup():
        """Delete old analysis records per retention policy."""
        from backend.services.database import cleanup_old_records
        deleted = await cleanup_old_records()
        if deleted:
            logger.info("Retention cleanup removed %d old records", deleted)

    def get_latest_price(self, ticker: str) -> float | None:
        """Get latest streaming price for a ticker."""
        trade = self._latest_trades.get(ticker)
        return trade["price"] if trade else None

    async def stop(self):
        """Stop all scheduled tasks and streaming."""
        self._running = False
        if self._streaming_client:
            await self._streaming_client.disconnect()
            self._streaming_client = None
        for name, task in self._tasks.items():
            task.cancel()
            logger.info("Cancelled task: %s", name)
        self._tasks.clear()

    async def _periodic(self, name: str, interval: int, func):
        """Run a function periodically."""
        while self._running:
            try:
                logger.debug("Running scheduled task: %s", name)
                await func()
                self._last_run[name] = dt.datetime.now(dt.timezone.utc).isoformat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduled task %s failed: %s", name, e)
            await asyncio.sleep(interval)

    def status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "tasks": list(self._tasks.keys()),
            "last_run": dict(self._last_run),
        }


# Singleton
scheduler_service = SchedulerService()
