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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2e_paths import prepare_evidence_paths, write_json_log
from tools.e2e_visual import assert_title_bar_visible, rect_snapshot, window_snapshot

SMOKE_CONTAINER = "r1nodesmoke"
SMOKE_VOLUME = "r1volsmoke"
SMOKE_SECONDARY_CONTAINER = "r1nodesmoke2"
SMOKE_SECONDARY_VOLUME = "r1volsmoke2"
SMOKE_VALID_NODE_ADDRESS = "0xai_smokeprimary123"
SMOKE_SDK_ADDRESS = "0xai_smokelauncher123"
SMOKE_CONTAINER_APP_SECRET = "smoke-registry-secret"
SMOKE_WORKER_APP_SECRET = "smoke-github-token"
SMOKE_STATUS_SECRET = "smoke-status-token"


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


class FakeSdkDeploymentClient:
    """Deterministic SDK boundary for visible smoke app-management scenarios."""

    def __init__(self):
        self.events = []
        self.deployed = {}
        self.stopped = set()
        self.status_errors = {}

    def launch_container_app(self, spec):
        self.events.append(
            {
                "operation": "launch_container",
                "app_name": spec.app_name,
                "pipeline_name": spec.pipeline_name,
                "file_volume_count": len(spec.file_volumes),
                "has_registry_password": bool(spec.registry_password),
            }
        )
        return self._result_for_spec(spec, "https://smoke-car.example.test")

    def launch_worker_app(self, spec):
        self.events.append(
            {
                "operation": "launch_worker",
                "app_name": spec.app_name,
                "pipeline_name": spec.pipeline_name,
                "file_volume_count": len(spec.file_volumes),
                "has_github_token": bool(spec.github_token),
            }
        )
        return self._result_for_spec(spec, "https://smoke-war.example.test")

    def list_node_apps(self, node_address):
        from services.app_deployment_models import SdkAppStatus

        self.events.append({"operation": "list_node_apps", "node_address": node_address})
        statuses = []
        for result in self.deployed.values():
            if result.node_address != node_address:
                continue
            stopped_key = (result.node_address, result.pipeline_name)
            status_key = (result.node_address, result.pipeline_name)
            statuses.append(
                SdkAppStatus(
                    node_address=result.node_address,
                    app_name=result.app_name,
                    plugin_signature=result.plugin_signature,
                    instance_id=result.instance_id,
                    status="stopped" if stopped_key in self.stopped else "online",
                    url=result.app_url,
                    last_error=self.status_errors.get(status_key, ""),
                )
            )
        return statuses

    def stop_app(self, node_address, pipeline_name):
        self.events.append(
            {
                "operation": "stop_app",
                "node_address": node_address,
                "pipeline_name": pipeline_name,
            }
        )
        self.stopped.add((node_address, pipeline_name))
        return True

    def _result_for_spec(self, spec, url):
        from services.app_deployment_models import DeploymentResult

        result = DeploymentResult(
            app_id=f"{spec.node_address}:{spec.pipeline_name}:{spec.app_type}",
            app_name=spec.app_name,
            app_type=spec.app_type,
            node_address=spec.node_address,
            pipeline_name=spec.pipeline_name,
            plugin_signature=spec.plugin_signature,
            instance_id=f"smoke-{spec.pipeline_name}",
            app_url=url,
            status="deployed",
        )
        self.deployed[result.app_id] = result
        self.stopped.discard((result.node_address, result.pipeline_name))
        return result


class FakeAppLaunchPreflight:
    def __init__(self):
        self.calls = []

    def prepare(self, container_name):
        if not container_name:
            raise ValueError("Target container is required for SDK allow-list setup.")
        changed = not self.calls
        self.calls.append(container_name)
        return SimpleNamespace(
            container_name=container_name,
            allowlist=SimpleNamespace(changed=changed),
        )


class FakeSdkIdentityService:
    def __init__(self):
        self.calls = 0

    def load_identity(self):
        from services.sdk_identity_service import SdkIdentity

        self.calls += 1
        return SdkIdentity(
            sdk_address=SMOKE_SDK_ADDRESS,
            eth_address="0xsmokeethlauncher",
            evm_network="devnet",
            local_cache_base_folder="C:/tmp/r1-launcher-smoke",
        )


def write_log(log, output_path):
    write_json_log(log, output_path)


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
        "edgeImageBadge",
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


def scroll_sidebar_to(launcher, position):
    from PyQt5.QtWidgets import QScrollArea

    sidebar_scroll = launcher.findChild(QScrollArea, "sidebarScrollArea")
    if sidebar_scroll is None:
        raise AssertionError("sidebarScrollArea was not found")

    scrollbar = sidebar_scroll.verticalScrollBar()
    original_value = scrollbar.value()
    if position == "bottom":
        scrollbar.setValue(scrollbar.maximum())
    elif position == "top":
        scrollbar.setValue(scrollbar.minimum())
    else:
        scrollbar.setValue(int(position))
    return original_value


