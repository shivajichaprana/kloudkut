"""AWS client factory with retry and session management."""
import boto3
from functools import lru_cache
from botocore.config import Config

_BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})


@lru_cache(maxsize=128)
def _session(region: str) -> boto3.Session:
    return boto3.Session(region_name=region)


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
