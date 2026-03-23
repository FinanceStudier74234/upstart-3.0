"""Yahoo Finance adapter — free fallback for equity/options data.
Uses Yahoo Finance API directly via requests (no yfinance dependency).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import requests
import pandas as pd

from backend.adapters.base import (
    BaseMarketAdapter, BaseFundamentalAdapter, DataEnvelope,
)

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
}

_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "1h": "60m",
    "1d": "1d", "1w": "1wk", "1M": "1mo", "1min": "1m",
}


class YahooMarketAdapter(BaseMarketAdapter):
    """Yahoo Finance market-data adapter using direct HTTP requests."""

    async def get_quote(self, ticker: str) -> DataEnvelope:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            resp = requests.get(url, headers=_HEADERS, params={"interval": "1d", "range": "2d"}, timeout=10)
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            meta = result["meta"]
            data = {
                "ticker": ticker,
                "price": meta.get("regularMarketPrice"),
                "previous_close": meta.get("chartPreviousClose") or meta.get("previousClose"),
                "market_cap": None,  # Not available in chart endpoint
                "volume": meta.get("regularMarketVolume"),
            }
            if data["price"] is None:
                return DataEnvelope(data=None, source="yfinance", quality_score=0.0,
                                    warnings=["No price in Yahoo response"])
            return DataEnvelope(data=data, source="yfinance", source_label="official")
        except Exception as e:
            logger.warning("Yahoo quote error for %s: %s", ticker, e)
            return DataEnvelope(
                data=None, source="yfinance", source_label="official",
                quality_score=0.0, warnings=[str(e)],
            )

    async def get_bars(
        self, ticker: str, timeframe: str, start: dt.date, end: dt.date,
    ) -> DataEnvelope:
        try:
            yf_tf = _TF_MAP.get(timeframe, "1d")
            period1 = int(dt.datetime.combine(start, dt.time.min).timestamp())
            period2 = int(dt.datetime.combine(end, dt.time.max).timestamp())

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {"interval": yf_tf, "period1": period1, "period2": period2}
            resp = requests.get(url, headers=_HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()["chart"]["result"][0]

            timestamps = data.get("timestamp", [])
            quotes = data.get("indicators", {}).get("quote", [{}])[0]
            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])

            if not timestamps:
                return DataEnvelope(
                    data=[], source="yfinance", quality_score=0.5,
                    warnings=["Empty response from Yahoo"],
                )

            records = []
            for i, ts in enumerate(timestamps):
                if i >= len(closes) or closes[i] is None:
                    continue
                bar_time = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
                records.append({
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "bar_time": bar_time,
                    "open": float(opens[i]) if opens[i] is not None else float(closes[i]),
                    "high": float(highs[i]) if highs[i] is not None else float(closes[i]),
                    "low": float(lows[i]) if lows[i] is not None else float(closes[i]),
                    "close": float(closes[i]),
                    "volume": int(volumes[i]) if volumes[i] is not None else 0,
                })
            return DataEnvelope(data=records, source="yfinance", source_label="official")
        except Exception as e:
            logger.warning("Yahoo bars error for %s: %s", ticker, e)
            return DataEnvelope(data=[], source="yfinance", quality_score=0.0, warnings=[str(e)])

    async def get_options_chain(self, ticker: str) -> DataEnvelope:
        try:
            url = f"https://query1.finance.yahoo.com/v7/finance/options/{ticker}"
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            result = resp.json()["optionChain"]["result"][0]

            underlying_price = result.get("quote", {}).get("regularMarketPrice")
            expirations_ts = result.get("expirationDates", [])
            expirations = [dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in expirations_ts]

            contracts = []
            # Parse first expiration from initial response
            for chain in result.get("options", []):
                exp = dt.datetime.fromtimestamp(chain.get("expirationDate", 0)).strftime("%Y-%m-%d")
                for call in chain.get("calls", []):
                    contracts.append(_parse_yahoo_option(call, ticker, exp, "call"))
                for put in chain.get("puts", []):
                    contracts.append(_parse_yahoo_option(put, ticker, exp, "put"))

            # Fetch additional expirations (up to 5 more)
            for exp_ts in expirations_ts[1:6]:
                try:
                    resp2 = requests.get(url, headers=_HEADERS,
                                         params={"date": exp_ts}, timeout=10)
                    resp2.raise_for_status()
                    result2 = resp2.json()["optionChain"]["result"][0]
                    for chain in result2.get("options", []):
                        exp = dt.datetime.fromtimestamp(chain.get("expirationDate", 0)).strftime("%Y-%m-%d")
                        for call in chain.get("calls", []):
                            contracts.append(_parse_yahoo_option(call, ticker, exp, "call"))
                        for put in chain.get("puts", []):
                            contracts.append(_parse_yahoo_option(put, ticker, exp, "put"))
                except Exception:
                    continue

            return DataEnvelope(
                data={
                    "ticker": ticker,
                    "underlying_price": underlying_price,
                    "expirations": expirations,
                    "contracts": contracts,
                },
                source="yfinance", source_label="official",
            )
        except Exception as e:
            logger.warning("Yahoo options error for %s: %s", ticker, e)
            return DataEnvelope(
                data={"expirations": [], "contracts": []},
                source="yfinance", quality_score=0.0, warnings=[str(e)],
            )


class YahooFundamentalAdapter(BaseFundamentalAdapter):
    """Yahoo Finance fundamental data adapter."""

    async def get_financials(self, ticker: str) -> DataEnvelope:
        try:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            params = {"modules": "incomeStatementHistoryQuarterly,balanceSheetHistoryQuarterly,cashflowStatementHistoryQuarterly,defaultKeyStatistics"}
            resp = requests.get(url, headers=_HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            result = resp.json()["quoteSummary"]["result"][0]

            quarters = []
            income_stmts = result.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", [])
            balance_stmts = result.get("balanceSheetHistoryQuarterly", {}).get("balanceSheetStatements", [])
            cashflow_stmts = result.get("cashflowStatementHistoryQuarterly", {}).get("cashflowStatements", [])
            key_stats = result.get("defaultKeyStatistics", {})

            shares = key_stats.get("sharesOutstanding", {}).get("raw", 85_000_000)

            for i, stmt in enumerate(income_stmts[:8]):
                rev = stmt.get("totalRevenue", {}).get("raw", 0)
                ebitda = stmt.get("ebitda", {}).get("raw", 0)
                net_income = stmt.get("netIncome", {}).get("raw", 0)

                cash = 0
                debt = 0
                if i < len(balance_stmts):
                    bs = balance_stmts[i]
                    cash = bs.get("cash", {}).get("raw", 0)
                    debt = bs.get("longTermDebt", {}).get("raw", 0) + bs.get("shortLongTermDebt", {}).get("raw", 0)

                end_date = stmt.get("endDate", {}).get("fmt", "")
                quarters.append({
                    "ticker": ticker,
                    "period_end": end_date,
                    "revenue": rev,
                    "ebitda": ebitda,
                    "adjusted_ebitda": ebitda,
                    "eps_diluted": round(net_income / max(shares, 1), 2),
                    "cash_and_equivalents": cash,
                    "total_debt": debt,
                    "shares_outstanding": shares,
                    "gross_margin": 0,
                    "operating_margin": 0,
                })

            return DataEnvelope(data=quarters if quarters else {}, source="yfinance", source_label="official")
        except Exception as e:
            logger.warning("Yahoo financials error for %s: %s", ticker, e)
            return DataEnvelope(data={}, source="yfinance", quality_score=0.0, warnings=[str(e)])

    async def get_earnings(self, ticker: str) -> DataEnvelope:
        try:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            params = {"modules": "earningsHistory,earningsTrend"}
            resp = requests.get(url, headers=_HEADERS, params=params, timeout=10)
            resp.raise_for_status()
            result = resp.json()["quoteSummary"]["result"][0]

            history = result.get("earningsHistory", {}).get("history", [])
            releases = []
            for entry in history:
                releases.append({
                    "ticker": ticker,
                    "report_date": entry.get("quarter", {}).get("fmt", ""),
                    "eps_estimate": entry.get("epsEstimate", {}).get("raw"),
                    "eps_actual": entry.get("epsActual", {}).get("raw"),
                    "surprise_pct": entry.get("surprisePercent", {}).get("raw"),
                })
            return DataEnvelope(data=releases if releases else {}, source="yfinance", source_label="official")
        except Exception as e:
            logger.warning("Yahoo earnings error for %s: %s", ticker, e)
            return DataEnvelope(data={}, source="yfinance", quality_score=0.0, warnings=[str(e)])


def _parse_yahoo_option(opt: dict, ticker: str, exp: str, opt_type: str) -> dict:
    """Parse a Yahoo Finance option contract dict."""
    return {
        "ticker": ticker,
        "option_type": opt_type,
        "strike": opt.get("strike", {}).get("raw", 0) if isinstance(opt.get("strike"), dict) else opt.get("strike", 0),
        "expiration": exp,
        "bid": opt.get("bid", {}).get("raw") if isinstance(opt.get("bid"), dict) else opt.get("bid"),
        "ask": opt.get("ask", {}).get("raw") if isinstance(opt.get("ask"), dict) else opt.get("ask"),
        "last": opt.get("lastPrice", {}).get("raw") if isinstance(opt.get("lastPrice"), dict) else opt.get("lastPrice"),
        "volume": opt.get("volume", {}).get("raw", 0) if isinstance(opt.get("volume"), dict) else opt.get("volume", 0),
        "open_interest": opt.get("openInterest", {}).get("raw", 0) if isinstance(opt.get("openInterest"), dict) else opt.get("openInterest", 0),
        "implied_volatility": opt.get("impliedVolatility", {}).get("raw") if isinstance(opt.get("impliedVolatility"), dict) else opt.get("impliedVolatility"),
        "in_the_money": opt.get("inTheMoney", False),
    }
