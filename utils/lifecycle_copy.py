from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LifecycleDialogCopy:
    title: str
    message: str


def launch_dialog_copy(node_alias: Optional[str], *, is_new_node: bool = False) -> LifecycleDialogCopy:
    title = "Starting Node" if is_new_node else "Launching Node"
    if node_alias:
        message = f"Please wait while node '{node_alias}' is being launched..."
    elif is_new_node:
        message = "Please wait while new Edge Node is being launched..."
    else:
        message = "Please wait while Edge Node is being launched..."

    return LifecycleDialogCopy(title=title, message=message)


def stop_dialog_copy(node_alias: Optional[str]) -> LifecycleDialogCopy:
    if node_alias:
        message = f"Please wait while node '{node_alias}' is being stopped..."
    else:
        message = "Please wait while Edge Node is being stopped..."

    return LifecycleDialogCopy(title="Stopping Node", message=message)


def launch_success_notification(node_alias: Optional[str]) -> str:
    if node_alias:
        return f"Node '{node_alias}' launched successfully"
    return "Edge Node launched successfully"


def stop_success_notification(node_alias: Optional[str]) -> str:
    if node_alias:
        return f"Node '{node_alias}' stopped successfully"
    return "Edge Node stopped successfully"


def new_node_success_notification(display_name: Optional[str]) -> str:
    if display_name:
        return f"New Node '{display_name}' created successfully"
    return "New Edge Node created successfully"
