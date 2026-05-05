from services.app_launch_preflight import AppLaunchPreflightService
from services.node_allowlist_service import AllowListMergeResult
from services.sdk_identity_service import SdkIdentity


class FakeIdentityService:
    def __init__(self):
        self.calls = 0

    def load_identity(self):
        self.calls += 1
        return SdkIdentity(sdk_address="0xai_launcher", eth_address="0xeth")


class FakeAllowListService:
    def __init__(self):
        self.calls = []

    def ensure_allowed(self, container_name, sdk_address, alias):
        self.calls.append((container_name, sdk_address, alias))
        return AllowListMergeResult(
            changed=True,
            addresses={"0xai_existing": "Alice", sdk_address: alias},
            command=["docker", "exec", container_name, "add_allowed", sdk_address, alias],
        )


def test_app_launch_preflight_loads_identity_and_merges_allowlist():
    identity_service = FakeIdentityService()
    allowlist_service = FakeAllowListService()
    service = AppLaunchPreflightService(
        identity_service=identity_service,
        allowlist_service=allowlist_service,
        allowed_alias="launcher-sdk",
    )

    result = service.prepare("r1devnode")

    assert identity_service.calls == 1
    assert allowlist_service.calls == [("r1devnode", "0xai_launcher", "launcher-sdk")]
    assert result.identity.sdk_address == "0xai_launcher"
    assert result.allowlist.changed is True
    assert result.allowlist.addresses["0xai_existing"] == "Alice"
