"""SEC EDGAR adapter — fetch filings, transcripts, and insider transactions."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from typing import Any

import aiohttp

from backend.adapters.base import DataEnvelope
from backend.config.settings import settings

logger = logging.getLogger(__name__)

_BASE = "https://efts.sec.gov/LATEST"
_EDGAR_BASE = "https://data.sec.gov"
_CIK_MAP = {"UPST": "0001647639"}  # Upstart Holdings CIK


class SECEdgarAdapter:
    """Fetches SEC filings, insider transactions, and institutional ownership."""

    def __init__(self):
        self._user_agent = settings.sec_edgar_user_agent
        self._session: aiohttp.ClientSession | None = None
        self._rate_limit_delay = 0.12  # SEC requires <= 10 req/s

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/json",
                },
            )
        return self._session

    async def _request(self, url: str) -> dict | None:
        await asyncio.sleep(self._rate_limit_delay)
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("SEC EDGAR %s returned %d", url, resp.status)
                    return None
                return await resp.json(content_type=None)
        except Exception as e:
            logger.error("SEC EDGAR request error: %s", e)
            return None

    async def get_filings(self, ticker: str, filing_types: list[str] | None = None,
                          limit: int = 40) -> DataEnvelope:
        """Fetch recent SEC filings for ticker."""
        cik = _CIK_MAP.get(ticker)
        if not cik:
            return DataEnvelope(data=[], source="sec_edgar", quality_score=0.0,
                                warnings=[f"No CIK mapping for {ticker}"])

        # EDGAR full-text search API
        url = f"{_BASE}/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms={','.join(filing_types or ['10-K', '10-Q', '8-K', 'DEF 14A'])}"
        data = await self._request(url)

        # Also try the submissions API
        submissions_url = f"{_EDGAR_BASE}/submissions/CIK{cik}.json"
        submissions = await self._request(submissions_url)

        filings = []
        if submissions:
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            descriptions = recent.get("primaryDocDescription", [])
            docs = recent.get("primaryDocument", [])

            for i in range(min(limit, len(forms))):
                form = forms[i] if i < len(forms) else ""
                if filing_types and form not in filing_types:
                    continue

                accession = accessions[i].replace("-", "") if i < len(accessions) else ""
                doc = docs[i] if i < len(docs) else ""
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}"
                    f"/{accession}/{doc}"
                ) if accession and doc else ""

                # Scan description for covenant/funding keywords
                desc = descriptions[i] if i < len(descriptions) else ""
                has_covenant = bool(re.search(
                    r'covenant|waiver|amendment|facility|warehouse|credit.line',
                    desc, re.IGNORECASE,
                ))
                has_funding = bool(re.search(
                    r'fund|securitiz|abs|warehouse|forward.flow|committed',
                    desc, re.IGNORECASE,
                ))

                filings.append({
                    "ticker": ticker,
                    "filing_type": form,
                    "filed_date": dates[i] if i < len(dates) else "",
                    "accession_number": accessions[i] if i < len(accessions) else "",
                    "description": desc,
                    "url": filing_url,
                    "has_covenant_mention": has_covenant,
                    "has_funding_mention": has_funding,
                })

        return DataEnvelope(
            data=filings, source="sec_edgar", source_label="official",
            confidence=0.95 if filings else 0.3,
        )

    async def get_insider_transactions(self, ticker: str, limit: int = 50) -> DataEnvelope:
        """Fetch insider transactions (Form 4) from SEC EDGAR."""
        cik = _CIK_MAP.get(ticker)
        if not cik:
            return DataEnvelope(data=[], source="sec_edgar", quality_score=0.0,
                                warnings=[f"No CIK for {ticker}"])

        # Fetch Form 4 filings
        submissions_url = f"{_EDGAR_BASE}/submissions/CIK{cik}.json"
        submissions = await self._request(submissions_url)

        transactions = []
        if submissions:
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])

            for i in range(min(len(forms), 200)):
                if forms[i] not in ("4", "4/A"):
                    continue
                if len(transactions) >= limit:
                    break
                transactions.append({
                    "ticker": ticker,
                    "filing_date": dates[i] if i < len(dates) else "",
                    "accession_number": accessions[i] if i < len(accessions) else "",
                    "form_type": forms[i],
                })

        return DataEnvelope(
            data=transactions, source="sec_edgar", source_label="official",
            confidence=0.90 if transactions else 0.3,
        )

    async def get_institutional_ownership(self, ticker: str) -> DataEnvelope:
        """Fetch 13F institutional ownership summary. Requires parsing; returns metadata."""
        cik = _CIK_MAP.get(ticker)
        if not cik:
            return DataEnvelope(data=[], source="sec_edgar", quality_score=0.0,
                                warnings=[f"No CIK for {ticker}"])

        # Company facts for shares outstanding
        facts_url = f"{_EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
        facts = await self._request(facts_url)

        shares_outstanding = None
        if facts:
            us_gaap = facts.get("facts", {}).get("us-gaap", {})
            shares_data = us_gaap.get("CommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
            if shares_data:
                shares_outstanding = shares_data[-1].get("val")

        return DataEnvelope(
            data={
                "ticker": ticker,
                "shares_outstanding": shares_outstanding,
                "source_note": "13F data requires specialized parsing; use EDGAR API for full coverage",
            },
            source="sec_edgar", source_label="official",
            confidence=0.7,
        )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
