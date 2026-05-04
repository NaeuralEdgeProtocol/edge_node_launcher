from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LifecycleOperation:
    operation: str
    container_name: str

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "container_name": self.container_name,
        }


@dataclass(frozen=True)
class LaunchContext:
    container_name: str
    volume_name: str

    def to_dict(self) -> dict:
        return {
            "container_name": self.container_name,
            "volume_name": self.volume_name,
        }


@dataclass(frozen=True)
class BeginOperationResult:
    started: bool
    operation: Optional[LifecycleOperation] = None
    blocked_operation: Optional[LifecycleOperation] = None
    superseded_operation: Optional[LifecycleOperation] = None


@dataclass(frozen=True)
class LifecycleSnapshot:
    active_operation: Optional[dict]
    pending_launch_context: Optional[dict]
    docker_pull_in_progress: bool


class LifecycleState:
    """Tracks user-visible lifecycle operation ownership."""

    def __init__(self):
        self._active_operation: Optional[LifecycleOperation] = None
        self._pending_launch_context: Optional[LaunchContext] = None
        self.docker_pull_in_progress = False

    @property
    def active_operation(self) -> Optional[LifecycleOperation]:
        return self._active_operation

    @property
    def pending_launch_context(self) -> Optional[LaunchContext]:
        return self._pending_launch_context

    def begin_operation(self, operation: str, container_name: str) -> LifecycleOperation:
        self._active_operation = LifecycleOperation(operation, container_name)
        return self._active_operation

    def try_begin_operation(
        self,
        operation: str,
        container_name: str,
        container_running: bool,
    ) -> BeginOperationResult:
        if self._active_operation is not None:
            can_supersede_completed_stop = (
                operation == "start"
                and self._active_operation.operation == "stop"
                and self._active_operation.container_name == container_name
                and not container_running
            )
            if not can_supersede_completed_stop:
                return BeginOperationResult(
                    started=False,
                    blocked_operation=self._active_operation,
                )

            superseded_operation = self._active_operation
            self._active_operation = None
            started_operation = self.begin_operation(operation, container_name)
            return BeginOperationResult(
                started=True,
                operation=started_operation,
                superseded_operation=superseded_operation,
            )

        return BeginOperationResult(
            started=True,
            operation=self.begin_operation(operation, container_name),
        )

    def end_operation(self, container_name: str = None) -> Optional[LifecycleOperation]:
        if self._active_operation is None:
            return None

        if container_name is not None and self._active_operation.container_name != container_name:
            return None

        ended = self._active_operation
        self._active_operation = None
        return ended

    def active_operation_dict(self) -> Optional[dict]:
        return self._active_operation.to_dict() if self._active_operation else None

    def start_docker_pull(self, container_name: str, volume_name: str) -> LaunchContext:
        self.docker_pull_in_progress = True
        self._pending_launch_context = LaunchContext(container_name, volume_name)
        return self._pending_launch_context

    def finish_docker_pull(self) -> Optional[LaunchContext]:
        context = self._pending_launch_context
        self.docker_pull_in_progress = False
        self._pending_launch_context = None
        return context

    def pending_launch_context_dict(self) -> Optional[dict]:
        return self._pending_launch_context.to_dict() if self._pending_launch_context else None

    def diagnostic_snapshot(self) -> LifecycleSnapshot:
        return LifecycleSnapshot(
            active_operation=self.active_operation_dict(),
            pending_launch_context=self.pending_launch_context_dict(),
            docker_pull_in_progress=self.docker_pull_in_progress,
        )

    def auto_restart_blocker(
        self,
        container_name: str,
        selected_container_name: str,
        user_stopped_container: bool,
    ) -> Optional[str]:
        if self._active_operation is not None:
            return "active_operation"
        if selected_container_name != container_name:
            return "stale_selection"
        if self.docker_pull_in_progress or self._pending_launch_context is not None:
            return "launch_in_progress"
        if user_stopped_container:
            return "user_stopped"
        return None
