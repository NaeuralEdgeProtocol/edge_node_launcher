"""Sidebar lifecycle control state presenter."""

from utils.const import LAUNCH_CONTAINER_BUTTON_TEXT, STOP_CONTAINER_BUTTON_TEXT


LIFECYCLE_BUSY_TOGGLE_TEXT = {
    "start": "Starting...",
    "launch": "Starting...",
    "stop": "Stopping...",
    "add_node": "Creating Node...",
    "rename_restart": "Renaming...",
}
LIFECYCLE_DOCKER_PULL_TOGGLE_TEXT = "Pulling Image..."
LIFECYCLE_BUSY_TOOLTIP = "Wait for the current node operation to finish."
_FALLBACK_BUSY_TEXT = "Working..."


class LifecycleControlsPresenter:
    """Synchronizes sidebar controls with active lifecycle work."""

    def __init__(self, launcher):
        self._launcher = launcher
        self._tooltips = {}

    def sync(self, *, use_operation_text: bool = True) -> bool:
        if not hasattr(self._launcher, "toggleButton"):
            return False

        is_busy = self._is_busy()
        for widget in self._node_control_widgets():
            self._set_widget_enabled(widget, not is_busy)

        if is_busy:
            if use_operation_text and self._can_start_after_active_stop():
                self.apply_toggle_state(False, enabled=True)
                return True

            if use_operation_text:
                self._set_toggle_busy_state()
            else:
                self._set_widget_enabled(self._launcher.toggleButton, False)
                self._launcher.apply_button_style(self._launcher.toggleButton, "disabled")
            return True

        self._set_widget_enabled(self._launcher.toggleButton, True)
        return False

    def restore_after_lifecycle(self, ended_operation=None) -> None:
        if not hasattr(self._launcher, "toggleButton"):
            return
        if self._is_busy():
            return

        busy_texts = set(LIFECYCLE_BUSY_TOGGLE_TEXT.values()) | {
            LIFECYCLE_DOCKER_PULL_TOGGLE_TEXT,
            _FALLBACK_BUSY_TEXT,
        }
        if self._launcher.toggleButton.text() in busy_texts:
            try:
                is_running = self._launcher.docker_handler.is_container_running()
            except Exception:
                is_running = getattr(ended_operation, "operation", None) != "stop"
            self.apply_toggle_state(is_running, enabled=True)
            return

        if self._launcher.toggleButton.text() == LAUNCH_CONTAINER_BUTTON_TEXT:
            self._launcher.apply_button_style(self._launcher.toggleButton, "toggle_start")
        elif self._launcher.toggleButton.text() == STOP_CONTAINER_BUTTON_TEXT:
            self._launcher.apply_button_style(self._launcher.toggleButton, "toggle_stop")

    def apply_toggle_state(self, is_running: bool, *, enabled: bool = True) -> None:
        new_text = STOP_CONTAINER_BUTTON_TEXT if is_running else LAUNCH_CONTAINER_BUTTON_TEXT
        new_style = "toggle_stop" if is_running else "toggle_start"

        if self._launcher.toggleButton.text() != new_text:
            self._launcher.toggleButton.setText(new_text)
            self._launcher.toggleButton.setAccessibleName(new_text)

        self._launcher.apply_button_style(self._launcher.toggleButton, new_style)
        self._set_widget_enabled(self._launcher.toggleButton, enabled)
        if not enabled:
            self._launcher.apply_button_style(self._launcher.toggleButton, "disabled")

    def _is_busy(self) -> bool:
        return (
            self._launcher._active_lifecycle_operation() is not None
            or self._launcher._docker_pull_in_progress()
        )

    def _node_control_widgets(self):
        return [
            widget
            for widget in (
                getattr(self._launcher, "add_node_button", None),
                getattr(self._launcher, "renameNodeButton", None),
                getattr(self._launcher, "refreshButton", None),
                getattr(self._launcher, "container_combo", None),
            )
            if widget is not None
        ]

    def _set_widget_enabled(self, widget, enabled: bool) -> None:
        if widget is None:
            return

        tooltip_key = id(widget)
        if enabled:
            if tooltip_key in self._tooltips:
                widget.setToolTip(self._tooltips.pop(tooltip_key))
        else:
            self._tooltips.setdefault(tooltip_key, widget.toolTip())
            widget.setToolTip(LIFECYCLE_BUSY_TOOLTIP)

        widget.setEnabled(enabled)

    def _set_toggle_busy_state(self) -> None:
        active_operation = self._launcher._active_lifecycle_operation()
        operation_name = active_operation.get("operation") if active_operation else None
        busy_text = LIFECYCLE_BUSY_TOGGLE_TEXT.get(operation_name)
        if busy_text is None and self._launcher._docker_pull_in_progress():
            busy_text = LIFECYCLE_DOCKER_PULL_TOGGLE_TEXT
        if busy_text is None:
            busy_text = _FALLBACK_BUSY_TEXT

        if self._launcher.toggleButton.text() != busy_text:
            self._launcher.toggleButton.setText(busy_text)
            self._launcher.toggleButton.setAccessibleName(busy_text)

        self._set_widget_enabled(self._launcher.toggleButton, False)
        self._launcher.apply_button_style(self._launcher.toggleButton, "disabled")

    def _can_start_after_active_stop(self) -> bool:
        active_operation = self._launcher._active_lifecycle_operation()
        if active_operation is None or active_operation.get("operation") != "stop":
            return False

        try:
            return not self._launcher.is_container_running()
        except Exception:
            return False
