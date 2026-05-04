from dataclasses import dataclass
from time import time
from typing import Callable, Dict


NODE_INFO_FAILURE_ACTION_DEFER_STARTUP = "defer_startup"
NODE_INFO_FAILURE_ACTION_RECORD_FAILURE = "record_failure"
NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED = "threshold_reached"

STARTUP_PENDING_NODE_INFO_ERROR_MARKERS = (
    "local_info.json does not exist",
    "no such file or directory",
    "timed out",
    "timeout",
    "connection refused",
)


@dataclass(frozen=True)
class NodeInfoSuccessResult:
    previous_failure_count: int
    startup_grace_cleared: bool


@dataclass(frozen=True)
class NodeInfoFailureDecision:
    action: str
    failure_count: int
    threshold: int
    startup_grace_remaining_seconds: int = 0
    error_is_startup_pending: bool = False

    @property
    def threshold_reached(self) -> bool:
        return self.action == NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED


class NodeStatusService:
    """Interprets startup grace and node-info failure state without UI code."""

    def __init__(
        self,
        *,
        failure_threshold: int,
        startup_grace_seconds: int,
        clock: Callable[[], float] = time,
    ):
        self.failure_threshold = failure_threshold
        self.startup_grace_seconds = startup_grace_seconds
        self._clock = clock
        self._startup_grace_started_at: Dict[str, float] = {}
        self.node_info_failure_count = 0

    @property
    def startup_grace_started_at(self) -> Dict[str, float]:
        return self._startup_grace_started_at

    def mark_startup_grace(self, container_name: str) -> None:
        if not container_name:
            return
        self._startup_grace_started_at[container_name] = self._clock()

    def clear_startup_grace(self, container_name: str) -> bool:
        return self._startup_grace_started_at.pop(container_name, None) is not None

    def startup_grace_remaining_seconds(self, container_name: str) -> int:
        started_at = self._startup_grace_started_at.get(container_name)
        if started_at is None:
            return 0
        elapsed = max(0, int(self._clock() - started_at))
        return max(0, self.startup_grace_seconds - elapsed)

    def is_startup_pending_node_info_error(self, error: str) -> bool:
        normalized = (error or "").lower()
        return any(marker in normalized for marker in STARTUP_PENDING_NODE_INFO_ERROR_MARKERS)

    def should_defer_node_info_failure(self, container_name: str, error: str) -> bool:
        return (
            self.startup_grace_remaining_seconds(container_name) > 0
            and self.is_startup_pending_node_info_error(error)
        )

    def reset_node_info_failure_count(self) -> int:
        previous_failure_count = self.node_info_failure_count
        self.node_info_failure_count = 0
        return previous_failure_count

    def record_node_info_success(self, container_name: str) -> NodeInfoSuccessResult:
        previous_failure_count = self.reset_node_info_failure_count()
        return NodeInfoSuccessResult(
            previous_failure_count=previous_failure_count,
            startup_grace_cleared=self.clear_startup_grace(container_name),
        )

    def record_node_info_failure(self, container_name: str, error: str) -> NodeInfoFailureDecision:
        error_is_startup_pending = self.is_startup_pending_node_info_error(error)
        remaining = self.startup_grace_remaining_seconds(container_name)

        if remaining > 0 and error_is_startup_pending:
            self.reset_node_info_failure_count()
            return NodeInfoFailureDecision(
                action=NODE_INFO_FAILURE_ACTION_DEFER_STARTUP,
                failure_count=self.node_info_failure_count,
                threshold=self.failure_threshold,
                startup_grace_remaining_seconds=remaining,
                error_is_startup_pending=True,
            )

        self.node_info_failure_count += 1
        action = (
            NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED
            if self.node_info_failure_count >= self.failure_threshold
            else NODE_INFO_FAILURE_ACTION_RECORD_FAILURE
        )
        return NodeInfoFailureDecision(
            action=action,
            failure_count=self.node_info_failure_count,
            threshold=self.failure_threshold,
            startup_grace_remaining_seconds=remaining,
            error_is_startup_pending=error_is_startup_pending,
        )
