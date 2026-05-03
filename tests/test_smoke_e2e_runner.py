from types import SimpleNamespace
import webbrowser

import tools.run_smoke_e2e as smoke


def test_smoke_fake_docker_handler_never_reports_running():
    handler = smoke.FakeDockerHandler(smoke.SMOKE_CONTAINER)

    handler.set_container_name("other")
    handler.set_debug_mode(True)

    assert handler.is_container_running() is False
    assert handler.container_names == [smoke.SMOKE_CONTAINER, "other"]
    assert handler.debug_values == [True]


def test_smoke_fake_docker_handler_returns_empty_history():
    handler = smoke.FakeDockerHandler(smoke.SMOKE_CONTAINER)
    received = []

    handler.get_node_history(received.append, lambda error: received.append(error))

    assert received
    assert received[0].timestamps == []
    assert received[0].cpu_load == []


def test_smoke_window_snapshot_serializes_geometry():
    class FakeRect:
        def __init__(self, x, y, w, h):
            self._x = x
            self._y = y
            self._w = w
            self._h = h

        def x(self):
            return self._x

        def y(self):
            return self._y

        def width(self):
            return self._w

        def height(self):
            return self._h

    launcher = SimpleNamespace(
        windowTitle=lambda: "Ratio1 Edge Node Launcher",
        geometry=lambda: FakeRect(10, 20, 300, 200),
        frameGeometry=lambda: FakeRect(8, 0, 304, 240),
        isVisible=lambda: True,
    )

    assert smoke.window_snapshot(launcher) == {
        "title": "Ratio1 Edge Node Launcher",
        "client": {"x": 10, "y": 20, "w": 300, "h": 200},
        "frame": {"x": 8, "y": 0, "w": 304, "h": 240},
        "visible": True,
    }


def test_rect_snapshot_includes_edges():
    class FakeRect:
        def x(self):
            return 10

        def y(self):
            return 20

        def width(self):
            return 30

        def height(self):
            return 40

    assert smoke.rect_snapshot(FakeRect()) == {
        "x": 10,
        "y": 20,
        "w": 30,
        "h": 40,
        "left": 10,
        "top": 20,
        "right": 39,
        "bottom": 59,
    }


def test_safe_area_status_flags_scrollbar_overlap():
    assert smoke.safe_area_status({"right": 98}, safe_right=100) == {
        "safe_right": 100,
        "inside_safe_area": True,
        "overlaps_scrollbar": False,
    }
    assert smoke.safe_area_status({"right": 101}, safe_right=100) == {
        "safe_right": 100,
        "inside_safe_area": False,
        "overlaps_scrollbar": True,
    }


def test_smoke_browser_recorder_captures_and_restores_open(monkeypatch):
    original_open = webbrowser.open
    log = {}

    restore = smoke.install_browser_recorder(log)
    try:
        assert webbrowser.open("https://example.test") is True
        assert log["opened_urls"] == ["https://example.test"]
    finally:
        restore()

    assert webbrowser.open is original_open


def test_click_visible_button_rejects_hidden_buttons():
    class FakeButton:
        def isVisible(self):
            return False

    try:
        smoke.click_visible_button(None, FakeButton(), "copy node address")
    except AssertionError as exc:
        assert "copy node address button is not visible" in str(exc)
    else:
        raise AssertionError("hidden smoke buttons should fail fast")
