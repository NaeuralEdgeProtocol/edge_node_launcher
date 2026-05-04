import os
import re
import sys
from dataclasses import dataclass
from typing import Mapping, Sequence


EDGE_NODE_REPOSITORY = "ratio1/edge_node"
GPU_EDGE_NODE_REPOSITORY = "ratio1/edge_node_gpu"
MAINNET_TAG = "mainnet"
DEVNET_TAG = "devnet"
TESTNET_TAG = "testnet"
PRODUCTION_EDGE_NODE_IMAGE = f"{EDGE_NODE_REPOSITORY}:{MAINNET_TAG}"
GPU_PRODUCTION_EDGE_NODE_IMAGE = f"{GPU_EDGE_NODE_REPOSITORY}:{MAINNET_TAG}"
DEVNET_EDGE_NODE_IMAGE = f"{EDGE_NODE_REPOSITORY}:{DEVNET_TAG}"
EDGE_IMAGE_ENV_VAR = "R1_EDGE_NODE_IMAGE"
EDGE_IMAGE_TAG_ENV_VAR = "R1_EDGE_NODE_TAG"
EDGE_IMAGE_CLI_ARG = "--edge-image"
KNOWN_NETWORK_TAGS = {MAINNET_TAG, DEVNET_TAG, TESTNET_TAG}
MAINNET_CONTAINER_PREFIX = "r1node"
MAINNET_VOLUME_PREFIX = "r1vol"
RESOURCE_NAME_PREFIXES = {
    MAINNET_TAG: (MAINNET_CONTAINER_PREFIX, MAINNET_VOLUME_PREFIX),
    DEVNET_TAG: ("r1devnode", "r1devvol"),
    TESTNET_TAG: ("r1testnode", "r1testvol"),
}


@dataclass(frozen=True)
class EdgeNodeImageConfig:
    image: str
    source: str
    requested_image: str | None = None
    override_allowed: bool = True
    production_mode: bool = False
    ignored_reason: str = ""

    @property
    def tag(self) -> str:
        last_segment = self.image.rsplit("/", 1)[-1]
        if ":" not in last_segment:
            return MAINNET_TAG
        return last_segment.rsplit(":", 1)[-1]

    @property
    def environment_key(self) -> str:
        return self.tag if self.tag in KNOWN_NETWORK_TAGS else MAINNET_TAG

    @property
    def display_name(self) -> str:
        if self.tag in KNOWN_NETWORK_TAGS:
            return self.tag.capitalize()
        return self.resource_key.capitalize()

    @property
    def is_mainnet(self) -> bool:
        return self.tag == MAINNET_TAG

    @property
    def gpu_image(self) -> str:
        return f"{GPU_EDGE_NODE_REPOSITORY}:{self.tag}"

    @property
    def resource_key(self) -> str:
        if self.tag in RESOURCE_NAME_PREFIXES:
            return self.tag

        sanitized = re.sub(r"[^a-z0-9]+", "", self.tag.lower())
        return sanitized or "custom"

    @property
    def container_prefix(self) -> str:
        prefixes = RESOURCE_NAME_PREFIXES.get(self.resource_key)
        if prefixes:
            return prefixes[0]
        return f"r1{self.resource_key}node"

    @property
    def volume_prefix(self) -> str:
        prefixes = RESOURCE_NAME_PREFIXES.get(self.resource_key)
        if prefixes:
            return prefixes[1]
        return f"r1{self.resource_key}vol"

    @property
    def default_container_name(self) -> str:
        return self.container_prefix

    @property
    def default_volume_name(self) -> str:
        return self.volume_prefix


_active_config: EdgeNodeImageConfig | None = None


def running_from_frozen_executable() -> bool:
    return bool(getattr(sys, "frozen", False))


def normalize_edge_node_image(value: str | None) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return PRODUCTION_EDGE_NODE_IMAGE
    if candidate in KNOWN_NETWORK_TAGS:
        return f"{EDGE_NODE_REPOSITORY}:{candidate}"

    last_segment = candidate.rsplit("/", 1)[-1]
    if ":" not in last_segment:
        return f"{candidate}:{MAINNET_TAG}"
    return candidate


def _requested_image_from_environment(environ: Mapping[str, str]) -> tuple[str | None, str]:
    if EDGE_IMAGE_ENV_VAR in environ and environ[EDGE_IMAGE_ENV_VAR].strip():
        return environ[EDGE_IMAGE_ENV_VAR], EDGE_IMAGE_ENV_VAR
    if EDGE_IMAGE_TAG_ENV_VAR in environ and environ[EDGE_IMAGE_TAG_ENV_VAR].strip():
        return environ[EDGE_IMAGE_TAG_ENV_VAR], EDGE_IMAGE_TAG_ENV_VAR
    return None, "default"


def resolve_edge_node_image_config(
    *,
    cli_image: str | None = None,
    environ: Mapping[str, str] | None = None,
    production_mode: bool | None = None,
) -> EdgeNodeImageConfig:
    env = environ if environ is not None else os.environ
    env_image, env_source = _requested_image_from_environment(env)
    requested = cli_image or env_image
    source = "cli" if cli_image else env_source
    production = running_from_frozen_executable() if production_mode is None else production_mode

    if production:
        ignored_reason = ""
        if requested and normalize_edge_node_image(requested) != PRODUCTION_EDGE_NODE_IMAGE:
            ignored_reason = "Non-mainnet Docker image overrides are ignored in packaged production runs."
        return EdgeNodeImageConfig(
            image=PRODUCTION_EDGE_NODE_IMAGE,
            source="production-default",
            requested_image=requested,
            override_allowed=False,
            production_mode=True,
            ignored_reason=ignored_reason,
        )

    if requested:
        return EdgeNodeImageConfig(
            image=normalize_edge_node_image(requested),
            source=source,
            requested_image=requested,
            override_allowed=True,
            production_mode=False,
        )

    return EdgeNodeImageConfig(
        image=PRODUCTION_EDGE_NODE_IMAGE,
        source="default",
        production_mode=False,
    )


def configure_edge_node_image(
    *,
    cli_image: str | None = None,
    environ: Mapping[str, str] | None = None,
    production_mode: bool | None = None,
) -> EdgeNodeImageConfig:
    global _active_config
    _active_config = resolve_edge_node_image_config(
        cli_image=cli_image,
        environ=environ,
        production_mode=production_mode,
    )
    return _active_config


def get_edge_node_image_config() -> EdgeNodeImageConfig:
    global _active_config
    if _active_config is None:
        _active_config = resolve_edge_node_image_config()
    return _active_config


def get_edge_node_image() -> str:
    return get_edge_node_image_config().image


def consume_edge_image_cli_args(argv: Sequence[str]) -> tuple[str | None, list[str]]:
    if not argv:
        return None, []

    cleaned = [argv[0]]
    requested_image = None
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == EDGE_IMAGE_CLI_ARG:
            if index + 1 >= len(argv):
                raise ValueError(f"{EDGE_IMAGE_CLI_ARG} requires an image value")
            requested_image = argv[index + 1]
            index += 2
            continue
        if arg.startswith(f"{EDGE_IMAGE_CLI_ARG}="):
            requested_image = arg.split("=", 1)[1]
            index += 1
            continue

        cleaned.append(arg)
        index += 1

    return requested_image, cleaned


def reset_edge_node_image_config_for_tests() -> None:
    global _active_config
    _active_config = None
