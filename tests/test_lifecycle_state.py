from utils.lifecycle_state import LifecycleState


def test_lifecycle_operation_ends_only_for_matching_container():
    state = LifecycleState()

    state.begin_operation("launch", "r1node")

    assert state.active_operation_dict() == {
        "operation": "launch",
        "container_name": "r1node",
    }
    assert state.end_operation("r1node2") is None
    assert state.active_operation_dict() == {
        "operation": "launch",
        "container_name": "r1node",
    }

    ended = state.end_operation("r1node")

    assert ended.operation == "launch"
    assert ended.container_name == "r1node"
    assert state.active_operation_dict() is None


def test_lifecycle_operation_can_be_force_cleared():
    state = LifecycleState()

    state.begin_operation("add_node", "r1node2")
    ended = state.end_operation()

    assert ended.operation == "add_node"
    assert state.active_operation_dict() is None


def test_lifecycle_try_begin_blocks_overlapping_operations():
    state = LifecycleState()
    state.begin_operation("start", "r1node")

    result = state.try_begin_operation("add_node", "r1node2", container_running=False)

    assert result.started is False
    assert result.blocked_operation.operation == "start"
    assert result.blocked_operation.container_name == "r1node"
    assert state.active_operation_dict() == {
        "operation": "start",
        "container_name": "r1node",
    }


def test_lifecycle_try_begin_supersedes_completed_stop_for_same_container():
    state = LifecycleState()
    state.begin_operation("stop", "r1node")

    result = state.try_begin_operation("start", "r1node", container_running=False)

    assert result.started is True
    assert result.operation.operation == "start"
    assert result.operation.container_name == "r1node"
    assert result.superseded_operation.operation == "stop"
    assert state.active_operation_dict() == {
        "operation": "start",
        "container_name": "r1node",
    }


def test_lifecycle_try_begin_does_not_supersede_running_stop():
    state = LifecycleState()
    state.begin_operation("stop", "r1node")

    result = state.try_begin_operation("start", "r1node", container_running=True)

    assert result.started is False
    assert result.blocked_operation.operation == "stop"
    assert state.active_operation_dict() == {
        "operation": "stop",
        "container_name": "r1node",
    }


def test_docker_pull_context_is_captured_and_cleared_together():
    state = LifecycleState()

    state.start_docker_pull("r1node", "r1vol")

    assert state.docker_pull_in_progress is True
    assert state.pending_launch_context_dict() == {
        "container_name": "r1node",
        "volume_name": "r1vol",
    }

    context = state.finish_docker_pull()

    assert context.container_name == "r1node"
    assert context.volume_name == "r1vol"
    assert state.docker_pull_in_progress is False
    assert state.pending_launch_context_dict() is None


def test_auto_restart_blocker_reports_active_launch_and_user_stop_reasons():
    state = LifecycleState()

    assert state.auto_restart_blocker("r1node", "r1node", user_stopped_container=False) is None

    state.begin_operation("launch", "r1node")
    assert state.auto_restart_blocker("r1node", "r1node", user_stopped_container=False) == "active_operation"
    state.end_operation("r1node")

    assert state.auto_restart_blocker("r1node", "r1node2", user_stopped_container=False) == "stale_selection"

    state.start_docker_pull("r1node", "r1vol")
    assert state.auto_restart_blocker("r1node", "r1node", user_stopped_container=False) == "launch_in_progress"
    state.finish_docker_pull()

    assert state.auto_restart_blocker("r1node", "r1node", user_stopped_container=True) == "user_stopped"
