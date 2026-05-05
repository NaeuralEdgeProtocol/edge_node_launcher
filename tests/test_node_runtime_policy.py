from services.node_runtime_policy import (
    GPU_REASON_ALREADY_ASSIGNED,
    GPU_REASON_AVAILABLE,
    GPU_REASON_NON_PRIMARY_NODE,
    GPU_REASON_NOT_AVAILABLE,
    NEAR_BOUNDARY_NODE_RAM_GB,
    RECOMMENDED_NODE_CPU_COUNT,
    RECOMMENDED_NODE_RAM_GB,
    evaluate_node_capacity,
    plan_node_launch,
    runtime_policy_display,
)
from utils.edge_image_config import (
    DEVNET_EDGE_NODE_IMAGE,
    GPU_EDGE_NODE_REPOSITORY,
    resolve_edge_node_image_config,
)


def test_capacity_policy_uses_r1setup_resource_model():
    decision = evaluate_node_capacity(total_ram_gb=64.0, existing_node_count=2)

    assert decision.min_required_gb == RECOMMENDED_NODE_RAM_GB
    assert decision.recommended_cpu_count == RECOMMENDED_NODE_CPU_COUNT
    assert decision.max_nodes_supported == 4
    assert decision.used_by_nodes_gb == 32
    assert decision.can_add_node is True
    assert decision.to_legacy_dict()["can_add_node"] is True


def test_capacity_policy_flags_near_boundary_ram():
    decision = evaluate_node_capacity(
        total_ram_gb=NEAR_BOUNDARY_NODE_RAM_GB,
        existing_node_count=0,
    )

    assert decision.can_add_node is False
    assert decision.max_nodes_supported == 0
    assert decision.available_for_next_node_gb == NEAR_BOUNDARY_NODE_RAM_GB
    assert decision.near_boundary_warning is True


def test_cpu_launch_plan_keeps_current_image_and_namespaces():
    config = resolve_edge_node_image_config(environ={}, production_mode=False)

    plan = plan_node_launch("r1node", config, gpu_available=False)

    assert plan.image == config.image
    assert plan.use_gpu is False
    assert plan.gpu_reason == GPU_REASON_NOT_AVAILABLE
    assert config.container_prefix == "r1node"
    assert config.volume_prefix == "r1vol"


def test_devnet_cpu_launch_plan_keeps_isolated_dev_resources():
    config = resolve_edge_node_image_config(
        cli_image="devnet",
        environ={},
        production_mode=False,
    )

    plan = plan_node_launch("r1devnode2", config, gpu_available=True)

    assert config.image == DEVNET_EDGE_NODE_IMAGE
    assert config.container_prefix == "r1devnode"
    assert config.volume_prefix == "r1devvol"
    assert plan.image == DEVNET_EDGE_NODE_IMAGE
    assert plan.use_gpu is False
    assert plan.gpu_reason == GPU_REASON_NON_PRIMARY_NODE


def test_primary_node_uses_gpu_image_when_gpu_is_available():
    config = resolve_edge_node_image_config(
        cli_image="devnet",
        environ={},
        production_mode=False,
    )

    plan = plan_node_launch("r1devnode", config, gpu_available=True)

    assert plan.image == f"{GPU_EDGE_NODE_REPOSITORY}:devnet"
    assert plan.use_gpu is True
    assert plan.gpu_reason == GPU_REASON_AVAILABLE


def test_gpu_policy_allows_only_one_assigned_node():
    config = resolve_edge_node_image_config(environ={}, production_mode=False)

    plan = plan_node_launch(
        "r1node",
        config,
        gpu_available=True,
        existing_gpu_container_names=["r1node2"],
    )

    assert plan.image == config.image
    assert plan.use_gpu is False
    assert plan.gpu_reason == GPU_REASON_ALREADY_ASSIGNED


def test_runtime_policy_display_explains_primary_gpu_eligibility():
    config = resolve_edge_node_image_config(
        cli_image="devnet",
        environ={},
        production_mode=False,
    )

    display = runtime_policy_display("r1devnode", config)

    assert display.text == "Runtime: GPU eligible"
    assert config.image in display.tooltip
    assert config.gpu_image in display.tooltip


def test_runtime_policy_display_explains_secondary_cpu_only_policy():
    config = resolve_edge_node_image_config(
        cli_image="devnet",
        environ={},
        production_mode=False,
    )

    display = runtime_policy_display("r1devnode2", config)

    assert display.text == "Runtime: CPU-only"
    assert config.default_container_name in display.tooltip
    assert config.image in display.tooltip
