"""Diagnostic and evaluation report rendering in HTML, JSON, and CSV formats."""

from __future__ import annotations

import json
from pathlib import Path

from dv360_bidkit.contracts.schemas import EvaluationReport, MetricStatus


def render_html_report(report: EvaluationReport) -> str:
    """Renders a standalone, responsive HTML evaluation report."""
    m = report.metrics
    r = report.readiness

    def fmt_stat(mv) -> str:
        if mv.status != MetricStatus.COMPUTED or mv.value is None:
            return f"<span style='color: #888;'>Unavailable ({mv.assumption or 'N/A'})</span>"
        return f"<strong>{mv.value:.4f}</strong>"

    diag_rows = ""
    for d in report.diagnostics:
        sev_color = "#e53e3e" if d.severity.value == "error" else ("#d69e2e" if d.severity.value == "warning" else "#3182ce")
        diag_rows += f"""
        <tr>
            <td style="color: {sev_color}; font-weight: bold;">{d.severity.value.upper()}</td>
            <td><code>{d.code}</code></td>
            <td>{d.message}</td>
            <td><small>{d.corrective_action or '-'}</small></td>
        </tr>
        """

    if not diag_rows:
        diag_rows = "<tr><td colspan='4' style='text-align: center; color: #38a169;'>No diagnostics or warnings encountered.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DV360 Custom Bidding Pre-Flight Evaluation Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f7fafc;
            color: #2d3748;
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 8px;
            padding: 32px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        h1 {{ margin-top: 0; color: #1a202c; border-bottom: 2px solid #edf2f7; padding-bottom: 12px; }}
        h2 {{ color: #2b6cb0; margin-top: 28px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 16px;
        }}
        .card-label {{ font-size: 12px; text-transform: uppercase; color: #718096; margin-bottom: 4px; }}
        .card-val {{ font-size: 20px; font-weight: 600; color: #2d3748; }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 600;
        }}
        .badge-green {{ background: #c6f6d5; color: #22543d; }}
        .badge-yellow {{ background: #fefcbf; color: #744210; }}
        .badge-gray {{ background: #e2e8f0; color: #4a5568; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}
        th, td {{
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid #edf2f7;
            font-size: 14px;
        }}
        th {{ background: #edf2f7; color: #4a5568; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>DV360 Custom Bidding Pre-Flight Evaluation</h1>

        <div style="margin-bottom: 24px;">
            <strong>Readiness Assessment (Google S2):</strong>
            <span class="badge { 'badge-green' if r.status.value == 'MEETS_MINIMUM_HISTORY' else ('badge-yellow' if r.status.value == 'INSUFFICIENT_HISTORY' else 'badge-gray') }">
                {r.status.value}
            </span>
            <span style="color: #718096; font-size: 14px; margin-left: 12px;">
                Observed Positives: {r.observed_advertiser_positives:,} (Required: {r.required_advertiser_positives:,})
            </span>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-label">Total Impressions</div>
                <div class="card-val">{m.total_impressions:,}</div>
            </div>
            <div class="card">
                <div class="card-label">Positive Impressions</div>
                <div class="card-val">{m.positive_score_impressions:,}</div>
            </div>
            <div class="card">
                <div class="card-label">Excluded (None)</div>
                <div class="card-val">{m.excluded_impressions:,}</div>
            </div>
            <div class="card">
                <div class="card-label">Zero Scores</div>
                <div class="card-val">{m.zero_score_impressions:,}</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-label">Positive Rate (All)</div>
                <div class="card-val">{fmt_stat(m.positive_rate_all)}</div>
            </div>
            <div class="card">
                <div class="card-label">Positive Rate (Scored)</div>
                <div class="card-val">{fmt_stat(m.positive_rate_scored)}</div>
            </div>
            <div class="card">
                <div class="card-label">Weighted Mean Score</div>
                <div class="card-val">{fmt_stat(m.weighted_mean)}</div>
            </div>
            <div class="card">
                <div class="card-label">Positive Score Median</div>
                <div class="card-val">{fmt_stat(m.weighted_median)}</div>
            </div>
        </div>

        <h2>Pre-Flight Diagnostics</h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 100px;">Severity</th>
                    <th style="width: 180px;">Code</th>
                    <th>Message</th>
                    <th>Corrective Action</th>
                </tr>
            </thead>
            <tbody>
                {diag_rows}
            </tbody>
        </table>
    </div>
</body>
</html>"""
    return html


def render_report(report: EvaluationReport, *, output_path: str) -> None:
    """Renders evaluation report to HTML, JSON, or text file depending on path extension."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.suffix.lower() == ".json":
        out.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    elif out.suffix.lower() in (".html", ".htm"):
        html_content = render_html_report(report)
        out.write_text(html_content, encoding="utf-8")
    else:
        # Default plain text
        text_lines = [
            f"=== DV360 Custom Bidding Simulation ===",
            f"Total Impressions: {report.metrics.total_impressions}",
            f"Positive Impressions: {report.metrics.positive_score_impressions}",
            f"Readiness: {report.readiness.status.value}",
        ]
        out.write_text("\n".join(text_lines), encoding="utf-8")
