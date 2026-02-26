"""Telemetry and metrics collection."""
import time
from functools import wraps
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime, UTC

@dataclass
class ScanMetrics:
    service: str
    region: str
    duration: float
    findings_count: int
    error: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

_metrics: List[ScanMetrics] = []

def track_scan(func):
    """Decorator to track scanner performance."""
    @wraps(func)
    def wrapper(self, region: str):
        start = time.time()
        error = ""
        findings = []
        try:
            findings = func(self, region)
            return findings
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration = time.time() - start
            _metrics.append(ScanMetrics(
                service=self.service,
                region=region,
                duration=duration,
                findings_count=len(findings),
                error=error
            ))
    return wrapper

def get_metrics() -> List[Dict]:
    """Get collected metrics."""
    return [{"service": m.service, "region": m.region, "duration": m.duration,
             "findings": m.findings_count, "error": m.error,
             "timestamp": m.timestamp.isoformat()} for m in _metrics]

def clear_metrics():
    """Clear collected metrics."""
    _metrics.clear()

def get_summary() -> Dict:
    """Get metrics summary."""
    if not _metrics:
        return {}
    total_duration = sum(m.duration for m in _metrics)
    errors = [m for m in _metrics if m.error]
    return {
        "total_scans": len(_metrics),
        "total_duration": round(total_duration, 2),
        "total_findings": sum(m.findings_count for m in _metrics),
        "errors": len(errors),
        "avg_scan_time": round(total_duration / len(_metrics), 2),
        "services_scanned": len(set(m.service for m in _metrics))
    }
