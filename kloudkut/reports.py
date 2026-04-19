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
    from collections import defaultdict
    from kloudkut import __version__

    path = _safe_path(path)
    monthly = round(sum(f.monthly_cost for f in findings), 2)
    annual = round(monthly * 12, 2)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # ── Global service breakdown table ──
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

    # ── Region breakdown table ──
    region_totals: dict[str, float] = {}
    for f in findings:
        region_totals[f.region] = region_totals.get(f.region, 0) + f.monthly_cost
    region_breakdown_rows = ""
    for reg, total in sorted(region_totals.items(), key=lambda x: x[1], reverse=True):
        count = sum(1 for f in findings if f.region == reg)
        svcs = len({f.service for f in findings if f.region == reg})
        region_breakdown_rows += (
            f"<tr><td><a href=\"#region-{reg}\">{reg}</a></td><td>{count}</td><td>{svcs}</td>"
            f"<td class=\"cost\">${total:,.2f}</td>"
            f"<td class=\"cost\">${total * 12:,.2f}</td></tr>\n"
        )

    # ── Group findings: region → service → [findings] ──
    grouped: dict[str, dict[str, list[Finding]]] = defaultdict(lambda: defaultdict(list))
    for f in findings:
        grouped[f.region][f.service].append(f)

    # Sort regions by total cost descending
    sorted_regions = sorted(grouped.keys(),
                            key=lambda r: sum(f.monthly_cost for f in findings if f.region == r),
                            reverse=True)

    # ── Build region → service sections ──
    region_sections = ""
    for region in sorted_regions:
        services = grouped[region]
        region_monthly = round(sum(f.monthly_cost for svc_findings in services.values() for f in svc_findings), 2)
        region_count = sum(len(v) for v in services.values())

        # Sort services by cost descending within region
        sorted_services = sorted(services.keys(),
                                 key=lambda s: sum(f.monthly_cost for f in services[s]),
                                 reverse=True)

        service_blocks = ""
        for svc in sorted_services:
            svc_findings = services[svc]
            svc_monthly = round(sum(f.monthly_cost for f in svc_findings), 2)

            # Build finding rows for this service
            finding_rows = ""
            for f in sorted(svc_findings, key=lambda x: x.monthly_cost, reverse=True):
                console_url = f.details.get("console_url", "")
                link = f'<a href="{console_url}" target="_blank">{f.resource_name}</a>' if console_url else f.resource_name
                remediation_cell = f'<code>{f.remediation}</code>' if f.remediation else '<span class="na">—</span>'
                finding_rows += (
                    f"<tr>"
                    f"<td>{link}</td>"
                    f"<td class=\"reason\">{f.reason}</td>"
                    f"<td class=\"cost\">${f.monthly_cost:,.2f}</td>"
                    f"<td class=\"remediation\">{remediation_cell}</td>"
                    f"</tr>\n"
                )

            service_blocks += f"""
      <div class="service-block">
        <div class="service-header" onclick="this.parentElement.classList.toggle('collapsed')">
          <span class="toggle-icon">▼</span>
          <span class="service-name">{svc}</span>
          <span class="service-meta">{len(svc_findings)} finding{'s' if len(svc_findings) != 1 else ''}</span>
          <span class="service-cost">${svc_monthly:,.2f}/mo</span>
        </div>
        <div class="service-body">
          <table class="findings-table">
            <tr><th>Resource</th><th>Reason</th><th>Monthly Cost</th><th>Remediation</th></tr>
            {finding_rows}
          </table>
        </div>
      </div>"""

        region_sections += f"""
  <div class="region-section" id="region-{region}">
    <div class="region-header">
      <h2>📍 {region}</h2>
      <div class="region-stats">
        <span class="region-badge">{region_count} finding{'s' if region_count != 1 else ''}</span>
        <span class="region-badge">{len(sorted_services)} service{'s' if len(sorted_services) != 1 else ''}</span>
        <span class="region-badge cost">${region_monthly:,.2f}/mo</span>
      </div>
    </div>
    {service_blocks}
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KloudKut Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f2f5; color: #1a1a2e; padding: 2rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}

  /* Header */
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
             color: #fff; padding: 2rem; border-radius: 12px; margin-bottom: 2rem; }}
  .header h1 {{ font-size: 2rem; margin-bottom: 0.25rem; }}
  .header .subtitle {{ color: #94a3b8; margin: 0; }}

  /* Summary cards */
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: #fff; border-radius: 10px; padding: 1.5rem;
           box-shadow: 0 2px 8px rgba(0,0,0,0.06); border: 1px solid #e5e7eb; }}
  .card .label {{ font-size: 0.8rem; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 2rem; font-weight: 700; margin-top: 0.25rem; }}
  .card .value.green {{ color: #16a34a; }}
  .card .value.blue {{ color: #2563eb; }}

  /* Tables */
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 10px; overflow: hidden;
           box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 1.5rem;
           border: 1px solid #e5e7eb; }}
  th {{ background: #1a1a2e; color: #fff; text-align: left; padding: 0.75rem 1rem;
       font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  td {{ padding: 0.65rem 1rem; border-bottom: 1px solid #f1f3f5; font-size: 0.88rem; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #f8fafc; }}
  .cost {{ text-align: right; font-family: 'SF Mono', 'Menlo', monospace; font-weight: 600; }}
  .reason {{ max-width: 450px; line-height: 1.45; color: #374151; }}
  .remediation code {{ font-size: 0.78rem; }}
  .na {{ color: #9ca3af; }}

  /* Section headings */
  h2 {{ font-size: 1.3rem; margin: 0; }}
  .section-title {{ font-size: 1.2rem; color: #1a1a2e; margin: 2rem 0 1rem;
                    padding-bottom: 0.5rem; border-bottom: 2px solid #e5e7eb; }}

  /* Region sections */
  .region-section {{ background: #fff; border-radius: 12px; padding: 1.5rem;
                     margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                     border: 1px solid #e5e7eb; }}
  .region-header {{ display: flex; justify-content: space-between; align-items: center;
                    margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }}
  .region-header h2 {{ margin: 0; font-size: 1.3rem; }}
  .region-stats {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
  .region-badge {{ background: #f1f3f5; color: #374151; padding: 0.3rem 0.75rem;
                   border-radius: 20px; font-size: 0.8rem; font-weight: 500; }}
  .region-badge.cost {{ background: #dcfce7; color: #166534; font-weight: 700;
                        font-family: 'SF Mono', 'Menlo', monospace; }}

  /* Service blocks */
  .service-block {{ border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 0.75rem;
                    overflow: hidden; }}
  .service-header {{ display: flex; align-items: center; padding: 0.75rem 1rem;
                     background: #f8fafc; cursor: pointer; user-select: none;
                     border-bottom: 1px solid #e5e7eb; gap: 0.75rem; }}
  .service-header:hover {{ background: #f1f5f9; }}
  .toggle-icon {{ font-size: 0.7rem; color: #6b7280; transition: transform 0.2s; }}
  .collapsed .toggle-icon {{ transform: rotate(-90deg); }}
  .service-name {{ font-weight: 600; font-size: 0.95rem; }}
  .service-meta {{ color: #6b7280; font-size: 0.82rem; }}
  .service-cost {{ margin-left: auto; font-weight: 700; color: #16a34a;
                   font-family: 'SF Mono', 'Menlo', monospace; font-size: 0.9rem; }}
  .collapsed .service-body {{ display: none; }}
  .service-body {{ padding: 0; }}
  .findings-table {{ margin: 0; border: none; border-radius: 0; box-shadow: none; }}
  .findings-table th {{ background: #eef2f7; color: #374151; }}

  /* Code & links */
  code {{ background: #f1f3f5; padding: 2px 6px; border-radius: 4px; font-size: 0.78rem;
          word-break: break-all; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* Footer */
  .footer {{ text-align: center; color: #9ca3af; font-size: 0.8rem; margin-top: 2rem;
             padding-top: 1.5rem; border-top: 1px solid #e5e7eb; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>KloudKut Report</h1>
    <p class="subtitle">Generated {generated}</p>
  </div>

  <div class="cards">
    <div class="card">
      <div class="label">Idle Resources</div>
      <div class="value blue">{len(findings)}</div>
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
      <div class="label">Regions Affected</div>
      <div class="value blue">{len(region_totals)}</div>
    </div>
    <div class="card">
      <div class="label">Services Affected</div>
      <div class="value blue">{len(svc_totals)}</div>
    </div>
  </div>

  <h3 class="section-title">Savings by Region</h3>
  <table>
    <tr><th>Region</th><th>Findings</th><th>Services</th><th>Monthly</th><th>Annual</th></tr>
    {region_breakdown_rows}
  </table>

  <h3 class="section-title">Savings by Service</h3>
  <table>
    <tr><th>Service</th><th>Resources</th><th>Monthly</th><th>Annual</th></tr>
    {breakdown_rows}
  </table>

  <h3 class="section-title">Findings by Region &amp; Service</h3>
  {region_sections}

  <p class="footer">KloudKut v{__version__} &mdash; AWS Cost Optimization</p>
</div>

<script>
// Expand/collapse all
document.querySelectorAll('.service-header').forEach(h => {{
  h.addEventListener('click', () => h.parentElement.classList.toggle('collapsed'));
}});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    return path
