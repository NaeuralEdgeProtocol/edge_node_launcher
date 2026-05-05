from __future__ import annotations

from dataclasses import dataclass


DEFAULT_ALLOWED_ALIAS = "launcher-sdk"
DEFAULT_ALLOWED_TIMEOUT = 90


class NodeAllowListError(RuntimeError):
    pass


@dataclass(frozen=True)
class AllowListMergeResult:
    changed: bool
    addresses: dict[str, str]
    command: list[str] | None = None


def build_get_allowed_command(container_name: str) -> list[str]:
    return ["docker", "exec", container_name, "get_allowed"]


def build_add_allowed_command(container_name: str, sdk_address: str, alias: str) -> list[str]:
    return ["docker", "exec", container_name, "add_allowed", sdk_address, alias]


def parse_allowed_addresses(output: str) -> dict[str, str]:
    addresses: dict[str, str] = {}
    for line in (output or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        address = parts[0]
        alias = parts[1].strip() if len(parts) > 1 else ""
        addresses[address] = alias
    return addresses


class NodeAllowListService:
    """Merge the launcher SDK address into a local node allowed list."""

    def __init__(self, docker_runtime, *, timeout: int = DEFAULT_ALLOWED_TIMEOUT):
        self.docker_runtime = docker_runtime
        self.timeout = timeout

    def get_allowed(self, container_name: str) -> dict[str, str]:
        stdout, stderr, return_code = self.docker_runtime.execute_command(
            build_get_allowed_command(container_name),
            timeout=self.timeout,
        )
        if return_code != 0:
            raise NodeAllowListError(stderr.strip() or stdout.strip() or "get_allowed failed")
        return parse_allowed_addresses(stdout)

    def ensure_allowed(
        self,
        container_name: str,
        sdk_address: str,
        alias: str = DEFAULT_ALLOWED_ALIAS,
    ) -> AllowListMergeResult:
        addresses = self.get_allowed(container_name)
        if sdk_address in addresses:
            return AllowListMergeResult(changed=False, addresses=addresses)

        command = build_add_allowed_command(container_name, sdk_address, alias)
        stdout, stderr, return_code = self.docker_runtime.execute_command(
            command,
            timeout=self.timeout,
        )
        if return_code != 0:
            raise NodeAllowListError(stderr.strip() or stdout.strip() or "add_allowed failed")

        merged = dict(addresses)
        merged[sdk_address] = alias
        return AllowListMergeResult(changed=True, addresses=merged, command=command)
