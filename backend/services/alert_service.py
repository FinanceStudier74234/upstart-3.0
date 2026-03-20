"""
Alert Generation Service — Monitors analysis outputs and generates
actionable alerts based on thresholds and conditions.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    id: str
    timestamp: str
    severity: str  # info | warning | critical | urgent
    category: str  # price | options | short | funding | macro | risk | data
    title: str
    message: str
    value: float | None = None
    threshold: float | None = None
    action_required: bool = False
    acknowledged: bool = False


class AlertService:
    """Generates alerts from analysis outputs."""

    def __init__(self):
        self._alerts: list[Alert] = []
        self._alert_counter = 0
        self._lock = threading.Lock()

    def evaluate(self, analysis: dict) -> list[Alert]:
        """Run all alert rules against current analysis."""
        new_alerts = []
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        # Price alerts
        price = analysis.get("price", 0)
        if price > 0:
            tech = analysis.get("technical", {})
            # Price near support
            supports = tech.get("support_levels", [])
            if supports and price > 0:
                nearest_support = supports[0] if supports else 0
                if nearest_support > 0 and (price - nearest_support) / price < 0.02:
                    new_alerts.append(self._make_alert(
                        now, "warning", "price",
                        "Price Near Support",
                        f"UPST at ${price:.2f}, within 2% of support at ${nearest_support:.2f}",
                        value=price, threshold=nearest_support,
                    ))

            # Volatility expansion
            vol_regime = tech.get("volatility_regime", "normal")
            if vol_regime == "expanded":
                new_alerts.append(self._make_alert(
                    now, "warning", "price",
                    "Volatility Expansion",
                    "Short-term volatility significantly above long-term — breakout/breakdown likely",
                ))

        # Options alerts
        options = analysis.get("options", {})
        atm_iv = options.get("atm_iv", 0)
        if atm_iv and atm_iv > 1.0:
            new_alerts.append(self._make_alert(
                now, "critical", "options",
                "Extreme Implied Volatility",
                f"ATM IV at {atm_iv*100:.0f}% — market pricing massive move",
                value=atm_iv * 100, threshold=100,
            ))
        pc_ratio = options.get("put_call_volume_ratio", 0)
        if pc_ratio and pc_ratio > 2.0:
            new_alerts.append(self._make_alert(
                now, "warning", "options",
                "Elevated Put/Call Ratio",
                f"P/C ratio at {pc_ratio:.2f} — heavy put buying detected",
                value=pc_ratio, threshold=2.0,
            ))

        # Short / squeeze alerts
        short = analysis.get("short", {})
        squeeze = short.get("squeeze_risk_score", 0)
        if squeeze and squeeze > 75:
            new_alerts.append(self._make_alert(
                now, "critical", "short",
                "Squeeze Risk Elevated",
                f"Squeeze risk score {squeeze:.0f}/100 — short covering cascade possible",
                value=squeeze, threshold=75, action_required=True,
            ))
        if short.get("do_not_short_flag"):
            new_alerts.append(self._make_alert(
                now, "urgent", "short",
                "DO NOT SHORT Flag Active",
                "Short conditions extremely unfavorable — avoid new short positions",
                action_required=True,
            ))

        # Score alerts
        scores = analysis.get("scores", {})
        composite = scores.get("composite_opportunity", {})
        if isinstance(composite, dict):
            comp_val = composite.get("value", 50)
        else:
            comp_val = 50
        if comp_val > 75:
            new_alerts.append(self._make_alert(
                now, "info", "risk",
                "High Composite Opportunity",
                f"Composite score {comp_val:.0f}/100 — strong opportunity detected",
                value=comp_val, threshold=75,
            ))
        elif comp_val < 25:
            new_alerts.append(self._make_alert(
                now, "warning", "risk",
                "Low Composite Score",
                f"Composite score {comp_val:.0f}/100 — unfavorable conditions",
                value=comp_val, threshold=25,
            ))

        # Risk alerts
        risk = analysis.get("risk", {})
        max_dd = risk.get("max_drawdown", 0)
        if max_dd and abs(max_dd) > 30:
            new_alerts.append(self._make_alert(
                now, "warning", "risk",
                "Large Historical Drawdown",
                f"Max drawdown {max_dd:.1f}% — elevated risk profile",
                value=abs(max_dd), threshold=30,
            ))

        # Data quality alerts
        warnings = analysis.get("warnings", [])
        if len(warnings) > 3:
            new_alerts.append(self._make_alert(
                now, "warning", "data",
                "Multiple Data Warnings",
                f"{len(warnings)} data quality warnings — review data sources",
            ))

        with self._lock:
            self._alerts = new_alerts + self._alerts
            self._alerts = self._alerts[:100]  # keep last 100

        return new_alerts

    def get_alerts(self, severity: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            alerts = list(self._alerts)
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return [self._alert_to_dict(a) for a in alerts[:limit]]

    def acknowledge(self, alert_id: str) -> bool:
        with self._lock:
            for a in self._alerts:
                if a.id == alert_id:
                    a.acknowledged = True
                    return True
        return False

    def _make_alert(self, timestamp, severity, category, title, message,
                    value=None, threshold=None, action_required=False) -> Alert:
        with self._lock:
            self._alert_counter += 1
            alert_id = f"alert_{self._alert_counter}"
        return Alert(
            id=alert_id,
            timestamp=timestamp,
            severity=severity,
            category=category,
            title=title,
            message=message,
            value=value,
            threshold=threshold,
            action_required=action_required,
        )

    def _alert_to_dict(self, a: Alert) -> dict:
        return {
            "id": a.id, "timestamp": a.timestamp, "severity": a.severity,
            "category": a.category, "title": a.title, "message": a.message,
            "value": a.value, "threshold": a.threshold,
            "action_required": a.action_required, "acknowledged": a.acknowledged,
        }


# Singleton
alert_service = AlertService()
