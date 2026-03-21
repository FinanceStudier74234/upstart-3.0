"""
Comprehensive tests for backend services:
  - AlertService
  - ExportService
  - WebSocketManager
  - SchedulerService
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.services.alert_service import AlertService
from backend.services.export_service import ExportService
from backend.services.websocket_manager import WebSocketManager, MAX_CONNECTIONS
from backend.services.scheduler import SchedulerService


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_analysis(**overrides) -> dict:
    """Return a realistic mock analysis dict; override any top-level key."""
    base = {
        "price": 52.75,
        "technical": {
            "support_levels": [52.00],
            "resistance_levels": [55.00],
            "volatility_regime": "normal",
            "trend_signal": "neutral",
        },
        "options": {
            "atm_iv": 0.65,
            "iv_percentile": 55,
            "put_call_volume_ratio": 1.1,
            "unusual_activity": [],
            "large_call_sweep": False,
            "large_put_sweep": False,
        },
        "short": {
            "squeeze_risk_score": 30,
            "do_not_short_flag": False,
            "short_interest_change_pct": 2.0,
            "cost_to_borrow": 8.0,
            "utilization": 45,
        },
        "funding": {
            "new_deal_detected": False,
            "nearest_expiry_months": 18,
            "covenant_mention_detected": False,
            "concentration_risk": 20,
        },
        "origination": {
            "new_data_available": False,
            "qoq_growth": 5.0,
            "yoy_growth": 12.0,
        },
        "macro": {
            "rate_regime_change": None,
            "yield_curve_slope": 0.15,
            "hy_spread": 350,
            "world_risk_level": "normal",
        },
        "valuation": {
            "valuation_attractiveness_score": 55,
        },
        "scores": {
            "composite_opportunity": {"value": 60, "explanation": "Moderate opportunity"},
            "technical_score": {"value": 55, "explanation": "Neutral technicals"},
        },
        "risk": {
            "max_drawdown": -18,
            "risk_of_ruin": 0.03,
            "var_95_1d": 3.20,
            "recommended_size_pct": 4.0,
        },
        "spy_relationship": {
            "rolling_beta": 1.5,
            "relative_strength_divergence": 0.5,
            "rolling_correlation": 0.55,
            "beta": 1.55,
            "alpha": 0.02,
        },
        "learning": {"model_drift_detected": False},
        "forecast": {
            "confidence_score": 62,
            "ensemble_point": 58.0,
            "ensemble_lower": 48.0,
            "ensemble_upper": 68.0,
        },
        "trade_decision": {
            "action": "buy",
            "vehicle": "stock",
            "confidence": 0.72,
            "entry_price": 52.50,
            "target_price": 62.00,
            "stop_price": 48.00,
            "reward_risk_ratio": 2.1,
            "trade_quality": "good",
            "signal_conflict": False,
        },
        "warnings": [],
        "data_governance": {"stale_sources": []},
        "overfitting": {"overfitting_risk_level": "low"},
    }
    base.update(overrides)
    return base


# ===================================================================
# AlertService Tests
# ===================================================================

class TestAlertServicePriceAlerts:
    """Price / technical alert tests."""

    def test_no_alerts_on_normal_data(self):
        svc = AlertService()
        # Use price far from support/resistance so no price alerts fire
        analysis = _make_analysis(
            price=53.50,
            technical={"support_levels": [48.00], "resistance_levels": [60.00],
                        "volatility_regime": "normal", "trend_signal": "neutral"},
        )
        alerts = svc.evaluate(analysis)
        price_alerts = [a for a in alerts if a.category == "price"]
        assert len(price_alerts) == 0

    def test_price_near_support(self):
        svc = AlertService()
        # price 52.00, support at 51.80 => within 2%
        analysis = _make_analysis(
            price=52.00,
            technical={"support_levels": [51.80], "resistance_levels": [60.0],
                        "volatility_regime": "normal", "trend_signal": "neutral"},
        )
        alerts = svc.evaluate(analysis)
        titles = [a.title for a in alerts]
        assert "Price Near Support" in titles

    def test_price_near_resistance(self):
        svc = AlertService()
        analysis = _make_analysis(
            price=54.90,
            technical={"support_levels": [45.0], "resistance_levels": [55.0],
                        "volatility_regime": "normal", "trend_signal": "neutral"},
        )
        alerts = svc.evaluate(analysis)
        titles = [a.title for a in alerts]
        assert "Price Near Resistance" in titles

    def test_breakout_detected(self):
        svc = AlertService()
        analysis = _make_analysis(
            technical={"support_levels": [], "resistance_levels": [],
                        "volatility_regime": "normal", "trend_signal": "breakout"},
        )
        alerts = svc.evaluate(analysis)
        breakout = [a for a in alerts if a.title == "Price Breakout Detected"]
        assert len(breakout) == 1
        assert breakout[0].severity == "critical"
        assert breakout[0].action_required is True

    def test_breakdown_detected(self):
        svc = AlertService()
        analysis = _make_analysis(
            technical={"support_levels": [], "resistance_levels": [],
                        "volatility_regime": "normal", "trend_signal": "breakdown"},
        )
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Price Breakdown Detected" for a in alerts)

    def test_volatility_expansion(self):
        svc = AlertService()
        analysis = _make_analysis(
            technical={"support_levels": [], "resistance_levels": [],
                        "volatility_regime": "expanded", "trend_signal": "neutral"},
        )
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Volatility Expansion" for a in alerts)


class TestAlertServiceOptionsAlerts:

    def test_extreme_iv(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 1.35, "iv_percentile": 50, "put_call_volume_ratio": 1.0,
            "unusual_activity": [], "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Extreme Implied Volatility" for a in alerts)

    def test_elevated_put_call_ratio(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 0.5, "iv_percentile": 50, "put_call_volume_ratio": 2.5,
            "unusual_activity": [], "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Elevated Put/Call Ratio" for a in alerts)

    def test_unusual_options_activity(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 0.5, "iv_percentile": 50, "put_call_volume_ratio": 1.0,
            "unusual_activity": ["t1", "t2", "t3", "t4"],
            "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Unusual Options Activity" for a in alerts)

    def test_iv_extreme_percentile(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 0.5, "iv_percentile": 95, "put_call_volume_ratio": 1.0,
            "unusual_activity": [], "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "IV at Extreme Percentile" for a in alerts)


class TestAlertServiceShortAlerts:

    def test_squeeze_risk(self):
        svc = AlertService()
        analysis = _make_analysis(short={
            "squeeze_risk_score": 85, "do_not_short_flag": False,
            "short_interest_change_pct": 0, "cost_to_borrow": 5, "utilization": 50,
        })
        alerts = svc.evaluate(analysis)
        sq = [a for a in alerts if a.title == "Squeeze Risk Elevated"]
        assert len(sq) == 1
        assert sq[0].severity == "critical"

    def test_do_not_short_flag(self):
        svc = AlertService()
        analysis = _make_analysis(short={
            "squeeze_risk_score": 0, "do_not_short_flag": True,
            "short_interest_change_pct": 0, "cost_to_borrow": 5, "utilization": 50,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "DO NOT SHORT Flag Active" for a in alerts)
        dns = [a for a in alerts if a.title == "DO NOT SHORT Flag Active"][0]
        assert dns.severity == "urgent"


class TestAlertServiceFundingAlerts:

    def test_funding_expiry_critical(self):
        svc = AlertService()
        analysis = _make_analysis(funding={
            "new_deal_detected": False, "nearest_expiry_months": 2,
            "covenant_mention_detected": False, "concentration_risk": 10,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Funding Expiry Approaching" for a in alerts)

    def test_covenant_mention(self):
        svc = AlertService()
        analysis = _make_analysis(funding={
            "new_deal_detected": False, "nearest_expiry_months": 24,
            "covenant_mention_detected": True, "concentration_risk": 10,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Covenant / Waiver Mention Detected" for a in alerts)


class TestAlertServiceMacroAlerts:

    def test_credit_spread_widening(self):
        svc = AlertService()
        analysis = _make_analysis(macro={
            "rate_regime_change": None, "yield_curve_slope": 0.10,
            "hy_spread": 600, "world_risk_level": "normal",
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Credit Spreads Widening" for a in alerts)

    def test_rate_regime_change(self):
        svc = AlertService()
        analysis = _make_analysis(macro={
            "rate_regime_change": "tightening", "yield_curve_slope": 0.10,
            "hy_spread": 300, "world_risk_level": "normal",
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Rate Regime Change" for a in alerts)


class TestAlertServiceModelAndDataAlerts:

    def test_model_drift(self):
        svc = AlertService()
        analysis = _make_analysis(learning={"model_drift_detected": True})
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Model Drift Detected" for a in alerts)

    def test_data_quality_warnings(self):
        svc = AlertService()
        analysis = _make_analysis(warnings=["w1", "w2", "w3", "w4"])
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Multiple Data Warnings" for a in alerts)

    def test_stale_data_sources(self):
        svc = AlertService()
        analysis = _make_analysis(data_governance={"stale_sources": ["yahoo", "sec"]})
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Stale Data Sources" for a in alerts)


class TestAlertServiceSPYAlerts:

    def test_beta_regime_shift(self):
        svc = AlertService()
        analysis = _make_analysis(spy_relationship={
            "rolling_beta": 2.5, "relative_strength_divergence": 0,
            "rolling_correlation": 0.5, "beta": 2.5, "alpha": 0.0,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Beta Regime Shift" for a in alerts)

    def test_correlation_breakdown(self):
        svc = AlertService()
        analysis = _make_analysis(spy_relationship={
            "rolling_beta": 1.5, "relative_strength_divergence": 0,
            "rolling_correlation": 0.05, "beta": 1.5, "alpha": 0.0,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Correlation Breakdown vs SPY" for a in alerts)


class TestAlertServiceValuationAlerts:

    def test_valuation_attractive(self):
        svc = AlertService()
        analysis = _make_analysis(valuation={"valuation_attractiveness_score": 90})
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Valuation Extremely Attractive" for a in alerts)

    def test_valuation_stretched(self):
        svc = AlertService()
        analysis = _make_analysis(valuation={"valuation_attractiveness_score": 10})
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Valuation Extremely Stretched" for a in alerts)


class TestAlertServiceOriginationAlerts:

    def test_origination_collapse(self):
        svc = AlertService()
        analysis = _make_analysis(origination={
            "new_data_available": False, "qoq_growth": -10, "yoy_growth": -40,
        })
        alerts = svc.evaluate(analysis)
        assert any(a.title == "Origination Volume Collapse" for a in alerts)


class TestAlertServiceFiltering:

    def test_get_alerts_returns_dicts(self):
        svc = AlertService()
        # Trigger a few alerts
        analysis = _make_analysis(
            warnings=["w1", "w2", "w3", "w4"],
            short={"squeeze_risk_score": 90, "do_not_short_flag": True,
                    "short_interest_change_pct": 0, "cost_to_borrow": 5, "utilization": 50},
        )
        svc.evaluate(analysis)
        result = svc.get_alerts()
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "id" in result[0]
        assert "severity" in result[0]

    def test_get_alerts_severity_filter(self):
        svc = AlertService()
        analysis = _make_analysis(
            short={"squeeze_risk_score": 90, "do_not_short_flag": True,
                    "short_interest_change_pct": 0, "cost_to_borrow": 5, "utilization": 50},
            warnings=["w1", "w2", "w3", "w4"],
        )
        svc.evaluate(analysis)
        critical = svc.get_alerts(severity="critical")
        assert all(a["severity"] == "critical" for a in critical)
        urgent = svc.get_alerts(severity="urgent")
        assert all(a["severity"] == "urgent" for a in urgent)

    def test_get_alerts_limit(self):
        svc = AlertService()
        # Generate many alerts
        analysis = _make_analysis(
            technical={"support_levels": [52.70], "resistance_levels": [52.80],
                        "volatility_regime": "expanded", "trend_signal": "breakout"},
            options={"atm_iv": 1.5, "iv_percentile": 95, "put_call_volume_ratio": 3.0,
                      "unusual_activity": ["a", "b", "c", "d"],
                      "large_call_sweep": True, "large_put_sweep": True},
            short={"squeeze_risk_score": 90, "do_not_short_flag": True,
                    "short_interest_change_pct": 20, "cost_to_borrow": 50, "utilization": 95},
        )
        svc.evaluate(analysis)
        limited = svc.get_alerts(limit=3)
        assert len(limited) == 3

    def test_acknowledge(self):
        svc = AlertService()
        analysis = _make_analysis(warnings=["w1", "w2", "w3", "w4"])
        svc.evaluate(analysis)
        all_alerts = svc.get_alerts()
        alert_id = all_alerts[0]["id"]
        assert svc.acknowledge(alert_id) is True
        updated = svc.get_alerts()
        acked = [a for a in updated if a["id"] == alert_id][0]
        assert acked["acknowledged"] is True

    def test_acknowledge_nonexistent(self):
        svc = AlertService()
        assert svc.acknowledge("nonexistent_id_999") is False


# ===================================================================
# ExportService Tests
# ===================================================================

class TestExportServiceCSV:

    def test_csv_contains_header(self):
        svc = ExportService()
        csv_out = svc.to_csv(_make_analysis())
        assert "UPST Quant Finance Hub" in csv_out

    def test_csv_contains_price(self):
        svc = ExportService()
        csv_out = svc.to_csv(_make_analysis(price=52.75))
        assert "52.75" in csv_out

    def test_csv_contains_sections(self):
        svc = ExportService()
        csv_out = svc.to_csv(_make_analysis())
        for section in ["SCORES", "TRADE DECISION", "TECHNICAL", "OPTIONS",
                         "SHORT / SQUEEZE", "FUNDING", "ORIGINATION", "MACRO",
                         "RISK", "FORECAST", "SPY RELATIONSHIP", "VALUATION"]:
            assert section in csv_out, f"Missing section: {section}"


class TestExportServiceJSON:

    def test_json_valid(self):
        svc = ExportService()
        json_out = svc.to_json(_make_analysis())
        parsed = json.loads(json_out)
        assert "export_meta" in parsed
        assert "analysis" in parsed

    def test_json_contains_ticker(self):
        svc = ExportService()
        json_out = svc.to_json(_make_analysis())
        parsed = json.loads(json_out)
        assert parsed["export_meta"]["ticker"] == "UPST"

    def test_json_preserves_scores(self):
        svc = ExportService()
        analysis = _make_analysis()
        json_out = svc.to_json(analysis)
        parsed = json.loads(json_out)
        assert "composite_opportunity" in parsed["analysis"]["scores"]


class TestExportServiceHTML:

    def test_html_structure(self):
        svc = ExportService()
        html = svc.to_html(_make_analysis())
        assert "<!DOCTYPE html>" in html
        assert "UPST Quant Finance Hub" in html
        assert "DISCLAIMER" in html

    def test_html_contains_price(self):
        svc = ExportService()
        html = svc.to_html(_make_analysis(price=99.99))
        assert "$99.99" in html

    def test_html_contains_trade_action(self):
        svc = ExportService()
        html = svc.to_html(_make_analysis())
        assert "BUY" in html


class TestExportServiceSummaryText:

    def test_summary_structure(self):
        svc = ExportService()
        text = svc.to_summary_text(_make_analysis())
        assert "DAILY SUMMARY" in text
        assert "PRICE:" in text
        assert "ACTION:" in text
        assert "DISCLAIMER" in text

    def test_summary_contains_forecast(self):
        svc = ExportService()
        text = svc.to_summary_text(_make_analysis())
        assert "FORECAST:" in text
        assert "58.0" in text

    def test_summary_contains_spy(self):
        svc = ExportService()
        text = svc.to_summary_text(_make_analysis())
        assert "SPY RELATIONSHIP:" in text
        assert "Beta:" in text


# ===================================================================
# WebSocketManager Tests
# ===================================================================

def _make_ws_mock():
    """Create a mock WebSocket with async accept/close/send_text."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestWebSocketManager:

    @pytest.mark.asyncio
    async def test_connect_and_count(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        await mgr.connect(ws)
        assert mgr.connection_count == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        await mgr.connect(ws)
        assert mgr.connection_count == 1
        await mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_ws(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        # Should not raise
        await mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        mgr = WebSocketManager()
        ws1 = _make_ws_mock()
        ws2 = _make_ws_mock()
        await mgr.connect(ws1)
        await mgr.connect(ws2)
        await mgr.broadcast("test_event", {"key": "val"})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()
        sent = json.loads(ws1.send_text.call_args[0][0])
        assert sent["event"] == "test_event"
        assert sent["data"]["key"] == "val"

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self):
        mgr = WebSocketManager()
        good = _make_ws_mock()
        bad = _make_ws_mock()
        bad.send_text.side_effect = RuntimeError("connection lost")
        await mgr.connect(good)
        await mgr.connect(bad)
        assert mgr.connection_count == 2
        await mgr.broadcast("ping", {})
        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_max_connections_rejected(self):
        mgr = WebSocketManager()
        # Fill up to MAX_CONNECTIONS
        connected = []
        for _ in range(MAX_CONNECTIONS):
            ws = _make_ws_mock()
            await mgr.connect(ws)
            connected.append(ws)
        assert mgr.connection_count == MAX_CONNECTIONS

        # Next one should be rejected
        extra = _make_ws_mock()
        await mgr.connect(extra)
        assert mgr.connection_count == MAX_CONNECTIONS
        extra.close.assert_awaited_once()
        extra.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_price_update(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        await mgr.connect(ws)
        await mgr.send_price_update(55.50)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["event"] == "price_update"
        assert sent["data"]["price"] == 55.50
        assert sent["data"]["ticker"] == "UPST"

    @pytest.mark.asyncio
    async def test_send_alert(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        await mgr.connect(ws)
        await mgr.send_alert({"id": "alert_1", "title": "Test"})
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["event"] == "alert"
        assert sent["data"]["id"] == "alert_1"

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        mgr = WebSocketManager()
        # Should not raise when there are no connections
        await mgr.broadcast("empty", {"a": 1})


# ===================================================================
# SchedulerService Tests
# ===================================================================

class TestSchedulerService:

    def test_initial_status(self):
        svc = SchedulerService()
        status = svc.status()
        assert status["running"] is False
        assert status["tasks"] == []
        assert status["last_run"] == {}

    @pytest.mark.asyncio
    async def test_start_disabled(self):
        svc = SchedulerService()
        with patch("backend.services.scheduler.settings", create=True) as mock_settings:
            mock_settings.scheduler_enabled = False
            # Patch the import inside start()
            with patch.dict("sys.modules", {"backend.config.settings": MagicMock(settings=mock_settings)}):
                await svc.start(MagicMock())
        assert svc._running is False

    @pytest.mark.asyncio
    async def test_stop_clears_tasks(self):
        svc = SchedulerService()
        svc._running = True
        # Simulate a task
        dummy_task = asyncio.create_task(asyncio.sleep(999))
        svc._tasks["dummy"] = dummy_task
        await svc.stop()
        # Allow event loop to process the cancellation
        await asyncio.sleep(0)
        assert svc._running is False
        assert len(svc._tasks) == 0
        assert dummy_task.cancelled()

    def test_status_reflects_state(self):
        svc = SchedulerService()
        svc._running = True
        svc._last_run["market_data"] = "2026-03-21T12:00:00+00:00"
        svc._tasks["market_data"] = MagicMock()
        status = svc.status()
        assert status["running"] is True
        assert "market_data" in status["tasks"]
        assert "market_data" in status["last_run"]
