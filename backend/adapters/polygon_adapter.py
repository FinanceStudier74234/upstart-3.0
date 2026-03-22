"""Polygon.io adapter — institutional-grade market data with real-time WebSocket streaming."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from typing import Any, Callable

import aiohttp

from backend.adapters.base import BaseMarketAdapter, DataEnvelope
from backend.config.settings import settings

logger = logging.getLogger(__name__)

_TF_MAP = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1, "1w": 1, "1M": 1}
_SPAN_MAP = {"1m": "minute", "5m": "minute", "15m": "minute", "1h": "hour",
             "1d": "day", "1w": "week", "1M": "month"}
_BASE = "https://api.polygon.io"


class PolygonMarketAdapter(BaseMarketAdapter):
    """Polygon.io REST adapter for equity, options, and snapshot data."""

    def __init__(self):
        self._key = settings.polygon_api_key
        self._plan = settings.polygon_plan  # basic | starter | developer | advanced
        self._session: aiohttp.ClientSession | None = None
        self._rate_limit_until = 0.0
        self._calls_this_minute = 0
        self._minute_start = 0.0
        # Basic plan: 5 calls/min; Starter+: higher
        self._max_calls_per_min = 5 if self._plan == "basic" else 100

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"Authorization": f"Bearer {self._key}"},
            )
        return self._session

    async def _request(self, url: str, params: dict | None = None) -> dict | None:
        """Rate-limited GET request to Polygon API."""
        now = time.monotonic()
        if now < self._rate_limit_until:
            await asyncio.sleep(self._rate_limit_until - now)

        # Rolling rate limit
        if now - self._minute_start > 60:
            self._calls_this_minute = 0
            self._minute_start = now
        if self._calls_this_minute >= self._max_calls_per_min:
            wait = 60 - (now - self._minute_start)
            if wait > 0:
                logger.info("Polygon rate limit: waiting %.1fs", wait)
                await asyncio.sleep(wait)
            self._calls_this_minute = 0
            self._minute_start = time.monotonic()

        session = await self._get_session()
        full_params = {**(params or {}), "apiKey": self._key}

        try:
            async with session.get(url, params=full_params) as resp:
                self._calls_this_minute += 1
                if resp.status == 429:
                    self._rate_limit_until = time.monotonic() + 60
                    logger.warning("Polygon 429 rate limited, backing off 60s")
                    return None
                if resp.status != 200:
                    logger.warning("Polygon %s returned %d", url, resp.status)
                    return None
                return await resp.json()
        except Exception as e:
            logger.error("Polygon request error: %s", e)
            return None

    async def get_quote(self, ticker: str) -> DataEnvelope:
        data = await self._request(f"{_BASE}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        if not data or data.get("status") != "OK":
            return DataEnvelope(data=None, source="polygon", quality_score=0.0,
                                warnings=["Polygon quote fetch failed"])

        snap = data.get("ticker", {})
        day = snap.get("day", {})
        prev = snap.get("prevDay", {})
        last_trade = snap.get("lastTrade", {})

        return DataEnvelope(
            data={
                "ticker": ticker,
                "price": last_trade.get("p", day.get("c", 0)),
                "previous_close": prev.get("c", 0),
                "volume": day.get("v", 0),
                "vwap": day.get("vw", 0),
                "market_cap": None,  # Not available from snapshot
                "bid": snap.get("lastQuote", {}).get("p", 0),
                "ask": snap.get("lastQuote", {}).get("P", 0),
                "bid_size": snap.get("lastQuote", {}).get("s", 0),
                "ask_size": snap.get("lastQuote", {}).get("S", 0),
                "todays_change_pct": snap.get("todaysChangePerc", 0),
                "updated": snap.get("updated", 0),
            },
            source="polygon", source_label="official", confidence=0.95,
        )

    async def get_bars(
        self, ticker: str, timeframe: str, start: dt.date, end: dt.date,
    ) -> DataEnvelope:
        multiplier = _TF_MAP.get(timeframe, 1)
        span = _SPAN_MAP.get(timeframe, "day")
        url = (f"{_BASE}/v2/aggs/ticker/{ticker}/range/"
               f"{multiplier}/{span}/{start.isoformat()}/{end.isoformat()}")

        records = []
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}

        data = await self._request(url, params)
        if not data or data.get("resultsCount", 0) == 0:
            return DataEnvelope(data=[], source="polygon", quality_score=0.0,
                                warnings=["No bar data returned"])

        for bar in data.get("results", []):
            ts_ms = bar.get("t", 0)
            bar_time = dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc)
            records.append({
                "ticker": ticker, "timeframe": timeframe,
                "bar_time": bar_time,
                "open": bar.get("o", 0), "high": bar.get("h", 0),
                "low": bar.get("l", 0), "close": bar.get("c", 0),
                "volume": bar.get("v", 0),
                "vwap": bar.get("vw", 0),
                "trade_count": bar.get("n", 0),
            })

        return DataEnvelope(
            data=records, source="polygon", source_label="official", confidence=0.98,
        )

    async def get_options_chain(self, ticker: str) -> DataEnvelope:
        """Fetch full options chain via Polygon snapshot endpoint."""
        url = f"{_BASE}/v3/snapshot/options/{ticker}"
        params = {"limit": 250}
        all_contracts = []
        underlying_price = None

        # Paginate through results
        while url:
            data = await self._request(url, params)
            if not data:
                break

            for result in data.get("results", []):
                details = result.get("details", {})
                greeks = result.get("greeks", {})
                day = result.get("day", {})
                underlying = result.get("underlying_asset", {})
                if underlying_price is None:
                    underlying_price = underlying.get("price")

                all_contracts.append({
                    "ticker": ticker,
                    "option_type": details.get("contract_type", "").lower(),
                    "strike": details.get("strike_price", 0),
                    "expiration": details.get("expiration_date", ""),
                    "bid": day.get("bid", result.get("last_quote", {}).get("bid", 0)),
                    "ask": day.get("ask", result.get("last_quote", {}).get("ask", 0)),
                    "last": day.get("close", 0),
                    "volume": day.get("volume", 0),
                    "open_interest": result.get("open_interest", 0),
                    "implied_volatility": result.get("implied_volatility"),
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                })

            next_url = data.get("next_url")
            if next_url:
                url = next_url
                params = {}  # next_url includes params
            else:
                break

        return DataEnvelope(
            data={
                "ticker": ticker,
                "underlying_price": underlying_price,
                "contracts": all_contracts,
            },
            source="polygon", source_label="official",
            confidence=0.95 if all_contracts else 0.0,
        )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


class PolygonStreamingClient:
    """WebSocket streaming client for real-time Polygon data.

    Supports: trades, quotes, second/minute aggregates.
    Usage:
        client = PolygonStreamingClient()
        client.on_trade = my_callback
        await client.connect()
        await client.subscribe(["T.UPST", "Q.UPST", "AM.UPST", "T.SPY"])
    """

    CLUSTER_URLS = {
        "stocks": "wss://socket.polygon.io/stocks",
        "options": "wss://socket.polygon.io/options",
    }

    def __init__(self, cluster: str = "stocks"):
        self._key = settings.polygon_api_key
        self._url = self.CLUSTER_URLS.get(cluster, self.CLUSTER_URLS["stocks"])
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._subscriptions: list[str] = []

        # Callbacks
        self.on_trade: Callable[[dict], None] | None = None
        self.on_quote: Callable[[dict], None] | None = None
        self.on_aggregate: Callable[[dict], None] | None = None
        self.on_status: Callable[[dict], None] | None = None

    async def connect(self):
        """Connect and authenticate with Polygon WebSocket."""
        self._running = True
        self._session = aiohttp.ClientSession()

        while self._running:
            try:
                self._ws = await self._session.ws_connect(self._url)
                self._reconnect_delay = 1.0
                logger.info("Polygon WS connected to %s", self._url)

                # Authenticate
                await self._ws.send_json({"action": "auth", "params": self._key})

                # Re-subscribe after reconnect
                if self._subscriptions:
                    await self._ws.send_json({
                        "action": "subscribe",
                        "params": ",".join(self._subscriptions),
                    })

                # Message loop
                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        import json
                        events = json.loads(msg.data)
                        for event in events if isinstance(events, list) else [events]:
                            self._dispatch(event)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break

            except Exception as e:
                logger.error("Polygon WS error: %s", e)

            if self._running:
                logger.info("Polygon WS reconnecting in %.0fs...", self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

    async def subscribe(self, channels: list[str]):
        """Subscribe to channels. Prefixes: T.=trades, Q.=quotes, AM.=min aggs."""
        self._subscriptions.extend(channels)
        if self._ws and not self._ws.closed:
            await self._ws.send_json({
                "action": "subscribe",
                "params": ",".join(channels),
            })

    async def disconnect(self):
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()

    def _dispatch(self, event: dict):
        ev_type = event.get("ev", event.get("status", ""))
        if ev_type == "T" and self.on_trade:
            self.on_trade({
                "ticker": event.get("sym", event.get("T", "")),
                "price": event.get("p", 0),
                "size": event.get("s", 0),
                "timestamp": event.get("t", 0),
                "conditions": event.get("c", []),
            })
        elif ev_type == "Q" and self.on_quote:
            self.on_quote({
                "ticker": event.get("sym", event.get("T", "")),
                "bid": event.get("bp", event.get("p", 0)),
                "ask": event.get("ap", event.get("P", 0)),
                "bid_size": event.get("bs", event.get("s", 0)),
                "ask_size": event.get("as", event.get("S", 0)),
                "timestamp": event.get("t", 0),
            })
        elif ev_type in ("AM", "A") and self.on_aggregate:
            self.on_aggregate({
                "ticker": event.get("sym", event.get("T", "")),
                "open": event.get("o", 0),
                "high": event.get("h", 0),
                "low": event.get("l", 0),
                "close": event.get("c", 0),
                "volume": event.get("v", 0),
                "vwap": event.get("vw", 0),
                "trades": event.get("z", event.get("n", 0)),
                "start_ts": event.get("s", 0),
                "end_ts": event.get("e", 0),
            })
        elif ev_type == "status" and self.on_status:
            self.on_status(event)
