from __future__ import annotations

from dataclasses import dataclass


SDK_CREDENTIALS_MESSAGE = "Ratio1 SDK credentials are not configured. Configure network credentials, then retry."
SDK_VERSION_MESSAGE = "Ratio1 rejected the launcher SDK version. Update the Ratio1 SDK, then retry."


@dataclass(frozen=True)
class SdkErrorMessage:
    category: str
    user_message: str
    diagnostic: str
    classified: bool


def classify_sdk_error(error: str) -> SdkErrorMessage:
    diagnostic = str(error or "Unknown SDK error").strip() or "Unknown SDK error"
    normalized = diagnostic.lower()

    if "no user specified" in normalized and (
        "edge protocol network" in normalized or "credential" in normalized
    ):
        return SdkErrorMessage(
            category="credentials",
            user_message=SDK_CREDENTIALS_MESSAGE,
            diagnostic=diagnostic,
            classified=True,
        )

    if (
        ("dauth rejected" in normalized and "version check failed" in normalized)
        or ("sender app version" in normalized and "too old" in normalized)
    ):
        return SdkErrorMessage(
            category="version",
            user_message=SDK_VERSION_MESSAGE,
            diagnostic=diagnostic,
            classified=True,
        )

    return SdkErrorMessage(
        category="sdk",
        user_message=diagnostic,
        diagnostic=diagnostic,
        classified=False,
    )
