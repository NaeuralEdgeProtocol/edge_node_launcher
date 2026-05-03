from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SelectedContainer:
    """Selected node identity as represented by the container combo box."""

    name: str
    display_name: str
    index: int


def selected_container_from_combo(combo) -> Optional[SelectedContainer]:
    """Return the selected Docker container identity from a combo box.

    The combo display text may be a user-facing alias. The item data is the
    Docker/config identity used by container operations.
    """
    index = combo.currentIndex()
    if index < 0:
        return None

    container_name = combo.itemData(index)
    if not container_name:
        return None

    display_name = combo.currentText() if hasattr(combo, "currentText") else container_name
    return SelectedContainer(
        name=container_name,
        display_name=display_name or container_name,
        index=index,
    )


def select_container_by_name(combo, container_name: str) -> bool:
    """Select a combo item by Docker container name stored in item data."""
    if not container_name:
        return False

    for index in range(combo.count()):
        if combo.itemData(index) == container_name:
            if combo.currentIndex() != index:
                combo.setCurrentIndex(index)
            return True
    return False
