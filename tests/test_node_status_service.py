from services.node_status_service import (
    NODE_INFO_FAILURE_ACTION_DEFER_STARTUP,
    NODE_INFO_FAILURE_ACTION_RECORD_FAILURE,
    NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED,
    NODE_RUNTIME_STATE_DEGRADED,
    NODE_RUNTIME_STATE_NEEDS_ATTENTION,
    NODE_RUNTIME_STATE_RUNNING,
    NODE_RUNTIME_STATE_STARTING,
    NODE_RUNTIME_STATE_STOPPED,
    NodeStatusService,
)


def test_startup_grace_tracks_remaining_time_and_clear():
    now = 1000.0
    service = NodeStatusService(
        failure_threshold=3,
        startup_grace_seconds=60,
        clock=lambda: now,
    )

    service.mark_startup_grace("r1node")

    assert service.startup_grace_remaining_seconds("r1node") == 60
    now = 1025.0
    assert service.startup_grace_remaining_seconds("r1node") == 35
    assert service.clear_startup_grace("r1node") is True
    assert service.startup_grace_remaining_seconds("r1node") == 0


def test_node_info_startup_pending_errors_are_deferred_during_grace():
    service = NodeStatusService(
        failure_threshold=3,
        startup_grace_seconds=60,
        clock=lambda: 1000.0,
    )
    service.mark_startup_grace("r1node")
    service.node_info_failure_count = 2

    decision = service.record_node_info_failure(
        "r1node",
        "Error: /edge_node/_local_cache/_data/local_info.json does not exist",
    )

    assert decision.action == NODE_INFO_FAILURE_ACTION_DEFER_STARTUP
    assert decision.failure_count == 0
    assert decision.startup_grace_remaining_seconds == 60
    assert decision.error_is_startup_pending is True


def test_node_info_failures_count_until_threshold():
    service = NodeStatusService(
        failure_threshold=2,
        startup_grace_seconds=60,
        clock=lambda: 1000.0,
    )

    first = service.record_node_info_failure("r1node", "unexpected argument")
    second = service.record_node_info_failure("r1node", "unexpected argument")

    assert first.action == NODE_INFO_FAILURE_ACTION_RECORD_FAILURE
    assert first.failure_count == 1
    assert first.threshold_reached is False
    assert second.action == NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED
    assert second.failure_count == 2
    assert second.threshold_reached is True


def test_expired_startup_grace_no_longer_defers_pending_errors():
    now = 1000.0
    service = NodeStatusService(
        failure_threshold=2,
        startup_grace_seconds=60,
        clock=lambda: now,
    )
    service.mark_startup_grace("r1node")
    now = 1061.0

    decision = service.record_node_info_failure("r1node", "connection refused")

    assert decision.action == NODE_INFO_FAILURE_ACTION_RECORD_FAILURE
    assert decision.failure_count == 1
    assert decision.startup_grace_remaining_seconds == 0
    assert decision.error_is_startup_pending is True


def test_node_info_success_resets_failures_and_clears_grace():
    service = NodeStatusService(
        failure_threshold=3,
        startup_grace_seconds=60,
        clock=lambda: 1000.0,
    )
    service.mark_startup_grace("r1node")
    service.node_info_failure_count = 2

    result = service.record_node_info_success("r1node")

    assert result.previous_failure_count == 2
    assert result.startup_grace_cleared is True
    assert service.node_info_failure_count == 0
    assert service.startup_grace_remaining_seconds("r1node") == 0


def test_runtime_state_interprets_stopped_starting_running_and_degraded():
    now = 1000.0
    service = NodeStatusService(
        failure_threshold=3,
        startup_grace_seconds=60,
        clock=lambda: now,
    )

    assert service.runtime_state(container_running=False).state == NODE_RUNTIME_STATE_STOPPED
    assert service.runtime_state(container_running=True).state == NODE_RUNTIME_STATE_RUNNING

    degraded = service.runtime_state(container_running=True, failure_count=1)
    assert degraded.state == NODE_RUNTIME_STATE_DEGRADED
    assert "1/3" in degraded.detail

    attention = service.runtime_state(container_running=True, failure_count=3)
    assert attention.state == NODE_RUNTIME_STATE_NEEDS_ATTENTION
    assert "3/3" in attention.detail

    service.mark_startup_grace("r1node")
    starting = service.runtime_state(container_running=True, container_name="r1node")
    assert starting.state == NODE_RUNTIME_STATE_STARTING
    assert "60 more seconds" in starting.detail
