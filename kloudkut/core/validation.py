"""Input validation and sanitization."""
import re
from typing import List, Optional

def validate_region(region: str) -> bool:
    """Validate AWS region format."""
    pattern = r"^[a-z]{2}-[a-z]+-\d{1}$"
    return bool(re.match(pattern, region))

def validate_account_id(account_id: str) -> bool:
    """Validate AWS account ID format."""
    return bool(re.match(r"^\d{12}$", account_id))

def validate_service_name(service: str) -> bool:
    """Validate service name format."""
    return bool(re.match(r"^[A-Z][A-Za-z0-9]{1,30}$", service))

def sanitize_tag_key(key: str) -> str:
    """Sanitize tag key to prevent injection."""
    return re.sub(r"[^a-zA-Z0-9_\-:./]", "", key)[:128]

def sanitize_tag_value(value: str) -> str:
    """Sanitize tag value to prevent injection."""
    return re.sub(r"[^a-zA-Z0-9_\-:./@ ]", "", value)[:256]

def validate_cost_threshold(value: float) -> bool:
    """Validate cost threshold is reasonable."""
    return 0 <= value <= 1000000

def validate_regions(regions: List[str]) -> List[str]:
    """Validate and filter region list."""
    return [r for r in regions if validate_region(r)]

def validate_date_format(date_str: str) -> Optional[str]:
    """Validate date format YYYY-MM-DD."""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    return None
