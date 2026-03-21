"""
Alert Generation Service — Monitors analysis outputs and generates
actionable alerts based on thresholds and conditions.

Covers all institutional alert categories:
- Price action (breakout, breakdown, support/resistance proximity)
- Options flow (IV spikes, put/call extremes, unusual flow)
- Short / squeeze (SI spikes, squeeze risk, borrow cost, DO NOT SHORT)
- Funding (new deals, expiry approaching, covenant mentions)
- Origination (volume updates, collapse detection)
- Macro (threshold changes, rate moves, world-news shocks)
- Valuation (extreme levels)
- Model / data (drift, forecast collapse, signal conflict, quality)
- SPY / beta (divergence, regime shift)
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
    category: str  # price | options | short | funding | origination | macro | valuation | model | data | spy | risk
    title: str
    message: str
    value: float | None = None
    threshold: float | None = None
    action_required: bool = False
    acknowledged: bool = False


class AlertService:
    """Generates alerts from analysis outputs across all institutional categories."""

    def __init__(self):
        self._alerts: list[Alert] = []
        self._alert_counter = 0
        self._lock = threading.Lock()

    def evaluate(self, analysis: dict) -> list[Alert]:
        """Run all alert rules against current analysis."""
        new_alerts = []
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        new_alerts.extend(self._price_alerts(analysis, now))
        new_alerts.extend(self._options_alerts(analysis, now))
        new_alerts.extend(self._short_alerts(analysis, now))
        new_alerts.extend(self._funding_alerts(analysis, now))
        new_alerts.extend(self._origination_alerts(analysis, now))
        new_alerts.extend(self._macro_alerts(analysis, now))
        new_alerts.extend(self._valuation_alerts(analysis, now))
        new_alerts.extend(self._score_alerts(analysis, now))
        new_alerts.extend(self._risk_alerts(analysis, now))
        new_alerts.extend(self._spy_alerts(analysis, now))
        new_alerts.extend(self._model_alerts(analysis, now))
        new_alerts.extend(self._data_quality_alerts(analysis, now))

        with self._lock:
            self._alerts = new_alerts + self._alerts
            self._alerts = self._alerts[:200]  # keep last 200

        return new_alerts

    # ── Price / Technical Alerts ──

    def _price_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        price = analysis.get("price", 0)
        if price <= 0:
            return alerts

        tech = analysis.get("technical", {})

        # Price near support
        supports = tech.get("support_levels", [])
        if supports:
            nearest_support = supports[0]
            if nearest_support > 0 and (price - nearest_support) / price < 0.02:
                alerts.append(self._make_alert(
                    now, "warning", "price",
                    "Price Near Support",
                    f"UPST at ${price:.2f}, within 2% of support at ${nearest_support:.2f}",
                    value=price, threshold=nearest_support,
                ))

        # Price near resistance
        resistances = tech.get("resistance_levels", [])
        if resistances:
            nearest_resistance = resistances[0]
            if nearest_resistance > 0 and (nearest_resistance - price) / price < 0.02:
                alerts.append(self._make_alert(
                    now, "info", "price",
                    "Price Near Resistance",
                    f"UPST at ${price:.2f}, within 2% of resistance at ${nearest_resistance:.2f}",
                    value=price, threshold=nearest_resistance,
                ))

        # Volatility expansion
        vol_regime = tech.get("volatility_regime", "normal")
        if vol_regime == "expanded":
            alerts.append(self._make_alert(
                now, "warning", "price",
                "Volatility Expansion",
                "Short-term volatility significantly above long-term — breakout/breakdown likely",
            ))

        # Breakout detection
        trend_signal = tech.get("trend_signal", "")
        if trend_signal == "breakout":
            alerts.append(self._make_alert(
                now, "critical", "price",
                "Price Breakout Detected",
                f"UPST breaking out above resistance — momentum acceleration at ${price:.2f}",
                value=price, action_required=True,
            ))
        elif trend_signal == "breakdown":
            alerts.append(self._make_alert(
                now, "critical", "price",
                "Price Breakdown Detected",
                f"UPST breaking below support — downside acceleration at ${price:.2f}",
                value=price, action_required=True,
            ))

        return alerts

    # ── Options / Volatility Alerts ──

    def _options_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        options = analysis.get("options", {})

        # Extreme IV
        atm_iv = options.get("atm_iv", 0)
        if atm_iv and atm_iv > 1.0:
            alerts.append(self._make_alert(
                now, "critical", "options",
                "Extreme Implied Volatility",
                f"ATM IV at {atm_iv*100:.0f}% — market pricing massive move",
                value=atm_iv * 100, threshold=100,
            ))

        # IV spike detection (rapid IV increase)
        iv_percentile = options.get("iv_percentile", 50)
        if iv_percentile and iv_percentile > 90:
            alerts.append(self._make_alert(
                now, "warning", "options",
                "IV at Extreme Percentile",
                f"IV percentile at {iv_percentile:.0f}th — historically elevated",
                value=iv_percentile, threshold=90,
            ))

        # Elevated put/call ratio
        pc_ratio = options.get("put_call_volume_ratio", 0)
        if pc_ratio and pc_ratio > 2.0:
            alerts.append(self._make_alert(
                now, "warning", "options",
                "Elevated Put/Call Ratio",
                f"P/C ratio at {pc_ratio:.2f} — heavy put buying detected",
                value=pc_ratio, threshold=2.0,
            ))
        elif pc_ratio and pc_ratio < 0.4:
            alerts.append(self._make_alert(
                now, "info", "options",
                "Extremely Low Put/Call Ratio",
                f"P/C ratio at {pc_ratio:.2f} — heavy call speculation / complacency",
                value=pc_ratio, threshold=0.4,
            ))

        # Unusual options flow
        unusual_flow = options.get("unusual_activity", [])
        if isinstance(unusual_flow, list) and len(unusual_flow) >= 3:
            alerts.append(self._make_alert(
                now, "warning", "options",
                "Unusual Options Activity",
                f"{len(unusual_flow)} unusual options trades detected — institutional flow possible",
                value=len(unusual_flow), threshold=3, action_required=True,
            ))

        # Large call/put sweeps
        call_sweep = options.get("large_call_sweep", False)
        if call_sweep:
            alerts.append(self._make_alert(
                now, "info", "options",
                "Large Call Sweep Detected",
                "Aggressive call sweep activity — bullish institutional positioning",
                action_required=True,
            ))
        put_sweep = options.get("large_put_sweep", False)
        if put_sweep:
            alerts.append(self._make_alert(
                now, "warning", "options",
                "Large Put Sweep Detected",
                "Aggressive put sweep activity — bearish institutional positioning",
                action_required=True,
            ))

        return alerts

    # ── Short / Squeeze Alerts ──

    def _short_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        short = analysis.get("short", {})

        squeeze = short.get("squeeze_risk_score", 0)
        if squeeze and squeeze > 75:
            alerts.append(self._make_alert(
                now, "critical", "short",
                "Squeeze Risk Elevated",
                f"Squeeze risk score {squeeze:.0f}/100 — short covering cascade possible",
                value=squeeze, threshold=75, action_required=True,
            ))

        if short.get("do_not_short_flag"):
            alerts.append(self._make_alert(
                now, "urgent", "short",
                "DO NOT SHORT Flag Active",
                "Short conditions extremely unfavorable — avoid new short positions",
                action_required=True,
            ))

        # Short interest spike
        si_change = short.get("short_interest_change_pct", 0)
        if si_change and abs(si_change) > 15:
            direction = "increased" if si_change > 0 else "decreased"
            alerts.append(self._make_alert(
                now, "warning", "short",
                f"Short Interest {direction.title()} Sharply",
                f"SI changed {si_change:+.1f}% — significant positioning shift",
                value=si_change, threshold=15,
            ))

        # Borrow cost spike
        borrow_cost = short.get("cost_to_borrow", 0)
        if borrow_cost and borrow_cost > 30:
            alerts.append(self._make_alert(
                now, "warning", "short",
                "Borrow Cost Spike",
                f"Cost to borrow at {borrow_cost:.1f}% — short maintenance expensive",
                value=borrow_cost, threshold=30,
            ))

        # Utilization extreme
        utilization = short.get("utilization", 0)
        if utilization and utilization > 90:
            alerts.append(self._make_alert(
                now, "critical", "short",
                "Share Utilization Extreme",
                f"Utilization at {utilization:.0f}% — very few shares available to borrow",
                value=utilization, threshold=90,
            ))

        return alerts

    # ── Funding Alerts ──

    def _funding_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        funding = analysis.get("funding", {})

        # New funding deal
        if funding.get("new_deal_detected"):
            alerts.append(self._make_alert(
                now, "info", "funding",
                "New Funding Deal Detected",
                f"New funding facility or securitization announced",
            ))

        # Funding expiry approaching
        months_to_expiry = funding.get("nearest_expiry_months", 999)
        if months_to_expiry < 3:
            alerts.append(self._make_alert(
                now, "critical", "funding",
                "Funding Expiry Approaching",
                f"Nearest facility expiry in {months_to_expiry:.0f} months — renewal risk",
                value=months_to_expiry, threshold=3, action_required=True,
            ))
        elif months_to_expiry < 6:
            alerts.append(self._make_alert(
                now, "warning", "funding",
                "Funding Expiry Watch",
                f"Facility expiry in {months_to_expiry:.0f} months — monitor renewal",
                value=months_to_expiry, threshold=6,
            ))

        # Covenant / waiver mention
        if funding.get("covenant_mention_detected"):
            alerts.append(self._make_alert(
                now, "critical", "funding",
                "Covenant / Waiver Mention Detected",
                "Filing or report mentions covenant test or waiver — review immediately",
                action_required=True,
            ))

        # Concentration risk
        concentration = funding.get("concentration_risk", 0)
        if concentration and concentration > 40:
            alerts.append(self._make_alert(
                now, "warning", "funding",
                "Funding Concentration Risk",
                f"Top partner at {concentration:.0f}% of capacity — diversification concern",
                value=concentration, threshold=40,
            ))

        return alerts

    # ── Origination Alerts ──

    def _origination_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        orig = analysis.get("origination", {})

        # Origination update
        if orig.get("new_data_available"):
            growth = orig.get("qoq_growth", 0)
            alerts.append(self._make_alert(
                now, "info", "origination",
                "Origination Data Update",
                f"New origination data: QoQ growth {growth:+.1f}%",
                value=growth,
            ))

        # Origination collapse
        yoy_growth = orig.get("yoy_growth", 0)
        if yoy_growth and yoy_growth < -30:
            alerts.append(self._make_alert(
                now, "critical", "origination",
                "Origination Volume Collapse",
                f"YoY origination growth at {yoy_growth:.1f}% — severe business deterioration",
                value=yoy_growth, threshold=-30, action_required=True,
            ))

        return alerts

    # ── Macro Alerts ──

    def _macro_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        macro = analysis.get("macro", {})

        # Rate regime change
        rate_regime = macro.get("rate_regime_change")
        if rate_regime:
            alerts.append(self._make_alert(
                now, "warning", "macro",
                "Rate Regime Change",
                f"Interest rate regime shifted to '{rate_regime}' — reassess rate sensitivity",
            ))

        # Yield curve inversion
        yield_curve = macro.get("yield_curve_slope", 0)
        if yield_curve and yield_curve < -0.2:
            alerts.append(self._make_alert(
                now, "warning", "macro",
                "Yield Curve Deeply Inverted",
                f"2s10s at {yield_curve:.2f}% — recession signal elevated",
                value=yield_curve, threshold=-0.2,
            ))

        # Credit spread widening
        hy_spread = macro.get("hy_spread", 0)
        if hy_spread and hy_spread > 500:
            alerts.append(self._make_alert(
                now, "critical", "macro",
                "Credit Spreads Widening",
                f"HY spread at {hy_spread:.0f}bps — credit stress, UPST highly sensitive",
                value=hy_spread, threshold=500, action_required=True,
            ))

        # World / geopolitical risk
        world_risk = macro.get("world_risk_level")
        if world_risk == "elevated":
            alerts.append(self._make_alert(
                now, "warning", "macro",
                "World Risk Event",
                "Elevated geopolitical / world risk — risk-off pressure on growth names",
            ))

        return alerts

    # ── Valuation Alerts ──

    def _valuation_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        val = analysis.get("valuation", {})

        # Extreme cheapness
        attractiveness = val.get("valuation_attractiveness_score", 50)
        if attractiveness and attractiveness > 85:
            alerts.append(self._make_alert(
                now, "info", "valuation",
                "Valuation Extremely Attractive",
                f"Valuation attractiveness at {attractiveness:.0f}/100 — significantly below fair value",
                value=attractiveness, threshold=85,
            ))
        elif attractiveness and attractiveness < 15:
            alerts.append(self._make_alert(
                now, "warning", "valuation",
                "Valuation Extremely Stretched",
                f"Valuation attractiveness at {attractiveness:.0f}/100 — priced well above fair value",
                value=attractiveness, threshold=15,
            ))

        return alerts

    # ── Composite Score Alerts ──

    def _score_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        scores = analysis.get("scores", {})
        composite = scores.get("composite_opportunity", {})
        comp_val = composite.get("value", 50) if isinstance(composite, dict) else 50

        if comp_val > 75:
            alerts.append(self._make_alert(
                now, "info", "risk",
                "High Composite Opportunity",
                f"Composite score {comp_val:.0f}/100 — strong opportunity detected",
                value=comp_val, threshold=75,
            ))
        elif comp_val < 25:
            alerts.append(self._make_alert(
                now, "warning", "risk",
                "Low Composite Score",
                f"Composite score {comp_val:.0f}/100 — unfavorable conditions",
                value=comp_val, threshold=25,
            ))

        return alerts

    # ── Risk Alerts ──

    def _risk_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        risk = analysis.get("risk", {})

        max_dd = risk.get("max_drawdown", 0)
        if max_dd and abs(max_dd) > 30:
            alerts.append(self._make_alert(
                now, "warning", "risk",
                "Large Historical Drawdown",
                f"Max drawdown {max_dd:.1f}% — elevated risk profile",
                value=abs(max_dd), threshold=30,
            ))

        # Risk of ruin
        risk_of_ruin = risk.get("risk_of_ruin", 0)
        if risk_of_ruin and risk_of_ruin > 0.10:
            alerts.append(self._make_alert(
                now, "critical", "risk",
                "Risk of Ruin Elevated",
                f"Estimated risk of ruin at {risk_of_ruin*100:.1f}% — reduce position",
                value=risk_of_ruin * 100, threshold=10, action_required=True,
            ))

        return alerts

    # ── SPY / Beta Alerts ──

    def _spy_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        spy = analysis.get("spy_relationship", {})

        # Beta regime shift
        rolling_beta = spy.get("rolling_beta", 1.5)
        if rolling_beta and abs(rolling_beta - 1.5) > 0.5:
            alerts.append(self._make_alert(
                now, "warning", "spy",
                "Beta Regime Shift",
                f"Rolling beta vs SPY at {rolling_beta:.2f} — diverging from historical norm of ~1.5",
                value=rolling_beta, threshold=1.5,
            ))

        # SPY divergence
        relative_divergence = spy.get("relative_strength_divergence", 0)
        if relative_divergence and abs(relative_divergence) > 2.0:
            direction = "outperforming" if relative_divergence > 0 else "underperforming"
            alerts.append(self._make_alert(
                now, "info", "spy",
                f"SPY Relative Divergence",
                f"UPST {direction} SPY by {abs(relative_divergence):.1f} z-scores",
                value=relative_divergence,
            ))

        # Correlation breakdown
        rolling_corr = spy.get("rolling_correlation", 0.5)
        if rolling_corr is not None and rolling_corr < 0.15:
            alerts.append(self._make_alert(
                now, "info", "spy",
                "Correlation Breakdown vs SPY",
                f"Rolling correlation at {rolling_corr:.2f} — UPST trading idiosyncratically",
                value=rolling_corr, threshold=0.15,
            ))

        return alerts

    # ── Model / Forecast Alerts ──

    def _model_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []

        # Model drift
        learning = analysis.get("learning", {})
        if learning.get("model_drift_detected"):
            alerts.append(self._make_alert(
                now, "warning", "model",
                "Model Drift Detected",
                "Prediction accuracy has deteriorated — models may need recalibration",
                action_required=True,
            ))

        # Forecast confidence collapse
        forecast = analysis.get("forecast", {})
        conf = forecast.get("confidence_score", 50)
        if conf and conf < 20:
            alerts.append(self._make_alert(
                now, "warning", "model",
                "Forecast Confidence Collapse",
                f"Ensemble forecast confidence at {conf:.0f}/100 — high uncertainty, reduce sizing",
                value=conf, threshold=20, action_required=True,
            ))

        # Signal conflict / no-edge condition
        td = analysis.get("trade_decision", {})
        if td.get("signal_conflict") or td.get("trade_quality") == "poor":
            alerts.append(self._make_alert(
                now, "info", "model",
                "Signal Conflict / No Edge",
                "Multiple signals disagree — no clear directional edge detected",
            ))

        # Overfitting warning
        overfit = analysis.get("overfitting", {})
        overfit_level = overfit.get("overfitting_risk_level", "")
        if overfit_level in ("high", "critical"):
            alerts.append(self._make_alert(
                now, "warning", "model",
                "Overfitting Risk Elevated",
                f"Overfitting risk level: {overfit_level} — signals may be spurious",
                action_required=True,
            ))

        return alerts

    # ── Data Quality Alerts ──

    def _data_quality_alerts(self, analysis: dict, now: str) -> list[Alert]:
        alerts = []
        warnings = analysis.get("warnings", [])
        if len(warnings) > 3:
            alerts.append(self._make_alert(
                now, "warning", "data",
                "Multiple Data Warnings",
                f"{len(warnings)} data quality warnings — review data sources",
            ))

        # Stale data
        governance = analysis.get("data_governance", {})
        stale_sources = governance.get("stale_sources", [])
        if isinstance(stale_sources, list) and len(stale_sources) > 0:
            alerts.append(self._make_alert(
                now, "warning", "data",
                "Stale Data Sources",
                f"{len(stale_sources)} data sources are stale: {', '.join(stale_sources[:3])}",
            ))

        return alerts

    # ── Public Interface ──

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
