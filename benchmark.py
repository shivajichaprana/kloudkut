#!/usr/bin/env python3
"""Performance benchmarking for KloudKut."""
import time
from kloudkut.core.telemetry import get_summary, clear_metrics
from kloudkut.scanners import ALL_SCANNERS
from kloudkut.core import load_config, get_regions

def benchmark():
    clear_metrics()
    config = load_config()
    regions = ["us-east-1"]
    
    print("🔬 Benchmarking KloudKut Performance\n")
    print(f"Services: {len(ALL_SCANNERS)}")
    print(f"Regions: {len(regions)}\n")
    
    start = time.time()
    total_findings = 0
    
    for scanner_cls in ALL_SCANNERS:
        scanner = scanner_cls(config, regions)
        findings = scanner.scan(use_cache=False)
        total_findings += len(findings)
    
    elapsed = time.time() - start
    summary = get_summary()
    
    print(f"✓ Completed in {elapsed:.2f}s")
    print(f"  Total findings: {total_findings}")
    print(f"  Avg scan time: {summary.get('avg_scan_time', 0):.2f}s")
    print(f"  Errors: {summary.get('errors', 0)}")

if __name__ == "__main__":
    benchmark()
