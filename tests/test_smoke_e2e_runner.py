from types import SimpleNamespace
import webbrowser

from PyQt5.QtWidgets import QApplication, QComboBox, QDialog, QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea, QWidget

import tools.run_smoke_e2e as smoke
from services.app_deployment_models import ContainerAppSpec
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


def test_prepare_evidence_paths_resolves_before_launcher_changes_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = SimpleNamespace(output="evidence/result.json", screenshot_dir="evidence/screens")

    smoke.prepare_evidence_paths(args)

    output_path = tmp_path / "evidence" / "result.json"
    screenshot_dir = tmp_path / "evidence" / "screens"
    assert args.output == str(output_path.resolve())
    assert args.screenshot_dir == str(screenshot_dir.resolve())
    assert output_path.parent.exists()
    assert screenshot_dir.exists()

    changed_cwd = tmp_path / "changed"
    changed_cwd.mkdir()
    monkeypatch.chdir(changed_cwd)
    smoke.record_step({"steps": []}, args.output, {"step": "after cwd change"})

    assert output_path.exists()
    assert not (changed_cwd / "evidence" / "result.json").exists()


def test_configure_qt_font_dir_for_windows_uses_system_fonts_when_available(tmp_path):
    env = {"WINDIR": str(tmp_path)}
    fonts = tmp_path / "Fonts"
    fonts.mkdir()

    selected = smoke.configure_qt_font_dir_for_windows(
        environ=env,
        platform_name="nt",
        path_exists=lambda path: path == fonts,
    )

    assert selected == str(fonts)
    assert env["QT_QPA_FONTDIR"] == str(fonts)


def test_configure_qt_font_dir_for_windows_preserves_existing_setting(tmp_path):
    env = {"WINDIR": str(tmp_path), "QT_QPA_FONTDIR": "custom-fonts"}

    selected = smoke.configure_qt_font_dir_for_windows(
        environ=env,
        platform_name="nt",
        path_exists=lambda _path: True,
    )

    assert selected == ""
    assert env["QT_QPA_FONTDIR"] == "custom-fonts"


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


def test_smoke_window_snapshot_flags_hidden_title_bar():
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
        geometry=lambda: FakeRect(10, 60, 300, 200),
        frameGeometry=lambda: FakeRect(8, 20, 304, 240),
        isVisible=lambda: True,
        _available_screen_geometry=lambda: FakeRect(0, 40, 500, 400),
    )

    snapshot = smoke.window_snapshot(launcher)

    assert snapshot["available"] == {
        "x": 0,
        "y": 40,
        "w": 500,
        "h": 400,
        "left": 0,
        "top": 40,
        "right": 499,
        "bottom": 439,
    }
    assert snapshot["title_bar_visible"] is False
    assert snapshot["frame_inside_available"] is False


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


def test_smoke_fake_sdk_client_maps_launch_refresh_and_stop_without_secrets():
    client = smoke.FakeSdkDeploymentClient()
    spec = ContainerAppSpec(
        app_name="smoke_car",
        node_address=smoke.SMOKE_VALID_NODE_ADDRESS,
        image="nginx:alpine",
        registry_password=smoke.SMOKE_CONTAINER_APP_SECRET,
    )

    result = client.launch_container_app(spec)
    statuses = client.list_node_apps(smoke.SMOKE_VALID_NODE_ADDRESS)
    client.stop_app(result.node_address, result.pipeline_name)
    stopped_statuses = client.list_node_apps(smoke.SMOKE_VALID_NODE_ADDRESS)

    assert result.app_url == "https://smoke-car.example.test"
    assert statuses[0].status == "online"
    assert stopped_statuses[0].status == "stopped"
    assert smoke.SMOKE_CONTAINER_APP_SECRET not in repr(client.events)
    assert client.events[0]["has_registry_password"] is True


def test_secret_line_edit_snapshot_reports_password_echo_without_raw_secret(qtbot):
    line_edit = QLineEdit()
    line_edit.setObjectName("secretInput")
    line_edit.setAccessibleName("Secret")
    line_edit.setEchoMode(QLineEdit.Password)
    line_edit.setText(smoke.SMOKE_CONTAINER_APP_SECRET)
    qtbot.addWidget(line_edit)

    snapshot = smoke.secret_line_edit_snapshot(line_edit, smoke.SMOKE_CONTAINER_APP_SECRET)

    assert snapshot["object_name"] == "secretInput"
    assert snapshot["uses_password_echo"] is True
    assert snapshot["raw_secret_visible"] is False
    assert "display_text" not in snapshot


