"""
WebSocket Manager — Real-time update broadcasting to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 100


class WebSocketManager:
    """Manages WebSocket connections and broadcasts updates."""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        async with self._lock:
            if len(self._connections) >= MAX_CONNECTIONS:
                await websocket.close(code=1013, reason="Max connections reached")
                logger.warning("Rejected WebSocket — max connections (%d)", MAX_CONNECTIONS)
                return
            await websocket.accept()
            self._connections.add(websocket)
            logger.info("WebSocket client connected (%d total)", len(self._connections))

    async def disconnect(self, websocket: WebSocket):
        """Remove a disconnected client."""
        async with self._lock:
            self._connections.discard(websocket)
            logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, event: str, data: Any):
        """Broadcast an event to all connected clients."""
        async with self._lock:
            if not self._connections:
                return
            current = list(self._connections)

        message = json.dumps({"event": event, "data": data}, default=str)
        disconnected = []

        for ws in current:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        if disconnected:
            async with self._lock:
                self._connections -= set(disconnected)

    async def send_analysis_update(self, analysis: dict):
        """Broadcast a full analysis update."""
        await self.broadcast("analysis_update", analysis)

    async def send_alert(self, alert: dict):
        """Broadcast a new alert."""
        await self.broadcast("alert", alert)

    async def send_price_update(self, price: float):
        """Broadcast a price update."""
        await self.broadcast("price_update", {"price": price, "ticker": "UPST"})

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton
ws_manager = WebSocketManager()
