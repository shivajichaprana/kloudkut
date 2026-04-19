"""AWS client factory with retry and session management.

Fixes file-descriptor leak: replaces @lru_cache on get_client() with a
manually-managed dict that closes evicted clients' HTTP connection pools.
"""
import boto3
import logging
from functools import lru_cache
from botocore.config import Config

logger = logging.getLogger(__name__)

_BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})

# Module-level profile name -- set by main.py before scanning starts.
_profile: str | None = None

# ---------- client cache with explicit close-on-evict ----------
_client_cache: dict[tuple[str, str], object] = {}
_CLIENT_CACHE_MAX = 64  # keep recent clients; 64 < typical ulimit of 256


def _close_client(client) -> None:
        """Shut down a boto3 client's HTTP connection pool to free FDs."""
        try:
                    session = getattr(client, "_endpoint", None)
                    if session:
                                    http = getattr(session, "http_session", None)
                                    if http:
                                                        http.close()
        except Exception:
                    pass


def _evict_oldest(n: int = 1) -> None:
        """Remove the *n* oldest entries from _client_cache, closing each."""
        keys = list(_client_cache.keys())[:n]
        for k in keys:
                    _close_client(_client_cache.pop(k, None))


def close_all_clients() -> None:
        """Close every cached client -- call between service scans or at exit."""
        for client in _client_cache.values():
                    _close_client(client)
                _client_cache.clear()


def set_profile(profile: str | None) -> None:
        """Set the AWS profile for all subsequent client creation.

            Must be called before scanning starts.  Clears existing caches so new
                clients pick up the updated credentials.
                    """
    global _profile
    _profile = profile
    _session.cache_clear()
    close_all_clients()


@lru_cache(maxsize=128)
def _session(region: str) -> boto3.Session:
        return boto3.Session(profile_name=_profile, region_name=region)


def get_client(service: str, region: str):
        key = (service, region)
    client = _client_cache.get(key)
    if client is not None:
                return client

    # Evict oldest if at capacity
    if len(_client_cache) >= _CLIENT_CACHE_MAX:
                _evict_oldest(len(_client_cache) - _CLIENT_CACHE_MAX + 1)

    client = _session(region).client(service, config=_BOTO_CONFIG)
    _client_cache[key] = client
    return client


def get_client_for_session(session: boto3.Session, service: str, region: str):
        """Return a boto3 client bound to a specific session (for multi-account)."""
    return session.client(service, region_name=region, config=_BOTO_CONFIG)


@lru_cache(maxsize=1)
def get_regions() -> list[str]:
        try:
                    return [r["RegionName"] for r in get_client("ec2", "us-east-1").describe_regions()["Regions"]]
except Exception:
        return ["us-east-1"]
