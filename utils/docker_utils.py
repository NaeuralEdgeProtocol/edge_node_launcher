"""Docker utility functions."""

import json
import os
import subprocess
from pathlib import Path

from utils.edge_image_config import (
    MAINNET_TAG,
    RESOURCE_NAME_PREFIXES,
    EdgeNodeImageConfig,
    get_edge_node_image_config,
)

DOCKER_NAME_CHECK_TIMEOUT = 10
WINDOWS_CREATE_NO_WINDOW = 0x08000000


def _docker_container_names(name_filter: str):
    command = [
        'docker',
        'ps',
        '-a',
        '--format',
        '{{.Names}}',
        '--filter',
        f'name={name_filter}',
    ]
    kwargs = {
        "capture_output": True,
        "text": True,
        "timeout": DOCKER_NAME_CHECK_TIMEOUT,
    }
    if os.name == 'nt':
        kwargs["creationflags"] = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            WINDOWS_CREATE_NO_WINDOW,
        )

    try:
        result = subprocess.run(command, **kwargs)
    except Exception:
        return []

    return [name.strip() for name in result.stdout.split('\n') if name.strip()]


def get_container_name_prefix(config: EdgeNodeImageConfig | None = None) -> str:
    """Return the active Docker container prefix for edge-node resources."""
    image_config = config or get_edge_node_image_config()
    return image_config.container_prefix


def get_volume_name_prefix(config: EdgeNodeImageConfig | None = None) -> str:
    """Return the active Docker volume prefix for edge-node resources."""
    image_config = config or get_edge_node_image_config()
    return image_config.volume_prefix


def get_default_container_name(config: EdgeNodeImageConfig | None = None) -> str:
    """Return the first container name for the active edge-node image network."""
    return get_container_name_prefix(config)


def get_default_volume_name(config: EdgeNodeImageConfig | None = None) -> str:
    """Return the first volume name for the active edge-node image network."""
    return get_volume_name_prefix(config)


def _sequential_suffix(name: str, prefix: str) -> str | None:
    if name == prefix:
        return ""
    if not name.startswith(prefix):
        return None

    suffix = name[len(prefix):]
    return suffix if suffix.isdigit() else None


def _resource_prefix_pairs() -> list[tuple[str, str]]:
    return list(RESOURCE_NAME_PREFIXES.values())


def is_non_mainnet_container_name(container_name: str) -> bool:
    """Return True when a name belongs to a known non-mainnet namespace."""
    for environment, (container_prefix, _volume_prefix) in RESOURCE_NAME_PREFIXES.items():
        if environment == MAINNET_TAG:
            continue
        if _sequential_suffix(container_name, container_prefix) is not None:
            return True
    return False


def is_container_name_for_config(
    container_name: str,
    config: EdgeNodeImageConfig | None = None,
    *,
    default_container_name: str | None = None,
) -> bool:
    """Return whether a saved container should be shown for the active image config."""
    image_config = config or get_edge_node_image_config()
    if default_container_name and container_name == default_container_name:
        return True

    if image_config.is_mainnet:
        return not is_non_mainnet_container_name(container_name)

    return _sequential_suffix(container_name, image_config.container_prefix) is not None


def get_volume_name(container_name):
    """Get volume name from container name.
    
    Args:
        container_name: Name of the container
        
    Returns:
        str: Name of the volume
    """
    # For legacy container names
    if "edge_node_container" in container_name:
        return container_name.replace("container", "volume")
    
    for container_prefix, volume_prefix in _resource_prefix_pairs():
        suffix = _sequential_suffix(container_name, container_prefix)
        if suffix is not None:
            return f"{volume_prefix}{suffix}"
    
    # Fallback
    return f"volume_{container_name}"


def generate_container_name(prefix=None):
    """Generate a sequential container name.
    
    First container is named just like the active network prefix
    (for example "r1node" or "r1devnode"), subsequent containers
    append a numeric suffix.
    
    This function checks both Docker containers and the config file
    for the highest index, then increments from there. It also validates
    that the generated name doesn't exist in Docker but not in the config.
    
    Args:
        prefix: Prefix for the container name
        
    Returns:
        str: Sequential container name
    """
    if prefix is None:
        prefix = get_container_name_prefix()

    # Config file path
    config_dir = os.path.join(str(Path.home()), ".ratio1", "edge_node_launcher")
    containers_file = os.path.join(config_dir, "containers.json")
    
    # Find highest index in Docker containers
    docker_highest_index = -1  # Start from -1 so first container can be r1node (without number)
    try:
        existing_containers = _docker_container_names(prefix)
        
        for container in existing_containers:
            if container.startswith(prefix):
                try:
                    # Extract the number after the prefix
                    index_str = container[len(prefix):]
                    if not index_str:  # This is "r1node" with no number
                        docker_highest_index = max(docker_highest_index, 0)
                    elif index_str.isdigit():
                        index = int(index_str)
                        docker_highest_index = max(docker_highest_index, index)
                except (ValueError, IndexError):
                    continue
    except Exception:
        docker_highest_index = -1
    
    # Find highest index in config file
    config_highest_index = -1
    try:
        if os.path.exists(containers_file):
            with open(containers_file, 'r') as f:
                data = json.load(f)
                for container_data in data:
                    container_name = container_data.get('name', '')
                    if container_name.startswith(prefix):
                        try:
                            # Extract the number after the prefix
                            index_str = container_name[len(prefix):]
                            if not index_str:  # This is "r1node" with no number
                                config_highest_index = max(config_highest_index, 0)
                            elif index_str.isdigit():
                                index = int(index_str)
                                config_highest_index = max(config_highest_index, index)
                        except (ValueError, IndexError):
                            continue
    except Exception:
        config_highest_index = -1
    
    # Use the highest index from both sources
    highest_index = max(docker_highest_index, config_highest_index)
    
    # Generate the next name
    while True:
        next_index = highest_index + 1
        
        # Format the name
        if next_index == 0:  # First container is just "r1node"
            next_name = prefix
        else:
            next_name = f"{prefix}{next_index}"
        
        # Check if this name exists in Docker but not in config
        exists_in_docker = False
        try:
            docker_containers = _docker_container_names(next_name)
            exists_in_docker = next_name in docker_containers
        except Exception:
            exists_in_docker = False
        
        exists_in_config = False
        try:
            if os.path.exists(containers_file):
                with open(containers_file, 'r') as f:
                    data = json.load(f)
                    exists_in_config = any(container_data.get('name') == next_name for container_data in data)
        except Exception:
            exists_in_config = False
        
        # If the name exists in Docker but not in config, we need to try the next index
        if exists_in_docker and not exists_in_config:
            highest_index = next_index
            continue
        
        # Otherwise return the name
        return next_name
