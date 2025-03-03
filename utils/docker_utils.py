"""Docker utility functions."""

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
    
    First container is named just "r1node" (no number),
    subsequent containers are "r1node1", "r1node2", etc.
    
    Args:
        prefix: Prefix for the container name
        
    Returns:
        str: Sequential container name
    """
    import subprocess
    
    # Get list of existing containers with the prefix
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--format', '{{.Names}}', '--filter', f'name={prefix}'],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            # If command fails, default to r1node (no number)
            return prefix
            
        # Parse existing container names and find the highest index
        existing_containers = result.stdout.strip().split('\n')
        existing_containers = [c for c in existing_containers if c]  # Remove empty strings
        
        # Check if the base name (without number) exists
        base_name_exists = any(c.strip() == prefix for c in existing_containers)
        
        highest_index = 0
        for container in existing_containers:
            # Skip the exact prefix match (r1node)
            if container.strip() == prefix:
                continue
                
            # Extract the numeric part after the prefix
            if container.startswith(prefix):
                try:
                    # Extract the number after the prefix
                    index_str = container[len(prefix):]
                    if index_str.isdigit():
                        index = int(index_str)
                        highest_index = max(highest_index, index)
                except (ValueError, IndexError):
                    # If we can't parse the index, just continue
                    pass
        
        # If base name doesn't exist, use it first
        if not base_name_exists:
            return prefix
            
        # Otherwise, return the next available index
        return f"{prefix}{highest_index + 1}"
        
    except Exception as e:
        # In case of any error, default to r1node (no number)
        print(f"Error generating container name: {str(e)}")
        return prefix 