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


def calculate_visible_frame_client_geometry(
    available_geometry: QRect,
    client_geometry: QRect,
    frame_geometry: QRect,
    margin: int = WINDOW_SCREEN_MARGIN,
) -> QRect:
    """Return client geometry that keeps the native window frame on screen."""
    if (
        available_geometry is None
        or available_geometry.isNull()
        or not available_geometry.isValid()
        or client_geometry is None
        or client_geometry.isNull()
        or not client_geometry.isValid()
        or frame_geometry is None
        or frame_geometry.isNull()
        or not frame_geometry.isValid()
    ):
        return QRect(client_geometry)

    safe_margin = max(
        0,
        min(margin, available_geometry.width() // 4, available_geometry.height() // 4),
    )
    safe_geometry = QRect(available_geometry)
    safe_geometry.adjust(safe_margin, safe_margin, -safe_margin, -safe_margin)
    if safe_geometry.width() <= 0 or safe_geometry.height() <= 0:
        safe_geometry = QRect(available_geometry)

    left_frame = max(0, client_geometry.x() - frame_geometry.x())
    top_frame = max(0, client_geometry.y() - frame_geometry.y())
    right_frame = max(0, frame_geometry.width() - client_geometry.width() - left_frame)
    bottom_frame = max(0, frame_geometry.height() - client_geometry.height() - top_frame)

    max_client_width = max(1, safe_geometry.width() - left_frame - right_frame)
    max_client_height = max(1, safe_geometry.height() - top_frame - bottom_frame)
    client_width = min(client_geometry.width(), max_client_width)
    client_height = min(client_geometry.height(), max_client_height)

    frame_width = client_width + left_frame + right_frame
    frame_height = client_height + top_frame + bottom_frame
    max_frame_x = safe_geometry.x() + max(0, safe_geometry.width() - frame_width)
    max_frame_y = safe_geometry.y() + max(0, safe_geometry.height() - frame_height)
    frame_x = min(max(frame_geometry.x(), safe_geometry.x()), max_frame_x)
    frame_y = min(max(frame_geometry.y(), safe_geometry.y()), max_frame_y)

    return QRect(
        frame_x + left_frame,
        frame_y + top_frame,
        client_width,
        client_height,
    )
