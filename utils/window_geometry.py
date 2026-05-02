from PyQt5.QtCore import QRect


PREFERRED_WINDOW_WIDTH = 1600
PREFERRED_WINDOW_HEIGHT = 900
WINDOW_SCREEN_MARGIN = 24


def format_rect(rect: QRect) -> str:
    return f"x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}"


def calculate_initial_window_geometry(
    available_geometry: QRect,
    preferred_width: int = PREFERRED_WINDOW_WIDTH,
    preferred_height: int = PREFERRED_WINDOW_HEIGHT,
    margin: int = WINDOW_SCREEN_MARGIN,
) -> QRect:
    if available_geometry is None or available_geometry.isNull() or not available_geometry.isValid():
        return QRect(100, 100, preferred_width, preferred_height)

    safe_margin = max(
        0,
        min(margin, available_geometry.width() // 4, available_geometry.height() // 4),
    )
    max_width = max(1, available_geometry.width() - safe_margin * 2)
    max_height = max(1, available_geometry.height() - safe_margin * 2)
    width = min(preferred_width, max_width)
    height = min(preferred_height, max_height)
    x = available_geometry.x() + max(0, (available_geometry.width() - width) // 2)
    y = available_geometry.y() + max(0, (available_geometry.height() - height) // 2)
    return QRect(x, y, width, height)
