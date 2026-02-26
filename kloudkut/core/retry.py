"""Retry logic with exponential backoff for AWS API calls."""
import time
import logging
from functools import wraps
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    """Decorator for retrying AWS API calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code in ["Throttling", "RequestLimitExceeded", "TooManyRequestsException"]:
                        if attempt < max_retries - 1:
                            delay = min(base_delay * (2 ** attempt), max_delay)
                            logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                            time.sleep(delay)
                            continue
                    raise
                except Exception:
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator
