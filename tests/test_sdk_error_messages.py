from services.sdk_error_messages import (
    SDK_CREDENTIALS_MESSAGE,
    SDK_VERSION_MESSAGE,
    classify_sdk_error,
)


def test_classify_sdk_credentials_error():
    result = classify_sdk_error(
        "Error: No user specified for ratio1 Edge Protocol network connection. "
        "Please make sure you have the correct credentials."
    )

    assert result.classified is True
    assert result.category == "credentials"
    assert result.user_message == SDK_CREDENTIALS_MESSAGE
    assert "No user specified" in result.diagnostic


def test_classify_sdk_version_error():
    result = classify_sdk_error(
        "dAuth rejected node: Version check failed: FAIL: Sender app version 1.1.10 is too old"
    )

    assert result.classified is True
    assert result.category == "version"
    assert result.user_message == SDK_VERSION_MESSAGE


def test_classify_sdk_error_keeps_unknown_diagnostic():
    result = classify_sdk_error("Unexpected SDK failure")

    assert result.classified is False
    assert result.category == "sdk"
    assert result.user_message == "Unexpected SDK failure"
    assert result.diagnostic == "Unexpected SDK failure"
