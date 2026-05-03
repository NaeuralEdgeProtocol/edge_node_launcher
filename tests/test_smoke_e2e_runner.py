from types import SimpleNamespace
import webbrowser

from PyQt5.QtWidgets import QDialog, QLabel, QLineEdit, QProgressBar, QPushButton

import tools.run_smoke_e2e as smoke
from widgets.ToastWidget import NotificationType, ToastWidget


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


def test_record_step_prints_unicode_as_ascii_json(tmp_path, capsys):
    log = {"steps": []}
    output_path = tmp_path / "smoke.json"

    smoke.record_step(log, str(output_path), {"step": "toast", "icon": "\u26a0"})

    captured = capsys.readouterr()
    assert "\\u26a0" in captured.out
    assert "\u26a0" not in captured.out
    assert output_path.exists()
    assert log["steps"] == [{"step": "toast", "icon": "\u26a0"}]


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


def test_dialog_visual_snapshot_records_dialog_content(qtbot):
    dialog = QDialog()
    dialog.setWindowTitle("Review Dialog")
    label = QLabel("Important copy", dialog)
    label.setObjectName("dialogCopy")
    label.setWordWrap(True)
    line_edit = QLineEdit(dialog)
    line_edit.setObjectName("dialogInput")
    line_edit.setText("alpha")
    line_edit.setPlaceholderText("Alias")
    progress_bar = QProgressBar(dialog)
    progress_bar.setObjectName("dialogProgress")
    progress_bar.setRange(0, 100)
    progress_bar.setValue(42)
    button = QPushButton("Save", dialog)
    button.setObjectName("dialogSaveButton")
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    snapshot = smoke.dialog_visual_snapshot(dialog)

    assert snapshot["title"] == "Review Dialog"
    assert snapshot["visible"] is True
    assert snapshot["labels"][0]["object_name"] == "dialogCopy"
    assert snapshot["labels"][0]["text"] == "Important copy"
    assert snapshot["labels"][0]["word_wrap"] is True
    assert snapshot["line_edits"][0]["object_name"] == "dialogInput"
    assert snapshot["line_edits"][0]["text"] == "alpha"
    assert snapshot["line_edits"][0]["placeholder"] == "Alias"
    assert snapshot["buttons"][0]["object_name"] == "dialogSaveButton"
    assert snapshot["buttons"][0]["text"] == "Save"
    assert snapshot["progress_bars"][0]["object_name"] == "dialogProgress"
    assert snapshot["progress_bars"][0]["value"] == 42


def test_capture_dialog_visual_evidence_omits_screenshot_without_dir(qtbot):
    dialog = QDialog()
    dialog.setWindowTitle("No Screenshot")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    evidence = smoke.capture_dialog_visual_evidence(dialog, "", "no_screenshot")

    assert evidence["label"] == "no_screenshot"
    assert evidence["dialog"]["title"] == "No Screenshot"
    assert "screenshot" not in evidence


def test_toast_visual_snapshot_records_visible_notification(qtbot):
    parent = QDialog()
    parent.resize(500, 300)
    toast = ToastWidget(parent)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    launcher = SimpleNamespace(toast=toast)
    toast.show_notification(NotificationType.INFO, "Visual review message", duration=5000)
    qtbot.waitUntil(toast.isVisible)

    snapshot = smoke.toast_visual_snapshot(launcher)

    assert snapshot["found"] is True
    assert snapshot["visible"] is True
    assert snapshot["title"] == "Information"
    assert snapshot["message"] == "Visual review message"
    assert snapshot["icon"] == "i"
    assert snapshot["icon"].isascii()
    assert snapshot["rect"]["w"] >= 280
    assert "#FFFFFF" in toast.styleSheet()


def test_toast_notification_icons_are_ascii_safe():
    for style in ToastWidget.STYLES.values():
        assert style["icon"].isascii()


def test_warning_toast_uses_dark_foreground_for_yellow_background(qtbot):
    parent = QDialog()
    parent.resize(500, 300)
    toast = ToastWidget(parent)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    toast.show_notification(NotificationType.WARNING, "Readable warning", duration=5000)
    qtbot.waitUntil(toast.isVisible)

    stylesheet = toast.styleSheet()
    assert "#FFC107" in stylesheet
    assert "color: #1F2937;" in stylesheet
    assert "color: white;" not in stylesheet
    assert "color: #FFFFFF;" not in stylesheet