def scroll_apps_workspace_to(launcher, position):
    from PyQt5.QtWidgets import QScrollArea

    apps_scroll = launcher.findChild(QScrollArea, "appsWorkspaceScrollArea")
    if apps_scroll is None:
        return scroll_sidebar_to(launcher, position)

    scrollbar = apps_scroll.verticalScrollBar()
    original_value = scrollbar.value()
    if position == "bottom":
        scrollbar.setValue(scrollbar.maximum())
    elif position == "top":
        scrollbar.setValue(scrollbar.minimum())
    else:
        scrollbar.setValue(int(position))
    return original_value


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


def save_widget_region_screenshot(source_widget, target_widget, screenshot_dir, filename):
    """Save target_widget's composed region by cropping source_widget's grab."""
    if not screenshot_dir:
        return ""

    from PyQt5.QtCore import QPoint, QRect

    target_dir = Path(screenshot_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    source_pixmap = source_widget.grab()
    target_top_left = target_widget.mapTo(source_widget, QPoint(0, 0))
    target_rect = QRect(target_top_left, target_widget.size()).intersected(source_widget.rect())
    if target_rect.isEmpty():
        raise RuntimeError(f"Could not crop {target_widget.objectName() or target_widget} from source widget")
    if not source_pixmap.copy(target_rect).save(str(target_path)):
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
            evidence["sidebar_screenshot"] = save_widget_region_screenshot(
                launcher,
                sidebar_scroll,
                screenshot_dir,
                f"{label}_sidebar.png",
            )
    return evidence


def combo_popup_visual_snapshot(app, combo):
    combo.showPopup()
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()

    popup = combo.view().window()
    return {
        "combo_object_name": combo.objectName(),
        "combo_accessible_name": combo.accessibleName(),
        "combo_tooltip": combo.toolTip(),
        "combo_rect": widget_global_rect(combo),
        "current_text": combo.currentText(),
        "current_index": combo.currentIndex(),
        "items": [
            {
                "index": index,
                "text": combo.itemText(index),
                "data": combo.itemData(index),
            }
            for index in range(combo.count())
        ],
        "popup_visible": popup.isVisible(),
        "popup_rect": widget_global_rect(popup),
        "popup_widget": popup,
    }


def capture_combo_popup_visual_evidence(app, combo, screenshot_dir, label):
    snapshot = combo_popup_visual_snapshot(app, combo)
    popup = snapshot.pop("popup_widget")
    evidence = {
        "label": label,
        "combo_popup": snapshot,
    }
    if screenshot_dir and snapshot["popup_visible"]:
        evidence["screenshot"] = save_widget_screenshot(
            popup,
            screenshot_dir,
            f"{label}_combo_popup.png",
        )
    combo.hidePopup()
    app.processEvents()
    return evidence


def dialog_visual_snapshot(dialog):
    from PyQt5.QtWidgets import QLabel, QLineEdit, QProgressBar, QPushButton

    return {
        "title": dialog.windowTitle(),
        "object_name": dialog.objectName(),
        "accessible_name": dialog.accessibleName(),
        "visible": dialog.isVisible(),
        "rect": widget_global_rect(dialog),
        "labels": [
            {
                "object_name": label.objectName(),
                "accessible_name": label.accessibleName(),
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
                "accessible_name": line_edit.accessibleName(),
                "role": line_edit.property("role"),
                "text": line_edit.text(),
                "placeholder": line_edit.placeholderText(),
                "visible": line_edit.isVisible(),
                "enabled": line_edit.isEnabled(),
                "minimum_height": line_edit.minimumHeight(),
                "rect": widget_global_rect(line_edit),
            }
            for line_edit in dialog.findChildren(QLineEdit)
        ],
        "buttons": [
            {
                "object_name": button.objectName(),
                "accessible_name": button.accessibleName(),
                "text": button.text(),
                "visible": button.isVisible(),
                "enabled": button.isEnabled(),
                "rect": widget_global_rect(button),
            }
            for button in dialog.findChildren(QPushButton)
        ],
        "progress_bars": [
            {
                "object_name": progress_bar.objectName(),
                "accessible_name": progress_bar.accessibleName(),
                "value": progress_bar.value(),
                "minimum": progress_bar.minimum(),
                "maximum": progress_bar.maximum(),
                "visible": progress_bar.isVisible(),
                "rect": widget_global_rect(progress_bar),
            }
            for progress_bar in dialog.findChildren(QProgressBar)
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
        "object_name": toast.objectName(),
        "accessible_name": toast.accessibleName(),
        "rect": widget_global_rect(toast),
        "title": toast.title.text() if hasattr(toast, "title") else "",
        "icon": toast.icon.text() if hasattr(toast, "icon") else "",
        "message": toast.message.text() if hasattr(toast, "message") else "",
        "message_word_wrap": toast.message.wordWrap() if hasattr(toast, "message") else False,
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


def click_tab(app, tab_widget, index, label):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest

    if not tab_widget.isVisible():
        raise AssertionError(f"{label} tab group is not visible")
    tab_bar = tab_widget.tabBar()
    tab_rect = tab_bar.tabRect(index)
    if not tab_rect.isValid():
        raise AssertionError(f"{label} tab index {index} is not valid")
    QTest.mouseClick(tab_bar, Qt.LeftButton, Qt.NoModifier, tab_rect.center())
    app.processEvents()
    if tab_widget.currentIndex() != index:
        raise AssertionError(f"{label} tab did not become active")
    return label


def set_line_edit_value(app, line_edit, value):
    line_edit.setFocus()
    line_edit.clear()
    line_edit.setText(value)
    app.processEvents()


def set_plain_text_value(app, plain_text_edit, value):
    plain_text_edit.setFocus()
    plain_text_edit.setPlainText(value)
    app.processEvents()


def app_table_snapshot(apps_page):
    rows = []
    for row in range(apps_page.apps_table.rowCount()):
        rows.append(
            {
                "name": _table_text(apps_page.apps_table, row, 0),
                "type": _table_text(apps_page.apps_table, row, 1),
                "status": _table_text(apps_page.apps_table, row, 2),
            }
        )
    return rows


def secret_line_edit_snapshot(line_edit, raw_secret):
    from PyQt5.QtWidgets import QLineEdit

    display_text = line_edit.displayText()
    return {
        "object_name": line_edit.objectName(),
        "accessible_name": line_edit.accessibleName(),
        "uses_password_echo": line_edit.echoMode() == QLineEdit.Password,
        "display_text_length": len(display_text),
        "raw_secret_visible": bool(raw_secret and raw_secret in display_text),
    }


def _table_text(table, row, column):
    item = table.item(row, column)
    return item.text() if item is not None else ""


def show_launcher_page(app, launcher, page_name):
    panel = getattr(launcher, "sidebar_panel", None)
    if panel is None or not hasattr(panel, "show_page"):
        return
    panel.show_page(page_name)
    app.processEvents()


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


def run_mocked_sdk_apps_scenario(
    app,
    launcher,
    log,
    output_path,
    screenshot_dir,
    timeout,
    fake_sdk_client,
    fake_preflight,
    app_registry,
):
    apps_page = launcher.apps_page
    if getattr(launcher, "toast", None) is not None:
        launcher.toast.hide()
    apps_page.deployment_client = fake_sdk_client
    apps_page.set_launch_preflight_service(fake_preflight)
    apps_page.set_target_node(node_address=SMOKE_VALID_NODE_ADDRESS, container_name=SMOKE_CONTAINER)
    set_line_edit_value(app, apps_page.node_address_input, SMOKE_VALID_NODE_ADDRESS)

    show_launcher_page(app, launcher, "apps")
    scroll_apps_workspace_to(launcher, "top")
    app.processEvents()
    record_step(log, output_path, {"step": "show apps page for mocked SDK app E2E"})

    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.sdk_settings_button, "open SDK settings from apps")},
    )
    if getattr(launcher, "sidebar_panel", None) is None or launcher.sidebar_panel.current_page_name() != "network":
        raise AssertionError("SDK settings button did not switch to the Network page")
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, launcher.refresh_sdk_identity_button, "refresh SDK identity")},
    )
    wait_until(
        app,
        lambda: launcher.sidebar_panel.sdk_identity_address_label.text() == SMOKE_SDK_ADDRESS,
        timeout,
        "mocked SDK identity refresh",
    )
    record_step(
        log,
        output_path,
        {
            "step": click_visible_button(app, launcher.copy_sdk_identity_address_button, "copy SDK identity address"),
            "clipboard": app.clipboard().text(),
        },
    )
    if app.clipboard().text() != SMOKE_SDK_ADDRESS:
        raise AssertionError("SDK identity address copy used an unexpected value")
    sdk_settings_visual = capture_visual_evidence(launcher, screenshot_dir, "network_sdk_identity")
    record_step(
        log,
        output_path,
        {
            "step": "captured SDK settings visual evidence",
            "visual": sdk_settings_visual,
        },
    )
    show_launcher_page(app, launcher, "apps")
    scroll_apps_workspace_to(launcher, "top")
    app.processEvents()
    record_step(log, output_path, {"step": "returned to apps page after SDK settings shortcut"})
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.check_sdk_access_button, "check SDK node access")},
    )
    wait_until(
        app,
        lambda: apps_page.validation_message.isVisible()
        and apps_page.validation_message.text() in {"SDK access added", "SDK access ready"},
        timeout,
        "SDK access check",
    )
    record_step(
        log,
        output_path,
        {
            "step": "SDK access checked before app launch",
            "message": apps_page.validation_message.text(),
            "preflight_calls": list(fake_preflight.calls),
        },
    )

    set_line_edit_value(app, apps_page.app_name_input, "smoke_car")
    set_line_edit_value(app, apps_page.car_image_input, "nginx:alpine")
    set_line_edit_value(app, apps_page.car_port_input, "8080")
    set_line_edit_value(app, apps_page.car_registry_input, "docker.io")
    set_line_edit_value(app, apps_page.car_registry_user_input, "smoke-user")
    set_line_edit_value(app, apps_page.car_registry_password_input, SMOKE_CONTAINER_APP_SECRET)

    if not apps_page.advanced_options_toggle.isChecked():
        record_step(
            log,
            output_path,
            {"step": click_visible_button(app, apps_page.advanced_options_toggle, "show advanced app options")},
        )
    record_step(
        log,
        output_path,
        {"step": click_tab(app, apps_page.advanced_options_tabs, 2, "select environment app options")},
    )
    set_plain_text_value(app, apps_page.env_input, "SMOKE_MODE=mock\nPUBLIC_VALUE=visible")
    record_step(
        log,
        output_path,
        {"step": click_tab(app, apps_page.advanced_options_tabs, 1, "select storage app options")},
    )
    set_line_edit_value(app, apps_page.app_volume_source_input, "smoke_car_cache")
    set_line_edit_value(app, apps_page.app_volume_mount_input, "/app/cache")
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.add_volume_button, "add container app volume mount")},
    )
    if apps_page.app_volumes_table.rowCount() != 1:
        raise AssertionError("container app volume mount was not added")
    set_line_edit_value(app, apps_page.app_file_volume_name_input, "settings")
    set_line_edit_value(app, apps_page.app_file_volume_mount_input, "/app/settings.ini")
    set_plain_text_value(app, apps_page.app_file_volume_content_input, "FEATURE_FLAG=true")
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.add_file_volume_button, "add container app config file")},
    )
    if apps_page.app_file_volumes_table.rowCount() != 1:
        raise AssertionError("container app config file was not added")
    scroll_apps_workspace_to(launcher, "bottom")
    app.processEvents()
    if getattr(launcher, "toast", None) is not None:
        launcher.toast.hide()
    container_secret_visual = capture_visual_evidence(launcher, screenshot_dir, "apps_container_secret_fields")
    container_secret_snapshot = secret_line_edit_snapshot(
        apps_page.car_registry_password_input,
        SMOKE_CONTAINER_APP_SECRET,
    )
    if not container_secret_snapshot["uses_password_echo"] or container_secret_snapshot["raw_secret_visible"]:
        raise AssertionError("container registry password is visible in the Apps page")
    record_step(
        log,
        output_path,
        {
            "step": "captured container app secret-field visual evidence",
            "visual": container_secret_visual,
            "secret_field": container_secret_snapshot,
        },
    )

    scroll_apps_workspace_to(launcher, "top")
    app.processEvents()
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.validate_button, "validate container app")})
    wait_until(
        app,
        lambda: apps_page.validation_message.isVisible() and apps_page.validation_message.text() == "Ready",
        timeout,
        "container app validation",
    )
    record_step(
        log,
        output_path,
        {
            "step": click_visible_button(app, apps_page.launch_button, "launch container app"),
            "preflight_calls_before_wait": len(fake_preflight.calls),
        },
    )
    wait_until(
        app,
        lambda: apps_page.apps_table.rowCount() >= 1 and apps_page.validation_message.text() == "Launched",
        timeout,
        "container app launch",
    )
    registry_payload = app_registry.registry_file.read_text(encoding="utf-8")
    if "FEATURE_FLAG=true" in registry_payload:
        raise AssertionError("container app config file content was written to the app registry")
    if SMOKE_CONTAINER_APP_SECRET in registry_payload:
        raise AssertionError("container app secret was written to the app registry")
    record_step(
        log,
        output_path,
        {
            "step": "container app launched through mocked SDK",
            "table": app_table_snapshot(apps_page),
            "preflight_calls": list(fake_preflight.calls),
            "registry_secret_redacted": "***REDACTED***" in registry_payload,
            "events": list(fake_sdk_client.events),
        },
    )

    apps_page.apps_table.selectRow(0)
    app.processEvents()
    record_step(log, output_path, {"step": "select container app row"})
    fake_sdk_client.status_errors[(SMOKE_VALID_NODE_ADDRESS, "smoke_car")] = (
        f"health probe failed token={SMOKE_STATUS_SECRET}"
    )
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.refresh_button, "refresh container app status")})
    wait_until(
        app,
        lambda: _table_text(apps_page.apps_table, 0, 2) == "online",
        timeout,
        "container app status refresh",
    )
    registry_payload = app_registry.registry_file.read_text(encoding="utf-8")
    if SMOKE_STATUS_SECRET in registry_payload:
        raise AssertionError("SDK status diagnostic secret was written to the app registry")
    details_text = launcher.apps_detail_text.toPlainText()
    if "health probe failed token=[redacted]" not in details_text:
        raise AssertionError("redacted SDK status diagnostic was not visible in app details")
    diagnostics_visual = capture_visual_evidence(launcher, screenshot_dir, "apps_status_diagnostics")
    record_step(
        log,
        output_path,
        {
            "step": "container app status refreshed",
            "table": app_table_snapshot(apps_page),
            "details_contains_redacted_diagnostic": True,
            "visual": diagnostics_visual,
        },
    )
    record_step(
        log,
        output_path,
        {
            "step": click_visible_button(app, apps_page.copy_url_button, "copy container app URL"),
            "clipboard": app.clipboard().text(),
        },
    )
    if app.clipboard().text() != "https://smoke-car.example.test":
        raise AssertionError("container app URL copy used an unexpected value")
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.stop_button, "stop container app")})
    wait_until(
        app,
        lambda: _table_text(apps_page.apps_table, 0, 2) == "stopped",
        timeout,
        "container app stop",
    )

    apps_page.app_volumes_table.selectRow(0)
    app.processEvents()
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.remove_volume_button, "remove container app volume mount")},
    )
    if apps_page.app_volumes_table.rowCount() != 0:
        raise AssertionError("container app volume mount was not removed")
    apps_page.app_file_volumes_table.selectRow(0)
    app.processEvents()
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.remove_file_volume_button, "remove container app config file")},
    )
    if apps_page.app_file_volumes_table.rowCount() != 0:
        raise AssertionError("container app config file was not removed")

    apps_page.runner_type_combo.setCurrentIndex(1)
    app.processEvents()
    set_line_edit_value(app, apps_page.app_name_input, "smoke_war")
    set_line_edit_value(app, apps_page.node_address_input, SMOKE_VALID_NODE_ADDRESS)
    set_line_edit_value(app, apps_page.worker_repo_input, "https://github.com/ratio1/smoke-app")
    set_line_edit_value(app, apps_page.worker_branch_input, "main")
    set_line_edit_value(app, apps_page.worker_image_input, "node:22")
    set_line_edit_value(app, apps_page.worker_port_input, "4173")
    set_line_edit_value(app, apps_page.worker_github_user_input, "smoke-user")
    set_line_edit_value(app, apps_page.worker_github_token_input, SMOKE_WORKER_APP_SECRET)
    set_plain_text_value(app, apps_page.worker_commands_input, "npm install\nnpm run build\nnpm run start")
    record_step(
        log,
        output_path,
        {"step": click_tab(app, apps_page.advanced_options_tabs, 2, "select worker environment app options")},
    )
    set_plain_text_value(app, apps_page.env_input, "SMOKE_MODE=mock\nPUBLIC_VALUE=worker")
    record_step(
        log,
        output_path,
        {"step": click_tab(app, apps_page.advanced_options_tabs, 1, "select worker storage app options")},
    )
    set_line_edit_value(app, apps_page.app_volume_source_input, "smoke_worker_cache")
    set_line_edit_value(app, apps_page.app_volume_mount_input, "/workspace/cache")
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.add_volume_button, "add worker app volume mount")},
    )
    if apps_page.app_volumes_table.rowCount() != 1:
        raise AssertionError("worker app volume mount was not added")
    set_line_edit_value(app, apps_page.app_file_volume_name_input, "worker_env")
    set_line_edit_value(app, apps_page.app_file_volume_mount_input, "/workspace/.env")
    set_plain_text_value(app, apps_page.app_file_volume_content_input, "PUBLIC_VALUE=worker")
    record_step(
        log,
        output_path,
        {"step": click_visible_button(app, apps_page.add_file_volume_button, "add worker app config file")},
    )
    if apps_page.app_file_volumes_table.rowCount() != 1:
        raise AssertionError("worker app config file was not added")

    scroll_apps_workspace_to(launcher, "bottom")
    app.processEvents()
    if getattr(launcher, "toast", None) is not None:
        launcher.toast.hide()
    worker_secret_visual = capture_visual_evidence(launcher, screenshot_dir, "apps_worker_secret_fields")
    worker_secret_snapshot = secret_line_edit_snapshot(
        apps_page.worker_github_token_input,
        SMOKE_WORKER_APP_SECRET,
    )
    if not worker_secret_snapshot["uses_password_echo"] or worker_secret_snapshot["raw_secret_visible"]:
        raise AssertionError("worker GitHub token is visible in the Apps page")
    record_step(
        log,
        output_path,
        {
            "step": "captured worker app secret-field visual evidence",
            "visual": worker_secret_visual,
            "secret_field": worker_secret_snapshot,
        },
    )

    scroll_apps_workspace_to(launcher, "top")
    app.processEvents()
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.validate_button, "validate worker app")})
    wait_until(
        app,
        lambda: apps_page.validation_message.isVisible() and apps_page.validation_message.text() == "Ready",
        timeout,
        "worker app validation",
    )
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.launch_button, "launch worker app")})
    wait_until(
        app,
        lambda: apps_page.apps_table.rowCount() >= 2 and apps_page.validation_message.text() == "Launched",
        timeout,
        "worker app launch",
    )
    registry_payload = app_registry.registry_file.read_text(encoding="utf-8")
    if "PUBLIC_VALUE=worker" in registry_payload:
        raise AssertionError("worker app config file content was written to the app registry")
    if SMOKE_WORKER_APP_SECRET in registry_payload:
        raise AssertionError("worker app secret was written to the app registry")
    apps_page.apps_table.selectRow(1)
    app.processEvents()
    record_step(log, output_path, {"step": "select worker app row"})
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.refresh_button, "refresh worker app status")})
    wait_until(
        app,
        lambda: _table_text(apps_page.apps_table, 1, 2) == "online",
        timeout,
        "worker app status refresh",
    )
    record_step(
        log,
        output_path,
        {
            "step": click_visible_button(app, apps_page.copy_url_button, "copy worker app URL"),
            "clipboard": app.clipboard().text(),
        },
    )
    if app.clipboard().text() != "https://smoke-war.example.test":
        raise AssertionError("worker app URL copy used an unexpected value")
    record_step(log, output_path, {"step": click_visible_button(app, apps_page.stop_button, "stop worker app")})
    wait_until(
        app,
        lambda: _table_text(apps_page.apps_table, 1, 2) == "stopped",
        timeout,
        "worker app stop",
    )
    scroll_apps_workspace_to(launcher, "top")
    app.processEvents()
    final_visual = capture_visual_evidence(launcher, screenshot_dir, "apps_mocked_final")
    record_step(
        log,
        output_path,
        {
            "step": "mocked SDK app E2E completed",
            "table": app_table_snapshot(apps_page),
            "visual": final_visual,
            "preflight_calls": list(fake_preflight.calls),
            "events": list(fake_sdk_client.events),
            "registry_path": str(app_registry.registry_file),
        },
    )


