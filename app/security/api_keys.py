"""API key generation and hashing helpers."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from hashlib import sha256

API_KEY_HEADER = "X-Sentinel-API-Key"
DEFAULT_KEY_PREFIX = "sk_sentinel"
TEST_KEY_PREFIX = "sk_test"


@dataclass
class ApiKeyPrincipal:
    """Authenticated principal derived from an API key."""

    email: str
    key_id: str
    label: str | None = None


def generate_api_key(prefix: str = DEFAULT_KEY_PREFIX) -> str:
    """Generate a new API key string.

    The key is formatted as ``<prefix>_<hex>`` where the hex string contains
    32 random bytes (64 hex characters).
    """

    random_part = secrets.token_hex(32)
    return f"{prefix}_{random_part}"


def key_prefix(api_key: str, length: int = 8) -> str:
    """Return a short prefix used for lookup and display."""

    cleaned = api_key.strip()
    if "_" in cleaned:
        cleaned = cleaned.rsplit("_", maxsplit=1)[-1]
    return cleaned[:length]


def hash_api_key(api_key: str, pepper: str) -> str:
    """Return a HMAC-SHA256 hash of the API key using the provided pepper."""

    if not pepper:
        raise ValueError("API key pepper must be configured to hash keys")

    digest = hmac.new(pepper.encode(), api_key.encode(), sha256)
    return digest.hexdigest()


def is_test_key(api_key: str) -> bool:
    """Return True if the provided key is intended for test environments."""

    return api_key.startswith(f"{TEST_KEY_PREFIX}_")

