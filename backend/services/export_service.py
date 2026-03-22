"""
Reporting / Export Service — CSV, JSON, HTML, and plain-text export of analysis data.

Supports all institutional export formats:
- CSV: Tabular data for spreadsheet import
- JSON: Full structured data for programmatic consumption
- HTML: Styled interactive report for browser viewing
- Plain Text: Daily summary for email / terminal
"""

from __future__ import annotations

import csv
import html as html_mod
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

        # Funding
        writer.writerow(["=== FUNDING ==="])
        funding = analysis.get("funding", {})
        for k, v in funding.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Origination
        writer.writerow(["=== ORIGINATION ==="])
        orig = analysis.get("origination", {})
        for k, v in orig.items():
            if not isinstance(v, (list, dict)):
                writer.writerow([k, v])
        writer.writerow([])

        # Macro
        writer.writerow(["=== MACRO ==="])
        macro = analysis.get("macro", {})
        for k, v in macro.items():
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
        writer.writerow([])

        # Valuation
        writer.writerow(["=== VALUATION ==="])
        val = analysis.get("valuation", {})
        for k, v in val.items():
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

    def to_html(self, analysis: dict) -> str:
        """Export analysis as styled HTML report."""
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        price = analysis.get("price", 0)
        td = analysis.get("trade_decision", {})
        scores = analysis.get("scores", {})
        forecast = analysis.get("forecast", {})
        risk = analysis.get("risk", {})
        spy = analysis.get("spy_relationship", {})

        # Build scores table rows
        score_rows = ""
        for name, data in scores.items():
            val = data.get("value", "?") if isinstance(data, dict) else data
            expl = data.get("explanation", "") if isinstance(data, dict) else ""
            color = "#22c55e" if isinstance(val, (int, float)) and val > 60 else "#ef4444" if isinstance(val, (int, float)) and val < 40 else "#f59e0b"
            score_rows += f'<tr><td>{html_mod.escape(str(name))}</td><td style="color:{color};font-weight:bold">{html_mod.escape(str(val))}</td><td>{html_mod.escape(str(expl))}</td></tr>\n'

        # Build section blocks for each analysis domain
        section_blocks = ""
        for section_name, section_key in [
            ("Technical Analysis", "technical"),
            ("Options / Volatility", "options"),
            ("Short / Squeeze", "short"),
            ("Funding Analysis", "funding"),
            ("Origination", "origination"),
            ("Macro / Credit", "macro"),
            ("Valuation", "valuation"),
            ("Factor Exposure", "factor"),
            ("Reflexivity", "reflexivity"),
            ("Execution / Microstructure", "execution"),
            ("Behavioral / Psychology", "behavioral"),
            ("News Sentiment", "news"),
        ]:
            section_data = analysis.get(section_key, {})
            if section_data:
                rows = ""
                for k, v in section_data.items():
                    if not isinstance(v, (list, dict)):
                        rows += f"<tr><td>{html_mod.escape(str(k))}</td><td>{html_mod.escape(str(v))}</td></tr>\n"
                if rows:
                    section_blocks += f"""
                    <div class="section">
                        <h2>{section_name}</h2>
                        <table><tbody>{rows}</tbody></table>
                    </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UPST Quant Finance Hub — Analysis Report</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 20px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ color: #38bdf8; font-size: 1.8em; margin-bottom: 4px; }}
    h2 {{ color: #94a3b8; font-size: 1.1em; margin: 16px 0 8px; border-bottom: 1px solid #334155; padding-bottom: 4px; }}
    .meta {{ color: #64748b; font-size: 0.85em; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 16px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-header {{ font-size: 0.85em; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .big-number {{ font-size: 2em; font-weight: bold; color: #f1f5f9; }}
    .action {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }}
    .action-buy {{ background: #166534; color: #4ade80; }}
    .action-sell, .action-short {{ background: #7f1d1d; color: #f87171; }}
    .action-no_trade {{ background: #374151; color: #9ca3af; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
    td, th {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #1e293b; }}
    tr:hover {{ background: #1e293b; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
    .disclaimer {{ margin-top: 30px; padding: 12px; background: #1c1917; border: 1px solid #44403c; border-radius: 4px; font-size: 0.8em; color: #a8a29e; }}
</style>
</head>
<body>
<div class="container">
    <h1>UPST Quant Finance Hub</h1>
    <div class="meta">Generated: {now} | System v3.0 | For research & simulation only</div>

    <div class="grid">
        <div class="card">
            <div class="card-header">Current Price</div>
            <div class="big-number">${price:.2f}</div>
        </div>
        <div class="card">
            <div class="card-header">Trade Decision</div>
            <div><span class="action action-{td.get('action', 'no_trade')}">{td.get('action', 'N/A').upper()}</span></div>
            <div style="margin-top:8px;font-size:0.85em">
                Vehicle: {td.get('vehicle', 'N/A')} | Quality: {td.get('trade_quality', 'N/A')} | R:R: {td.get('reward_risk_ratio', 'N/A')}
            </div>
        </div>
        <div class="card">
            <div class="card-header">Forecast</div>
            <div class="big-number">${forecast.get('ensemble_point', 'N/A')}</div>
            <div style="font-size:0.85em">Range: ${forecast.get('ensemble_lower', '?')} — ${forecast.get('ensemble_upper', '?')}</div>
        </div>
        <div class="card">
            <div class="card-header">Risk</div>
            <div style="font-size:0.85em">
                VaR 95% (1d): ${risk.get('var_95_1d', 'N/A')}<br>
                Max DD: {risk.get('max_drawdown', 'N/A')}%<br>
                Size: {risk.get('recommended_size_pct', 'N/A')}%
            </div>
        </div>
        <div class="card">
            <div class="card-header">SPY Relationship</div>
            <div style="font-size:0.85em">
                Beta: {spy.get('beta', 'N/A')}<br>
                Correlation: {spy.get('rolling_correlation', 'N/A')}<br>
                Alpha: {spy.get('alpha', 'N/A')}
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Mandatory Scores (15)</h2>
        <table>
            <thead><tr><th>Score</th><th>Value</th><th>Explanation</th></tr></thead>
            <tbody>{score_rows}</tbody>
        </table>
    </div>

    {section_blocks}

    <div class="disclaimer">
        DISCLAIMER: This report is generated by the UPST Quant Finance Hub for research,
        simulation, and decision-support purposes only. It does not constitute financial advice,
        investment recommendation, or solicitation to trade. All data, scores, and projections
        are estimates subject to model risk, data quality limitations, and market uncertainty.
    </div>
</div>
</body>
</html>"""
        return html

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
        lines.append(f"ENTRY: ${td.get('entry_price') or 0:.2f}")
        lines.append(f"TARGET: ${td.get('target_price') or 0:.2f}")
        lines.append(f"STOP: ${td.get('stop_price') or 0:.2f}")
        lines.append(f"R:R: {td.get('reward_risk_ratio') or 0:.2f}")
        lines.append("")

        # Key Scores
        lines.append("KEY SCORES:")
        scores = analysis.get("scores", {})
        for name, data in scores.items():
            val = data.get("value", "?") if isinstance(data, dict) else data
            lines.append(f"  {name}: {val}")
        lines.append("")

        # SPY Relationship
        spy = analysis.get("spy_relationship", {})
        if spy:
            lines.append("SPY RELATIONSHIP:")
            lines.append(f"  Beta: {spy.get('beta', 'N/A')}")
            lines.append(f"  Correlation: {spy.get('rolling_correlation', 'N/A')}")
            lines.append(f"  Alpha: {spy.get('alpha', 'N/A')}")
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
