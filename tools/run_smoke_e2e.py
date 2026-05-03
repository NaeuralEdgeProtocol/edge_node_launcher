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
    print(f"SMOKE_E2E_STEP: {json.dumps(step, ensure_ascii=True)}", flush=True)


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


def rect_snapshot(rect):
    return {
        "x": rect.x(),
        "y": rect.y(),
        "w": rect.width(),
        "h": rect.height(),
        "left": rect.x(),
        "top": rect.y(),
        "right": rect.x() + rect.width() - 1,
        "bottom": rect.y() + rect.height() - 1,
    }


def widget_global_rect(widget):
    top_left = widget.mapToGlobal(widget.rect().topLeft())
    return {
        "x": top_left.x(),
        "y": top_left.y(),
        "w": widget.rect().width(),
        "h": widget.rect().height(),
        "left": top_left.x(),
        "top": top_left.y(),
        "right": top_left.x() + widget.rect().width() - 1,
        "bottom": top_left.y() + widget.rect().height() - 1,
    }


def safe_area_status(control_rect, safe_right):
    overlaps_scrollbar = control_rect["right"] > safe_right
    return {
        "safe_right": safe_right,
        "inside_safe_area": not overlaps_scrollbar,
        "overlaps_scrollbar": overlaps_scrollbar,
    }


def sidebar_visual_snapshot(launcher):
    from PyQt5.QtWidgets import QScrollArea, QWidget

    sidebar_scroll = launcher.findChild(QScrollArea, "sidebarScrollArea")
    if sidebar_scroll is None:
        return {"found": False, "issues": ["sidebarScrollArea was not found"], "passed": False}

    viewport = sidebar_scroll.viewport()
    scrollbar = sidebar_scroll.verticalScrollBar()
    sidebar_widget = sidebar_scroll.widget()
    viewport_rect = widget_global_rect(viewport)
    scrollbar_rect = widget_global_rect(scrollbar) if scrollbar.isVisible() else None
    safe_right = (scrollbar_rect["left"] - 2) if scrollbar_rect else (viewport_rect["right"] - 2)
    issues = []

    if sidebar_widget is not None and sidebar_widget.width() > viewport.width():
        issues.append(
            f"sidebar content width {sidebar_widget.width()} exceeds viewport width {viewport.width()}"
        )
    content_fits_viewport = sidebar_widget is not None and sidebar_widget.width() <= viewport.width()

    controls = []
    control_names = (
        "addNodeButton",
        "renameNodeButton",
        "startNodeButton",
        "downloadDockerButton",
        "openDappButton",
        "openExplorerButton",
        "refreshNodeInfoButton",
        "themeToggleButton",
        "forceDebugCheckbox",
    )
    for object_name in control_names:
        control = launcher.findChild(QWidget, object_name)
        if control is None:
            issues.append(f"{object_name} was not found")
            continue

        control_rect = widget_global_rect(control)
        status = safe_area_status(control_rect, safe_right)
        intersects_viewport = (
            control_rect["bottom"] >= viewport_rect["top"]
            and control_rect["top"] <= viewport_rect["bottom"]
        )
        if control.isVisible() and intersects_viewport and not status["inside_safe_area"]:
            issues.append(f"{object_name} overlaps the sidebar scrollbar safe area")

        controls.append(
            {
                "object_name": object_name,
                "text": control.text() if hasattr(control, "text") else "",
                "visible": control.isVisible(),
                "intersects_viewport": intersects_viewport,
                "rect": control_rect,
                **status,
            }
        )

    return {
        "found": True,
        "scroll_area": widget_global_rect(sidebar_scroll),
        "viewport": viewport_rect,
        "content": widget_global_rect(sidebar_widget) if sidebar_widget is not None else None,
        "content_fits_viewport": content_fits_viewport,
        "vertical_scrollbar_visible": scrollbar.isVisible(),
        "vertical_scrollbar": scrollbar_rect,
        "vertical_scrollbar_value": scrollbar.value(),
        "horizontal_scrollbar_policy": int(sidebar_scroll.horizontalScrollBarPolicy()),
        "safe_right": safe_right,
        "controls": controls,
        "issues": issues,
        "passed": not issues,
    }


