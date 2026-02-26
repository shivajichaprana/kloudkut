#!/usr/bin/env python3
"""KloudKut Web Dashboard."""
import csv
import io
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from threading import Lock
from flask import Flask, jsonify, render_template_string, request, Response

app = Flask(__name__)
_lock = Lock()
_scan_results = {"findings": [], "last_scan": None, "scanning": False}
_logger = logging.getLogger(__name__)
_TOKEN = os.getenv("KLOUDKUT_TOKEN", "")


def _auth_required():
    """Return 401 response if token auth is configured and token doesn't match."""
    if not _TOKEN:
        return None
    token = request.headers.get("X-KloudKut-Token") or request.args.get("token", "")
    if token != _TOKEN:
        return Response("Unauthorized", status=401)
    return None

TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <title>KloudKut Dashboard</title>
  <meta charset="utf-8">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
    .nav{background:#1e293b;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #334155}
    .nav h1{font-size:20px;font-weight:700;color:#67e8f9}
    .nav .badge{background:#0891b2;color:white;padding:4px 12px;border-radius:20px;font-size:12px}
    .container{max-width:1400px;margin:0 auto;padding:24px}
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
    .stat{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}
    .stat label{font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}
    .stat .val{font-size:32px;font-weight:700;margin-top:8px}
    .green{color:#4ade80}.yellow{color:#fbbf24}.red{color:#f87171}.blue{color:#60a5fa}
    .section{background:#1e293b;border:1px solid #334155;border-radius:12px;overflow:hidden;margin-bottom:24px}
    .section-header{padding:16px 20px;border-bottom:1px solid #334155;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
    .section-header h2{font-size:16px;font-weight:600}
    .filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .filters input,.filters select{background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:13px}
    .filters input:focus,.filters select:focus{outline:none;border-color:#0891b2}
    table{width:100%;border-collapse:collapse}
    th{padding:12px 16px;text-align:left;font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #334155}
    td{padding:12px 16px;border-bottom:1px solid #1e293b;font-size:14px}
    tr:hover td{background:#0f172a}
    .badge-svc{background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:12px}
    .cost{color:#4ade80;font-weight:600}
    .remediation{color:#fbbf24;font-size:11px;font-family:monospace}
    .btn{background:#0891b2;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:14px}
    .btn:hover{background:#0e7490}.btn:disabled{opacity:.5;cursor:not-allowed}
    .btn-sm{padding:4px 10px;font-size:12px}
    .btn-export{background:#065f46}
    .btn-export:hover{background:#047857}
    .spinner{display:inline-block;width:16px;height:16px;border:2px solid #334155;border-top-color:#67e8f9;border-radius:50%;animation:spin 1s linear infinite;margin-right:8px}
    @keyframes spin{to{transform:rotate(360deg)}}
    .empty{text-align:center;padding:40px;color:#64748b}
    .pagination{display:flex;align-items:center;justify-content:center;gap:8px;padding:16px}
    .page-info{color:#94a3b8;font-size:13px}
    a.console-link{color:#67e8f9;font-size:11px;text-decoration:none;margin-left:6px}
    a.console-link:hover{text-decoration:underline}
    .trend-section{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:24px}
    .trend-section h2{font-size:16px;font-weight:600;margin-bottom:16px}
    canvas{width:100%;height:120px}
  </style>
</head>
<body>
  <nav class="nav">
    <h1>🎯 KloudKut</h1>
    <span class="badge" id="status">Ready</span>
  </nav>
  <div class="container">
    <div class="stats">
      <div class="stat"><label>Total Findings</label><div class="val blue" id="total-findings">—</div></div>
      <div class="stat"><label>Filtered Findings</label><div class="val yellow" id="filtered-findings">—</div></div>
      <div class="stat"><label>Monthly Savings</label><div class="val green" id="monthly">—</div></div>
      <div class="stat"><label>Annual Savings</label><div class="val green" id="annual">—</div></div>
    </div>
    <div class="trend-section" id="trend-section" style="display:none">
      <h2>📈 Savings Trend</h2>
      <canvas id="trend-chart"></canvas>
    </div>
    <div class="section">
      <div class="section-header">
        <h2>Idle Resources</h2>
        <div class="filters">
          <input type="text" id="search" placeholder="Search resources..." oninput="applyFilters()">
          <select id="filter-service" onchange="applyFilters()"><option value="">All Services</option></select>
          <select id="filter-region" onchange="applyFilters()"><option value="">All Regions</option></select>
          <input type="number" id="min-cost" placeholder="Min $/mo" min="0" step="1" oninput="applyFilters()" style="width:100px">
          <button class="btn" id="scan-btn" onclick="startScan()">▶ Run Scan</button>
          <button class="btn btn-sm btn-export" onclick="exportCSV()">⬇ CSV</button>
          <button class="btn btn-sm btn-export" onclick="exportJSON()">⬇ JSON</button>
        </div>
      </div>
      <div id="table-container">
        <div class="empty">Click "Run Scan" to start scanning your AWS account</div>
      </div>
      <div class="pagination" id="pagination" style="display:none">
        <button class="btn btn-sm" onclick="changePage(-1)" id="prev-btn">← Prev</button>
        <span class="page-info" id="page-info"></span>
        <button class="btn btn-sm" onclick="changePage(1)" id="next-btn">Next →</button>
      </div>
    </div>
  </div>
  <script>
    let allFindings = [], filtered = [], currentPage = 1;
    const PAGE_SIZE = 50;

    function startScan() {
      document.getElementById('scan-btn').disabled = true;
      document.getElementById('status').innerHTML = '<span class="spinner"></span>Scanning...';
      fetch('/api/scan', {method:'POST'}).then(() => pollStatus());
    }
    function pollStatus() {
      fetch('/api/status').then(r=>r.json()).then(d => {
        if (d.scanning) { setTimeout(pollStatus, 2000); return; }
        document.getElementById('scan-btn').disabled = false;
        document.getElementById('status').textContent = 'Last scan: ' + (d.last_scan || 'Never');
        loadData();
        loadTrend();
      });
    }
    function loadData() {
      fetch('/api/findings').then(r=>r.json()).then(data => {
        allFindings = data.findings || [];
        populateFilters();
        applyFilters();
      });
    }
    function loadTrend() {
      fetch('/api/trend').then(r=>r.json()).then(data => {
        const points = data.trend || [];
        if (points.length < 2) return;
        document.getElementById('trend-section').style.display = 'block';
        drawTrend(points);
      });
    }
    function drawTrend(points) {
      const canvas = document.getElementById('trend-chart');
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.offsetWidth; canvas.height = 120;
      const vals = points.map(p => p.monthly_savings);
      const max = Math.max(...vals), min = Math.min(...vals);
      const w = canvas.width, h = canvas.height, pad = 10;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = '#4ade80'; ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = pad + (i / (points.length - 1)) * (w - pad*2);
        const y = h - pad - ((p.monthly_savings - min) / (max - min || 1)) * (h - pad*2);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    function populateFilters() {
      const services = [...new Set(allFindings.map(f=>f.service))].sort();
      const regions = [...new Set(allFindings.map(f=>f.region))].sort();
      document.getElementById('filter-service').innerHTML =
        '<option value="">All Services</option>' + services.map(s=>`<option>${s}</option>`).join('');
      document.getElementById('filter-region').innerHTML =
        '<option value="">All Regions</option>' + regions.map(r=>`<option>${r}</option>`).join('');
    }
    function applyFilters() {
      const search = document.getElementById('search').value.toLowerCase();
      const svc = document.getElementById('filter-service').value;
      const reg = document.getElementById('filter-region').value;
      const minCost = parseFloat(document.getElementById('min-cost').value) || 0;
      filtered = allFindings.filter(f =>
        (!svc || f.service === svc) && (!reg || f.region === reg) &&
        (f.monthly_cost >= minCost) &&
        (!search || f.resource_name.toLowerCase().includes(search) ||
         f.service.toLowerCase().includes(search) || f.reason.toLowerCase().includes(search))
      );
      currentPage = 1;
      renderTable();
    }
    function changePage(dir) {
      const maxPage = Math.ceil(filtered.length / PAGE_SIZE);
      currentPage = Math.max(1, Math.min(currentPage + dir, maxPage));
      renderTable();
    }
    function renderTable() {
      const filtTotal = filtered.reduce((s,f)=>s+f.monthly_cost,0);
      document.getElementById('total-findings').textContent = allFindings.length;
      document.getElementById('filtered-findings').textContent = filtered.length;
      document.getElementById('monthly').textContent = '$'+filtTotal.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
      document.getElementById('annual').textContent = '$'+(filtTotal*12).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
      if (!filtered.length) {
        document.getElementById('table-container').innerHTML = '<div class="empty">No findings match filters</div>';
        document.getElementById('pagination').style.display = 'none';
        return;
      }
      const maxPage = Math.ceil(filtered.length / PAGE_SIZE);
      const page = filtered.slice((currentPage-1)*PAGE_SIZE, currentPage*PAGE_SIZE);
      const rows = page.map(f => {
        const link = f.console_url ? `<a class="console-link" href="${f.console_url}" target="_blank">↗ Console</a>` : '';
        const rem = f.remediation ? `<br><span class="remediation">⚡ ${f.remediation}</span>` : '';
        return `<tr>
          <td><span class="badge-svc">${f.service}</span></td>
          <td>${f.resource_name}${link}${rem}</td>
          <td>${f.region}</td>
          <td>${f.reason}</td>
          <td class="cost">$${f.monthly_cost.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2})}/mo</td>
        </tr>`;
      }).join('');
      document.getElementById('table-container').innerHTML = `
        <table>
          <thead><tr><th>Service</th><th>Resource</th><th>Region</th><th>Reason</th><th>Monthly Cost</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>`;
      document.getElementById('pagination').style.display = maxPage > 1 ? 'flex' : 'none';
      document.getElementById('page-info').textContent = `Page ${currentPage} of ${maxPage} (${filtered.length} findings)`;
      document.getElementById('prev-btn').disabled = currentPage === 1;
      document.getElementById('next-btn').disabled = currentPage === maxPage;
    }
    function exportCSV() { window.location = '/api/export?fmt=csv'; }
    function exportJSON() { window.location = '/api/export?fmt=json'; }
    loadData();
    loadTrend();
  </script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/api/findings")
def findings():
    if err := _auth_required(): return err
    with _lock:
        data = list(_scan_results["findings"])
    return jsonify({
        "findings": [
            {"service": f.service, "resource_name": f.resource_name, "region": f.region,
             "reason": f.reason, "monthly_cost": f.monthly_cost,
             "console_url": f.details.get("console_url", ""),
             "remediation": f.remediation}
            for f in data
        ]
    })


@app.route("/api/status")
def status():
    if err := _auth_required(): return err
    with _lock:
        return jsonify({"scanning": _scan_results["scanning"], "last_scan": _scan_results["last_scan"]})


@app.route("/api/trend")
def trend():
    if err := _auth_required(): return err
    from kloudkut.core.history import get_trend
    return jsonify({"trend": get_trend()})


@app.route("/api/export")
def export():
    if err := _auth_required(): return err
    fmt = request.args.get("fmt", "csv")
    with _lock:
        data = list(_scan_results["findings"])

    if fmt == "json":
        from dataclasses import asdict
        payload = json.dumps([asdict(f) for f in data], indent=2, default=str)
        return Response(payload, mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=kloudkut_findings.json"})

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["service", "resource_name", "region", "reason", "monthly_cost", "remediation"])
    for f in data:
        writer.writerow([f.service, f.resource_name, f.region, f.reason, f.monthly_cost, f.remediation])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=kloudkut_findings.csv"})


@app.route("/api/scan", methods=["POST"])
def trigger_scan():
    if err := _auth_required(): return err
    with _lock:
        if _scan_results["scanning"]:
            return jsonify({"status": "already_running"})
        _scan_results["scanning"] = True

    def run():
        from kloudkut.core import load_config, get_regions, save_scan
        from kloudkut.scanners import ALL_SCANNERS
        config = load_config()
        regions = get_regions()
        findings = []
        # Use ThreadPoolExecutor so a hung scanner doesn't block the rest
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(lambda cls=cls: cls(config, regions).scan(use_cache=True)): cls
                       for cls in ALL_SCANNERS}
            for future in as_completed(futures):
                try:
                    findings.extend(future.result())
                except Exception as e:
                    _logger.warning("Scanner failed: %s", e)
        findings.sort(key=lambda f: f.monthly_cost, reverse=True)
        save_scan(findings)
        with _lock:
            _scan_results["findings"] = findings
            _scan_results["last_scan"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            _scan_results["scanning"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


if __name__ == "__main__":
    print("🚀 Dashboard → http://localhost:5000")
    if _TOKEN:
        print("🔒 Auth enabled — set X-KloudKut-Token header or ?token= param")
    else:
        print("⚠️  WARNING: No auth. Set KLOUDKUT_TOKEN env var or use on trusted networks only.")
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="127.0.0.1", port=5000, debug=debug)
