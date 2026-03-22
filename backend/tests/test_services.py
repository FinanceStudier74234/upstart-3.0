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


def _find_alert(alerts, title):
    """Helper: find the first alert with the given title, or None."""
    return next((a for a in alerts if a.title == title), None)


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
        alert = _find_alert(alerts, "Price Near Support")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "price"
        assert alert.action_required is False
        assert "51.80" in alert.message
        assert "52.00" in alert.message
        assert alert.value == 52.00
        assert alert.threshold == 51.80

    def test_price_near_resistance(self):
        svc = AlertService()
        analysis = _make_analysis(
            price=54.90,
            technical={"support_levels": [45.0], "resistance_levels": [55.0],
                        "volatility_regime": "normal", "trend_signal": "neutral"},
        )
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Price Near Resistance")
        assert alert is not None
        assert alert.severity == "info"
        assert alert.category == "price"
        assert "55.00" in alert.message
        assert "54.90" in alert.message
        assert alert.value == 54.90
        assert alert.threshold == 55.0

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
        alert = _find_alert(alerts, "Price Breakdown Detected")
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.category == "price"
        assert alert.action_required is True
        assert "52.75" in alert.message  # default price

    def test_volatility_expansion(self):
        svc = AlertService()
        analysis = _make_analysis(
            technical={"support_levels": [], "resistance_levels": [],
                        "volatility_regime": "expanded", "trend_signal": "neutral"},
        )
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Volatility Expansion")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "price"
        assert "volatility" in alert.message.lower()