def save_widget_screenshot(widget, screenshot_dir, filename):
    if not screenshot_dir:
        return ""
    target_dir = Path(screenshot_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    pixmap = widget.grab()
    if not pixmap.save(str(target_path)):
        raise RuntimeError(f"Could not save screenshot to {target_path}")
    return str(target_path)


def capture_visual_evidence(launcher, screenshot_dir, label):
    from PyQt5.QtWidgets import QScrollArea

    evidence = {
        "label": label,
        "window": window_snapshot(launcher),
        "sidebar": sidebar_visual_snapshot(launcher),
    }
    if screenshot_dir:
        evidence["full_window_screenshot"] = save_widget_screenshot(
            launcher,
            screenshot_dir,
            f"{label}_full_window.png",
        )
        sidebar_scroll = launcher.findChild(QScrollArea, "sidebarScrollArea")
        if sidebar_scroll is not None:
            evidence["sidebar_screenshot"] = save_widget_screenshot(
                sidebar_scroll,
                screenshot_dir,
                f"{label}_sidebar.png",
            )
    return evidence


def dialog_visual_snapshot(dialog):
    from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton

    return {
        "title": dialog.windowTitle(),
        "object_name": dialog.objectName(),
        "visible": dialog.isVisible(),
        "rect": widget_global_rect(dialog),
        "labels": [
            {
                "object_name": label.objectName(),
                "text": label.text(),
                "visible": label.isVisible(),
                "word_wrap": label.wordWrap(),
                "rect": widget_global_rect(label),
            }
            for label in dialog.findChildren(QLabel)
        ],
        "line_edits": [
            {
                "object_name": line_edit.objectName(),
                "text": line_edit.text(),
                "placeholder": line_edit.placeholderText(),
                "visible": line_edit.isVisible(),
                "enabled": line_edit.isEnabled(),
                "rect": widget_global_rect(line_edit),
            }
            for line_edit in dialog.findChildren(QLineEdit)
        ],
        "buttons": [
            {
                "object_name": button.objectName(),
                "text": button.text(),
                "visible": button.isVisible(),
                "enabled": button.isEnabled(),
                "rect": widget_global_rect(button),
            }
            for button in dialog.findChildren(QPushButton)
        ],
    }


def capture_dialog_visual_evidence(dialog, screenshot_dir, label):
    evidence = {
        "label": label,
        "dialog": dialog_visual_snapshot(dialog),
    }
    if screenshot_dir:
        evidence["screenshot"] = save_widget_screenshot(
            dialog,
            screenshot_dir,
            f"{label}_dialog.png",
        )
    return evidence


def toast_visual_snapshot(launcher):
    toast = getattr(launcher, "toast", None)
    if toast is None:
        return {"found": False, "visible": False}

    return {
        "found": True,
        "visible": toast.isVisible(),
        "rect": widget_global_rect(toast),
        "title": toast.title.text() if hasattr(toast, "title") else "",
        "icon": toast.icon.text() if hasattr(toast, "icon") else "",
        "message": toast.message.text() if hasattr(toast, "message") else "",
    }


def capture_toast_visual_evidence(launcher, screenshot_dir, label):
    evidence = {
        "label": label,
        "toast": toast_visual_snapshot(launcher),
    }
    toast = getattr(launcher, "toast", None)
    if screenshot_dir and toast is not None and toast.isVisible():
        evidence["screenshot"] = save_widget_screenshot(
            toast,
            screenshot_dir,
            f"{label}_toast.png",
        )
    return evidence


def show_and_capture_dialog(app, dialog, log, output_path, screenshot_dir, label):
    dialog.show()
    app.processEvents()
    record_step(
        log,
        output_path,
        {
            "step": f"captured {label} dialog visual evidence",
            "visual": capture_dialog_visual_evidence(dialog, screenshot_dir, label),
        },
    )
    dialog.close()
    app.processEvents()


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


def click_visible_button(app, button, label):
    if not button.isVisible():
        raise AssertionError(f"{label} button is not visible")
    return click_button(app, button, label)


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
    from widgets.dialogs.DockerCheckDialog import DockerCheckDialog
    from widgets.LoadingDialog import LoadingDialog

    log = {
        "started_at": datetime.now().isoformat(),
        "destructive": False,
        "containers": [SMOKE_CONTAINER],
        "volumes": [SMOKE_VOLUME],
        "screenshot_dir": args.screenshot_dir,
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
        startup_visual = capture_visual_evidence(launcher, args.screenshot_dir, "startup")
        record_step(log, args.output, {"step": "captured startup visual evidence", "visual": startup_visual})
        if not startup_visual["sidebar"]["passed"]:
            raise AssertionError("; ".join(startup_visual["sidebar"]["issues"]))

        original_minimum_size = launcher.minimumSize()
        launcher.setMinimumSize(800, 520)
        launcher.resize(900, 560)
        app.processEvents()
        compact_visual = capture_visual_evidence(launcher, args.screenshot_dir, "compact_height")
        record_step(
            log,
            args.output,
            {"step": "captured compact sidebar visual evidence", "visual": compact_visual},
        )
        if not compact_visual["sidebar"]["passed"]:
            raise AssertionError("; ".join(compact_visual["sidebar"]["issues"]))

        launcher.setMinimumSize(original_minimum_size)
        launcher.resize(1600, 900)
        app.processEvents()

        docker_check_dialog = DockerCheckDialog(launcher)
        show_and_capture_dialog(
            app,
            docker_check_dialog,
            log,
            args.output,
            args.screenshot_dir,
            "docker_check",
        )

        loading_dialog = LoadingDialog(
            launcher,
            title="Starting Node",
            message="Please wait while new Edge Node is being launched...",
            size=50,
            stylesheet=launcher._current_stylesheet,
        )
        show_and_capture_dialog(
            app,
            loading_dialog,
            log,
            args.output,
            args.screenshot_dir,
            "startup_loading",
        )

        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle light theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.DARK_DASHBOARD_BUTTON_TEXT, args.timeout, "light theme")
        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle dark theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.LIGHT_DASHBOARD_BUTTON_TEXT, args.timeout, "dark theme")

        record_step(log, args.output, {"step": click_button(app, launcher.refreshButton, "refresh stopped node")})
        wait_until(
            app,
            lambda: launcher.toast.isVisible() and "cached data" in launcher.toast.message.text(),
            args.timeout,
            "refresh stopped-node toast",
        )
        record_step(
            log,
            args.output,
            {
                "step": "captured refresh stopped-node toast visual evidence",
                "visual": capture_toast_visual_evidence(launcher, args.screenshot_dir, "refresh_stopped_node"),
            },
        )
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(app, launcher.copyAddrButton, "copy node address"),
                "clipboard": app.clipboard().text(),
            },
        )
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(app, launcher.copyEthButton, "copy eth address"),
                "clipboard": app.clipboard().text(),
            },
        )
        record_step(log, args.output, {"step": click_button(app, launcher.force_debug_checkbox, "toggle force debug")})
        record_step(log, args.output, {"step": click_button(app, launcher.dapp_button, "open dapp link")})
        record_step(log, args.output, {"step": click_button(app, launcher.explorer_button, "show explorer placeholder")})
        wait_until(
            app,
            lambda: launcher.toast.isVisible() and "Explorer" in launcher.toast.message.text(),
            args.timeout,
            "explorer placeholder toast",
        )
        record_step(
            log,
            args.output,
            {
                "step": "captured explorer placeholder toast visual evidence",
                "visual": capture_toast_visual_evidence(launcher, args.screenshot_dir, "explorer_placeholder"),
            },
        )
        record_step(log, args.output, {"step": click_button(app, launcher.docker_download_button, "open docker download link")})

        def capture_and_cancel_add_node_dialog():
            dialog = find_dialog(app, "Add New Node")
            if dialog is None:
                QTimer.singleShot(100, capture_and_cancel_add_node_dialog)
                return
            record_step(
                log,
                args.output,
                {
                    "step": "captured add-node dialog visual evidence",
                    "visual": capture_dialog_visual_evidence(dialog, args.screenshot_dir, "add_node"),
                },
            )
            click_dialog_button(app, dialog, "createNodeCancelButton")

        QTimer.singleShot(100, capture_and_cancel_add_node_dialog)
        record_step(log, args.output, {"step": click_button(app, launcher.add_node_button, "open and cancel add node dialog")})

        original_is_container_running = launcher.is_container_running
        launcher.is_container_running = lambda: True

        def capture_and_cancel_rename_dialog():
            dialog = find_dialog(app, "Rename Node")
            if dialog is None:
                QTimer.singleShot(100, capture_and_cancel_rename_dialog)
                return
            record_step(
                log,
                args.output,
                {
                    "step": "captured rename dialog visual evidence",
                    "visual": capture_dialog_visual_evidence(dialog, args.screenshot_dir, "rename_node"),
                },
            )
            click_dialog_button(app, dialog, "renameNodeCancelButton")

        try:
            QTimer.singleShot(100, capture_and_cancel_rename_dialog)
            record_step(log, args.output, {"step": click_button(app, launcher.renameNodeButton, "open and cancel rename dialog")})
        finally:
            launcher.is_container_running = original_is_container_running

        record_step(log, args.output, {"step": click_button(app, launcher.renameNodeButton, "rename stopped node guard")})
        wait_until(
            app,
            lambda: launcher.toast.isVisible() and "Container not running" in launcher.toast.message.text(),
            args.timeout,
            "rename stopped-node toast",
        )
        record_step(
            log,
            args.output,
            {
                "step": "captured rename stopped-node toast visual evidence",
                "visual": capture_toast_visual_evidence(launcher, args.screenshot_dir, "rename_stopped_node"),
            },
        )

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
    parser.add_argument("--screenshot-dir", default="")
    args = parser.parse_args()
    log = run_scenarios(args)
    if log.get("result") != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
