"""Yahoo Finance adapter — free fallback for equity/options data."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import yfinance as yf
import pandas as pd

from backend.adapters.base import (
    BaseMarketAdapter, BaseFundamentalAdapter, DataEnvelope,
)

logger = logging.getLogger(__name__)

_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "1h": "60m",
    "1d": "1d", "1w": "1wk", "1M": "1mo",
}


class YahooMarketAdapter(BaseMarketAdapter):
    """Yahoo Finance market-data adapter."""

    async def get_quote(self, ticker: str) -> DataEnvelope:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            data = {
                "ticker": ticker,
                "price": float(info.last_price) if hasattr(info, "last_price") else None,
                "previous_close": float(info.previous_close) if hasattr(info, "previous_close") else None,
                "market_cap": float(info.market_cap) if hasattr(info, "market_cap") else None,
                "volume": int(info.last_volume) if hasattr(info, "last_volume") else None,
            }
            return DataEnvelope(data=data, source="yfinance", source_label="official")
        except Exception as e:
            logger.error("Yahoo quote error for %s: %s", ticker, e)
            return DataEnvelope(
                data=None, source="yfinance", source_label="official",
                quality_score=0.0, warnings=[str(e)],
            )

    async def get_bars(
        self, ticker: str, timeframe: str, start: dt.date, end: dt.date,
    ) -> DataEnvelope:
        try:
            yf_tf = _TF_MAP.get(timeframe, "1d")
            t = yf.Ticker(ticker)
            df: pd.DataFrame = t.history(
                start=start.isoformat(), end=end.isoformat(), interval=yf_tf,
            )
            if df.empty:
                return DataEnvelope(
                    data=[], source="yfinance", quality_score=0.5,
                    warnings=["Empty dataframe returned"],
                )
            records = []
            for idx, row in df.iterrows():
                records.append({
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "bar_time": idx.to_pydatetime(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return DataEnvelope(data=records, source="yfinance", source_label="official")
        except Exception as e:
            logger.error("Yahoo bars error for %s: %s", ticker, e)
            return DataEnvelope(data=[], source="yfinance", quality_score=0.0, warnings=[str(e)])

    async def get_options_chain(self, ticker: str) -> DataEnvelope:
        try:
            t = yf.Ticker(ticker)
            expirations = t.options
            if not expirations:
                return DataEnvelope(
                    data={"expirations": [], "contracts": []},
                    source="yfinance", quality_score=0.5,
                    warnings=["No options expirations found"],
                )
            contracts = []
            underlying_price = None
            info = t.fast_info
            if hasattr(info, "last_price"):
                underlying_price = float(info.last_price)

            for exp in expirations[:6]:  # Limit to 6 nearest expirations
                chain = t.option_chain(exp)
                for _, row in chain.calls.iterrows():
                    contracts.append(_parse_yf_option(row, ticker, exp, "call"))
                for _, row in chain.puts.iterrows():
                    contracts.append(_parse_yf_option(row, ticker, exp, "put"))

            return DataEnvelope(
                data={
                    "ticker": ticker,
                    "underlying_price": underlying_price,
                    "expirations": list(expirations),
                    "contracts": contracts,
                },
                source="yfinance", source_label="official",
            )
        except Exception as e:
            logger.error("Yahoo options error for %s: %s", ticker, e)
            return DataEnvelope(
                data={"expirations": [], "contracts": []},
                source="yfinance", quality_score=0.0, warnings=[str(e)],
            )


class YahooFundamentalAdapter(BaseFundamentalAdapter):
    """Yahoo Finance fundamental data adapter."""

    async def get_financials(self, ticker: str) -> DataEnvelope:
        try:
            t = yf.Ticker(ticker)
            income = t.quarterly_income_stmt
            balance = t.quarterly_balance_sheet
            cashflow = t.quarterly_cashflow
            data = {
                "income": income.to_dict() if income is not None else {},
                "balance": balance.to_dict() if balance is not None else {},
                "cashflow": cashflow.to_dict() if cashflow is not None else {},
            }
            return DataEnvelope(data=data, source="yfinance", source_label="official")
        except Exception as e:
            logger.error("Yahoo financials error for %s: %s", ticker, e)
            return DataEnvelope(data={}, source="yfinance", quality_score=0.0, warnings=[str(e)])

    async def get_earnings(self, ticker: str) -> DataEnvelope:
        try:
            t = yf.Ticker(ticker)
            earnings = t.earnings_dates
            data = earnings.to_dict() if earnings is not None else {}
            return DataEnvelope(data=data, source="yfinance", source_label="official")
        except Exception as e:
            logger.error("Yahoo earnings error for %s: %s", ticker, e)
            return DataEnvelope(data={}, source="yfinance", quality_score=0.0, warnings=[str(e)])


def _parse_yf_option(row: Any, ticker: str, exp: str, opt_type: str) -> dict:
    """Parse a yfinance option row into a dict."""
    return {
        "ticker": ticker,
        "option_type": opt_type,
        "strike": float(row.get("strike", 0)),
        "expiration": exp,
        "bid": float(row.get("bid", 0)) if pd.notna(row.get("bid")) else None,
        "ask": float(row.get("ask", 0)) if pd.notna(row.get("ask")) else None,
        "last": float(row.get("lastPrice", 0)) if pd.notna(row.get("lastPrice")) else None,
        "volume": int(row.get("volume", 0)) if pd.notna(row.get("volume")) else 0,
        "open_interest": int(row.get("openInterest", 0)) if pd.notna(row.get("openInterest")) else 0,
        "implied_volatility": float(row.get("impliedVolatility", 0)) if pd.notna(row.get("impliedVolatility")) else None,
        "in_the_money": bool(row.get("inTheMoney", False)),
    }
