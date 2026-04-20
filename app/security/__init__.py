"""Security utilities for sensorhub."""

import hashlib
import hmac
import secrets
import time


def generate_api_key(length: int = 32) -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(length)


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return secrets.compare_digest(a, b)


def compute_hmac(key: str, message: str) -> str:
    """Compute HMAC-SHA256 of a message using the given key."""
    return hmac.new(
        key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_hmac(key: str, message: str, expected: str) -> bool:
    """Verify HMAC signature using constant-time comparison."""
    computed = compute_hmac(key, message)
    return constant_time_compare(computed, expected)


def is_timestamp_fresh(timestamp_str: str, max_age_seconds: int = 30) -> bool:
    """Check if a timestamp is within the acceptable age window."""
    try:
        ts = int(timestamp_str)
        now = int(time.time())
        return abs(now - ts) <= max_age_seconds
    except (ValueError, TypeError):
        return False


def generate_nonce() -> str:
    """Generate a random 128-bit hex nonce."""
    return secrets.token_hex(16)