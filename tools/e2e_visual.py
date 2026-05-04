"""Shared visual evidence helpers for launcher E2E runners."""


def rect_snapshot(rect):
    return {
        "x": rect.x(),
        "y": rect.y(),
        "w": rect.width(),
        "h": rect.height(),
        "left": rect.x(),
        "top": rect.y(),
        "right": rect.x() + rect.width() - 1,
        "bottom": rect.y() + rect.height() - 1,
    }


def window_snapshot(launcher):
    frame = launcher.frameGeometry()
    client = launcher.geometry()
    snapshot = {
        "title": launcher.windowTitle(),
        "client": {"x": client.x(), "y": client.y(), "w": client.width(), "h": client.height()},
        "frame": {"x": frame.x(), "y": frame.y(), "w": frame.width(), "h": frame.height()},
        "visible": launcher.isVisible(),
    }
    if hasattr(launcher, "_available_screen_geometry"):
        available = launcher._available_screen_geometry()
        snapshot["available"] = rect_snapshot(available)
        snapshot["title_bar_visible"] = frame.y() >= available.y()
        snapshot["frame_inside_available"] = (
            frame.x() >= available.x()
            and frame.y() >= available.y()
            and frame.x() + frame.width() <= available.x() + available.width()
            and frame.y() + frame.height() <= available.y() + available.height()
        )
    return snapshot


def assert_title_bar_visible(window):
    if not window.get("title_bar_visible", True):
        raise AssertionError(
            f"window title bar is outside the available screen area: {window}"
        )


def widget_global_rect_snapshot(widget):
    local_rect = widget.rect()
    top_left = widget.mapToGlobal(local_rect.topLeft())
    return {
        "x": top_left.x(),
        "y": top_left.y(),
        "w": local_rect.width(),
        "h": local_rect.height(),
        "left": top_left.x(),
        "top": top_left.y(),
        "right": top_left.x() + local_rect.width() - 1,
        "bottom": top_left.y() + local_rect.height() - 1,
    }


def control_snapshot(widget):
    if widget is None:
        return {"found": False}

    snapshot = {
        "found": True,
        "object_name": widget.objectName() if hasattr(widget, "objectName") else "",
        "accessible_name": widget.accessibleName() if hasattr(widget, "accessibleName") else "",
        "tooltip": widget.toolTip() if hasattr(widget, "toolTip") else "",
        "visible": widget.isVisible() if hasattr(widget, "isVisible") else None,
        "enabled": widget.isEnabled() if hasattr(widget, "isEnabled") else None,
    }
    if hasattr(widget, "rect") and hasattr(widget, "mapToGlobal"):
        snapshot["rect"] = widget_global_rect_snapshot(widget)
    if hasattr(widget, "text"):
        snapshot["text"] = widget.text()
    if hasattr(widget, "currentText"):
        snapshot["current_text"] = widget.currentText()
    return snapshot


def lifecycle_controls_snapshot(launcher):
    controls = {
        "add_node": getattr(launcher, "add_node_button", None),
        "rename": getattr(launcher, "renameNodeButton", None),
        "toggle": getattr(launcher, "toggleButton", None),
        "refresh": getattr(launcher, "refreshButton", None),
        "node_selector": getattr(launcher, "container_combo", None),
        "theme_toggle": getattr(launcher, "themeToggleButton", None),
    }
    return {
        name: control_snapshot(widget)
        for name, widget in controls.items()
    }


def assert_lifecycle_controls_busy(snapshot, expected_toggle_text=None):
    missing = [name for name, control in snapshot.items() if not control.get("found")]
    if missing:
        raise AssertionError(f"missing lifecycle controls: {missing}")

    toggle = snapshot["toggle"]
    if expected_toggle_text is not None and toggle.get("text") != expected_toggle_text:
        raise AssertionError(
            f"expected toggle text {expected_toggle_text!r}, got {toggle.get('text')!r}: {toggle}"
        )

    disabled_controls = ["add_node", "rename", "toggle", "refresh", "node_selector"]
    still_enabled = [
        name
        for name in disabled_controls
        if snapshot[name].get("enabled")
    ]
    if still_enabled:
        raise AssertionError(f"expected lifecycle controls to be disabled: {still_enabled}")

    if not snapshot["theme_toggle"].get("enabled"):
        raise AssertionError("theme toggle should remain enabled during lifecycle work")
