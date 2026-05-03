from types import SimpleNamespace

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
