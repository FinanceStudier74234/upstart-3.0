"""FRED adapter for macro/rates/credit data."""

from __future__ import annotations

import datetime as dt
import logging

import httpx

from backend.adapters.base import BaseMacroAdapter, DataEnvelope
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# FRED series IDs mapped to our indicator names
FRED_SERIES = {
    "FED_FUNDS": "DFF",
    "TREASURY_2Y": "DGS2",
    "TREASURY_10Y": "DGS10",
    "CPI_YOY": "CPIAUCSL",
    "PCE_YOY": "PCEPI",
    "UNEMPLOYMENT": "UNRATE",
    "INITIAL_CLAIMS": "ICSA",
    "HY_SPREAD": "BAMLH0A0HYM2",
    "IG_SPREAD": "BAMLC0A0CM",
    "CONSUMER_CREDIT": "TOTALSL",
    "CONSUMER_DELINQUENCY": "DRCCLACBS",
    "VIX": "VIXCLS",
    "FINANCIAL_CONDITIONS": "NFCI",
    "RECESSION_PROB": "RECPROUSM156N",
    "LENDING_STANDARDS": "DRTSCILM",
}

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


class FREDAdapter(BaseMacroAdapter):
    """Fetches macro indicators from FRED API."""

    async def get_indicator(self, indicator: str) -> DataEnvelope:
        series_id = FRED_SERIES.get(indicator)
        if not series_id:
            return DataEnvelope(
                data=[], source="fred", quality_score=0.0,
                warnings=[f"Unknown indicator: {indicator}"],
            )
        if not settings.has_fred():
            return DataEnvelope(
                data=[], source="fred", quality_score=0.0,
                warnings=["FRED_API_KEY not configured"],
            )

        params = {
            "series_id": series_id,
            "api_key": settings.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 500,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(FRED_BASE, params=params)
                resp.raise_for_status()
                obs = resp.json().get("observations", [])

            records = []
            for o in obs:
                val = o.get("value", ".")
                if val == ".":
                    continue
                records.append({
                    "indicator": indicator,
                    "observation_date": o["date"],
                    "value": float(val),
                    "unit": _unit_for(indicator),
                    "frequency": _freq_for(indicator),
                })
            return DataEnvelope(data=records, source="fred", source_label="official")
        except Exception as e:
            logger.error("FRED error for %s: %s", indicator, e)
            return DataEnvelope(data=[], source="fred", quality_score=0.0, warnings=[str(e)])

    async def get_all_indicators(self) -> dict[str, DataEnvelope]:
        """Fetch all configured macro indicators."""
        results = {}
        for indicator in FRED_SERIES:
            results[indicator] = await self.get_indicator(indicator)
        return results


def _unit_for(indicator: str) -> str:
    units = {
        "FED_FUNDS": "percent", "TREASURY_2Y": "percent", "TREASURY_10Y": "percent",
        "CPI_YOY": "index", "UNEMPLOYMENT": "percent", "INITIAL_CLAIMS": "thousands",
        "HY_SPREAD": "bps", "IG_SPREAD": "bps", "VIX": "index",
    }
    return units.get(indicator, "value")


def _freq_for(indicator: str) -> str:
    daily = {"FED_FUNDS", "TREASURY_2Y", "TREASURY_10Y", "HY_SPREAD", "IG_SPREAD", "VIX"}
    weekly = {"INITIAL_CLAIMS", "FINANCIAL_CONDITIONS"}
    if indicator in daily:
        return "daily"
    if indicator in weekly:
        return "weekly"
    return "monthly"
