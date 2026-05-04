import re
from typing import Optional


def extract_conflicting_container_id(error_message: str) -> Optional[str]:
    """Return the container id from Docker's name-conflict error, if present."""
    if not error_message:
        return None

    container_id_match = re.search(r'by container "([^"]+)"', error_message)
    return container_id_match.group(1) if container_id_match else None
