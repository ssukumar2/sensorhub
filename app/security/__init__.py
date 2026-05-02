"""Security utilities for sensorhub.

Single source of truth: hmac_verify. This module re-exports its primitives
plus thin backward-compatible wrappers used by older tests.
"""
import hashlib
import hmac as _hmac
import secrets
import time

from app.security.hmac_verify import (
    generate_api_key,
    compute_hmac as compute_hmac_signed,
    verify_hmac as verify_hmac_signed,
)


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return secrets.compare_digest(a, b)


def compute_hmac(key: str, message: str) -> str:
    """Compute HMAC-SHA256 of a raw message (legacy 2-arg form)."""
    return _hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_hmac(key: str, message: str, expected: str) -> bool:
    """Verify HMAC of a raw message (legacy 3-arg form)."""
    return constant_time_compare(compute_hmac(key, message), expected)


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


__all__ = [
    "generate_api_key",
    "constant_time_compare",
    "compute_hmac",
    "verify_hmac",
    "compute_hmac_signed",
    "verify_hmac_signed",
    "is_timestamp_fresh",
    "generate_nonce",
]