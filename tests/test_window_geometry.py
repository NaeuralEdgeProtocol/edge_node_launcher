from PyQt5.QtCore import QRect

from utils.window_geometry import (
    calculate_initial_window_geometry,
    calculate_restored_window_geometry,
    calculate_visible_frame_client_geometry,
    format_rect,
)


def test_initial_window_geometry_stays_inside_available_screen():
    available = QRect(0, 40, 1366, 728)

    geometry = calculate_initial_window_geometry(available)

    assert available.contains(geometry)
    assert geometry.x() >= available.x()
    assert geometry.y() >= available.y()
    assert geometry.width() <= available.width()
    assert geometry.height() <= available.height()


def test_initial_window_geometry_uses_preferred_size_when_it_fits():
    available = QRect(0, 0, 2560, 1440)

    geometry = calculate_initial_window_geometry(available)

    assert geometry.width() == 1600
    assert geometry.height() == 900
    assert available.contains(geometry)


def test_visible_frame_geometry_moves_hidden_title_bar_into_available_screen():
    available = QRect(0, 47, 1920, 1153)
    client = QRect(160, 10, 1600, 900)
    frame = QRect(159, -28, 1602, 939)

    geometry = calculate_visible_frame_client_geometry(available, client, frame)
    adjusted_frame = QRect(
        geometry.x() - 1,
        geometry.y() - 38,
        geometry.width() + 2,
        geometry.height() + 39,
    )

    assert adjusted_frame.y() >= available.y()
    assert adjusted_frame.x() >= available.x()
    assert available.contains(adjusted_frame)


def test_visible_frame_geometry_shrinks_overlarge_client_to_available_screen():
    available = QRect(0, 40, 1366, 728)
    client = QRect(0, 0, 1500, 900)
    frame = QRect(-1, -38, 1502, 939)

    geometry = calculate_visible_frame_client_geometry(available, client, frame)
    adjusted_frame = QRect(
        geometry.x() - 1,
        geometry.y() - 38,
        geometry.width() + 2,
        geometry.height() + 39,
    )

    assert adjusted_frame.y() >= available.y()
    assert adjusted_frame.x() >= available.x()
    assert adjusted_frame.width() <= available.width()
    assert adjusted_frame.height() <= available.height()


def test_restored_window_geometry_clamps_stale_offscreen_position():
    available = QRect(0, 40, 1366, 728)
    saved = QRect(-2000, -1000, 1600, 900)

    geometry = calculate_restored_window_geometry(available, saved)

    assert geometry.x() >= available.x()
    assert geometry.y() >= available.y()
    assert geometry.width() <= available.width()
    assert geometry.height() <= available.height()


def test_restored_window_geometry_falls_back_to_initial_when_saved_invalid():
    available = QRect(0, 40, 1366, 728)

    geometry = calculate_restored_window_geometry(available, QRect())

    assert geometry == calculate_initial_window_geometry(available)


def test_format_rect_includes_position_and_size():
    assert format_rect(QRect(10, 20, 300, 400)) == "x=10, y=20, w=300, h=400"