def test_dialog_visual_snapshot_records_dialog_content(qtbot):
    dialog = QDialog()
    dialog.setWindowTitle("Review Dialog")
    dialog.setAccessibleName("Review Dialog")
    label = QLabel("Important copy", dialog)
    label.setObjectName("dialogCopy")
    label.setAccessibleName("Dialog copy")
    label.setWordWrap(True)
    line_edit = QLineEdit(dialog)
    line_edit.setObjectName("dialogInput")
    line_edit.setProperty("role", "dialogTextInput")
    line_edit.setAccessibleName("Dialog input")
    line_edit.setText("alpha")
    line_edit.setPlaceholderText("Alias")
    line_edit.setMinimumHeight(38)
    progress_bar = QProgressBar(dialog)
    progress_bar.setObjectName("dialogProgress")
    progress_bar.setAccessibleName("Dialog progress")
    progress_bar.setRange(0, 100)
    progress_bar.setValue(42)
    button = QPushButton("Save", dialog)
    button.setObjectName("dialogSaveButton")
    button.setAccessibleName("Save dialog")
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    snapshot = smoke.dialog_visual_snapshot(dialog)

    assert snapshot["title"] == "Review Dialog"
    assert snapshot["accessible_name"] == "Review Dialog"
    assert snapshot["visible"] is True
    assert snapshot["labels"][0]["object_name"] == "dialogCopy"
    assert snapshot["labels"][0]["accessible_name"] == "Dialog copy"
    assert snapshot["labels"][0]["text"] == "Important copy"
    assert snapshot["labels"][0]["word_wrap"] is True
    assert snapshot["line_edits"][0]["object_name"] == "dialogInput"
    assert snapshot["line_edits"][0]["accessible_name"] == "Dialog input"
    assert snapshot["line_edits"][0]["role"] == "dialogTextInput"
    assert snapshot["line_edits"][0]["text"] == "alpha"
    assert snapshot["line_edits"][0]["placeholder"] == "Alias"
    assert snapshot["line_edits"][0]["minimum_height"] == 38
    assert snapshot["buttons"][0]["object_name"] == "dialogSaveButton"
    assert snapshot["buttons"][0]["accessible_name"] == "Save dialog"
    assert snapshot["buttons"][0]["text"] == "Save"
    assert snapshot["progress_bars"][0]["object_name"] == "dialogProgress"
    assert snapshot["progress_bars"][0]["accessible_name"] == "Dialog progress"
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


def test_dialog_visual_snapshot_redacts_secret_line_edits(qtbot):
    dialog = QDialog()
    secret = QLineEdit(dialog)
    secret.setObjectName("registryPasswordInput")
    secret.setAccessibleName("Registry password")
    secret.setPlaceholderText("Registry password")
    secret.setText(smoke.SMOKE_CONTAINER_APP_SECRET)
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    snapshot = smoke.dialog_visual_snapshot(dialog)

    secret_snapshot = next(
        line_edit for line_edit in snapshot["line_edits"] if line_edit["object_name"] == "registryPasswordInput"
    )
    assert secret_snapshot["text"] == "***REDACTED***"
    assert smoke.SMOKE_CONTAINER_APP_SECRET not in repr(snapshot)


def test_save_widget_region_screenshot_crops_composed_parent_region(qtbot, tmp_path):
    parent = QDialog()
    parent.resize(120, 90)
    child = QWidget(parent)
    child.setObjectName("sidebarScrollArea")
    child.setGeometry(10, 20, 45, 30)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    screenshot = smoke.save_widget_region_screenshot(parent, child, str(tmp_path), "sidebar.png")

    from PyQt5.QtGui import QImage

    image = QImage(screenshot)
    assert image.width() == 45
    assert image.height() == 30


