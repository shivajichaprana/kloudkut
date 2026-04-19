"""Base scanner — parallel, cached, typed."""
import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import time

logger = logging.getLogger(__name__)
_CACHE_DIR = Path(".kloudkut_cache")
_CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(key: str) -> Path:
    # Filename is a SHA256 hex digest — no user input in the path
    cache_dir = _CACHE_DIR.resolve()
    file_path = cache_dir / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    # Ensure the resolved path is within cache directory
    if not str(file_path.resolve()).startswith(str(cache_dir)):
        raise ValueError("Invalid cache path")
    return file_path


def _cache_get(key: str):
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data.get("expires", 0) < time.time():
            path.unlink()
            return None
        return [Finding(**r) for r in data["findings"]]
    except (OSError, ValueError, KeyError) as e:
        logger.debug("Cache read failed for %s: %s", path, e)
        return None


def _cache_set(key: str, findings: list, expire: int = 3600) -> None:
    data = {"expires": time.time() + expire, "findings": [asdict(r) for r in findings]}
    _cache_path(key).write_text(json.dumps(data))


def _cache_clear() -> None:
    for p in _CACHE_DIR.glob("*.json"):
        p.unlink()


# Compatibility shim so existing code using _cache.clear() still works
class _CacheCompat:
    def clear(self): _cache_clear()
    def get(self, key): return _cache_get(key)
    def set(self, key, val, expire=3600): _cache_set(key, val, expire)


_cache = _CacheCompat()


@dataclass
class Finding:
    resource_id: str
    resource_name: str
    service: str
    region: str
    reason: str
    monthly_cost: float
    details: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""


class BaseScanner(ABC):
    service: str = ""

    def __init__(self, config: dict, regions: list[str]):
        self.config = config.get(self.service, {})
        self.regions = regions
        self._config_hash = hashlib.sha256(
            json.dumps(self.config, sort_keys=True).encode()
        ).hexdigest()[:8]

    @property
    def cw_days(self) -> int:
        return self.config.get("cloudwatch_metrics_days", 14)

    @property
    def cw_period(self) -> int:
        return self.config.get("cloudwatch_metrics_period", 1209600)

    @abstractmethod
    def scan_region(self, region: str) -> list[Finding]: ...

    def is_enabled(self, region: str) -> bool:
        """Check if this service is activated/available in the given region.

        Override in scanners for services that require explicit activation
        (e.g., GuardDuty, Macie, SecurityHub) or aren't available in all
        regions (e.g., Lightsail).  The default returns True — most AWS
        services are always available.

        Returns False when the service is *not activated* in the account for
        that region.  Permission errors (AccessDenied) should NOT cause a
        False return — those are handled separately.
        """
        return True

    def scan(self, use_cache: bool = True) -> list[Finding]:
        # Fix #4: cache key includes config hash so threshold changes invalidate cache
        cache_key = f"{self.service}:{','.join(sorted(self.regions))}:{self._config_hash}"

        if use_cache:
            cached = _cache_get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", self.service)
                return cached

        findings: list[Finding] = []
        workers = min(len(self.regions), 5) if self.regions else 1
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(self._safe_scan, r): r for r in self.regions}
            try:
                for future in as_completed(futures, timeout=600):
                    findings.extend(future.result())
            except TimeoutError:
                done = sum(1 for f in futures if f.done())
                logger.warning(
                    "%s timed out: %d/%d regions completed",
                    self.service, done, len(futures),
                )
                # Collect results from completed futures
                for future in futures:
                    if future.done() and not future.cancelled():
                        try:
                            findings.extend(future.result(timeout=0))
                        except Exception:
                            pass

        findings.sort(key=lambda f: f.monthly_cost, reverse=True)

        if use_cache:
            _cache_set(cache_key, findings, expire=3600)

        return findings

    def _safe_scan(self, region: str) -> list[Finding]:
        try:
            return self.scan_region(region)
        except Exception as e:
            logger.warning("%s scan failed in %s: %s", self.service, region, e)
            return []
