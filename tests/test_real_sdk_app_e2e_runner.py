import os
import time
from types import SimpleNamespace

import tools.run_real_sdk_app_e2e as real_e2e


def test_real_e2e_guard_requires_explicit_flag_and_node_context():
    guard = real_e2e.real_e2e_guard({})

    assert guard["enabled"] is False
    assert guard["missing_env"] == [
        real_e2e.REAL_E2E_FLAG,
        real_e2e.REAL_NODE_ADDRESS_ENV,
        real_e2e.REAL_NODE_CONTAINER_ENV,
    ]


def test_real_e2e_guard_accepts_required_env():
    guard = real_e2e.real_e2e_guard(
        {
            real_e2e.REAL_E2E_FLAG: "1",
            real_e2e.REAL_NODE_ADDRESS_ENV: "0xai_realnode123",
            real_e2e.REAL_NODE_CONTAINER_ENV: "r1node-dev",
        }
    )

    assert guard["enabled"] is True
    assert guard["missing_env"] == []


def test_real_war_e2e_requires_repo_source():
    args = SimpleNamespace(app_kind="war", war_repo="")

    issues = real_e2e.validate_real_args(args, {})

    assert issues == [f"{real_e2e.REAL_WAR_REPO_ENV} or --war-repo is required for WAR real E2E."]


def test_real_car_e2e_does_not_require_war_repo():
    args = SimpleNamespace(app_kind="car", war_repo="")

    assert real_e2e.validate_real_args(args, {}) == []


def test_real_sdk_e2e_parser_defaults_to_devnet_edge_image():
    parser = real_e2e.build_parser()
    args = parser.parse_args([])

    assert args.edge_image == real_e2e.DEVNET_EDGE_NODE_IMAGE


def test_wait_until_page_state_reports_current_ui_state(monkeypatch):
    page = SimpleNamespace(
        validation_message=SimpleNamespace(text=lambda: "Launching secret-value"),
        car_registry_password_input=SimpleNamespace(text=lambda: "secret-value"),
        worker_github_token_input=SimpleNamespace(text=lambda: ""),
        _active_workers=[SimpleNamespace(operation_name="launch", isRunning=lambda: True)],
    )

    def timeout(*_args, **_kwargs):
        raise TimeoutError("Timed out waiting for real CAR launch")

    monkeypatch.setattr(real_e2e, "wait_until", timeout)

    try:
        real_e2e.wait_until_page_state(None, page, lambda: False, 1, "real CAR launch")
    except TimeoutError as exc:
        message = str(exc)
    else:
        raise AssertionError("wait_until_page_state should re-raise timeout failures")

    assert "validation_message='Launching <redacted>'" in message
    assert "secret-value" not in message
    assert "'operation': 'launch'" in message
    assert "'running_count': 1" in message


def test_page_diagnostics_capture_validation_table_workers_and_screenshot(monkeypatch):
    page = SimpleNamespace(
        validation_message=SimpleNamespace(text=lambda: "Launch failed", isVisible=lambda: True),
        car_registry_password_input=SimpleNamespace(text=lambda: "registry-secret"),
        worker_github_token_input=SimpleNamespace(text=lambda: ""),
        _active_workers=[SimpleNamespace(operation_name="launch", isRunning=lambda: False)],
    )

    monkeypatch.setattr(real_e2e, "app_table_snapshot", lambda _page: [{"name": "demo", "status": "failed"}])
    monkeypatch.setattr(real_e2e, "screenshot", lambda _page, _dir, label: f"{label}.png")

    diagnostics = real_e2e.page_diagnostics(page, "screens", "real_sdk_failure")

    assert diagnostics["validation_message"] == "Launch failed"
    assert diagnostics["validation_visible"] is True
    assert diagnostics["table"] == [{"name": "demo", "status": "failed"}]
    assert diagnostics["active_workers"]["workers"] == [{"operation": "launch", "running": False}]
    assert diagnostics["screenshot"] == "real_sdk_failure.png"


def test_collect_sdk_log_tails_filters_recent_logs_and_redacts_secrets(tmp_path):
    old_log = tmp_path / "20260505_000000_R1_001_log.txt"
    old_log.write_text("old secret-value\n", encoding="utf-8")
    old_timestamp = time.time() - 3600
    os.utime(old_log, (old_timestamp, old_timestamp))

    recent_log = tmp_path / "20260505_010000_R1_001_error_log.txt"
    recent_log.write_text(
        "line 1\nsecret-value rejected by dAuth\n"
        "PEM_FILE: _pk.pem\n"
        r"Loaded sk from C:\Users\vital\.ratio1\edge_node_launcher\sdk\_data\_pk.pem",
        encoding="utf-8",
    )
    since = time.time() - 60

    tails = real_e2e.collect_sdk_log_tails(
        log_dir=tmp_path,
        since_epoch=since,
        secrets=("secret-value",),
    )

    assert len(tails) == 1
    assert tails[0]["path"].endswith("_error_log.txt")
    assert "secret-value" not in tails[0]["tail"]
    assert "<redacted> rejected by dAuth" in tails[0]["tail"]
    assert "_pk.pem" not in tails[0]["tail"]
    assert "<redacted-pem-file>" in tails[0]["tail"]
    assert "<redacted-pem-path>" in tails[0]["tail"]


def test_size_evidence_page_uses_readable_default_when_screen_is_unavailable():
    resized_to = []
    app = SimpleNamespace(primaryScreen=lambda: None)
    page = SimpleNamespace(
        minimumWidth=lambda: 299,
        minimumHeight=lambda: 864,
        resize=lambda width, height: resized_to.append((width, height)),
    )

    real_e2e.size_evidence_page(app, page)

    assert resized_to == [(760, 900)]
