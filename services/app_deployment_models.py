from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.app_secret_redaction import redact_secrets


APP_REGISTRY_SCHEMA_VERSION = 1
APP_TYPE_CONTAINER = "CAR"
APP_TYPE_WORKER = "WAR"
PLUGIN_SIGNATURE_CONTAINER = "CONTAINER_APP_RUNNER"
PLUGIN_SIGNATURE_WORKER = "WORKER_APP_RUNNER"

DEFAULT_CONTAINER_REGISTRY = "docker.io"
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = 1
DEFAULT_CONTAINER_PORT = 5000
DEFAULT_WORKER_IMAGE = "node:22"
DEFAULT_WORKER_COMMANDS = ("npm install", "npm run build", "npm run start")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def pipeline_name_from_app_name(app_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", app_name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "launcher_app"


@dataclass
class AppResourceSpec:
    cpu: float = DEFAULT_CPU_LIMIT
    memory: str = DEFAULT_MEMORY_LIMIT
    gpu: int = 0
    ports: list[int] = field(default_factory=list)

    def to_sdk_dict(self) -> dict[str, Any]:
        return {
            "cpu": self.cpu,
            "gpu": self.gpu,
            "memory": self.memory,
            "ports": list(self.ports),
        }


@dataclass
class FileVolumeSpec:
    content: str
    mounting_point: str

    def to_sdk_dict(self) -> dict[str, str]:
        return {
            "content": self.content,
            "mounting_point": self.mounting_point,
        }


@dataclass
class ContainerAppSpec:
    app_name: str
    node_address: str
    image: str
    port: int = DEFAULT_CONTAINER_PORT
    registry_server: str = DEFAULT_CONTAINER_REGISTRY
    registry_username: str = ""
    registry_password: str = ""
    env: dict[str, str] = field(default_factory=dict)
    dynamic_env: dict[str, str] = field(default_factory=dict)
    volumes: dict[str, str] = field(default_factory=dict)
    file_volumes: dict[str, FileVolumeSpec] = field(default_factory=dict)
    resources: AppResourceSpec = field(default_factory=AppResourceSpec)
    tunnel_engine_enabled: bool = True
    tunnel_engine: str = "ngrok"
    cloudflare_token: str = ""
    ngrok_edge_label: str = ""
    restart_policy: str = "always"
    image_pull_policy: str = "always"

    @property
    def app_type(self) -> str:
        return APP_TYPE_CONTAINER

    @property
    def plugin_signature(self) -> str:
        return PLUGIN_SIGNATURE_CONTAINER

    @property
    def pipeline_name(self) -> str:
        return pipeline_name_from_app_name(self.app_name)

    def to_sdk_kwargs(self) -> dict[str, Any]:
        kwargs = {
            "node": self.node_address,
            "name": self.app_name,
            "image": self.image,
            "port": self.port,
            "container_resources": self.resources.to_sdk_dict(),
            "cr": self.registry_server,
            "env": dict(self.env),
            "dynamic_env": dict(self.dynamic_env),
            "volumes": dict(self.volumes),
            "file_volumes": _file_volumes_to_sdk(self.file_volumes),
            "tunnel_engine_enabled": self.tunnel_engine_enabled,
            "tunnel_engine": self.tunnel_engine,
            "restart_policy": self.restart_policy,
            "image_pull_policy": self.image_pull_policy,
        }
        if self.registry_username:
            kwargs["cr_user"] = self.registry_username
        if self.registry_password:
            kwargs["cr_password"] = self.registry_password
        if self.cloudflare_token:
            kwargs["cloudflare_token"] = self.cloudflare_token
        if self.ngrok_edge_label:
            kwargs["ngrok_edge_label"] = self.ngrok_edge_label
        return kwargs

    def to_record_metadata(self) -> dict[str, Any]:
        return redact_secrets(
            {
                "image": self.image,
                "port": self.port,
                "registry_server": self.registry_server,
                "registry_username": self.registry_username,
                "registry_password": self.registry_password,
                "env": self.env,
                "volumes": self.volumes,
                "resources": self.resources.to_sdk_dict(),
                "tunnel_engine": self.tunnel_engine,
                "cloudflare_token": self.cloudflare_token,
                "restart_policy": self.restart_policy,
                "image_pull_policy": self.image_pull_policy,
            }
        )


@dataclass
class WorkerAppSpec:
    app_name: str
    node_address: str
    repo_url: str
    branch: str = "main"
    image: str = DEFAULT_WORKER_IMAGE
    github_username: str = ""
    github_token: str = ""
    commands: list[str] = field(default_factory=lambda: list(DEFAULT_WORKER_COMMANDS))
    port: int = 4173
    registry_server: str = DEFAULT_CONTAINER_REGISTRY
    registry_username: str = ""
    registry_password: str = ""
    env: dict[str, str] = field(default_factory=dict)
    dynamic_env: dict[str, str] = field(default_factory=dict)
    volumes: dict[str, str] = field(default_factory=dict)
    file_volumes: dict[str, FileVolumeSpec] = field(default_factory=dict)
    resources: AppResourceSpec = field(default_factory=AppResourceSpec)
    tunnel_engine_enabled: bool = True
    tunnel_engine: str = "cloudflare"
    cloudflare_token: str = ""
    ngrok_edge_label: str = ""
    endpoint_url: Optional[str] = None
    endpoint_poll_interval: int = 30
    restart_policy: str = "always"
    image_pull_policy: str = "always"
    image_poll_interval: int = 300
    vcs_poll_interval: int = 60

    @property
    def app_type(self) -> str:
        return APP_TYPE_WORKER

    @property
    def plugin_signature(self) -> str:
        return PLUGIN_SIGNATURE_WORKER

    @property
    def pipeline_name(self) -> str:
        return pipeline_name_from_app_name(self.app_name)

    def to_sdk_kwargs(self) -> dict[str, Any]:
        owner, repo_name = parse_github_repo_owner_name(self.repo_url)
        kwargs = {
            "node": self.node_address,
            "name": self.app_name,
            "tunnel_engine": self.tunnel_engine,
            "tunnel_engine_enabled": self.tunnel_engine_enabled,
            "vcs_data": {
                "PROVIDER": "github",
                "USERNAME": self.github_username or None,
                "TOKEN": self.github_token or None,
                "REPO_OWNER": owner,
                "REPO_NAME": repo_name,
                "BRANCH": self.branch,
            },
            "image": self.image,
            "build_and_run_commands": list(self.commands),
            "cr_data": {
                "SERVER": self.registry_server,
                "USERNAME": self.registry_username or None,
                "PASSWORD": self.registry_password or None,
            },
            "env": dict(self.env),
            "dynamic_env": dict(self.dynamic_env),
            "port": self.port,
            "endpoint_url": self.endpoint_url,
            "endpoint_poll_interval": self.endpoint_poll_interval,
            "container_resources": self.resources.to_sdk_dict(),
            "volumes": dict(self.volumes),
            "file_volumes": _file_volumes_to_sdk(self.file_volumes),
            "restart_policy": self.restart_policy,
            "image_pull_policy": self.image_pull_policy,
            "image_poll_interval": self.image_poll_interval,
            "vcs_poll_interval": self.vcs_poll_interval,
        }
        if self.cloudflare_token:
            kwargs["cloudflare_token"] = self.cloudflare_token
        if self.ngrok_edge_label:
            kwargs["ngrok_edge_label"] = self.ngrok_edge_label
        return kwargs

    def to_record_metadata(self) -> dict[str, Any]:
        return redact_secrets(
            {
                "repo_url": self.repo_url,
                "branch": self.branch,
                "image": self.image,
                "github_username": self.github_username,
                "github_token": self.github_token,
                "commands": self.commands,
                "port": self.port,
                "registry_server": self.registry_server,
                "registry_username": self.registry_username,
                "registry_password": self.registry_password,
                "env": self.env,
                "volumes": self.volumes,
                "resources": self.resources.to_sdk_dict(),
                "tunnel_engine": self.tunnel_engine,
                "cloudflare_token": self.cloudflare_token,
                "restart_policy": self.restart_policy,
                "image_pull_policy": self.image_pull_policy,
                "vcs_poll_interval": self.vcs_poll_interval,
            }
        )


@dataclass
class DeploymentResult:
    app_id: str
    app_name: str
    app_type: str
    node_address: str
    pipeline_name: str
    plugin_signature: str
    instance_id: str = ""
    app_url: str = ""
    status: str = "unknown"
    created_at: str = field(default_factory=utc_now_iso)

    def to_record(self, metadata: Optional[dict[str, Any]] = None) -> "ManagedAppRecord":
        return ManagedAppRecord(
            app_id=self.app_id,
            app_name=self.app_name,
            app_type=self.app_type,
            node_address=self.node_address,
            pipeline_name=self.pipeline_name,
            plugin_signature=self.plugin_signature,
            instance_id=self.instance_id,
            app_url=self.app_url,
            status=self.status,
            last_action="deployed",
            created_at=self.created_at,
            updated_at=utc_now_iso(),
            metadata=metadata or {},
        )


@dataclass
class ManagedAppRecord:
    app_id: str
    app_name: str
    app_type: str
    node_address: str
    pipeline_name: str
    plugin_signature: str
    instance_id: str = ""
    app_url: str = ""
    status: str = "unknown"
    last_action: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManagedAppRecord":
        return cls(
            app_id=data.get("app_id", ""),
            app_name=data.get("app_name", ""),
            app_type=data.get("app_type", ""),
            node_address=data.get("node_address", ""),
            pipeline_name=data.get("pipeline_name", ""),
            plugin_signature=data.get("plugin_signature", ""),
            instance_id=data.get("instance_id", ""),
            app_url=data.get("app_url", ""),
            status=data.get("status", "unknown"),
            last_action=data.get("last_action", ""),
            created_at=data.get("created_at") or utc_now_iso(),
            updated_at=data.get("updated_at") or utc_now_iso(),
            metadata=data.get("metadata") or {},
        )

    def to_dict(self, *, redact: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if redact:
            data = redact_secrets(data)
        return data


@dataclass
class SdkAppStatus:
    node_address: str
    app_name: str
    plugin_signature: str
    instance_id: str
    owner: str = ""
    status: str = "unknown"
    url: str = ""
    last_error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def parse_github_repo_owner_name(repo_url: str) -> tuple[str, str]:
    from urllib.parse import urlparse

    parsed = urlparse(repo_url.strip())
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        return "", ""
    repo_name = path_parts[1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return path_parts[0], repo_name


def _file_volumes_to_sdk(file_volumes: dict[str, FileVolumeSpec]) -> dict[str, dict[str, str]]:
    return {name: spec.to_sdk_dict() for name, spec in file_volumes.items()}
