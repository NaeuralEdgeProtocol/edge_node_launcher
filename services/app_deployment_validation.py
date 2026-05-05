from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from services.app_deployment_models import ContainerAppSpec, WorkerAppSpec


APP_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,36}$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NODE_ADDRESS_RE = re.compile(r"^0xai_[A-Za-z0-9_-]{8,48}$")
REGISTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]{1,5})?$")
MEMORY_RE = re.compile(r"^\d+(\.\d+)?\s*(m|mb|mi|mib|g|gb|gi|gib)$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


def validate_app_name(value: str, field: str = "app_name") -> list[ValidationIssue]:
    if not value or not value.strip():
        return [ValidationIssue(field, "App name is required.")]
    if not APP_NAME_RE.match(value.strip()):
        return [
            ValidationIssue(
                field,
                "Use 3-36 letters, numbers, hyphens, or underscores.",
            )
        ]
    return []


def validate_node_address(value: str, field: str = "node_address") -> list[ValidationIssue]:
    if not value or not value.strip():
        return [ValidationIssue(field, "Target node address is required.")]
    if len(value.strip()) > 52 or not NODE_ADDRESS_RE.match(value.strip()):
        return [ValidationIssue(field, "Use a valid SDK node address starting with 0xai_.")]
    return []


def validate_image(value: str, field: str = "image") -> list[ValidationIssue]:
    normalized = (value or "").strip()
    if len(normalized) < 3:
        return [ValidationIssue(field, "Docker image is required.")]
    if len(normalized) > 256 or any(char.isspace() for char in normalized):
        return [ValidationIssue(field, "Docker image must be a compact image reference.")]
    return []


def validate_registry(value: str, field: str = "registry_server") -> list[ValidationIssue]:
    normalized = (value or "").strip()
    if len(normalized) < 3 or len(normalized) > 128:
        return [ValidationIssue(field, "Registry server is required.")]
    if not REGISTRY_RE.match(normalized):
        return [ValidationIssue(field, "Use a valid registry host such as docker.io.")]
    if "." not in normalized and not normalized.startswith("localhost"):
        return [ValidationIssue(field, "Registry host must include a domain or localhost.")]
    return []


def validate_port(value: int, field: str = "port") -> list[ValidationIssue]:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return [ValidationIssue(field, "Port must be a number.")]
    if port < 1 or port > 65535:
        return [ValidationIssue(field, "Port must be between 1 and 65535.")]
    return []


def validate_memory(value: str, field: str = "resources.memory") -> list[ValidationIssue]:
    if not MEMORY_RE.match((value or "").strip()):
        return [ValidationIssue(field, "Memory must use a unit such as 512m or 1g.")]
    return []


def validate_cpu(value: float, field: str = "resources.cpu") -> list[ValidationIssue]:
    try:
        cpu = float(value)
    except (TypeError, ValueError):
        return [ValidationIssue(field, "CPU must be numeric.")]
    if cpu <= 0:
        return [ValidationIssue(field, "CPU must be greater than zero.")]
    return []


def validate_env_mapping(env: dict[str, str], field: str = "env") -> list[ValidationIssue]:
    issues = []
    for key, value in (env or {}).items():
        if not key or not str(key).strip():
            issues.append(ValidationIssue(field, "Environment variable key is required."))
        elif not ENV_KEY_RE.match(str(key)):
            issues.append(ValidationIssue(field, f"Invalid environment variable key: {key}."))
        if value is None:
            issues.append(ValidationIssue(field, f"Environment variable {key} needs a value."))
    return issues


def validate_commands(commands: list[str], field: str = "commands") -> list[ValidationIssue]:
    issues = []
    normalized = [command.strip() for command in commands or [] if command and command.strip()]
    if not normalized:
        return [ValidationIssue(field, "At least one build or run command is required.")]
    seen = set()
    for command in normalized:
        if len(command) < 2 or len(command) > 512:
            issues.append(ValidationIssue(field, "Commands must be 2-512 characters."))
        if command in seen:
            issues.append(ValidationIssue(field, f"Duplicate command: {command}."))
        seen.add(command)
    return issues


def validate_volumes(volumes: dict[str, str], field: str = "volumes") -> list[ValidationIssue]:
    issues = []
    for source, mount_path in (volumes or {}).items():
        if not str(source or "").strip() or not str(mount_path or "").strip():
            issues.append(ValidationIssue(field, "Volume source and mount path are required."))
            continue
        if not str(mount_path).strip().startswith("/"):
            issues.append(ValidationIssue(field, "Volume mount path must start with /."))
    return issues


def validate_poll_interval(value: int, field: str) -> list[ValidationIssue]:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return [ValidationIssue(field, "Poll interval must be a number of seconds.")]
    if interval < 5 or interval > 86400:
        return [ValidationIssue(field, "Poll interval must be between 5 seconds and 1 day.")]
    return []


def validate_github_repo_url(value: str, field: str = "repo_url") -> list[ValidationIssue]:
    normalized = (value or "").strip()
    if len(normalized) < 1:
        return [ValidationIssue(field, "GitHub repository URL is required.")]
    if len(normalized) > 512:
        return [ValidationIssue(field, "GitHub repository URL is too long.")]
    parsed = urlparse(normalized)
    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != "github.com":
        return [ValidationIssue(field, "Use a GitHub URL such as https://github.com/org/repo.")]
    if len(path_parts) < 2:
        return [ValidationIssue(field, "GitHub URL must include owner and repository.")]
    return []


def validate_container_spec(spec: ContainerAppSpec) -> list[ValidationIssue]:
    return [
        *validate_app_name(spec.app_name),
        *validate_node_address(spec.node_address),
        *validate_image(spec.image),
        *validate_port(spec.port),
        *validate_registry(spec.registry_server),
        *validate_cpu(spec.resources.cpu),
        *validate_memory(spec.resources.memory),
        *validate_env_mapping(spec.env),
        *validate_env_mapping(spec.dynamic_env, "dynamic_env"),
        *validate_volumes(spec.volumes),
    ]


def validate_worker_spec(spec: WorkerAppSpec) -> list[ValidationIssue]:
    return [
        *validate_app_name(spec.app_name),
        *validate_node_address(spec.node_address),
        *validate_github_repo_url(spec.repo_url),
        *validate_image(spec.image),
        *validate_port(spec.port),
        *validate_registry(spec.registry_server),
        *validate_cpu(spec.resources.cpu),
        *validate_memory(spec.resources.memory),
        *validate_env_mapping(spec.env),
        *validate_env_mapping(spec.dynamic_env, "dynamic_env"),
        *validate_commands(spec.commands),
        *validate_volumes(spec.volumes),
        *validate_poll_interval(spec.vcs_poll_interval, "vcs_poll_interval"),
    ]
