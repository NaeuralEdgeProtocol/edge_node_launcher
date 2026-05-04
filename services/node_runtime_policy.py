from dataclasses import dataclass
from typing import Iterable

from utils.edge_image_config import EdgeNodeImageConfig


RECOMMENDED_NODE_CPU_COUNT = 4
RECOMMENDED_NODE_RAM_GB = 16
NEAR_BOUNDARY_NODE_RAM_GB = 15

GPU_REASON_AVAILABLE = "gpu_available_for_primary_node"
GPU_REASON_NOT_AVAILABLE = "gpu_not_available"
GPU_REASON_NON_PRIMARY_NODE = "gpu_reserved_for_primary_node"
GPU_REASON_ALREADY_ASSIGNED = "gpu_already_assigned"


@dataclass(frozen=True)
class NodeCapacityDecision:
    total_ram_gb: float
    current_node_count: int
    max_nodes_supported: int
    can_add_node: bool
    used_by_nodes_gb: float
    min_required_gb: int = RECOMMENDED_NODE_RAM_GB
    recommended_cpu_count: int = RECOMMENDED_NODE_CPU_COUNT
    available_for_next_node_gb: float = 0.0
    near_boundary_warning: bool = False

    def to_legacy_dict(self) -> dict:
        return {
            "total_ram_gb": self.total_ram_gb,
            "used_by_nodes_gb": self.used_by_nodes_gb,
            "max_nodes_supported": self.max_nodes_supported,
            "current_node_count": self.current_node_count,
            "can_add_node": self.can_add_node,
            "min_required_gb": self.min_required_gb,
            "recommended_cpu_count": self.recommended_cpu_count,
            "available_for_next_node_gb": self.available_for_next_node_gb,
            "near_boundary_warning": self.near_boundary_warning,
        }


@dataclass(frozen=True)
class NodeLaunchPlan:
    container_name: str
    image: str
    use_gpu: bool
    gpu_reason: str


def evaluate_node_capacity(total_ram_gb: float, existing_node_count: int) -> NodeCapacityDecision:
    safe_total_ram_gb = max(0.0, float(total_ram_gb))
    safe_existing_count = max(0, int(existing_node_count))
    max_nodes_supported = int(safe_total_ram_gb // RECOMMENDED_NODE_RAM_GB)
    used_by_nodes_gb = safe_existing_count * RECOMMENDED_NODE_RAM_GB
    available_for_next_node_gb = max(0.0, safe_total_ram_gb - used_by_nodes_gb)
    can_add_node = safe_existing_count < max_nodes_supported
    near_boundary_warning = (
        not can_add_node
        and NEAR_BOUNDARY_NODE_RAM_GB <= available_for_next_node_gb < RECOMMENDED_NODE_RAM_GB
    )

    return NodeCapacityDecision(
        total_ram_gb=safe_total_ram_gb,
        current_node_count=safe_existing_count,
        max_nodes_supported=max_nodes_supported,
        can_add_node=can_add_node,
        used_by_nodes_gb=used_by_nodes_gb,
        available_for_next_node_gb=available_for_next_node_gb,
        near_boundary_warning=near_boundary_warning,
    )


def _normalized_gpu_assignments(container_names: Iterable[str] | None) -> set[str]:
    return {
        name
        for name in (container_names or [])
        if isinstance(name, str) and name.strip()
    }


def is_primary_node_container(container_name: str, image_config: EdgeNodeImageConfig) -> bool:
    return container_name == image_config.default_container_name


def plan_node_launch(
    container_name: str,
    image_config: EdgeNodeImageConfig,
    *,
    gpu_available: bool,
    existing_gpu_container_names: Iterable[str] | None = None,
) -> NodeLaunchPlan:
    gpu_assignments = _normalized_gpu_assignments(existing_gpu_container_names)
    assigned_to_other_node = any(name != container_name for name in gpu_assignments)

    if not gpu_available:
        return NodeLaunchPlan(
            container_name=container_name,
            image=image_config.image,
            use_gpu=False,
            gpu_reason=GPU_REASON_NOT_AVAILABLE,
        )

    if assigned_to_other_node:
        return NodeLaunchPlan(
            container_name=container_name,
            image=image_config.image,
            use_gpu=False,
            gpu_reason=GPU_REASON_ALREADY_ASSIGNED,
        )

    if not is_primary_node_container(container_name, image_config):
        return NodeLaunchPlan(
            container_name=container_name,
            image=image_config.image,
            use_gpu=False,
            gpu_reason=GPU_REASON_NON_PRIMARY_NODE,
        )

    return NodeLaunchPlan(
        container_name=container_name,
        image=image_config.gpu_image,
        use_gpu=True,
        gpu_reason=GPU_REASON_AVAILABLE,
    )
