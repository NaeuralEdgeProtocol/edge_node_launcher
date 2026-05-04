import pytest

from utils.edge_image_config import (
    DEVNET_EDGE_NODE_IMAGE,
    EDGE_IMAGE_CLI_ARG,
    EDGE_IMAGE_ENV_VAR,
    EDGE_IMAGE_TAG_ENV_VAR,
    PRODUCTION_EDGE_NODE_IMAGE,
    configure_edge_node_image,
    consume_edge_image_cli_args,
    normalize_edge_node_image,
    resolve_edge_node_image_config,
)


def test_default_image_is_mainnet_for_local_runs():
    config = resolve_edge_node_image_config(environ={}, production_mode=False)

    assert config.image == PRODUCTION_EDGE_NODE_IMAGE
    assert config.source == "default"
    assert config.environment_key == "mainnet"
    assert config.is_mainnet is True
    assert config.container_prefix == "r1node"
    assert config.volume_prefix == "r1vol"
    assert config.default_container_name == "r1node"
    assert config.default_volume_name == "r1vol"


def test_env_image_override_selects_devnet_for_local_runs():
    config = resolve_edge_node_image_config(
        environ={EDGE_IMAGE_ENV_VAR: DEVNET_EDGE_NODE_IMAGE},
        production_mode=False,
    )

    assert config.image == DEVNET_EDGE_NODE_IMAGE
    assert config.source == EDGE_IMAGE_ENV_VAR
    assert config.environment_key == "devnet"
    assert config.is_mainnet is False
    assert config.container_prefix == "r1devnode"
    assert config.volume_prefix == "r1devvol"
    assert config.default_container_name == "r1devnode"
    assert config.default_volume_name == "r1devvol"


def test_env_tag_override_accepts_network_alias():
    config = resolve_edge_node_image_config(
        environ={EDGE_IMAGE_TAG_ENV_VAR: "devnet"},
        production_mode=False,
    )

    assert config.image == DEVNET_EDGE_NODE_IMAGE
    assert config.source == EDGE_IMAGE_TAG_ENV_VAR


def test_testnet_uses_separate_resource_prefixes():
    config = resolve_edge_node_image_config(
        cli_image="testnet",
        environ={},
        production_mode=False,
    )

    assert config.environment_key == "testnet"
    assert config.container_prefix == "r1testnode"
    assert config.volume_prefix == "r1testvol"


def test_cli_override_takes_precedence_over_environment():
    config = resolve_edge_node_image_config(
        cli_image="devnet",
        environ={EDGE_IMAGE_ENV_VAR: PRODUCTION_EDGE_NODE_IMAGE},
        production_mode=False,
    )

    assert config.image == DEVNET_EDGE_NODE_IMAGE
    assert config.source == "cli"


def test_production_runtime_ignores_non_mainnet_overrides():
    config = resolve_edge_node_image_config(
        cli_image=DEVNET_EDGE_NODE_IMAGE,
        environ={},
        production_mode=True,
    )

    assert config.image == PRODUCTION_EDGE_NODE_IMAGE
    assert config.source == "production-default"
    assert config.override_allowed is False
    assert config.ignored_reason


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("devnet", DEVNET_EDGE_NODE_IMAGE),
        ("ratio1/edge_node", PRODUCTION_EDGE_NODE_IMAGE),
        (DEVNET_EDGE_NODE_IMAGE, DEVNET_EDGE_NODE_IMAGE),
    ],
)
def test_normalize_edge_node_image(value, expected):
    assert normalize_edge_node_image(value) == expected


def test_consume_edge_image_cli_args_strips_launcher_option():
    image, cleaned = consume_edge_image_cli_args(
        ["main.py", "--foo", f"{EDGE_IMAGE_CLI_ARG}=devnet", "--bar"]
    )

    assert image == "devnet"
    assert cleaned == ["main.py", "--foo", "--bar"]


def test_consume_edge_image_cli_args_requires_value():
    with pytest.raises(ValueError, match="requires an image value"):
        consume_edge_image_cli_args(["main.py", EDGE_IMAGE_CLI_ARG])


def test_configured_image_is_process_global_until_reset():
    config = configure_edge_node_image(cli_image="devnet", environ={}, production_mode=False)

    assert config.image == DEVNET_EDGE_NODE_IMAGE
