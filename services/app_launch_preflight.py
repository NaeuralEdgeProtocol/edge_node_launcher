from __future__ import annotations

from dataclasses import dataclass

from services.node_allowlist_service import DEFAULT_ALLOWED_ALIAS, AllowListMergeResult
from services.sdk_identity_service import SdkIdentity


@dataclass(frozen=True)
class AppLaunchPreflightResult:
    identity: SdkIdentity
    allowlist: AllowListMergeResult


class AppLaunchPreflightService:
    """Prepare a local node for SDK app deployment."""

    def __init__(
        self,
        *,
        identity_service,
        allowlist_service,
        allowed_alias: str = DEFAULT_ALLOWED_ALIAS,
    ):
        self.identity_service = identity_service
        self.allowlist_service = allowlist_service
        self.allowed_alias = allowed_alias

    def prepare(self, container_name: str) -> AppLaunchPreflightResult:
        if not container_name:
            raise ValueError("Target container is required for SDK allow-list setup.")
        identity = self.identity_service.load_identity()
        allowlist = self.allowlist_service.ensure_allowed(
            container_name,
            identity.sdk_address,
            self.allowed_alias,
        )
        return AppLaunchPreflightResult(identity=identity, allowlist=allowlist)
