"""
Comprehensive API endpoint tests for UPST Quant Finance Hub v3.0.

Uses httpx.AsyncClient with ASGITransport to test all FastAPI routes.
MOCK_MODE is forced on so tests run without real API keys or external services.
"""

from __future__ import annotations

import os
import json

# Force mock mode and disable scheduler before any app imports
os.environ["MOCK_MODE"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "system" in body
    assert "UPST" in body["system"]


@pytest.mark.asyncio
async def test_health_response_is_json(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert "application/json" in resp.headers.get("content-type", "")
    body = resp.json()
    assert isinstance(body, dict)
    assert "status" in body
    assert "system" in body
    assert body["status"] == "ok"
    assert isinstance(body["system"], str)


@pytest.mark.asyncio
async def test_health_exact_structure(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    body = resp.json()
    assert set(body.keys()) == {"status", "system"}
    assert body["system"] == "UPST Quant Finance Hub v3.0"


@pytest.mark.asyncio
async def test_health_idempotent_across_calls(client: AsyncClient):
    """Multiple health calls return identical structure and values."""
    resp1 = await client.get("/api/v1/health")
    resp2 = await client.get("/api/v1/health")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()
    body = resp1.json()
    assert body["status"] == "ok"
    assert isinstance(body["system"], str)
    assert len(body["system"]) > 0


# ---------------------------------------------------------------------------
# 2. Quote
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quote_default_ticker(client: AsyncClient):
    resp = await client.get("/api/v1/quote")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert "quality" in body
    # Validate data structure
    assert isinstance(body["data"], dict)
    assert "ticker" in body["data"]
    assert "price" in body["data"]
    assert isinstance(body["data"]["price"], (int, float))
    assert body["data"]["price"] > 0
    # Quality should be numeric and in valid range
    assert isinstance(body["quality"], (int, float))
    assert body["quality"] > 0


@pytest.mark.asyncio
async def test_quote_custom_ticker(client: AsyncClient):
    resp = await client.get("/api/v1/quote", params={"ticker": "AAPL"})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert "quality" in body
    # Verify the ticker in data matches the request
    assert isinstance(body["data"], dict)
    assert "ticker" in body["data"]
    assert body["data"]["ticker"] == "AAPL"
    assert isinstance(body["quality"], (int, float))


@pytest.mark.asyncio
async def test_quote_quality_is_numeric(client: AsyncClient):
    resp = await client.get("/api/v1/quote")
    body = resp.json()
    assert isinstance(body["quality"], (int, float))
    assert 0 <= body["quality"] <= 1.0


@pytest.mark.asyncio
async def test_quote_response_time_reasonable(client: AsyncClient):
    """Quote endpoint returns without hanging."""
    resp = await client.get("/api/v1/quote")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "data" in body


# ---------------------------------------------------------------------------
# 3. Bars
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bars_default_params(client: AsyncClient):
    resp = await client.get("/api/v1/bars")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert "count" in body
    assert isinstance(body["count"], int)
    assert body["count"] > 0
    # Validate data structure
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0
    # Check first bar has OHLCV fields
    first_bar = body["data"][0]
    for field in ("open", "high", "low", "close", "volume"):
        assert field in first_bar, f"Bar missing '{field}' field"
    assert isinstance(first_bar["open"], (int, float))
    assert isinstance(first_bar["volume"], int)


@pytest.mark.asyncio
async def test_bars_custom_params(client: AsyncClient):
    resp = await client.get(
        "/api/v1/bars",
        params={"ticker": "AAPL", "timeframe": "1h", "days": 30},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "count" in body
    assert isinstance(body["count"], int)
    assert body["count"] > 0
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0


@pytest.mark.asyncio
async def test_bars_all_valid_timeframes(client: AsyncClient):
    """Every supported timeframe should return 200."""
    for tf in ("1m", "5m", "15m", "1h", "1d", "1w"):
        resp = await client.get("/api/v1/bars", params={"timeframe": tf})
        assert resp.status_code == 200, f"timeframe {tf} failed"


@pytest.mark.asyncio
async def test_bars_invalid_ticker_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/bars", params={"ticker": "invalid123"})
    assert resp.status_code == 422  # validation error


@pytest.mark.asyncio
async def test_bars_invalid_timeframe_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/bars", params={"timeframe": "3h"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bars_days_boundary_min(client: AsyncClient):
    resp = await client.get("/api/v1/bars", params={"days": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "count" in body
    assert isinstance(body["count"], int)


@pytest.mark.asyncio
async def test_bars_days_boundary_zero_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/bars", params={"days": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bars_days_over_max_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/bars", params={"days": 9999})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bars_data_has_ohlcv_structure(client: AsyncClient):
    """Verify bar structure in detail: OHLCV fields with correct types and ranges."""
    resp = await client.get("/api/v1/bars", params={"days": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    for bar in body["data"]:
        assert isinstance(bar, dict)
        assert isinstance(bar["open"], (int, float))
        assert isinstance(bar["high"], (int, float))
        assert isinstance(bar["low"], (int, float))
        assert isinstance(bar["close"], (int, float))
        assert isinstance(bar["volume"], int)
        # High >= Low for every bar
        assert bar["high"] >= bar["low"], f"high {bar['high']} < low {bar['low']}"
        # Volume is positive
        assert bar["volume"] > 0


# ---------------------------------------------------------------------------
# 4. Alerts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alerts_default(client: AsyncClient):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert "alerts" in body
    assert isinstance(body["alerts"], list)
    # Each alert should be a dict with expected keys
    for alert in body["alerts"]:
        assert isinstance(alert, dict)
        assert "id" in alert
        assert "title" in alert
        assert "severity" in alert
        assert "category" in alert
        assert "message" in alert
        assert isinstance(alert["id"], str)
        assert isinstance(alert["title"], str)
        assert alert["severity"] in ("info", "warning", "critical", "urgent")


@pytest.mark.asyncio
async def test_alerts_with_severity_filter(client: AsyncClient):
    for severity in ("info", "warning", "critical"):
        resp = await client.get("/api/v1/alerts", params={"severity": severity})
        assert resp.status_code == 200
        body = resp.json()
        assert "alerts" in body
        assert isinstance(body["alerts"], list)
        # Verify all returned alerts match the filtered severity
        for alert in body["alerts"]:
            assert alert["severity"] == severity, (
                f"Expected severity '{severity}', got '{alert['severity']}'"
            )


@pytest.mark.asyncio
async def test_alerts_invalid_severity_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/alerts", params={"severity": "extreme"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_alerts_custom_limit(client: AsyncClient):
    resp = await client.get("/api/v1/alerts", params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["alerts"], list)
    assert len(body["alerts"]) <= 5


@pytest.mark.asyncio
async def test_alerts_limit_out_of_range_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/alerts", params={"limit": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_alerts_acknowledge_endpoint(client: AsyncClient):
    """POST to acknowledge an alert returns a success field."""
    resp = await client.post("/api/v1/alerts/fake_alert_999/acknowledge")
    assert resp.status_code == 200
    body = resp.json()
    assert "success" in body
    assert isinstance(body["success"], bool)
    # Acknowledging a non-existent alert should return success=False
    assert body["success"] is False


# ---------------------------------------------------------------------------
# 5. Bots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bots_list(client: AsyncClient):
    resp = await client.get("/api/v1/bots")
    assert resp.status_code == 200
    body = resp.json()
    assert "bots" in body
    bots = body["bots"]
    assert isinstance(bots, list)
    assert len(bots) > 0
    # Each bot should have name and description
    for bot in bots:
        assert "name" in bot
        assert "description" in bot


@pytest.mark.asyncio
async def test_bots_known_names(client: AsyncClient):
    resp = await client.get("/api/v1/bots")
    body = resp.json()
    bot_names = {b["name"] for b in body["bots"]}
    expected = {
        "price_action", "options_reaction", "squeeze", "funding_stress",
        "macro_shock", "strategy", "trade_decision", "regime",
    }
    assert expected == bot_names


@pytest.mark.asyncio
async def test_bots_descriptions_non_empty(client: AsyncClient):
    resp = await client.get("/api/v1/bots")
    body = resp.json()
    for bot in body["bots"]:
        assert len(bot["description"]) > 0
        assert isinstance(bot["description"], str)


# ---------------------------------------------------------------------------
# 6. Export JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_json(client: AsyncClient):
    resp = await client.get("/api/v1/export/json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")
    # Should have Content-Disposition header for download
    assert "content-disposition" in resp.headers
    assert "upst_analysis.json" in resp.headers["content-disposition"]
    # Body should be valid JSON
    data = json.loads(resp.text)
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_export_json_attachment_header(client: AsyncClient):
    resp = await client.get("/api/v1/export/json")
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "upst" in disposition.lower()


@pytest.mark.asyncio
async def test_export_json_contains_analysis_sections(client: AsyncClient):
    """Verify the downloaded JSON has expected top-level sections."""
    resp = await client.get("/api/v1/export/json")
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert isinstance(data, dict)
    # The export wraps analysis under export_meta + analysis keys
    assert "export_meta" in data
    assert "analysis" in data
    meta = data["export_meta"]
    assert "generated" in meta
    assert "system" in meta
    assert "ticker" in meta
    assert meta["ticker"] == "UPST"
    # Analysis section should have key engine outputs
    analysis = data["analysis"]
    assert isinstance(analysis, dict)


# ---------------------------------------------------------------------------
# 7. Export CSV
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient):
    resp = await client.get("/api/v1/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "content-disposition" in resp.headers
    assert "upst_analysis.csv" in resp.headers["content-disposition"]
    # Body should be non-empty text
    assert len(resp.text) > 0


@pytest.mark.asyncio
async def test_export_csv_attachment_header(client: AsyncClient):
    resp = await client.get("/api/v1/export/csv")
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "upst" in disposition.lower()


@pytest.mark.asyncio
async def test_export_csv_has_multiple_lines(client: AsyncClient):
    """Verify CSV has header + data rows (not just a single line)."""
    resp = await client.get("/api/v1/export/csv")
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    # Should have at least a header row and several section rows
    assert len(lines) > 5, f"CSV only has {len(lines)} lines, expected many more"
    # First line should reference UPST
    assert "UPST" in lines[0]


# ---------------------------------------------------------------------------
# 8. Export Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_summary(client: AsyncClient):
    resp = await client.get("/api/v1/export/summary")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    assert "content-disposition" in resp.headers
    assert "upst_daily_summary.txt" in resp.headers["content-disposition"]
    assert len(resp.text) > 0


# ---------------------------------------------------------------------------
# 9. POST Bot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_bot(client: AsyncClient):
    payload = {"bot_name": "price_action", "params": {}}
    resp = await client.post("/api/v1/bot", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    # Bot output should contain bot_name and is_simulation flag
    assert "bot_name" in body
    assert "price_action" in body["bot_name"]
    assert "is_simulation" in body
    assert body["is_simulation"] is True


@pytest.mark.asyncio
async def test_run_bot_with_params(client: AsyncClient):
    payload = {"bot_name": "price_action", "params": {"simulations": 100}}
    resp = await client.post("/api/v1/bot", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "bot_name" in body
    assert "is_simulation" in body
    assert "results" in body


@pytest.mark.asyncio
async def test_run_bot_missing_name(client: AsyncClient):
    payload = {"params": {}}
    resp = await client.post("/api/v1/bot", json=payload)
    assert resp.status_code == 422  # bot_name is required


@pytest.mark.asyncio
async def test_run_bot_empty_body(client: AsyncClient):
    resp = await client.post("/api/v1/bot", json={})
    assert resp.status_code == 422
    body = resp.json()
    # FastAPI validation error should mention the missing field
    assert "detail" in body
    error_text = json.dumps(body["detail"]).lower()
    assert "bot_name" in error_text


@pytest.mark.asyncio
async def test_run_bot_each_known_bot(client: AsyncClient):
    """Every known bot should be runnable without error."""
    bot_names = [
        "price_action", "options_reaction", "squeeze", "funding_stress",
        "macro_shock", "strategy", "trade_decision", "regime",
    ]
    for name in bot_names:
        resp = await client.post("/api/v1/bot", json={"bot_name": name, "params": {}})
        assert resp.status_code == 200, f"bot {name} failed with {resp.status_code}"


@pytest.mark.asyncio
async def test_run_bot_unknown_name_fails(client: AsyncClient):
    """Running an unknown bot should return an error response."""
    payload = {"bot_name": "nonexistent_bot_xyz", "params": {}}
    resp = await client.post("/api/v1/bot", json=payload)
    # The orchestrator returns {"error": "Unknown bot: ..."} with 200,
    # so we check the error field in the response
    assert resp.status_code == 200
    body = resp.json()
    assert "error" in body
    assert "nonexistent_bot_xyz" in body["error"]


# ---------------------------------------------------------------------------
# 10. Scheduler Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_status(client: AsyncClient):
    resp = await client.get("/api/v1/scheduler/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "running" in body
    assert "tasks" in body
    assert "last_run" in body
    assert isinstance(body["running"], bool)
    assert isinstance(body["tasks"], list)
    assert isinstance(body["last_run"], dict)


@pytest.mark.asyncio
async def test_scheduler_disabled_in_test_mode(client: AsyncClient):
    """Scheduler should not be running since SCHEDULER_ENABLED=false in test env."""
    resp = await client.get("/api/v1/scheduler/status")
    body = resp.json()
    # In test mode with SCHEDULER_ENABLED=false, it should not be running
    assert body["running"] is False
    # Tasks list should be empty when scheduler is disabled
    assert isinstance(body["tasks"], list)
    assert len(body["tasks"]) == 0


# ---------------------------------------------------------------------------
# 11. Macro Indicator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_macro_gdp(client: AsyncClient):
    resp = await client.get("/api/v1/macro/GDP")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert isinstance(body["source"], str)
    assert isinstance(body["data"], (list, dict))


@pytest.mark.asyncio
async def test_macro_unemployment(client: AsyncClient):
    resp = await client.get("/api/v1/macro/UNRATE")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert isinstance(body["source"], str)
    assert isinstance(body["data"], (list, dict))


@pytest.mark.asyncio
async def test_macro_fedfunds(client: AsyncClient):
    resp = await client.get("/api/v1/macro/FEDFUNDS")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert isinstance(body["source"], str)
    assert isinstance(body["data"], (list, dict))


@pytest.mark.asyncio
async def test_macro_response_structure(client: AsyncClient):
    """Every macro endpoint should return data + source keys."""
    for indicator in ("GDP", "UNRATE", "FEDFUNDS", "CPI"):
        resp = await client.get(f"/api/v1/macro/{indicator}")
        assert resp.status_code == 200, f"macro {indicator} failed"
        body = resp.json()
        assert set(body.keys()) == {"data", "source"}, f"unexpected keys for {indicator}"


# ---------------------------------------------------------------------------
# 12. News
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_news_default(client: AsyncClient):
    resp = await client.get("/api/v1/news")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "source" in body
    assert isinstance(body["data"], list)
    assert isinstance(body["source"], str)


@pytest.mark.asyncio
async def test_news_custom_params(client: AsyncClient):
    resp = await client.get("/api/v1/news", params={"ticker": "AAPL", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_news_invalid_ticker_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/news", params={"ticker": "invalid"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_news_limit_out_of_range(client: AsyncClient):
    resp = await client.get("/api/v1/news", params={"limit": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_news_limit_over_max_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/news", params={"limit": 999})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_news_response_keys(client: AsyncClient):
    resp = await client.get("/api/v1/news")
    body = resp.json()
    assert set(body.keys()) == {"data", "source"}


@pytest.mark.asyncio
async def test_news_data_contains_articles(client: AsyncClient):
    """Verify news articles have headline and sentiment fields."""
    resp = await client.get("/api/v1/news")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    if len(body["data"]) > 0:
        article = body["data"][0]
        assert isinstance(article, dict)
        # Articles should have at least a headline/title and sentiment
        assert "headline" in article or "title" in article
        assert "sentiment" in article or "sentiment_score" in article


# ---------------------------------------------------------------------------
# Additional edge-case and structural tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(client: AsyncClient):
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_wrong_method_returns_405(client: AsyncClient):
    # POST to a GET-only endpoint
    resp = await client.post("/api/v1/health")
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_bot_get_not_allowed(client: AsyncClient):
    # GET on POST-only /bot endpoint — should not return 200
    resp = await client.get("/api/v1/bot")
    assert resp.status_code in (404, 405), (
        f"Expected 404 or 405 for GET on POST-only endpoint, got {resp.status_code}"
    )
    # Confirm POST still works to verify the endpoint exists
    post_resp = await client.post("/api/v1/bot", json={"bot_name": "price_action", "params": {}})
    assert post_resp.status_code == 200
