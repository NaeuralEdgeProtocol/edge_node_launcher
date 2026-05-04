from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from models.ContainerStats import ContainerStats
from models.NodeHistory import NodeHistory


@dataclass
class NodeTelemetryMetadata:
    address: str = ""
    alias: str = ""
    eth_address: str = ""
    current_epoch: int = 0
    current_epoch_avail: float = 0.0
    uptime: str = ""
    version: str = ""


@dataclass
class TelemetryPlotSelection:
    history: Optional[NodeHistory]
    source: str
    updated_ui: bool
    fallback_reason: Optional[str] = None


class NodeTelemetryService:
    """Owns source selection for node metrics shown in the launcher UI."""

    def __init__(
        self,
        *,
        sample_limit: int = 100,
        stale_after_seconds: int = 300,
        now_factory: Callable[[], datetime] = datetime.now,
    ):
        self.sample_limit = sample_limit
        self.stale_after_seconds = stale_after_seconds
        self._now_factory = now_factory
        self._docker_stats_history: dict[str, list[ContainerStats]] = {}

    def clear(self) -> None:
        self._docker_stats_history = {}

    def stats_samples_for_container(self, container_name: str) -> list[ContainerStats]:
        return self._docker_stats_history.setdefault(container_name, [])

    def remember_container_stats_sample(self, container_name: str, stats: ContainerStats) -> list[ContainerStats]:
        samples = self.stats_samples_for_container(container_name)
        samples.append(stats)
        if len(samples) > self.sample_limit:
            del samples[:-self.sample_limit]
        return samples

    def history_fallback_reason(self, history) -> Optional[str]:
        if history is None:
            return "node history is not available"
        timestamps = getattr(history, "timestamps", None) or []
        if not timestamps:
            return "node history has no timestamps"
        if not self._has_metric_values(getattr(history, "cpu_load", None)):
            return "node history has no CPU samples"
        if not self._has_metric_values(getattr(history, "occupied_memory", None)):
            return "node history has no memory samples"
        if len(timestamps) < 2:
            return "node history has only one sample"
        age_seconds = self._history_age_seconds(history)
        if age_seconds is not None and age_seconds > self.stale_after_seconds:
            return f"node history is stale ({int(age_seconds)}s old)"
        return None

    def history_from_stats_samples(
        self,
        container_name: str,
        *,
        base_history=None,
        metadata: Optional[NodeTelemetryMetadata] = None,
    ) -> Optional[NodeHistory]:
        valid_samples = [
            sample
            for sample in self.stats_samples_for_container(container_name)
            if sample.has_cpu_memory()
        ]
        if not valid_samples:
            return None

        valid_samples = valid_samples[-self.sample_limit:]
        metadata = metadata or NodeTelemetryMetadata()
        timestamps = [sample.sampled_at.isoformat(timespec="seconds") for sample in valid_samples]
        memory_limits = [
            sample.memory_limit_gib if sample.memory_limit_gib is not None else sample.memory_used_gib or 0.0
            for sample in valid_samples
        ]

        return NodeHistory(
            address=self._history_value(base_history, "address", metadata.address),
            alias=self._history_value(base_history, "alias", metadata.alias or container_name),
            cpu_load=[sample.cpu_percent for sample in valid_samples],
            cpu_temp=getattr(base_history, "cpu_temp", []) if base_history is not None else [],
            current_epoch=self._history_value(base_history, "current_epoch", metadata.current_epoch),
            current_epoch_avail=self._history_value(
                base_history,
                "current_epoch_avail",
                metadata.current_epoch_avail,
            ),
            eth_address=self._history_value(base_history, "eth_address", metadata.eth_address),
            gpu_load=getattr(base_history, "gpu_load", None) if base_history is not None else None,
            gpu_occupied_memory=getattr(base_history, "gpu_occupied_memory", None) if base_history is not None else None,
            gpu_temp=getattr(base_history, "gpu_temp", None) if base_history is not None else None,
            gpu_total_memory=getattr(base_history, "gpu_total_memory", None) if base_history is not None else None,
            last_epochs=getattr(base_history, "last_epochs", []) if base_history is not None else [],
            last_save_time=timestamps[-1],
            occupied_memory=[sample.memory_used_gib for sample in valid_samples],
            timestamps=timestamps,
            total_memory=memory_limits,
            uptime=str(self._history_value(base_history, "uptime", metadata.uptime)),
            version=str(self._history_value(base_history, "version", metadata.version)),
        )

    def select_for_node_history(
        self,
        container_name: str,
        node_history: NodeHistory,
        *,
        metadata: Optional[NodeTelemetryMetadata] = None,
    ) -> TelemetryPlotSelection:
        fallback_reason = self.history_fallback_reason(node_history)
        stats_history = self.history_from_stats_samples(
            container_name,
            base_history=node_history,
            metadata=metadata,
        )
        if fallback_reason is not None and stats_history is not None:
            return TelemetryPlotSelection(
                history=stats_history,
                source="docker_stats",
                updated_ui=True,
                fallback_reason=fallback_reason,
            )
        return TelemetryPlotSelection(
            history=node_history,
            source="node_history",
            updated_ui=True,
            fallback_reason=fallback_reason,
        )

    def select_for_docker_stats(
        self,
        container_name: str,
        stats: ContainerStats,
        *,
        current_history=None,
        current_source: Optional[str] = None,
        metadata: Optional[NodeTelemetryMetadata] = None,
    ) -> TelemetryPlotSelection:
        self.remember_container_stats_sample(container_name, stats)
        fallback_reason = self.history_fallback_reason(current_history)
        stats_history = self.history_from_stats_samples(
            container_name,
            base_history=current_history,
            metadata=metadata,
        )
        should_update = (
            stats_history is not None
            and (current_source == "docker_stats" or fallback_reason is not None)
        )
        return TelemetryPlotSelection(
            history=stats_history if should_update else None,
            source="docker_stats",
            updated_ui=should_update,
            fallback_reason=fallback_reason if should_update else None,
        )

    @staticmethod
    def stats_log_summary(stats: ContainerStats) -> str:
        cpu_text = f"{stats.cpu_percent:.1f}%" if stats.cpu_percent is not None else "unavailable"
        pids_text = stats.pids if stats.pids is not None else "unavailable"
        return (
            f"CPU {cpu_text}, memory {stats.memory_summary()}, "
            f"PIDs {pids_text}, net {stats.net_io or 'n/a'}, block {stats.block_io or 'n/a'}"
        )

    @staticmethod
    def _has_metric_values(values) -> bool:
        return bool(values) and any(value is not None for value in values)

    @staticmethod
    def _history_value(history, field_name: str, fallback):
        value = getattr(history, field_name, None) if history is not None else None
        return fallback if value in (None, "") else value

    def _history_age_seconds(self, history) -> Optional[float]:
        timestamps = getattr(history, "timestamps", None) or []
        if not timestamps:
            return None
        last_timestamp = timestamps[-1]
        try:
            if isinstance(last_timestamp, str):
                timestamp_text = last_timestamp.replace("Z", "+00:00")
                last_dt = datetime.fromisoformat(timestamp_text)
            else:
                last_dt = datetime.fromtimestamp(float(last_timestamp))
            now = self._now_factory()
            if last_dt.tzinfo is not None and now.tzinfo is None:
                now = datetime.now(last_dt.tzinfo)
            age_seconds = (now - last_dt).total_seconds()
            return age_seconds if age_seconds >= 0 else None
        except (TypeError, ValueError):
            return None
