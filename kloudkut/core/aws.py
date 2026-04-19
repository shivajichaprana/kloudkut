"""AWS client factory with retry and session management."""
import boto3
from functools import lru_cache
from botocore.config import Config

_BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})

# Module-level profile name — set by main.py before scanning starts.
_profile: str | None = None


def set_profile(profile: str | None) -> None:
    """Set the AWS profile for all subsequent client creation.

    Must be called before scanning starts.  Clears existing caches so new
    clients pick up the updated credentials.
    """
    global _profile
    _profile = profile
    # Invalidate cached sessions/clients so they're recreated with the new profile
    _session.cache_clear()
    get_client.cache_clear()


@lru_cache(maxsize=128)
def _session(region: str) -> boto3.Session:
    return boto3.Session(profile_name=_profile, region_name=region)


@lru_cache(maxsize=256)
def get_client(service: str, region: str):
    return _session(region).client(service, config=_BOTO_CONFIG)


def get_client_for_session(session: boto3.Session, service: str, region: str):
    """Return a boto3 client bound to a specific session (for multi-account)."""
    return session.client(service, region_name=region, config=_BOTO_CONFIG)


@lru_cache(maxsize=1)
def get_regions() -> list[str]:
    try:
        return [r["RegionName"] for r in get_client("ec2", "us-east-1").describe_regions()["Regions"]]
    except Exception:
        return ["us-east-1"]
