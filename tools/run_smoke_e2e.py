"""Visible non-destructive launcher smoke scenario.

This runner opens the real PyQt launcher with a temporary config and a fake
Docker handler. It clicks safe UI controls without creating, stopping, or
removing Docker resources.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_CONTAINER = "r1nodesmoke"
SMOKE_VOLUME = "r1volsmoke"


class FakeDockerHandler:
    def __init__(self, container_name):
        self.container_name = container_name
        self.container_names = [container_name]
        self.debug_values = []
        self.node_name_updates = []

    def set_container_name(self, container_name):
        self.container_name = container_name
        self.container_names.append(container_name)

    def is_container_running(self):
        return False

    def set_debug_mode(self, value):
        self.debug_values.append(value)

    def execute_command(self, command):
        return "", "", 0

    def get_node_info(self, on_success, on_error):
        on_error("Smoke runner does not execute Docker commands")

    def get_node_history(self, callback, error_callback):
        callback(SimpleNamespace(timestamps=[], cpu_load=[], occupied_memory=[], gpu_load=[], gpu_occupied_memory=[]))

    def update_node_name(self, new_name, on_success, on_error):
        self.node_name_updates.append(new_name)
        on_error("Smoke runner does not rename nodes")

    def stop_container_threaded(self, container_name, callback, error_callback):
        error_callback("Smoke runner does not stop containers")

    def launch_container_threaded(self, volume_name=None, callback=None, error_callback=None):
        if error_callback:
            error_callback("Smoke runner does not launch containers")

    def pull_image(self, callback, error_callback, output_callback=None):
        if error_callback:
            error_callback("Smoke runner does not pull images")


def write_log(log, output_path):
    if output_path:
        Path(output_path).write_text(json.dumps(log, indent=2), encoding="utf-8")


def record_step(log, output_path, step):
    log["steps"].append(step)
    write_log(log, output_path)
    print(f"SMOKE_E2E_STEP: {step}", flush=True)


def wait_until(app, predicate, timeout, label, interval=0.1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {label}")


def window_snapshot(launcher):
    frame = launcher.frameGeometry()
    client = launcher.geometry()
    return {
        "title": launcher.windowTitle(),
        "client": {"x": client.x(), "y": client.y(), "w": client.width(), "h": client.height()},
        "frame": {"x": frame.x(), "y": frame.y(), "w": frame.width(), "h": frame.height()},
        "visible": launcher.isVisible(),
    }


def click_button(app, button, label):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest

    button.setFocus()
    QTest.mouseClick(button, Qt.LeftButton)
    app.processEvents()
    return label


def find_dialog(app, title):
    from PyQt5.QtWidgets import QDialog

    for widget in app.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.isVisible() and title in widget.windowTitle():
            return widget
    return None


def click_dialog_button(app, dialog, object_name):
    from PyQt5.QtWidgets import QPushButton

    button = dialog.findChild(QPushButton, object_name)
    if button is None:
        raise AssertionError(f"Could not find dialog button {object_name!r}")
    click_button(app, button, button.objectName() or button.text())


def patch_message_boxes(log, output_path):
    from PyQt5.QtWidgets import QMessageBox

    def record_box(kind, default_result):
        def handler(parent, title, text, *args, **kwargs):
            record_step(
                log,
                output_path,
                {
                    "step": "message box auto-answered",
                    "kind": kind,
                    "title": str(title),
                    "text": str(text),
                },
            )
            return default_result

        return handler

    QMessageBox.information = staticmethod(record_box("information", QMessageBox.Ok))
    QMessageBox.warning = staticmethod(record_box("warning", QMessageBox.Ok))
    QMessageBox.critical = staticmethod(record_box("critical", QMessageBox.Ok))
    QMessageBox.question = staticmethod(record_box("question", QMessageBox.Yes))


def install_browser_recorder(log):
    import webbrowser

    opened_urls = []
    original_open = webbrowser.open

    def record_open(url, *args, **kwargs):
        opened_urls.append(str(url))
        return True

    webbrowser.open = record_open
    log["opened_urls"] = opened_urls

    def restore():
        webbrowser.open = original_open

    return restore


def run_scenarios(args):
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))

    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication

    import app_forms.frm_main as frm_main
    from utils.config_manager import ConfigManager, ContainerConfig

    log = {
        "started_at": datetime.now().isoformat(),
        "destructive": False,
        "containers": [SMOKE_CONTAINER],
        "volumes": [SMOKE_VOLUME],
        "steps": [],
    }
    write_log(log, args.output)
    patch_message_boxes(log, args.output)
    restore_browser = install_browser_recorder(log)

    temp_root = Path(tempfile.mkdtemp(prefix="r1-launcher-smoke-"))
    config_manager = ConfigManager(str(temp_root / "config"))
    config_manager.add_container(
        ContainerConfig(
            name=SMOKE_CONTAINER,
            volume=SMOKE_VOLUME,
            node_address="0xsmokenode",
            eth_address="0xsmokeeth",
            node_alias="smoke-primary",
        )
    )
    fake_docker = FakeDockerHandler(SMOKE_CONTAINER)

    frm_main.DOCKER_CONTAINER_NAME = SMOKE_CONTAINER
    frm_main.ConfigManager = lambda: config_manager
    frm_main.DockerCommandHandler = lambda container_name: fake_docker
    frm_main.EdgeNodeLauncher.check_docker_with_ui = lambda self: True
    frm_main.EdgeNodeLauncher.docker_initialize = lambda self: None
    frm_main.EdgeNodeLauncher.check_for_updates = lambda self, verbose=False: None
    frm_main.EdgeNodeLauncher.container_exists_in_docker = lambda self, name: False

    app = QApplication.instance() or QApplication(sys.argv)
    launcher = frm_main.EdgeNodeLauncher()
    launcher.check_ram_for_new_node = lambda existing_node_count=0: {
        "can_add_node": True,
        "total_ram_gb": 128.0,
        "max_nodes_supported": 8,
        "current_node_count": existing_node_count,
        "min_required_gb": frm_main.MIN_NODE_RAM_GB,
    }
    launcher.show()
    if hasattr(launcher, "timer") and launcher.timer is not None:
        launcher.timer.stop()
    app.processEvents()

    try:
        record_step(log, args.output, {"step": "window shown", "window": window_snapshot(launcher)})

        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle light theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.DARK_DASHBOARD_BUTTON_TEXT, args.timeout, "light theme")
        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle dark theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.LIGHT_DASHBOARD_BUTTON_TEXT, args.timeout, "dark theme")

        record_step(log, args.output, {"step": click_button(app, launcher.refreshButton, "refresh stopped node")})
        record_step(log, args.output, {"step": click_button(app, launcher.force_debug_checkbox, "toggle force debug")})
        record_step(log, args.output, {"step": click_button(app, launcher.dapp_button, "open dapp link")})
        record_step(log, args.output, {"step": click_button(app, launcher.explorer_button, "show explorer placeholder")})
        record_step(log, args.output, {"step": click_button(app, launcher.docker_download_button, "open docker download link")})

        def cancel_add_node_dialog():
            dialog = find_dialog(app, "Add New Node")
            if dialog is None:
                QTimer.singleShot(100, cancel_add_node_dialog)
                return
            click_dialog_button(app, dialog, "createNodeCancelButton")

        QTimer.singleShot(100, cancel_add_node_dialog)
        record_step(log, args.output, {"step": click_button(app, launcher.add_node_button, "open and cancel add node dialog")})

        record_step(log, args.output, {"step": click_button(app, launcher.renameNodeButton, "rename stopped node guard")})

        log["result"] = "passed"
        return log
    except Exception as exc:
        log["result"] = "failed"
        log["error"] = str(exc)
        raise
    finally:
        try:
            restore_browser()
        finally:
            launcher.close()
            app.processEvents()
            log["finished_at"] = datetime.now().isoformat()
            write_log(log, args.output)
            print(json.dumps(log, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Run visible non-destructive launcher smoke scenarios.")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    log = run_scenarios(args)
    if log.get("result") != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
