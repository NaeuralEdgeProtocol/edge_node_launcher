"""Optional real devnet SDK app deployment E2E.

This runner is intentionally guarded. It does not execute real SDK deployment
unless R1_LAUNCHER_REAL_SDK_E2E=1 and a real node address/container are
provided. The default smoke runner remains fully mocked and safe for CI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2e_paths import prepare_evidence_paths, write_json_log
from tools.run_smoke_e2e import (
    app_table_snapshot,
    click_visible_button,
    save_widget_screenshot,
    secret_line_edit_snapshot,
    set_line_edit_value,
    set_plain_text_value,
    wait_until,
)


REAL_E2E_FLAG = "R1_LAUNCHER_REAL_SDK_E2E"
REAL_NODE_ADDRESS_ENV = "R1_LAUNCHER_REAL_NODE_ADDRESS"
REAL_NODE_CONTAINER_ENV = "R1_LAUNCHER_REAL_NODE_CONTAINER"
REAL_WAR_REPO_ENV = "R1_LAUNCHER_REAL_WAR_REPO"
REAL_CAR_IMAGE_ENV = "R1_LAUNCHER_REAL_CAR_IMAGE"
REAL_GITHUB_TOKEN_ENV = "R1_LAUNCHER_REAL_GITHUB_TOKEN"
REAL_REGISTRY_PASSWORD_ENV = "R1_LAUNCHER_REAL_REGISTRY_PASSWORD"

REQUIRED_REAL_ENV = (REAL_E2E_FLAG, REAL_NODE_ADDRESS_ENV, REAL_NODE_CONTAINER_ENV)
DEFAULT_SDK_LOG_DIR = Path.home() / ".ratio1" / "edge_node_launcher" / "sdk" / "_logs"
PEM_PATH_RE = re.compile(r"(?:[A-Za-z]:)?[\\/][^\s\"']*?\.pem")
PEM_FILENAME_RE = re.compile(r"\b[\w.-]+\.pem\b")


def real_e2e_guard(env: dict[str, str] | None = None) -> dict[str, object]:
    env = env or os.environ
    missing = []
    if env.get(REAL_E2E_FLAG) != "1":
        missing.append(REAL_E2E_FLAG)
    for name in (REAL_NODE_ADDRESS_ENV, REAL_NODE_CONTAINER_ENV):
        if not env.get(name):
            missing.append(name)
    return {
        "enabled": not missing,
        "missing_env": missing,
        "required_env": list(REQUIRED_REAL_ENV),
    }


def validate_real_args(args, env: dict[str, str] | None = None) -> list[str]:
    env = env or os.environ
    issues = []
    if args.app_kind in ("war", "both") and not (args.war_repo or env.get(REAL_WAR_REPO_ENV)):
        issues.append(f"{REAL_WAR_REPO_ENV} or --war-repo is required for WAR real E2E.")
    return issues


def record_step(log, output_path, step):
    log["steps"].append(step)
    write_json_log(log, output_path)
    print(f"REAL_SDK_E2E_STEP: {json.dumps(step, ensure_ascii=True)}", flush=True)


def guarded_skip_log(args, guard, issues=None):
    log = {
        "started_at": datetime.now().isoformat(),
        "result": "skipped",
        "reason": "real SDK E2E guard was not satisfied",
        "guard": guard,
        "issues": issues or [],
        "steps": [],
        "finished_at": datetime.now().isoformat(),
    }
    write_json_log(log, args.output)
    print(json.dumps(log, indent=2))
    return log


def screenshot(page, screenshot_dir, label):
    if not screenshot_dir:
        return ""
    return save_widget_screenshot(page, screenshot_dir, f"{label}.png")


def open_create_dialog(app, page, log, args, opened_create_dialogs, label):
    before = len(opened_create_dialogs)
    record_step(log, args.output, {"step": click_visible_button(app, page.create_app_button, label)})
    if len(opened_create_dialogs) <= before:
        raise AssertionError("Create App did not open the deploy dialog")
    dialog = opened_create_dialogs[-1]
    page._active_create_dialog = dialog
    if not dialog.isVisible():
        dialog.show()
    app.processEvents()
    screenshot_label = re.sub(r"[^a-z0-9_]+", "_", label.lower()).strip("_")
    record_step(
        log,
        args.output,
        {
            "step": f"real {label} dialog opened",
            "screenshot": screenshot(dialog, args.screenshot_dir, f"real_{screenshot_label}"),
        },
    )
    return dialog


def active_worker_snapshot(page) -> dict[str, object]:
    workers = []
    for worker in list(getattr(page, "_active_workers", [])):
        is_running = None
        if hasattr(worker, "isRunning"):
            try:
                is_running = bool(worker.isRunning())
            except RuntimeError:
                is_running = None
        workers.append(
            {
                "operation": getattr(worker, "operation_name", ""),
                "running": is_running,
            }
        )
    running_count = sum(1 for worker in workers if worker["running"] is True)
    return {
        "count": len(workers),
        "running_count": running_count,
        "workers": workers,
    }


def active_secrets(page) -> tuple[str, ...]:
    secrets = []
    for attr_name in ("car_registry_password_input", "worker_github_token_input"):
        widget = getattr(page, attr_name, None)
        if widget is None:
            continue
        try:
            value = widget.text()
        except RuntimeError:
            value = ""
        if value:
            secrets.append(value)
    for env_name in (REAL_REGISTRY_PASSWORD_ENV, REAL_GITHUB_TOKEN_ENV):
        value = os.environ.get(env_name, "")
        if value:
            secrets.append(value)
    return tuple(dict.fromkeys(secrets))


def redact_values(text: str, secrets: tuple[str, ...]) -> str:
    safe_text = str(text)
    for secret in secrets:
        if secret:
            safe_text = safe_text.replace(secret, "<redacted>")
    safe_text = PEM_PATH_RE.sub("<redacted-pem-path>", safe_text)
    safe_text = PEM_FILENAME_RE.sub("<redacted-pem-file>", safe_text)
    return safe_text


def collect_sdk_log_tails(
    *,
    log_dir: Path | str | None,
    since_epoch: float,
    secrets: tuple[str, ...] = (),
    max_files: int = 4,
    max_lines: int = 30,
) -> list[dict[str, object]]:
    if not log_dir:
        return []
    target_dir = Path(log_dir)
    if not target_dir.exists():
        return []

    candidates = []
    for pattern in ("*_error_log.txt", "*_log.txt"):
        candidates.extend(target_dir.glob(pattern))
    unique_candidates = {path.resolve(): path for path in candidates}.values()
    recent = [
        path
        for path in unique_candidates
        if path.is_file() and path.stat().st_mtime >= since_epoch
    ]
    recent.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    tails = []
    for path in recent[:max_files]:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            tails.append({"path": str(path), "error": str(exc)})
            continue
        tail = "\n".join(lines[-max_lines:])
        tails.append(
            {
                "path": str(path),
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "tail": redact_values(tail, secrets),
            }
        )
    return tails


def page_diagnostics(page, screenshot_dir, label, *, sdk_log_dir=None, sdk_log_since_epoch=0.0) -> dict[str, object]:
    secrets = active_secrets(page)
    validation_message = page_message_text(page)
    evidence = {
        "validation_message": redact_values(validation_message, secrets),
        "validation_visible": page_message_visible(page),
        "message": redact_values(validation_message, secrets),
        "table": app_table_snapshot(page),
        "active_workers": active_worker_snapshot(page),
        "screenshot": "",
        "sdk_log_tails": collect_sdk_log_tails(
            log_dir=sdk_log_dir,
            since_epoch=sdk_log_since_epoch,
            secrets=secrets,
        ),
    }
    try:
        evidence["screenshot"] = screenshot(page, screenshot_dir, label)
    except Exception as exc:  # pragma: no cover - evidence must never mask the real failure.
        evidence["screenshot_error"] = str(exc)
    return evidence


def wait_until_page_state(app, page, predicate, timeout, label):
    try:
        wait_until(app, predicate, timeout, label)
    except TimeoutError as exc:
        validation_message = redact_values(page_message_text(page), active_secrets(page))
        workers = active_worker_snapshot(page)
        raise TimeoutError(
            f"{exc}; validation_message={validation_message!r}; active_workers={workers}"
        ) from exc


def page_message_text(page) -> str:
    snapshots = []
    for attr_name in ("validation_message", "management_message"):
        label = getattr(page, attr_name, None)
        if label is None:
            continue
        try:
            visible = bool(label.isVisible()) if hasattr(label, "isVisible") else True
            snapshots.append((visible, label.text()))
        except (AttributeError, RuntimeError):
            snapshots.append((False, "<unavailable>"))
    for visible, text in snapshots:
        if visible and text:
            return text
    for _visible, text in snapshots:
        if text:
            return text
    return ""


def page_message_visible(page) -> bool:
    for attr_name in ("validation_message", "management_message"):
        label = getattr(page, attr_name, None)
        if label is None:
            continue
        try:
            if hasattr(label, "isVisible") and label.isVisible():
                return True
        except RuntimeError:
            continue
    return False


def wait_for_active_workers(app, page, timeout_seconds: float) -> dict[str, object]:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        app.processEvents()
        snapshot = active_worker_snapshot(page)
        if snapshot["running_count"] == 0:
            return snapshot
        time.sleep(0.05)
    app.processEvents()
    return active_worker_snapshot(page)


def size_evidence_page(app, page) -> None:
    width = 760
    height = 900
    screen = app.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        width = min(width, max(page.minimumWidth(), available.width() - 80))
        height = min(height, max(page.minimumHeight(), available.height() - 80))
    page.resize(width, height)


def run_real_e2e(args):
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))

    from PyQt5.QtWidgets import QApplication, QDialog

    from services.app_launch_preflight import AppLaunchPreflightService
    from services.app_registry import AppRegistry
    from services.docker_runtime_service import DockerRuntimeService
    from services.node_allowlist_service import NodeAllowListService
    from services.sdk_deployment_service import Ratio1SdkDeploymentClient
    from services.sdk_identity_service import SdkIdentityService
    from utils.docker_commands import DockerCommandHandler
    from widgets.app_widgets.apps_page import AppsPage, CreateAppDialog

    node_address = os.environ[REAL_NODE_ADDRESS_ENV]
    container_name = os.environ[REAL_NODE_CONTAINER_ENV]
    sdk_log_since_epoch = time.time() - 5
    temp_root = Path(tempfile.mkdtemp(prefix="r1-launcher-real-sdk-e2e-"))
    registry_file = Path(args.registry_file) if args.registry_file else temp_root / "apps.json"
    app_registry = AppRegistry(registry_file)
    deployment_client = Ratio1SdkDeploymentClient(app_registry=None, deploy_timeout=args.deploy_timeout)
    preflight = AppLaunchPreflightService(
        identity_service=SdkIdentityService(),
        allowlist_service=NodeAllowListService(
            DockerRuntimeService(DockerCommandHandler(container_name)),
            timeout=args.preflight_timeout,
        ),
    )

    log = {
        "started_at": datetime.now().isoformat(),
        "result": "running",
        "node_address": node_address,
        "container_name": container_name,
        "app_kind": args.app_kind,
        "registry_file": str(registry_file),
        "steps": [],
    }
    write_json_log(log, args.output)

    app = QApplication.instance() or QApplication(sys.argv)
    opened_create_dialogs = []
    original_create_dialog_exec = CreateAppDialog.exec_

    def nonblocking_create_dialog_exec(dialog):
        opened_create_dialogs.append(dialog)
        dialog.show()
        app.processEvents()
        return QDialog.Rejected

    CreateAppDialog.exec_ = nonblocking_create_dialog_exec
    page = AppsPage(
        app_registry=app_registry,
        deployment_client=deployment_client,
        launch_preflight_service=preflight,
    )
    page.set_target_node(node_address=node_address, container_name=container_name)
    size_evidence_page(app, page)
    page.show()
    app.processEvents()

    try:
        record_step(
            log,
            args.output,
            {
                "step": "real SDK Apps page shown",
                "screenshot": screenshot(page, args.screenshot_dir, "real_sdk_apps_page_initial"),
            },
        )
        if args.app_kind in ("car", "both"):
            _run_real_car(app, page, log, args, opened_create_dialogs)
        if args.app_kind in ("war", "both"):
            _run_real_war(app, page, log, args, opened_create_dialogs)
        log["result"] = "passed"
        return log
    except Exception as exc:
        log["result"] = "failed"
        log["error"] = str(exc)
        record_step(
            log,
            args.output,
            {
                "step": "real SDK E2E failed",
                "error": str(exc),
                "diagnostics": page_diagnostics(
                    page,
                    args.screenshot_dir,
                    "real_sdk_failure",
                    sdk_log_dir=args.sdk_log_dir or DEFAULT_SDK_LOG_DIR,
                    sdk_log_since_epoch=sdk_log_since_epoch,
                ),
            },
        )
        raise
    finally:
        CreateAppDialog.exec_ = original_create_dialog_exec
        log["worker_cleanup"] = wait_for_active_workers(app, page, args.worker_cleanup_timeout)
        page.close()
        app.processEvents()
        log["finished_at"] = datetime.now().isoformat()
        write_json_log(log, args.output)
        print(json.dumps(log, indent=2))


def _run_real_car(app, page, log, args, opened_create_dialogs):
    open_create_dialog(app, page, log, args, opened_create_dialogs, "open real CAR deploy app")
    app_name = args.car_app_name or f"launcher_e2e_car_{int(time.time())}"
    set_line_edit_value(app, page.app_name_input, app_name)
    set_line_edit_value(app, page.car_image_input, args.car_image or os.environ.get(REAL_CAR_IMAGE_ENV, "nginx:alpine"))
    set_line_edit_value(app, page.car_port_input, str(args.car_port))
    set_line_edit_value(app, page.car_registry_input, args.registry_server)
    set_line_edit_value(app, page.car_registry_user_input, args.registry_user)
    set_line_edit_value(app, page.car_registry_password_input, os.environ.get(REAL_REGISTRY_PASSWORD_ENV, ""))
    set_plain_text_value(app, page.env_input, "R1_LAUNCHER_E2E=real")

    secret_snapshot = secret_line_edit_snapshot(
        page.car_registry_password_input,
        os.environ.get(REAL_REGISTRY_PASSWORD_ENV, ""),
    )
    record_step(log, args.output, {"step": "real CAR form prepared", "secret_field": secret_snapshot})
    _click_validate_launch_refresh_copy_stop(app, page, log, args, "CAR")


def _run_real_war(app, page, log, args, opened_create_dialogs):
    open_create_dialog(app, page, log, args, opened_create_dialogs, "open real WAR deploy app")
    page.runner_type_combo.setCurrentIndex(1)
    app.processEvents()
    app_name = args.war_app_name or f"launcher_e2e_war_{int(time.time())}"
    set_line_edit_value(app, page.app_name_input, app_name)
    set_line_edit_value(app, page.worker_repo_input, args.war_repo or os.environ[REAL_WAR_REPO_ENV])
    set_line_edit_value(app, page.worker_branch_input, args.war_branch)
    set_line_edit_value(app, page.worker_image_input, args.war_image)
    set_line_edit_value(app, page.worker_port_input, str(args.war_port))
    set_line_edit_value(app, page.worker_github_user_input, args.github_user)
    set_line_edit_value(app, page.worker_github_token_input, os.environ.get(REAL_GITHUB_TOKEN_ENV, ""))
    set_plain_text_value(app, page.worker_commands_input, args.war_commands)
    set_plain_text_value(app, page.env_input, "R1_LAUNCHER_E2E=real")

    secret_snapshot = secret_line_edit_snapshot(
        page.worker_github_token_input,
        os.environ.get(REAL_GITHUB_TOKEN_ENV, ""),
    )
    record_step(log, args.output, {"step": "real WAR form prepared", "secret_field": secret_snapshot})
    _click_validate_launch_refresh_copy_stop(app, page, log, args, "WAR")


def _click_validate_launch_refresh_copy_stop(app, page, log, args, app_type):
    record_step(log, args.output, {"step": click_visible_button(app, page.validate_button, f"validate real {app_type}")})
    wait_until_page_state(
        app,
        page,
        lambda: page_message_text(page) == "Ready",
        args.timeout,
        f"real {app_type} validation",
    )
    record_step(log, args.output, {"step": click_visible_button(app, page.launch_button, f"launch real {app_type}")})
    wait_until_page_state(
        app,
        page,
        lambda: page_message_text(page) == "Launched",
        args.deploy_timeout + 30,
        f"real {app_type} launch",
    )
    page.apps_table.selectRow(page.apps_table.rowCount() - 1)
    app.processEvents()
    record_step(log, args.output, {"step": click_visible_button(app, page.refresh_button, f"refresh real {app_type}")})
    wait_until_page_state(
        app,
        page,
        lambda: page_message_text(page) in {"Status updated", "No launcher-owned status changes"},
        args.timeout,
        f"real {app_type} refresh",
    )
    record_step(log, args.output, {"step": click_visible_button(app, page.copy_url_button, f"copy real {app_type} URL")})
    record_step(log, args.output, {"step": click_visible_button(app, page.stop_button, f"stop real {app_type}")})
    wait_until_page_state(
        app,
        page,
        lambda: page_message_text(page) == "Stopped",
        args.timeout,
        f"real {app_type} stop",
    )
    record_step(
        log,
        args.output,
        {
            "step": f"real {app_type} E2E completed",
            "table": app_table_snapshot(page),
            "screenshot": screenshot(page, args.screenshot_dir, f"real_{app_type.lower()}_completed"),
        },
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Run optional real devnet SDK app E2E.")
    parser.add_argument("--app-kind", choices=("car", "war", "both"), default="car")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--deploy-timeout", type=int, default=240)
    parser.add_argument("--preflight-timeout", type=int, default=90)
    parser.add_argument("--output", default="")
    parser.add_argument("--screenshot-dir", default="")
    parser.add_argument("--registry-file", default="")
    parser.add_argument("--car-app-name", default="")
    parser.add_argument("--car-image", default="")
    parser.add_argument("--car-port", type=int, default=8080)
    parser.add_argument("--registry-server", default="docker.io")
    parser.add_argument("--registry-user", default="")
    parser.add_argument("--war-app-name", default="")
    parser.add_argument("--war-repo", default="")
    parser.add_argument("--war-branch", default="main")
    parser.add_argument("--war-image", default="node:22")
    parser.add_argument("--war-port", type=int, default=4173)
    parser.add_argument("--war-commands", default="npm install\nnpm run build\nnpm run start")
    parser.add_argument("--github-user", default="")
    parser.add_argument("--fail-on-skip", action="store_true")
    parser.add_argument("--sdk-log-dir", default="")
    parser.add_argument("--worker-cleanup-timeout", type=float, default=5.0)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    prepare_evidence_paths(args)
    guard = real_e2e_guard()
    issues = validate_real_args(args)
    if not guard["enabled"] or issues:
        guarded_skip_log(args, guard, issues)
        if args.fail_on_skip:
            raise SystemExit(3)
        return
    log = run_real_e2e(args)
    if log.get("result") != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
