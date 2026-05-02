from PyQt5.QtCore import QRect

from utils.window_geometry import calculate_initial_window_geometry, format_rect


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


def test_format_rect_includes_position_and_size():
    assert format_rect(QRect(10, 20, 300, 400)) == "x=10, y=20, w=300, h=400"
