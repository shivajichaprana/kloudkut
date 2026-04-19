"""Report generators — JSON, CSV, HTML with path-traversal protection."""
import csv
import json
import os
from dataclasses import asdict
from datetime import datetime, UTC
from pathlib import Path

from kloudkut.core.scanner import Finding


def _safe_path(path: str) -> str:
    """Reject paths that contain '..' directory traversal components."""
    # Normalise but preserve absolute-ness, then check for '..' segments
    normed = os.path.normpath(path)
    if ".." in normed.split(os.sep):
        raise ValueError(f"Path traversal detected: {path}")
    return os.path.realpath(path)


def generate_json(findings: list[Finding], path: str) -> str:
    """Write findings to a JSON file. Returns the output path."""
    path = _safe_path(path)
    monthly = round(sum(f.monthly_cost for f in findings), 2)
    data = {
        "tool": "kloudkut",
        "generated_at": datetime.now(UTC).isoformat(),
        "total_findings": len(findings),
        "total_monthly_savings": monthly,
        "total_annual_savings": round(monthly * 12, 2),
        "findings": [asdict(f) for f in findings],
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def generate_csv(findings: list[Finding], output_dir: str) -> str:
    """Write findings to a CSV file in *output_dir*. Returns the output path."""
    output_dir = _safe_path(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "kloudkut_findings.csv")
    fieldnames = [
        "resource_id", "resource_name", "service", "region",
        "reason", "monthly_cost", "remediation",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for finding in findings:
            row = asdict(finding)
            row.pop("details", None)
            writer.writerow(row)
    return path


def generate_html(findings: list[Finding], path: str) -> str:
    """Write findings to a standalone HTML report. Returns the output path."""
    path = _safe_path(path)
    monthly = round(sum(f.monthly_cost for f in findings), 2)
    annual = round(monthly * 12, 2)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Build table rows
    rows = ""
    for f in findings:
        console_url = f.details.get("console_url", "")
        link = f'<a href="{console_url}" target="_blank">{f.resource_name}</a>' if console_url else f.resource_name
        rows += (
            f"<tr>"
            f"<td>{f.service}</td>"
            f"<td>{link}</td>"
            f"<td>{f.region}</td>"
            f"<td>{f.reason}</td>"
            f"<td class=\"cost\">${f.monthly_cost:,.2f}</td>"
            f"<td><code>{f.remediation}</code></td>"
            f"</tr>\n"
        )

    # Service breakdown
    svc_totals: dict[str, float] = {}
    for f in findings:
        svc_totals[f.service] = svc_totals.get(f.service, 0) + f.monthly_cost
    breakdown_rows = ""
    for svc, total in sorted(svc_totals.items(), key=lambda x: x[1], reverse=True):
        count = sum(1 for f in findings if f.service == svc)
        breakdown_rows += (
            f"<tr><td>{svc}</td><td>{count}</td>"
            f"<td class=\"cost\">${total:,.2f}</td>"
            f"<td class=\"cost\">${total * 12:,.2f}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KloudKut Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8f9fa; color: #1a1a2e; padding: 2rem; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  .subtitle {{ color: #666; margin-bottom: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1.5rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card .label {{ font-size: 0.85rem; color: #666; text-transform: uppercase; }}
  .card .value {{ font-size: 1.8rem; font-weight: 700; margin-top: 0.25rem; }}
  .card .value.green {{ color: #16a34a; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 2rem; }}
  th {{ background: #1a1a2e; color: #fff; text-align: left; padding: 0.75rem 1rem;
       font-size: 0.85rem; text-transform: uppercase; }}
  td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
  tr:hover {{ background: #f0f7ff; }}
  .cost {{ text-align: right; font-family: monospace; font-weight: 600; }}
  code {{ background: #f1f3f5; padding: 2px 6px; border-radius: 3px; font-size: 0.8rem; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  h2 {{ font-size: 1.3rem; margin: 1.5rem 0 1rem; }}
  .footer {{ text-align: center; color: #999; font-size: 0.8rem; margin-top: 2rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>KloudKut Report</h1>
  <p class="subtitle">Generated {generated}</p>

  <div class="cards">
    <div class="card">
      <div class="label">Idle Resources</div>
      <div class="value">{len(findings)}</div>
    </div>
    <div class="card">
      <div class="label">Monthly Savings</div>
      <div class="value green">${monthly:,.2f}</div>
    </div>
    <div class="card">
      <div class="label">Annual Savings</div>
      <div class="value green">${annual:,.2f}</div>
    </div>
    <div class="card">
      <div class="label">Services Affected</div>
      <div class="value">{len(svc_totals)}</div>
    </div>
  </div>

  <h2>Savings by Service</h2>
  <table>
    <tr><th>Service</th><th>Resources</th><th>Monthly</th><th>Annual</th></tr>
    {breakdown_rows}
  </table>

  <h2>All Findings</h2>
  <table>
    <tr><th>Service</th><th>Resource</th><th>Region</th><th>Reason</th><th>Monthly Cost</th><th>Remediation</th></tr>
    {rows}
  </table>

  <p class="footer">KloudKut v5.1.0 &mdash; AWS Cost Optimization</p>
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    return path
