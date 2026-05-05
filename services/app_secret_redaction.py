from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping


REDACTED_SECRET = "***REDACTED***"

SECRET_KEY_PATTERNS = (
    "password",
    "passwd",
    "token",
    "secret",
    "private_key",
    "privatekey",
    "pem_path",
    "pemfile",
    "auth",
)


def is_secret_key(key: Any) -> bool:
    """Return True when a field name is expected to hold secret material."""
    normalized = str(key).lower().replace("-", "_")
    return any(pattern in normalized for pattern in SECRET_KEY_PATTERNS)


def redact_value(key: Any, value: Any) -> Any:
    """Redact a value if the associated key name suggests it is secret."""
    if is_secret_key(key) and value not in (None, ""):
        return REDACTED_SECRET
    return value


def redact_mapping(data: Mapping[str, Any]) -> dict:
    """Return a recursively redacted copy of a mapping."""
    return {key: redact_value(key, redact_secrets(value)) for key, value in data.items()}


def redact_secrets(value: Any) -> Any:
    """Return a copy of value with nested secret-looking fields redacted."""
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value