def test_scroll_sidebar_to_moves_and_restores_scroll_position(qtbot):
    parent = QDialog()
    parent.resize(140, 120)
    sidebar_scroll = QScrollArea(parent)
    sidebar_scroll.setObjectName("sidebarScrollArea")
    sidebar_scroll.setGeometry(0, 0, 120, 90)
    sidebar_content = QWidget()
    sidebar_content.setFixedSize(100, 360)
    sidebar_scroll.setWidget(sidebar_content)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    scrollbar = sidebar_scroll.verticalScrollBar()
    assert scrollbar.maximum() > 0

    original_position = smoke.scroll_sidebar_to(parent, "bottom")

    assert original_position == 0
    assert scrollbar.value() == scrollbar.maximum()

    smoke.scroll_sidebar_to(parent, original_position)
    assert scrollbar.value() == 0

    smoke.scroll_sidebar_to(parent, "top")
    assert scrollbar.value() == scrollbar.minimum()


def test_scroll_apps_workspace_to_uses_workspace_scroll_area(qtbot):
    parent = QDialog()
    parent.resize(180, 140)
    apps_scroll = QScrollArea(parent)
    apps_scroll.setObjectName("appsWorkspaceScrollArea")
    apps_scroll.setGeometry(0, 0, 160, 100)
    content = QWidget()
    content.setFixedSize(140, 360)
    apps_scroll.setWidget(content)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    original_position = smoke.scroll_apps_workspace_to(parent, "bottom")

    assert original_position == 0
    assert apps_scroll.verticalScrollBar().value() == apps_scroll.verticalScrollBar().maximum()


def test_combo_popup_visual_evidence_records_items_and_hides_popup(qtbot):
    app = QApplication.instance()
    parent = QDialog()
    combo = QComboBox(parent)
    combo.setObjectName("nodeSelectorCombo")
    combo.setAccessibleName("Node selector")
    combo.setToolTip("Select active node")
    combo.addItem("alpha", "r1node")
    combo.addItem("beta", "r1node2")
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    evidence = smoke.capture_combo_popup_visual_evidence(app, combo, "", "node_selector")

    assert evidence["label"] == "node_selector"
    assert evidence["combo_popup"]["combo_object_name"] == "nodeSelectorCombo"
    assert evidence["combo_popup"]["combo_accessible_name"] == "Node selector"
    assert evidence["combo_popup"]["combo_tooltip"] == "Select active node"
    assert evidence["combo_popup"]["items"] == [
        {"index": 0, "text": "alpha", "data": "r1node"},
        {"index": 1, "text": "beta", "data": "r1node2"},
    ]
    assert combo.view().window().isVisible() is False


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
    assert snapshot["object_name"] == "toastNotification"
    assert snapshot["accessible_name"] == "Notification"
    assert snapshot["title"] == "Information"
    assert snapshot["message"] == "Visual review message"
    assert snapshot["message_word_wrap"] is True
    assert snapshot["icon"] == "i"
    assert snapshot["icon"].isascii()
    assert snapshot["rect"]["w"] >= ToastWidget.MIN_WIDTH
    assert "#FFFFFF" in toast.styleSheet()


def test_toast_long_messages_keep_readable_width_and_visible_position(qtbot):
    parent = QDialog()
    parent.resize(520, 180)
    toast = ToastWidget(parent, bottom_margin=160)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    toast.show_notification(
        NotificationType.ERROR,
        "Failed to start the selected container because Docker returned a long diagnostic message "
        "that should wrap cleanly without pushing the notification outside the visible window.",
        duration=5000,
    )
    qtbot.waitUntil(toast.isVisible)

    assert toast.objectName() == "toastNotification"
    assert toast.container.objectName() == "toastContainer"
    assert toast.message.objectName() == "toastMessage"
    assert toast.message.wordWrap()
    assert toast.width() <= ToastWidget.MAX_WIDTH
    assert toast.width() >= ToastWidget.MIN_WIDTH
    assert toast.x() >= ToastWidget.EDGE_MARGIN
    assert toast.y() >= ToastWidget.EDGE_MARGIN
    assert toast.x() + toast.width() <= parent.width() - ToastWidget.EDGE_MARGIN
    assert toast.y() + toast.height() <= parent.height() - ToastWidget.EDGE_MARGIN


def test_toast_repeated_notifications_reset_dismiss_timer(qtbot):
    parent = QDialog()
    parent.resize(500, 300)
    toast = ToastWidget(parent)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    toast.show_notification(NotificationType.INFO, "First action", duration=60)
    qtbot.waitUntil(toast.isVisible)
    qtbot.wait(20)

    toast.show_notification(NotificationType.SUCCESS, "Second action", duration=1000)
    qtbot.wait(320)

    assert toast.isVisible()
    assert toast.message.text() == "Second action"
    assert toast.dismiss_timer.isActive()


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
