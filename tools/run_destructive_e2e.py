"""Visible destructive launcher scenarios.

This runner is intentionally not part of the default pytest suite. It drives the
real PyQt launcher visibly, uses real Docker for container/image operations, and
cleans up its own e2e containers afterward.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_CONTAINER = "r1nodee2e"
SECOND_CONTAINER = "r1nodee2e2"
PRIMARY_VOLUME = "r1vole2e"
SECOND_VOLUME = "r1vole2e2"
DEFAULT_DOCKER_IMAGE = "ratio1/edge_node:mainnet"
DEFAULT_STARTUP_TEMPLATE = REPO_ROOT.parent / "edge_node" / ".config_startup.json"
RENAME_DIALOG_TITLES = ("Rename Node", "Change Node Name")


def run_command(command, timeout=120, check=False):
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": -1,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            "timed_out": True,
            "timeout": timeout,
        }
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "timed_out": False,
    }


def write_log(log, output_path):
    if output_path:
        Path(output_path).write_text(json.dumps(log, indent=2), encoding="utf-8")


def record_step(log, output_path, step):
    log["steps"].append(step)
    write_log(log, output_path)
    print(f"E2E_STEP: {step}", flush=True)


def collect_container_diagnostics(container_name):
    return {
        "state": run_command(
            ["docker", "inspect", container_name, "--format", "{{json .State}}"],
            timeout=30,
        ),
        "logs_tail": run_command(["docker", "logs", "--tail", "120", container_name], timeout=60),
    }


def visible_dialog_titles(app):
    from PyQt5.QtWidgets import QDialog

    return [
        widget.windowTitle()
        for widget in app.topLevelWidgets()
        if isinstance(widget, QDialog) and widget.isVisible()
    ]


def visible_dialog_details(app):
    from PyQt5.QtWidgets import QDialog, QLabel, QProgressBar

    details = []
    for widget in app.topLevelWidgets():
        if not isinstance(widget, QDialog) or not widget.isVisible():
            continue

        labels = [
            label.text()
            for label in widget.findChildren(QLabel)
            if label.text()
        ]
        progress = [
            {
                "object_name": progress_bar.objectName(),
                "value": progress_bar.value(),
                "minimum": progress_bar.minimum(),
                "maximum": progress_bar.maximum(),
            }
            for progress_bar in widget.findChildren(QProgressBar)
        ]
        details.append(
            {
                "class": type(widget).__name__,
                "title": widget.windowTitle(),
                "labels": labels,
                "progress": progress,
            }
        )
    return details


def launcher_log_tail(launcher, max_chars=5000):
    if getattr(launcher, "logView", None) is not None:
        text = launcher.logView.toPlainText()
    else:
        text = "\n".join(getattr(launcher, "log_buffer", []))
    return text[-max_chars:]


def collect_launcher_diagnostics(app, launcher, containers):
    current_index = launcher.container_combo.currentIndex()
    current_container = launcher.container_combo.itemData(current_index) if current_index >= 0 else None
    return {
        "visible_dialogs": visible_dialog_titles(app),
        "dialog_details": visible_dialog_details(app),
        "current_container": current_container,
        "toggle_text": launcher.toggleButton.text(),
        "lifecycle_operation": getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation", None),
        "docker_pull_in_progress": getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress", None),
        "pending_launch_context": getattr(launcher, "_EdgeNodeLauncher__pending_launch_context", None),
        "launcher_log_tail": launcher_log_tail(launcher),
        "containers": {
            container_name: collect_container_diagnostics(container_name)
            for container_name in containers
        },
    }


def launcher_failure_message(launcher):
    log_tail = launcher_log_tail(launcher).lower()
    fatal_markers = [
        "failed to launch container",
        "error launching container",
        "docker image pull failed",
        "error pulling docker image",
        "docker pull completed without a pending launch target",
        "unexpected keyword argument",
        "traceback",
    ]
    for marker in fatal_markers:
        if marker in log_tail:
            return marker
    return None


def launch_progress_signature(app, launcher, container_name):
    current_index = launcher.container_combo.currentIndex()
    current_container = launcher.container_combo.itemData(current_index) if current_index >= 0 else None
    log_text = launcher_log_tail(launcher, max_chars=1000)
    return {
        "container": container_name,
        "docker_exists": docker_exists(container_name),
        "docker_running": docker_running(container_name),
        "visible_dialogs": visible_dialog_details(app),
        "log_length": len(log_text),
        "log_tail": log_text[-300:],
        "current_container": current_container,
        "toggle_text": launcher.toggleButton.text(),
        "lifecycle_operation": getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation", None),
        "docker_pull_in_progress": getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress", None),
        "pending_launch_context": getattr(launcher, "_EdgeNodeLauncher__pending_launch_context", None),
    }


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


def cleanup_resources(log, include_primary_r1node=False):
    containers = [PRIMARY_CONTAINER, SECOND_CONTAINER]
    if include_primary_r1node:
        containers.append("r1node")

    for container in containers:
        log["cleanup"].append(run_command(["docker", "rm", "-f", container], timeout=120))

    for volume in [PRIMARY_VOLUME, SECOND_VOLUME]:
        log["cleanup"].append(run_command(["docker", "volume", "rm", "-f", volume], timeout=120))


def remove_launcher_image(log, image):
    log["setup"].append(run_command(["docker", "image", "rm", "-f", image], timeout=600))


def docker_running(container_name):
    result = run_command(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        timeout=30,
    )
    return result["returncode"] == 0 and result["stdout"].strip().lower() == "true"


def docker_exists(container_name):
    result = run_command(
        ["docker", "inspect", "-f", "{{.Name}}", container_name],
        timeout=30,
    )
    return result["returncode"] == 0


def wait_until(app, predicate, timeout, label, interval=0.5):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        app.processEvents()
        try:
            if predicate():
                return
        except Exception as exc:
            last_error = exc
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {label}: {last_error}")


def wait_for_launch_activity(app, launcher, log, output_path, timeout, label):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        failure_marker = launcher_failure_message(launcher)
        if failure_marker:
            log["result"] = "failed_launcher_error"
            log["error"] = f"Launcher reported {failure_marker} while waiting for {label}"
            log["diagnostics"] = collect_launcher_diagnostics(app, launcher, [PRIMARY_CONTAINER, SECOND_CONTAINER])
            write_log(log, output_path)
            raise RuntimeError(log["error"])

        if (
            docker_running(PRIMARY_CONTAINER)
            or docker_running(SECOND_CONTAINER)
            or visible_dialog_titles(app)
            or getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress", False)
            or getattr(launcher, "_EdgeNodeLauncher__pending_launch_context", None)
        ):
            record_step(
                log,
                output_path,
                {
                    "step": "launch activity observed",
                    "label": label,
                    "visible_dialogs": visible_dialog_titles(app),
                    "docker_pull_in_progress": getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress", None),
                    "pending_launch_context": getattr(launcher, "_EdgeNodeLauncher__pending_launch_context", None),
                },
            )
            return
        time.sleep(0.25)

    log["result"] = "failed_no_launch_activity"
    log["error"] = f"No launch activity observed while waiting for {label}"
    log["diagnostics"] = collect_launcher_diagnostics(app, launcher, [PRIMARY_CONTAINER, SECOND_CONTAINER])
    write_log(log, output_path)
    raise TimeoutError(log["error"])


def wait_for_container_running(app, launcher, log, output_path, container_name, timeout, label, stall_timeout=120):
    deadline = time.monotonic() + timeout
    started_at = time.monotonic()
    last_progress_at = time.monotonic()
    next_heartbeat = started_at + 15
    last_signature = launch_progress_signature(app, launcher, container_name)

    while time.monotonic() < deadline:
        app.processEvents()
        if docker_running(container_name):
            return

        failure_marker = launcher_failure_message(launcher)
        if failure_marker:
            log["result"] = "failed_launcher_error"
            log["error"] = f"Launcher reported {failure_marker} while waiting for {label}"
            log["diagnostics"] = collect_launcher_diagnostics(app, launcher, [PRIMARY_CONTAINER, SECOND_CONTAINER])
            write_log(log, output_path)
            raise RuntimeError(log["error"])

        signature = launch_progress_signature(app, launcher, container_name)
        if signature != last_signature:
            last_progress_at = time.monotonic()
            last_signature = signature

        if time.monotonic() >= next_heartbeat:
            record_step(
                log,
                output_path,
                {
                    "step": "waiting for container",
                    "label": label,
                    "container": container_name,
                    "elapsed_seconds": round(time.monotonic() - started_at, 1),
                    "visible_dialogs": signature["visible_dialogs"],
                    "lifecycle_operation": signature["lifecycle_operation"],
                    "docker_exists": signature["docker_exists"],
                    "docker_running": signature["docker_running"],
                },
            )
            next_heartbeat = time.monotonic() + 15

        if time.monotonic() - last_progress_at > stall_timeout:
            log["result"] = "failed_stale_main_window"
            log["error"] = f"No visible launcher progress while waiting for {label}"
            log["diagnostics"] = collect_launcher_diagnostics(app, launcher, [PRIMARY_CONTAINER, SECOND_CONTAINER])
            write_log(log, output_path)
            raise TimeoutError(log["error"])

        time.sleep(0.5)

    log["result"] = "failed_timeout"
    log["error"] = f"Timed out waiting for {label}"
    log["diagnostics"] = collect_launcher_diagnostics(app, launcher, [PRIMARY_CONTAINER, SECOND_CONTAINER])
    write_log(log, output_path)
    raise TimeoutError(log["error"])


def wait_for_stable_container(app, container_name, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if not docker_running(container_name):
            return False
        time.sleep(1)
    return True


def click_button(app, button, label):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest

    button.setFocus()
    QTest.mouseClick(button, Qt.LeftButton)
    app.processEvents()
    return label


def find_dialog(app, title):
    from PyQt5.QtWidgets import QDialog

    titles = (title,) if isinstance(title, str) else tuple(title)
    for widget in app.topLevelWidgets():
        if (
            isinstance(widget, QDialog)
            and widget.isVisible()
            and any(candidate in widget.windowTitle() for candidate in titles)
        ):
            return widget
    return None


def click_dialog_button(app, dialog, object_name=None, title=None):
    from PyQt5.QtWidgets import QPushButton

    button = None
    if object_name:
        button = dialog.findChild(QPushButton, object_name)
    if button is None and title:
        for candidate in dialog.findChildren(QPushButton):
            if candidate.text() == title:
                button = candidate
                break
    if button is None:
        raise AssertionError(f"Could not find dialog button object={object_name!r} title={title!r}")
    click_button(app, button, button.objectName() or button.text())


def wait_for_node_command(container_name, timeout=300):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = run_command(["docker", "exec", container_name, "get_node_info"], timeout=45)
        if last["returncode"] == 0 and last["stdout"]:
            return last
        if not docker_running(container_name):
            return last
        time.sleep(5)
    return last


def build_startup_config(template_path, node_alias):
    if template_path and Path(template_path).exists():
        data = json.loads(Path(template_path).read_text(encoding="utf-8"))
    else:
        data = {
            "EE_ID": node_alias,
            "SECURED": True,
            "RESET_ADMIN_PIPELINE": True,
            "CONFIG_RETRIEVE": [
                {
                    "TYPE": "local",
                    "APP_CONFIG_ENDPOINT": "./.config_app.json",
                }
            ],
        }

    data["EE_ID"] = node_alias
    data["WORK_OFFLINE"] = True
    data.setdefault("COMMUNICATION_ENVIRONMENT", {})
    data["COMMUNICATION_ENVIRONMENT"]["CONN_MAX_RETRY_ITERS"] = 1
    return json.dumps(data, separators=(",", ":"))


def run_scenarios(args):
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))

    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication, QLineEdit

    import app_forms.frm_main as frm_main
    import utils.docker_commands as docker_commands
    import utils.docker as docker_mixin
    from utils.config_manager import ConfigManager, ContainerConfig

    log = {
        "started_at": datetime.now().isoformat(),
        "destructive": True,
        "containers": [PRIMARY_CONTAINER, SECOND_CONTAINER],
        "volumes": [PRIMARY_VOLUME, SECOND_VOLUME],
        "image": args.image,
        "image_removed_for_loader": args.remove_image,
        "offline_config": args.offline_config,
        "startup_template": str(args.startup_template),
        "setup": [],
        "steps": [],
        "cleanup": [],
    }

    cleanup_resources(log, include_primary_r1node=args.cleanup_existing_r1node)
    if args.remove_image:
        remove_launcher_image(log, args.image)

    patch_message_boxes(log, args.output)

    temp_root = Path(tempfile.mkdtemp(prefix="r1-launcher-e2e-"))
    runtime_home = temp_root / "runtime-home"
    runtime_home.mkdir(parents=True, exist_ok=True)
    config_manager = ConfigManager(str(temp_root / "config"))
    config_manager.add_container(
        ContainerConfig(
            name=PRIMARY_CONTAINER,
            volume=PRIMARY_VOLUME,
            node_alias="e2e-primary",
        )
    )

    frm_main.DOCKER_CONTAINER_NAME = PRIMARY_CONTAINER
    docker_commands.DOCKER_IMAGE = args.image
    original_get_launch_command = docker_commands.DockerCommandHandler.get_launch_command

    def get_launch_command_with_e2e_config(self, volume_name=None, *extra_args, **kwargs):
        command = original_get_launch_command(self, volume_name, *extra_args, **kwargs)
        if args.offline_config:
            target_container_name = kwargs.get("container_name", self.container_name)
            node_alias = "e2e-primary" if target_container_name == PRIMARY_CONTAINER else "e2e-second"
            startup_json = build_startup_config(args.startup_template, node_alias)
            image_index = len(command) - 1
            command[image_index:image_index] = [
                "-e",
                f"EE_CONFIG={startup_json}",
                "-e",
                f"EE_ID={node_alias}",
            ]
        return command

    docker_commands.DockerCommandHandler.get_launch_command = get_launch_command_with_e2e_config
    frm_main.generate_container_name = lambda prefix="r1node": SECOND_CONTAINER
    frm_main.get_volume_name = lambda container_name: {
        PRIMARY_CONTAINER: PRIMARY_VOLUME,
        SECOND_CONTAINER: SECOND_VOLUME,
    }.get(container_name, f"volume_{container_name}")
    frm_main.ConfigManager = lambda: config_manager
    docker_mixin.DOCKER_CONTAINER_NAME = PRIMARY_CONTAINER
    docker_mixin.get_user_folder = lambda: runtime_home

    app = QApplication.instance() or QApplication(sys.argv)
    launcher = frm_main.EdgeNodeLauncher()
    launcher.check_ram_for_new_node = lambda existing_node_count=0: {
        "can_add_node": True,
        "total_ram_gb": 256.0,
        "max_nodes_supported": 16,
        "current_node_count": existing_node_count,
        "min_required_gb": frm_main.MIN_NODE_RAM_GB,
    }
    launcher.show()
    if hasattr(launcher, "timer") and launcher.timer is not None:
        launcher.timer.stop()
    app.processEvents()

    try:
        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle light theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.DARK_DASHBOARD_BUTTON_TEXT, 10, "light theme")
        record_step(log, args.output, {"step": click_button(app, launcher.themeToggleButton, "toggle dark theme")})
        wait_until(app, lambda: launcher.themeToggleButton.text() == frm_main.LIGHT_DASHBOARD_BUTTON_TEXT, 10, "dark theme")

        record_step(log, args.output, {"step": click_button(app, launcher.toggleButton, "start primary container")})
        wait_for_launch_activity(
            app,
            launcher,
            log,
            args.output,
            45,
            "primary launch activity",
        )
        wait_for_container_running(
            app,
            launcher,
            log,
            args.output,
            PRIMARY_CONTAINER,
            args.launch_timeout,
            "primary container running",
            stall_timeout=args.ui_stall_timeout,
        )
        record_step(log, args.output, {"step": "primary container running", "container": PRIMARY_CONTAINER})

        node_info_result = wait_for_node_command(PRIMARY_CONTAINER, timeout=args.node_ready_timeout)
        record_step(
            log,
            args.output,
            {
                "step": "primary get_node_info readiness probe",
                "returncode": node_info_result["returncode"] if node_info_result else None,
                "stdout_tail": (node_info_result["stdout"] or "")[-500:] if node_info_result else "",
                "stderr_tail": (node_info_result["stderr"] or "")[-500:] if node_info_result else "",
            },
        )
        if not wait_for_stable_container(app, PRIMARY_CONTAINER, args.stability_window):
            log["result"] = "blocked_runtime_exited"
            log["diagnostics"] = {
                PRIMARY_CONTAINER: collect_container_diagnostics(PRIMARY_CONTAINER),
            }
            write_log(log, args.output)
            return log
        if not node_info_result or node_info_result["returncode"] != 0:
            record_step(
                log,
                args.output,
                {
                    "step": "node info unavailable but container remained stable",
                    "mode": "container-command scenario",
                },
            )
        record_step(
            log,
            args.output,
            {
                "step": "primary container remained stable",
                "seconds": args.stability_window,
            },
        )

        rename_state = {"forced_close": False, "error": None}
        rename_deadline = time.monotonic() + args.rename_timeout

        def save_rename_dialog():
            dialog = find_dialog(app, RENAME_DIALOG_TITLES)
            if dialog is None:
                if time.monotonic() >= rename_deadline:
                    rename_state["forced_close"] = True
                    rename_state["error"] = "Rename dialog was not found before timeout"
                    return
                QTimer.singleShot(250, save_rename_dialog)
                return
            name_input = dialog.findChild(QLineEdit, "renameNodeNameInput") or dialog.findChild(QLineEdit)
            if name_input is None:
                rename_state["forced_close"] = True
                rename_state["error"] = "Rename dialog has no text input"
                dialog.reject()
                return
            name_input.setText("e2e-renamed")
            click_dialog_button(app, dialog, object_name="renameNodeSaveButton")

        def abort_rename_dialog():
            dialog = find_dialog(app, RENAME_DIALOG_TITLES)
            if dialog is not None:
                rename_state["forced_close"] = True
                rename_state["error"] = "Rename dialog timed out"
                dialog.reject()

        QTimer.singleShot(300, save_rename_dialog)
        QTimer.singleShot(args.rename_timeout * 1000, abort_rename_dialog)
        record_step(log, args.output, {"step": "open rename primary node dialog"})
        click_button(app, launcher.renameNodeButton, "rename primary node")
        record_step(
            log,
            args.output,
            {
                "step": "rename dialog returned",
                "forced_close": rename_state["forced_close"],
                "error": rename_state["error"],
            },
        )
        if rename_state["forced_close"]:
            log["result"] = "blocked_rename_dialog_timeout"
            log["error"] = rename_state["error"] or "Rename dialog was closed by timeout guard"
            log["diagnostics"] = collect_launcher_diagnostics(app, launcher, [PRIMARY_CONTAINER, SECOND_CONTAINER])
            write_log(log, args.output)
            return log
        wait_until(app, lambda: not docker_running(PRIMARY_CONTAINER), args.rename_timeout, "primary stopped during rename restart")
        wait_for_container_running(
            app,
            launcher,
            log,
            args.output,
            PRIMARY_CONTAINER,
            args.launch_timeout,
            "primary running after rename",
            stall_timeout=args.ui_stall_timeout,
        )
        record_step(log, args.output, {"step": "rename flow completed"})

        record_step(log, args.output, {"step": click_button(app, launcher.toggleButton, "stop primary container")})
        wait_until(app, lambda: docker_exists(PRIMARY_CONTAINER) and not docker_running(PRIMARY_CONTAINER), 180, "primary stopped")
        record_step(log, args.output, {"step": "primary container stopped"})

        record_step(log, args.output, {"step": click_button(app, launcher.toggleButton, "restart primary container")})
        wait_for_container_running(
            app,
            launcher,
            log,
            args.output,
            PRIMARY_CONTAINER,
            args.launch_timeout,
            "primary restarted",
            stall_timeout=args.ui_stall_timeout,
        )
        record_step(log, args.output, {"step": "primary container restarted"})

        def create_add_node_dialog():
            dialog = find_dialog(app, "Add New Node")
            if dialog is None:
                QTimer.singleShot(250, create_add_node_dialog)
                return
            click_dialog_button(app, dialog, object_name="createNodeConfirmButton")

        QTimer.singleShot(300, create_add_node_dialog)
        record_step(log, args.output, {"step": "open create second node dialog"})
        click_button(app, launcher.add_node_button, "create second node")
        record_step(log, args.output, {"step": "create second node dialog returned"})
        wait_for_container_running(
            app,
            launcher,
            log,
            args.output,
            SECOND_CONTAINER,
            args.launch_timeout,
            "second container running",
            stall_timeout=args.ui_stall_timeout,
        )
        record_step(log, args.output, {"step": "second container running", "container": SECOND_CONTAINER})

        log["result"] = "passed"
        return log
    except Exception as exc:
        if "result" not in log:
            log["result"] = "failed"
        if "error" not in log:
            log["error"] = str(exc)
        raise
    finally:
        try:
            launcher.close()
            app.processEvents()
        finally:
            if args.cleanup:
                cleanup_resources(log)
            log["finished_at"] = datetime.now().isoformat()
            write_log(log, args.output)
            print(json.dumps(log, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Run visible destructive launcher E2E scenarios.")
    parser.add_argument("--remove-image", action="store_true", help="Remove the launcher Docker image before starting.")
    parser.add_argument("--image", default=DEFAULT_DOCKER_IMAGE, help="Docker image to pull and run.")
    parser.add_argument(
        "--offline-config",
        action="store_true",
        default=True,
        help="Inject an E2E startup config with WORK_OFFLINE=true into launched containers.",
    )
    parser.add_argument(
        "--no-offline-config",
        action="store_false",
        dest="offline_config",
        help="Run with the image's default startup configuration.",
    )
    parser.add_argument("--startup-template", default=str(DEFAULT_STARTUP_TEMPLATE))
    parser.add_argument("--cleanup", action="store_true", default=True, help="Remove e2e containers and volumes afterward.")
    parser.add_argument("--no-cleanup", action="store_false", dest="cleanup", help="Leave e2e containers and volumes.")
    parser.add_argument(
        "--cleanup-existing-r1node",
        action="store_true",
        help="Also remove an existing r1node container before the run. Use only for manual recovery.",
    )
    parser.add_argument("--launch-timeout", type=int, default=900)
    parser.add_argument("--rename-timeout", type=int, default=360)
    parser.add_argument("--node-ready-timeout", type=int, default=300)
    parser.add_argument("--stability-window", type=int, default=20)
    parser.add_argument("--ui-stall-timeout", type=int, default=120)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    log = run_scenarios(args)
    if log.get("result") != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
