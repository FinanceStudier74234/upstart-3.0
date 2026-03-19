"""
Reporting / Export Service — CSV, JSON, and PDF export of analysis data.
"""

from __future__ import annotations

import csv
import io
import json
import datetime as dt
import logging

logger = logging.getLogger(__name__)


class ExportService:
    """Exports analysis data in various formats."""

    def to_csv(self, analysis: dict) -> str:
        """Export analysis as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["UPST Quant Finance Hub — Analysis Export"])
        writer.writerow(["Generated", dt.datetime.now(dt.timezone.utc).isoformat()])
        writer.writerow(["Ticker", "UPST"])
        writer.writerow(["Price", analysis.get("price", "")])
        writer.writerow([])

        # Scores
        writer.writerow(["=== SCORES ==="])
        writer.writerow(["Score Name", "Value", "Explanation"])
        scores = analysis.get("scores", {})
        for name, data in scores.items():
            if isinstance(data, dict):
                writer.writerow([name, data.get("value", ""), data.get("explanation", "")])
            else:
                writer.writerow([name, data, ""])
        writer.writerow([])

        # Trade Decision
        writer.writerow(["=== TRADE DECISION ==="])
        td = analysis.get("trade_decision", {})
        for k, v in td.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Technical
        writer.writerow(["=== TECHNICAL ==="])
        tech = analysis.get("technical", {})
        for k, v in tech.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Options
        writer.writerow(["=== OPTIONS ==="])
        opts = analysis.get("options", {})
        for k, v in opts.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Short
        writer.writerow(["=== SHORT / SQUEEZE ==="])
        short = analysis.get("short", {})
        for k, v in short.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Risk
        writer.writerow(["=== RISK ==="])
        risk = analysis.get("risk", {})
        for k, v in risk.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Forecast
        writer.writerow(["=== FORECAST ==="])
        fc = analysis.get("forecast", {})
        for k, v in fc.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # SPY Relationship
        writer.writerow(["=== SPY RELATIONSHIP ==="])
        spy = analysis.get("spy_relationship", {})
        for k, v in spy.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])

        return output.getvalue()

    def to_json(self, analysis: dict) -> str:
        """Export analysis as formatted JSON."""
        export = {
            "export_meta": {
                "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
                "system": "UPST Quant Finance Hub v3.0",
                "ticker": "UPST",
            },
            "analysis": analysis,
        }
        return json.dumps(export, indent=2, default=str)

    def to_summary_text(self, analysis: dict) -> str:
        """Generate a plain-text daily summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("UPST QUANT FINANCE HUB — DAILY SUMMARY")
        lines.append(f"Date: {dt.date.today().isoformat()}")
        lines.append("=" * 60)
        lines.append("")

        price = analysis.get("price", 0)
        lines.append(f"PRICE: ${price:.2f}")
        lines.append("")

        # Trade Decision
        td = analysis.get("trade_decision", {})
        lines.append(f"ACTION: {td.get('action', 'N/A')}")
        lines.append(f"VEHICLE: {td.get('vehicle', 'N/A')}")
        lines.append(f"CONFIDENCE: {td.get('confidence', 'N/A')}")
        lines.append(f"ENTRY: ${td.get('entry_price', 0):.2f}")
        lines.append(f"TARGET: ${td.get('target_price', 0):.2f}")
        lines.append(f"STOP: ${td.get('stop_price', 0):.2f}")
        lines.append(f"R:R: {td.get('reward_risk_ratio', 0):.2f}")
        lines.append("")

        # Key Scores
        lines.append("KEY SCORES:")
        scores = analysis.get("scores", {})
        for name, data in scores.items():
            val = data.get("value", "?") if isinstance(data, dict) else data
            lines.append(f"  {name}: {val}")
        lines.append("")

        # Forecast
        fc = analysis.get("forecast", {})
        lines.append(f"FORECAST: ${fc.get('ensemble_point', 'N/A')}")
        lines.append(f"RANGE: ${fc.get('ensemble_lower', 'N/A')} — ${fc.get('ensemble_upper', 'N/A')}")
        lines.append(f"CONFIDENCE: {fc.get('confidence_score', 'N/A')}")
        lines.append("")

        # Risk
        risk = analysis.get("risk", {})
        lines.append(f"VaR 95% (1d): ${risk.get('var_95_1d', 'N/A')}")
        lines.append(f"MAX DD: {risk.get('max_drawdown', 'N/A')}%")
        lines.append(f"RECOMMENDED SIZE: {risk.get('recommended_size_pct', 'N/A')}%")
        lines.append("")

        lines.append("=" * 60)
        lines.append("DISCLAIMER: For research & simulation only. Not financial advice.")

        return "\n".join(lines)


# Singleton
export_service = ExportService()
