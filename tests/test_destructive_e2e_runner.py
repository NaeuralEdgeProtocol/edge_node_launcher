import json

import pytest

import tools.run_destructive_e2e as e2e


class FakeLogView:
    def __init__(self, text):
        self._text = text

    def toPlainText(self):
        return self._text


class FakeCombo:
    def currentIndex(self):
        return 0

    def itemData(self, _index):
        return e2e.PRIMARY_CONTAINER


class FakeButton:
    def text(self):
        return "Launch"


class FakeLauncher:
    def __init__(self, log_text=""):
        self.logView = FakeLogView(log_text)
        self.container_combo = FakeCombo()
        self.toggleButton = FakeButton()


class FakeApp:
    def processEvents(self):
        return None

    def topLevelWidgets(self):
        return []


def test_launcher_failure_message_detects_unexpected_argument():
    launcher = FakeLauncher("Failed to launch container: unexpected keyword argument 'container_name'")

    assert e2e.launcher_failure_message(launcher) == "failed to launch container"


def test_wait_for_container_running_fails_fast_on_stale_main_window(monkeypatch, tmp_path):
    output_path = tmp_path / "result.json"
    log = {"steps": []}
    launcher = FakeLauncher()

    monkeypatch.setattr(e2e, "docker_running", lambda _container_name: False)
    monkeypatch.setattr(e2e, "docker_exists", lambda _container_name: False)
    monkeypatch.setattr(e2e, "visible_dialog_titles", lambda _app: [])
    monkeypatch.setattr(
        e2e,
        "collect_launcher_diagnostics",
        lambda _app, _launcher, _containers: {"diagnostic": "captured"},
    )

    with pytest.raises(TimeoutError, match="No visible launcher progress"):
        e2e.wait_for_container_running(
            FakeApp(),
            launcher,
            log,
            str(output_path),
            e2e.PRIMARY_CONTAINER,
            timeout=30,
            label="primary container running",
            stall_timeout=0,
        )

    assert log["result"] == "failed_stale_main_window"
    assert log["diagnostics"] == {"diagnostic": "captured"}
    assert json.loads(output_path.read_text(encoding="utf-8"))["result"] == "failed_stale_main_window"


def test_run_command_returns_timeout_diagnostics(monkeypatch):
    def timeout_run(*args, **kwargs):
        raise e2e.subprocess.TimeoutExpired(
            cmd=["docker", "logs"],
            timeout=5,
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(e2e.subprocess, "run", timeout_run)

    result = e2e.run_command(["docker", "logs"], timeout=5)

    assert result["returncode"] == -1
    assert result["timed_out"] is True
    assert result["stdout"] == "partial stdout"
    assert result["stderr"] == "partial stderr"


def test_launcher_lifecycle_diagnostics_uses_public_helper():
    class DiagnosticLauncher(FakeLauncher):
        def lifecycle_diagnostics(self):
            return {
                "lifecycle_operation": {"operation": "launch", "container_name": e2e.PRIMARY_CONTAINER},
                "docker_pull_in_progress": True,
                "pending_launch_context": {
                    "container_name": e2e.PRIMARY_CONTAINER,
                    "volume_name": e2e.PRIMARY_VOLUME,
                },
            }

    assert e2e.launcher_lifecycle_diagnostics(DiagnosticLauncher()) == {
        "lifecycle_operation": {"operation": "launch", "container_name": e2e.PRIMARY_CONTAINER},
        "docker_pull_in_progress": True,
        "pending_launch_context": {
            "container_name": e2e.PRIMARY_CONTAINER,
            "volume_name": e2e.PRIMARY_VOLUME,
        },
    }


def test_launcher_lifecycle_diagnostics_falls_back_to_legacy_fields():
    launcher = FakeLauncher()
    setattr(
        launcher,
        "_EdgeNodeLauncher__active_lifecycle_operation",
        {"operation": "launch", "container_name": e2e.PRIMARY_CONTAINER},
    )
    setattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress", True)
    setattr(
        launcher,
        "_EdgeNodeLauncher__pending_launch_context",
        {
            "container_name": e2e.PRIMARY_CONTAINER,
            "volume_name": e2e.PRIMARY_VOLUME,
        },
    )

    assert e2e.launcher_lifecycle_diagnostics(launcher) == {
        "lifecycle_operation": {"operation": "launch", "container_name": e2e.PRIMARY_CONTAINER},
        "docker_pull_in_progress": True,
        "pending_launch_context": {
            "container_name": e2e.PRIMARY_CONTAINER,
            "volume_name": e2e.PRIMARY_VOLUME,
        },
    }


def test_wait_for_launch_activity_records_existing_activity(monkeypatch, tmp_path):
    output_path = tmp_path / "result.json"
    log = {"steps": []}
    launcher = FakeLauncher()

    monkeypatch.setattr(e2e, "docker_running", lambda _container_name: False)
    monkeypatch.setattr(e2e, "visible_dialog_titles", lambda _app: ["Pulling Docker Image"])

    e2e.wait_for_launch_activity(
        FakeApp(),
        launcher,
        log,
        str(output_path),
        timeout=1,
        label="primary launch activity",
    )

    assert log["steps"][-1]["step"] == "launch activity observed"
    assert log["steps"][-1]["visible_dialogs"] == ["Pulling Docker Image"]
    assert log["steps"][-1]["dialog_screenshots"] == []


def test_capture_visible_dialog_screenshots_records_dialog_image(qtbot, tmp_path):
    from PyQt5.QtWidgets import QDialog, QLabel

    dialog = QDialog()
    dialog.setWindowTitle("Pulling Docker Image")
    QLabel("Downloading layer", dialog)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    class FakeQtApp:
        def topLevelWidgets(self):
            return [dialog]

    screenshots = e2e.capture_visible_dialog_screenshots(
        FakeQtApp(),
        str(tmp_path),
        "primary launch activity",
    )

    assert screenshots == [
        {
            "title": "Pulling Docker Image",
            "path": str(tmp_path / "primary_launch_activity_0_Pulling_Docker_Image.png"),
        }
    ]
    assert (tmp_path / "primary_launch_activity_0_Pulling_Docker_Image.png").exists()


def test_find_dialog_matches_any_supported_title(qtbot):
    from PyQt5.QtWidgets import QDialog

    dialog = QDialog()
    qtbot.addWidget(dialog)
    dialog.setWindowTitle("Rename Node")
    dialog.show()

    class FakeQtApp:
        def topLevelWidgets(self):
            return [dialog]

    assert e2e.find_dialog(FakeQtApp(), e2e.RENAME_DIALOG_TITLES) is dialog
    assert e2e.find_dialog(FakeQtApp(), "Change Node Name") is None