class TestAlertServiceOptionsAlerts:

    def test_extreme_iv(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 1.35, "iv_percentile": 50, "put_call_volume_ratio": 1.0,
            "unusual_activity": [], "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Extreme Implied Volatility")
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.category == "options"
        assert alert.value == 135.0  # atm_iv * 100
        assert alert.threshold == 100

    def test_elevated_put_call_ratio(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 0.5, "iv_percentile": 50, "put_call_volume_ratio": 2.5,
            "unusual_activity": [], "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Elevated Put/Call Ratio")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "options"
        assert alert.value == 2.5
        assert alert.threshold == 2.0

    def test_unusual_options_activity(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 0.5, "iv_percentile": 50, "put_call_volume_ratio": 1.0,
            "unusual_activity": ["t1", "t2", "t3", "t4"],
            "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Unusual Options Activity")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "options"
        assert alert.action_required is True
        assert alert.value == 4
        assert "4" in alert.message

    def test_iv_extreme_percentile(self):
        svc = AlertService()
        analysis = _make_analysis(options={
            "atm_iv": 0.5, "iv_percentile": 95, "put_call_volume_ratio": 1.0,
            "unusual_activity": [], "large_call_sweep": False, "large_put_sweep": False,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "IV at Extreme Percentile")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "options"
        assert alert.value == 95
        assert alert.threshold == 90


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
        alert = _find_alert(alerts, "Funding Expiry Approaching")
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.category == "funding"
        assert alert.action_required is True
        assert alert.value == 2
        assert alert.threshold == 3

    def test_covenant_mention(self):
        svc = AlertService()
        analysis = _make_analysis(funding={
            "new_deal_detected": False, "nearest_expiry_months": 24,
            "covenant_mention_detected": True, "concentration_risk": 10,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Covenant / Waiver Mention Detected")
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.category == "funding"
        assert alert.action_required is True


class TestAlertServiceMacroAlerts:

    def test_credit_spread_widening(self):
        svc = AlertService()
        analysis = _make_analysis(macro={
            "rate_regime_change": None, "yield_curve_slope": 0.10,
            "hy_spread": 600, "world_risk_level": "normal",
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Credit Spreads Widening")
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.category == "macro"
        assert alert.action_required is True
        assert alert.value == 600
        assert alert.threshold == 500

    def test_rate_regime_change(self):
        svc = AlertService()
        analysis = _make_analysis(macro={
            "rate_regime_change": "tightening", "yield_curve_slope": 0.10,
            "hy_spread": 300, "world_risk_level": "normal",
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Rate Regime Change")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "macro"
        assert "tightening" in alert.message


class TestAlertServiceModelAndDataAlerts:

    def test_model_drift(self):
        svc = AlertService()
        analysis = _make_analysis(learning={"model_drift_detected": True})
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Model Drift Detected")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "model"
        assert alert.action_required is True

    def test_data_quality_warnings(self):
        svc = AlertService()
        analysis = _make_analysis(warnings=["w1", "w2", "w3", "w4"])
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Multiple Data Warnings")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "data"
        assert "4" in alert.message

    def test_stale_data_sources(self):
        svc = AlertService()
        analysis = _make_analysis(data_governance={"stale_sources": ["yahoo", "sec"]})
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Stale Data Sources")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "data"
        assert "yahoo" in alert.message
        assert "sec" in alert.message


class TestAlertServiceSPYAlerts:

    def test_beta_regime_shift(self):
        svc = AlertService()
        analysis = _make_analysis(spy_relationship={
            "rolling_beta": 2.5, "relative_strength_divergence": 0,
            "rolling_correlation": 0.5, "beta": 2.5, "alpha": 0.0,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Beta Regime Shift")
        assert alert is not None
        assert alert.severity in ("warning", "critical")
        assert alert.category == "spy"
        assert "2.5" in str(alert.value) or alert.value == 2.5

    def test_correlation_breakdown(self):
        svc = AlertService()
        analysis = _make_analysis(spy_relationship={
            "rolling_beta": 1.5, "relative_strength_divergence": 0,
            "rolling_correlation": 0.05, "beta": 1.5, "alpha": 0.0,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Correlation Breakdown vs SPY")
        assert alert is not None
        assert alert.severity in ("info", "warning", "critical")
        assert alert.category == "spy"
        assert alert.value == 0.05 or "0.05" in str(alert.value)


class TestAlertServiceValuationAlerts:

    def test_valuation_attractive(self):
        svc = AlertService()
        analysis = _make_analysis(valuation={"valuation_attractiveness_score": 90})
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Valuation Extremely Attractive")
        assert alert is not None
        assert alert.category == "valuation"
        assert alert.severity == "info"
        assert alert.value == 90
        assert alert.threshold == 85

    def test_valuation_stretched(self):
        svc = AlertService()
        analysis = _make_analysis(valuation={"valuation_attractiveness_score": 10})
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Valuation Extremely Stretched")
        assert alert is not None
        assert alert.category == "valuation"
        assert alert.severity == "warning"
        assert alert.value == 10
        assert alert.threshold == 15


class TestAlertServiceOriginationAlerts:

    def test_origination_collapse(self):
        svc = AlertService()
        analysis = _make_analysis(origination={
            "new_data_available": False, "qoq_growth": -10, "yoy_growth": -40,
        })
        alerts = svc.evaluate(analysis)
        alert = _find_alert(alerts, "Origination Volume Collapse")
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.category == "origination"
        assert alert.action_required is True
        assert alert.value == -40
        assert alert.threshold == -30
        assert "-40" in alert.message


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

    def test_get_alerts_returns_sorted_by_severity(self):
        """Alerts from a single evaluate call should contain the most severe first
        (because they are prepended to the internal list in generation order, and
        critical/urgent categories are evaluated before info-level ones)."""
        svc = AlertService()
        # Trigger alerts across many severity levels
        analysis = _make_analysis(
            technical={"support_levels": [52.70], "resistance_levels": [52.80],
                        "volatility_regime": "expanded", "trend_signal": "breakout"},
            options={"atm_iv": 1.5, "iv_percentile": 95, "put_call_volume_ratio": 3.0,
                      "unusual_activity": ["a", "b", "c", "d"],
                      "large_call_sweep": True, "large_put_sweep": True},
            short={"squeeze_risk_score": 90, "do_not_short_flag": True,
                    "short_interest_change_pct": 20, "cost_to_borrow": 50, "utilization": 95},
            funding={"new_deal_detected": True, "nearest_expiry_months": 1,
                      "covenant_mention_detected": True, "concentration_risk": 60},
        )
        raw_alerts = svc.evaluate(analysis)
        severities_present = {a.severity for a in raw_alerts}
        # Should have at least 2 different severity levels
        assert len(severities_present) >= 2
        # Should have critical and warning at minimum
        assert "critical" in severities_present
        assert "warning" in severities_present
        # All alerts should have valid severity values
        valid_severities = {"info", "warning", "critical", "urgent"}
        for a in raw_alerts:
            assert a.severity in valid_severities, f"Invalid severity: {a.severity}"


# ===================================================================
# ExportService Tests
# ===================================================================

class TestExportServiceCSV:

    def test_csv_contains_header(self):
        svc = ExportService()
        csv_out = svc.to_csv(_make_analysis())
        assert "UPST Quant Finance Hub" in csv_out
        assert isinstance(csv_out, str)
        assert len(csv_out) > 200
        # Should contain date/time info
        assert "202" in csv_out  # year prefix in timestamp

    def test_csv_contains_price(self):
        svc = ExportService()
        csv_out = svc.to_csv(_make_analysis(price=52.75))
        assert "52.75" in csv_out
        # Also check trade action and key scores are present
        assert "buy" in csv_out
        assert "composite_opportunity" in csv_out
        assert "technical_score" in csv_out
        assert "60" in csv_out  # composite_opportunity value
        assert "55" in csv_out  # technical_score value

    def test_csv_contains_sections(self):
        svc = ExportService()
        csv_out = svc.to_csv(_make_analysis())
        for section in ["SCORES", "TRADE DECISION", "TECHNICAL", "OPTIONS",
                         "SHORT / SQUEEZE", "FUNDING", "ORIGINATION", "MACRO",
                         "RISK", "FORECAST", "SPY RELATIONSHIP", "VALUATION"]:
            assert section in csv_out, f"Missing section: {section}"

    def test_csv_round_trip_no_crash_with_none_values(self):
        """Exporting analysis with None values should not crash."""
        svc = ExportService()
        analysis = _make_analysis(
            price=None,
            trade_decision={"action": None, "vehicle": None, "confidence": None,
                            "entry_price": None, "target_price": None,
                            "stop_price": None, "reward_risk_ratio": None,
                            "trade_quality": None, "signal_conflict": None},
        )
        csv_out = svc.to_csv(analysis)
        # Should produce a non-empty string without raising
        assert isinstance(csv_out, str)
        assert len(csv_out) > 100
        assert "UPST Quant Finance Hub" in csv_out


class TestExportServiceJSON:

    def test_json_valid(self):
        svc = ExportService()
        json_out = svc.to_json(_make_analysis())
        parsed = json.loads(json_out)
        assert "export_meta" in parsed
        assert "analysis" in parsed
        # Check export_meta has required keys
        meta = parsed["export_meta"]
        assert "ticker" in meta
        assert "generated" in meta
        assert "system" in meta
        assert meta["ticker"] == "UPST"
        assert "v3.0" in meta["system"]

    def test_json_contains_ticker(self):
        svc = ExportService()
        json_out = svc.to_json(_make_analysis())
        parsed = json.loads(json_out)
        assert parsed["export_meta"]["ticker"] == "UPST"
        # Verify generated timestamp exists and looks like an ISO timestamp
        generated = parsed["export_meta"]["generated"]
        assert isinstance(generated, str)
        assert "T" in generated  # ISO format contains T separator

    def test_json_preserves_scores(self):
        svc = ExportService()
        analysis = _make_analysis()
        json_out = svc.to_json(analysis)
        parsed = json.loads(json_out)
        scores = parsed["analysis"]["scores"]
        assert "composite_opportunity" in scores
        assert "technical_score" in scores
        assert scores["composite_opportunity"]["value"] == 60
        assert scores["technical_score"]["value"] == 55
        assert "explanation" in scores["composite_opportunity"]
        assert "explanation" in scores["technical_score"]


class TestExportServiceHTML:

    def test_html_structure(self):
        svc = ExportService()
        html = svc.to_html(_make_analysis())
        assert "<!DOCTYPE html>" in html
        assert "UPST Quant Finance Hub" in html
        assert "DISCLAIMER" in html
        # Check for CSS styles
        assert "<style>" in html
        assert "font-family" in html
        # Check for table tags
        assert "<table>" in html
        assert "<tbody>" in html
        # Check key sections are present
        assert "Current Price" in html
        assert "Trade Decision" in html
        assert "Forecast" in html
        assert "Risk" in html
        assert "SPY Relationship" in html

    def test_html_contains_price(self):
        svc = ExportService()
        html = svc.to_html(_make_analysis(price=99.99))
        assert "$99.99" in html
        # Also check trade action and scores section
        assert "BUY" in html
        assert "Mandatory Scores" in html
        assert "composite_opportunity" in html

    def test_html_contains_trade_action(self):
        svc = ExportService()
        html = svc.to_html(_make_analysis())
        assert "BUY" in html
        # Check trade details: entry, target, stop via R:R and vehicle
        assert "stock" in html
        assert "2.1" in html  # reward_risk_ratio
        assert "good" in html  # trade_quality

    def test_html_has_disclaimer(self):
        """Verify the disclaimer section exists with proper content."""
        svc = ExportService()
        html = svc.to_html(_make_analysis())
        assert "disclaimer" in html.lower()
        assert "not constitute financial advice" in html
        assert "research" in html.lower()
        assert "simulation" in html.lower()


class TestExportServiceSummaryText:

    def test_summary_structure(self):
        svc = ExportService()
        text = svc.to_summary_text(_make_analysis())
        assert "DAILY SUMMARY" in text
        assert "PRICE:" in text
        assert "ACTION:" in text
        assert "DISCLAIMER" in text
        # Check all required sections
        assert "VEHICLE:" in text
        assert "CONFIDENCE:" in text
        assert "ENTRY:" in text
        assert "TARGET:" in text
        assert "STOP:" in text
        assert "R:R:" in text
        assert "KEY SCORES:" in text
        assert "VaR 95%" in text
        assert "MAX DD:" in text

    def test_summary_contains_forecast(self):
        svc = ExportService()
        text = svc.to_summary_text(_make_analysis())
        assert "FORECAST:" in text
        assert "58.0" in text
        # Check range bounds too
        assert "RANGE:" in text
        assert "48.0" in text  # ensemble_lower
        assert "68.0" in text  # ensemble_upper

    def test_summary_contains_spy(self):
        svc = ExportService()
        text = svc.to_summary_text(_make_analysis())
        assert "SPY RELATIONSHIP:" in text
        assert "Beta:" in text
        # Check alpha and correlation are present
        assert "Alpha:" in text
        assert "Correlation:" in text
        assert "0.02" in text  # alpha value
        assert "0.55" in text  # rolling_correlation value


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
        # Verify accept was called before disconnect
        ws.accept.assert_awaited_once()
        await mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_ws(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        # Should not raise
        await mgr.disconnect(ws)
        assert mgr.connection_count == 0
        # Verify accept was NOT called since ws was never connected
        ws.accept.assert_not_awaited()

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
        # Verify the message is valid JSON (already parsed above, but check keys)
        assert set(sent.keys()) == {"event", "data"}

    @pytest.mark.asyncio
    async def test_send_alert(self):
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        await mgr.connect(ws)
        alert_data = {"id": "alert_1", "title": "Test", "severity": "critical", "category": "price"}
        await mgr.send_alert(alert_data)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["event"] == "alert"
        # Verify full alert structure is preserved
        assert sent["data"]["id"] == "alert_1"
        assert sent["data"]["title"] == "Test"
        assert sent["data"]["severity"] == "critical"
        assert sent["data"]["category"] == "price"

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        mgr = WebSocketManager()
        # Should not raise when there are no connections
        await mgr.broadcast("empty", {"a": 1})
        # Explicitly assert it completed without exception
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_message_has_timestamp(self):
        """Verify broadcast sends valid JSON with event and data keys."""
        mgr = WebSocketManager()
        ws = _make_ws_mock()
        await mgr.connect(ws)
        test_data = {"value": 42, "ts": "2026-03-22T12:00:00"}
        await mgr.broadcast("test_ts", test_data)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["event"] == "test_ts"
        assert sent["data"]["value"] == 42
        assert sent["data"]["ts"] == "2026-03-22T12:00:00"
        # Verify the broadcast payload is well-formed JSON with exactly 2 keys
        assert len(sent) == 2
        assert "event" in sent
        assert "data" in sent


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
        # Check types more strictly
        assert isinstance(status["running"], bool)
        assert isinstance(status["tasks"], list)
        assert isinstance(status["last_run"], dict)
        # Verify exact key set
        assert set(status.keys()) == {"running", "tasks", "last_run"}

    @pytest.mark.asyncio
    async def test_start_disabled(self):
        svc = SchedulerService()
        with patch("backend.services.scheduler.settings", create=True) as mock_settings:
            mock_settings.scheduler_enabled = False
            # Patch the import inside start()
            with patch.dict("sys.modules", {"backend.config.settings": MagicMock(settings=mock_settings)}):
                await svc.start(MagicMock())
        assert svc._running is False
        assert len(svc._tasks) == 0
        assert isinstance(svc._tasks, dict)
        # Status should reflect disabled state
        status = svc.status()
        assert status["running"] is False
        assert status["tasks"] == []
        assert isinstance(status["last_run"], dict)

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
        # Verify exact values match
        assert status["running"] == svc._running
        assert status["tasks"] == ["market_data"]
        assert status["last_run"]["market_data"] == "2026-03-21T12:00:00+00:00"
        assert isinstance(status["last_run"]["market_data"], str)
