import pytest

from services.node_allowlist_service import (
    NodeAllowListError,
    NodeAllowListService,
    build_add_allowed_command,
    build_get_allowed_command,
    parse_allowed_addresses,
)


class FakeDockerRuntime:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute_command(self, command, timeout=None):
        self.calls.append((command, timeout))
        return self.responses.pop(0)


def test_allowed_address_parser_ignores_comments_and_empty_lines():
    output = """
    0xai_existing Alice # comment

    0xai_no_alias
    """

    assert parse_allowed_addresses(output) == {
        "0xai_existing": "Alice",
        "0xai_no_alias": "",
    }


def test_allowlist_merge_does_not_overwrite_existing_alias():
    runtime = FakeDockerRuntime([("0xai_launcher ExistingAlias\n", "", 0)])
    service = NodeAllowListService(runtime, timeout=7)

    result = service.ensure_allowed("r1devnode", "0xai_launcher", "launcher-sdk")

    assert result.changed is False
    assert result.addresses == {"0xai_launcher": "ExistingAlias"}
    assert runtime.calls == [(build_get_allowed_command("r1devnode"), 7)]


def test_allowlist_merge_adds_missing_sdk_address():
    runtime = FakeDockerRuntime([("0xai_existing Alice\n", "", 0), ("ok", "", 0)])
    service = NodeAllowListService(runtime, timeout=7)

    result = service.ensure_allowed("r1devnode", "0xai_launcher", "launcher-sdk")

    assert result.changed is True
    assert result.addresses["0xai_existing"] == "Alice"
    assert result.addresses["0xai_launcher"] == "launcher-sdk"
    assert runtime.calls == [
        (build_get_allowed_command("r1devnode"), 7),
        (build_add_allowed_command("r1devnode", "0xai_launcher", "launcher-sdk"), 7),
    ]


def test_allowlist_merge_reports_docker_failure():
    runtime = FakeDockerRuntime([("", "container not running", 1)])
    service = NodeAllowListService(runtime)

    with pytest.raises(NodeAllowListError, match="container not running"):
        service.ensure_allowed("r1devnode", "0xai_launcher")
