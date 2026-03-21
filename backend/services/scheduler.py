"""
Scheduler Service — Periodic data refresh using APScheduler-like pattern.
Uses asyncio tasks for lightweight scheduling without APScheduler dependency.
"""

from __future__ import annotations

import asyncio
import logging
import datetime as dt

logger = logging.getLogger(__name__)


class SchedulerService:
    """Lightweight async scheduler for periodic data refresh."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._last_run: dict[str, str] = {}

    async def start(self, orchestrator):
        """Start all scheduled refresh tasks."""
        from backend.config.settings import settings

        if not settings.scheduler_enabled:
            logger.info("Scheduler disabled")
            return

        self._running = True
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

        logger.info("Scheduler started with %d tasks", len(self._tasks))

    async def stop(self):
        """Stop all scheduled tasks."""
        self._running = False
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