def run_scenarios(args):
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))

    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication

    import app_forms.frm_main as frm_main
    import widgets.app_widgets.sidebar_panel as sidebar_panel
    from services.app_registry import AppRegistry
    from utils.config_manager import ConfigManager, ContainerConfig
    from widgets.dialogs.AuthorizedAddressedDialog import AuthorizedAddressesDialog
    from widgets.dialogs.DockerCheckDialog import DockerCheckDialog
    from widgets.DockerPullDialog import DockerPullDialog
    from widgets.LoadingDialog import LoadingDialog

    log = {
        "started_at": datetime.now().isoformat(),
        "destructive": False,
        "containers": [SMOKE_CONTAINER, SMOKE_SECONDARY_CONTAINER],
        "volumes": [SMOKE_VOLUME, SMOKE_SECONDARY_VOLUME],
        "screenshot_dir": args.screenshot_dir,
        "steps": [],
    }
    write_log(log, args.output)
    patch_message_boxes(log, args.output)
    restore_browser = install_browser_recorder(log)

    temp_root = Path(tempfile.mkdtemp(prefix="r1-launcher-smoke-"))
    app_registry = AppRegistry(temp_root / "sdk-apps" / "apps.json")
    fake_sdk_client = FakeSdkDeploymentClient()
    fake_preflight = FakeAppLaunchPreflight()
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
    config_manager.add_container(
        ContainerConfig(
            name=SMOKE_SECONDARY_CONTAINER,
            volume=SMOKE_SECONDARY_VOLUME,
            node_address="0xsmokenode2",
            eth_address="0xsmokeeth2",
            node_alias="smoke-secondary",
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
    sidebar_panel.AppRegistry = lambda: app_registry
    sidebar_panel.Ratio1SdkDeploymentClient = lambda app_registry=None: fake_sdk_client
    sidebar_panel.SdkIdentityService = lambda: FakeSdkIdentityService()

    app = QApplication.instance() or QApplication(sys.argv)
    launcher = frm_main.EdgeNodeLauncher()
    launcher.apps_page.set_launch_preflight_service(fake_preflight)
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
        shown_window = window_snapshot(launcher)
        record_step(log, args.output, {"step": "window shown", "window": shown_window})
        assert_title_bar_visible(shown_window)
        startup_visual = capture_visual_evidence(launcher, args.screenshot_dir, "startup")
        record_step(log, args.output, {"step": "captured startup visual evidence", "visual": startup_visual})
        if not startup_visual["sidebar"]["passed"]:
            raise AssertionError("; ".join(startup_visual["sidebar"]["issues"]))

        original_sidebar_scroll = scroll_sidebar_to(launcher, "bottom")
        app.processEvents()
        sidebar_bottom_visual = capture_visual_evidence(launcher, args.screenshot_dir, "sidebar_bottom")
        record_step(
            log,
            args.output,
            {"step": "captured lower sidebar visual evidence", "visual": sidebar_bottom_visual},
        )
        if not sidebar_bottom_visual["sidebar"]["passed"]:
            raise AssertionError("; ".join(sidebar_bottom_visual["sidebar"]["issues"]))
        scroll_sidebar_to(launcher, original_sidebar_scroll)
        app.processEvents()

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

        record_step(
            log,
            args.output,
            {
                "step": "captured dark node selector popup visual evidence",
                "visual": capture_combo_popup_visual_evidence(
                    app,
                    launcher.container_combo,
                    args.screenshot_dir,
                    "dark_node_selector",
                ),
            },
        )

        launcher.setMinimumSize(original_minimum_size)
        launcher.resize(1600, 900)
        app.processEvents()

        for page_name in ("apps", "logs", "docker", "settings", "network", "nodes"):
            if getattr(launcher, "toast", None) is not None:
                launcher.toast.hide()
            show_launcher_page(app, launcher, page_name)
            page_visual = capture_visual_evidence(
                launcher,
                args.screenshot_dir,
                f"nav_{page_name}_page",
            )
            record_step(
                log,
                args.output,
                {
                    "step": f"captured {page_name} navigation page visual evidence",
                    "visual": page_visual,
                },
            )
            if not page_visual["sidebar"]["passed"]:
                raise AssertionError("; ".join(page_visual["sidebar"]["issues"]))

        run_mocked_sdk_apps_scenario(
            app,
            launcher,
            log,
            args.output,
            args.screenshot_dir,
            args.timeout,
            fake_sdk_client,
            fake_preflight,
            app_registry,
        )

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

        docker_pull_dialog = DockerPullDialog(launcher)
        docker_pull_dialog.update_pull_progress("ratio1/edge_node: Pulling from ratio1/edge_node")
        docker_pull_dialog.update_pull_progress("abcdef123456: Downloading 50%")
        docker_pull_dialog.update_pull_progress("123456abcdef: Pull complete")
        show_and_capture_dialog(
            app,
            docker_pull_dialog,
            log,
            args.output,
            args.screenshot_dir,
            "docker_pull_progress",
        )

        saved_authorized_payloads = []
        authorized_dialog = AuthorizedAddressesDialog(launcher, on_save_callback=saved_authorized_payloads.append)
        authorized_dialog.load_data(
            [
                {
                    "address": "0x1234567890abcdef1234567890abcdef12345678",
                    "alias": "smoke-admin",
                }
            ]
        )
        authorized_dialog.show()
        app.processEvents()
        authorized_visual = capture_dialog_visual_evidence(
            authorized_dialog,
            args.screenshot_dir,
            "authorized_addresses",
        )
        authorized_dialog_rect = authorized_visual["dialog"]["rect"]
        authorized_button_heights = {
            button["object_name"]: button["rect"]["h"]
            for button in authorized_visual["dialog"]["buttons"]
        }
        expected_authorized_heights = {
            "authorizedAddressCopyAddressButton": 44,
            "authorizedAddressCopyAliasButton": 44,
            "authorizedAddressDeleteButton": 44,
            "authorizedAddressAddButton": 52,
            "authorizedAddressSaveButton": 52,
            "authorizedAddressCloseButton": 52,
        }
        for object_name, expected_height in expected_authorized_heights.items():
            actual_height = authorized_button_heights.get(object_name)
            if actual_height != expected_height:
                raise AssertionError(
                    f"{object_name} rendered at {actual_height}px, expected {expected_height}px"
                )
        for button in authorized_visual["dialog"]["buttons"]:
            if button["visible"] and button["rect"]["right"] > authorized_dialog_rect["right"]:
                raise AssertionError(f"{button['object_name']} exceeds authorized dialog right edge")
        record_step(
            log,
            args.output,
            {
                "step": "captured authorized addresses dialog visual evidence",
                "visual": authorized_visual,
            },
        )
        expected_authorized_address = "0x1234567890abcdef1234567890abcdef12345678"
        expected_authorized_alias = "smoke-admin"
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(
                    app,
                    authorized_dialog.rows[0].copy_addr_btn,
                    "copy authorized address",
                ),
                "clipboard": app.clipboard().text(),
            },
        )
        if app.clipboard().text() != expected_authorized_address:
            raise AssertionError("authorized address copy did not preserve the raw address")
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(
                    app,
                    authorized_dialog.rows[0].copy_alias_btn,
                    "copy authorized alias",
                ),
                "clipboard": app.clipboard().text(),
            },
        )
        if app.clipboard().text() != expected_authorized_alias:
            raise AssertionError("authorized alias copy did not preserve the raw alias")
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(
                    app,
                    authorized_dialog.add_btn,
                    "add authorized address row",
                ),
                "row_count": len(authorized_dialog.rows),
            },
        )
        if len(authorized_dialog.rows) != 2:
            raise AssertionError("authorized add action did not create a second row")
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(
                    app,
                    authorized_dialog.rows[-1].delete_btn,
                    "remove blank authorized address row",
                ),
                "row_count": len(authorized_dialog.rows),
            },
        )
        if len(authorized_dialog.rows) != 1:
            raise AssertionError("authorized remove action did not remove the blank row")
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(
                    app,
                    authorized_dialog.save_btn,
                    "save authorized addresses",
                ),
                "saved_payloads": saved_authorized_payloads,
                "dialog_visible": authorized_dialog.isVisible(),
            },
        )
        expected_payload = f"{expected_authorized_address} {expected_authorized_alias}"
        if saved_authorized_payloads != [expected_payload]:
            raise AssertionError("authorized save action produced an unexpected payload")
        if authorized_dialog.isVisible():
            raise AssertionError("authorized save action did not close the dialog")

        def open_and_cancel_rename_dialog(label, click_step):
            original_running_check = launcher.is_container_running
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
                        "step": f"captured {label.replace('_', ' ')} dialog visual evidence",
                        "visual": capture_dialog_visual_evidence(dialog, args.screenshot_dir, label),
                    },
                )
                click_dialog_button(app, dialog, "renameNodeCancelButton")

            try:
                QTimer.singleShot(100, capture_and_cancel_rename_dialog)
                record_step(log, args.output, {"step": click_button(app, launcher.renameNodeButton, click_step)})
            finally:
                launcher.is_container_running = original_running_check

        show_launcher_page(app, launcher, "settings")
        record_step(log, args.output, {"step": "show settings page"})
        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle light theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.DARK_DASHBOARD_BUTTON_TEXT, args.timeout, "light theme")
        light_visual = capture_visual_evidence(launcher, args.screenshot_dir, "light_theme")
        record_step(log, args.output, {"step": "captured light theme visual evidence", "visual": light_visual})
        if not light_visual["sidebar"]["passed"]:
            raise AssertionError("; ".join(light_visual["sidebar"]["issues"]))

        original_light_sidebar_scroll = scroll_sidebar_to(launcher, "bottom")
        app.processEvents()
        light_sidebar_bottom_visual = capture_visual_evidence(
            launcher,
            args.screenshot_dir,
            "light_sidebar_bottom",
        )
        record_step(
            log,
            args.output,
            {"step": "captured light lower-sidebar visual evidence", "visual": light_sidebar_bottom_visual},
        )
        if not light_sidebar_bottom_visual["sidebar"]["passed"]:
            raise AssertionError("; ".join(light_sidebar_bottom_visual["sidebar"]["issues"]))
        scroll_sidebar_to(launcher, original_light_sidebar_scroll)
        app.processEvents()

        record_step(
            log,
            args.output,
            {
                "step": "captured light node selector popup visual evidence",
                "visual": capture_combo_popup_visual_evidence(
                    app,
                    launcher.container_combo,
                    args.screenshot_dir,
                    "light_node_selector",
                ),
            },
        )

        show_launcher_page(app, launcher, "nodes")
        record_step(log, args.output, {"step": "show nodes page"})
        open_and_cancel_rename_dialog("light_rename_node", "open and cancel light rename dialog")
        show_launcher_page(app, launcher, "settings")
        record_step(log, args.output, {"step": "show settings page"})
        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle dark theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.LIGHT_DASHBOARD_BUTTON_TEXT, args.timeout, "dark theme")

        show_launcher_page(app, launcher, "nodes")
        record_step(log, args.output, {"step": "show nodes page"})
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
        show_launcher_page(app, launcher, "settings")
        record_step(log, args.output, {"step": "show settings page"})
        record_step(log, args.output, {"step": click_button(app, launcher.force_debug_checkbox, "toggle force debug")})
        show_launcher_page(app, launcher, "network")
        record_step(log, args.output, {"step": "show network page"})
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
        show_launcher_page(app, launcher, "docker")
        record_step(log, args.output, {"step": "show docker page"})
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

        show_launcher_page(app, launcher, "nodes")
        record_step(log, args.output, {"step": "show nodes page"})
        QTimer.singleShot(100, capture_and_cancel_add_node_dialog)
        record_step(log, args.output, {"step": click_button(app, launcher.add_node_button, "open and cancel add node dialog")})

        open_and_cancel_rename_dialog("rename_node", "open and cancel rename dialog")

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
        activity_log_text = launcher.logView.toPlainText()
        record_step(
            log,
            args.output,
            {
                "step": click_visible_button(app, launcher.activity_log_copy_button, "copy activity log"),
                "clipboard_matches_log": app.clipboard().text() == activity_log_text,
            },
        )
        record_step(log, args.output, {"step": click_visible_button(app, launcher.activity_log_clear_button, "clear activity log")})
        wait_until(
            app,
            lambda: launcher.logView.toPlainText() == "" and not launcher.activity_log_clear_button.isEnabled(),
            args.timeout,
            "activity log cleared",
        )
        record_step(
            log,
            args.output,
            {
                "step": "activity log cleared",
                "copy_enabled": launcher.activity_log_copy_button.isEnabled(),
                "clear_enabled": launcher.activity_log_clear_button.isEnabled(),
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
    prepare_evidence_paths(args)
    log = run_scenarios(args)
    if log.get("result") != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
