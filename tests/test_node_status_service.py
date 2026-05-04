from services.node_status_service import (
    NODE_INFO_FAILURE_ACTION_DEFER_STARTUP,
    NODE_INFO_FAILURE_ACTION_RECORD_FAILURE,
    NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED,
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
