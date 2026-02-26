#!/usr/bin/env python3
"""AWS Lambda handler for KloudKut."""
import json
import os
from kloudkut.core import load_config, get_regions, save_scan, notify
from kloudkut.scanners import ALL_SCANNERS

def handler(event, context):
    """Lambda handler for scheduled KloudKut scans."""
    config = load_config()
    regions = os.environ.get("REGIONS", "us-east-1").split(",")
    min_cost = float(os.environ.get("MIN_COST", "0"))
    
    findings = []
    for scanner_cls in ALL_SCANNERS:
        scanner = scanner_cls(config, regions)
        findings.extend(scanner.scan(use_cache=False))
    
    findings = [f for f in findings if f.monthly_cost >= min_cost]
    findings.sort(key=lambda f: f.monthly_cost, reverse=True)
    
    save_scan(findings)
    
    if findings and os.environ.get("NOTIFY", "false") == "true":
        notify(config, findings)
    
    total_savings = sum(f.monthly_cost for f in findings)
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "findings": len(findings),
            "monthly_savings": round(total_savings, 2),
            "annual_savings": round(total_savings * 12, 2)
        })
    }
