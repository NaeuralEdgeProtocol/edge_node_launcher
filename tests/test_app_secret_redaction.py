from dataclasses import dataclass

from services.app_secret_redaction import (
    REDACTED_SECRET,
    is_secret_key,
    redact_secret_text,
    redact_secrets,
)


@dataclass
class SecretCarrier:
    registry_password: str
    visible_name: str


def test_secret_key_detection_matches_deployment_fields():
    assert is_secret_key("registry_password")
    assert is_secret_key("github_token")
    assert is_secret_key("cloudflare_token")
    assert is_secret_key("pem_path")
    assert not is_secret_key("image")


def test_redact_secrets_recurses_through_dicts_lists_and_dataclasses():
    payload = {
        "image": "nginx:alpine",
        "registry_password": "secret",
        "env": [
            {"key": "PUBLIC_VALUE", "value": "ok"},
            {"key": "API_TOKEN", "token": "abc"},
        ],
        "carrier": SecretCarrier(registry_password="hidden", visible_name="car"),
    }

    redacted = redact_secrets(payload)

    assert redacted["image"] == "nginx:alpine"
    assert redacted["registry_password"] == REDACTED_SECRET
    assert redacted["env"][0]["value"] == "ok"
    assert redacted["env"][1]["token"] == REDACTED_SECRET
    assert redacted["carrier"]["registry_password"] == REDACTED_SECRET
    assert redacted["carrier"]["visible_name"] == "car"


def test_redact_secret_text_masks_inline_assignments_and_bearer_tokens():
    text = "probe failed password: hunter2 token=abc123 Bearer ey.secret"

    redacted = redact_secret_text(text)

    assert "hunter2" not in redacted
    assert "abc123" not in redacted
    assert "ey.secret" not in redacted
    assert "password: [redacted]" in redacted
    assert "token=[redacted]" in redacted
    assert "Bearer [redacted]" in redacted
