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
