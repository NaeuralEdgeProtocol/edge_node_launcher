"""Docker utility functions."""

import json
import os
import subprocess
from pathlib import Path

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
    
    # For new r1node naming convention
    if container_name == "r1node":
        return "r1vol"  # First container gets simple volume name
    
    # For r1node with sequential numbers
    if container_name.startswith("r1node"):
        # Extract the number part
        try:
            # Get the numeric part after "r1node"
            number_part = container_name[6:]
            if number_part.isdigit():
                return f"r1vol{number_part}"
        except (ValueError, IndexError):
            pass
    
    # Fallback
    return f"volume_{container_name}"

def generate_container_name(prefix="r1node"):
    """Generate a sequential container name.
    
    First container is named just "r1node" (if available),
    subsequent containers are "r1node1", "r1node2", etc.
    
    This function checks both Docker containers and the config file
    for the highest index, then increments from there. It also validates
    that the generated name doesn't exist in Docker but not in the config.
    
    Args:
        prefix: Prefix for the container name
        
    Returns:
        str: Sequential container name
    """
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
