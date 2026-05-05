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
