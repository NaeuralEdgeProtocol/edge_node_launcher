from datetime import datetime, timedelta

from models.ContainerStats import ContainerStats
from models.NodeHistory import NodeHistory
from services.node_telemetry_service import NodeTelemetryMetadata, NodeTelemetryService


def _stats(cpu=56.48, memory=1.746, sampled_at=None):
    return ContainerStats(
        container="abc123",
        name="r1node",
        cpu_percent=cpu,
        memory_used_gib=memory,
        memory_limit_gib=15.62,
        memory_percent=11.18,
        pids=162,
        net_io="151MB / 5.32MB",
        block_io="0B / 0B",
        sampled_at=sampled_at or datetime(2026, 5, 5, 1, 0, 0),
    )


def _history(*, timestamps=None, cpu_load=None, occupied_memory=None):
    timestamps = timestamps if timestamps is not None else ["2026-05-05T01:00:00", "2026-05-05T01:00:10"]
    cpu_load = cpu_load if cpu_load is not None else [10.0, 20.0]
    occupied_memory = occupied_memory if occupied_memory is not None else [1.0, 1.1]
    return NodeHistory(
        address="0xnode",
        alias="alpha",
        cpu_load=cpu_load,
        cpu_temp=[],
        current_epoch=1,
        current_epoch_avail=0.5,
        eth_address="0xeth",
        gpu_load=None,
        gpu_occupied_memory=None,
        gpu_temp=None,
        gpu_total_memory=None,
        last_epochs=[],
        last_save_time=timestamps[-1] if timestamps else "",
        occupied_memory=occupied_memory,
        timestamps=timestamps,
        total_memory=[16.0 for _ in timestamps],
        uptime="1m",
        version="test-version",
    )


def test_node_telemetry_service_uses_stats_for_empty_history():
    service = NodeTelemetryService()
    service.remember_container_stats_sample("r1node", _stats())

    selection = service.select_for_node_history(
        "r1node",
        _history(timestamps=[], cpu_load=[], occupied_memory=[]),
        metadata=NodeTelemetryMetadata(alias="r1node"),
    )

    assert selection.updated_ui
    assert selection.source == "docker_stats"
    assert selection.fallback_reason == "node history has no timestamps"
    assert selection.history.cpu_load == [56.48]
    assert selection.history.occupied_memory == [1.746]


def test_node_telemetry_service_detects_stale_history():
    now = datetime(2026, 5, 5, 1, 10, 0)
    service = NodeTelemetryService(now_factory=lambda: now, stale_after_seconds=300)
    stale_time = (now - timedelta(minutes=8)).isoformat(timespec="seconds")

    assert service.history_fallback_reason(
        _history(timestamps=[stale_time, stale_time])
    ) == "node history is stale (480s old)"


def test_node_telemetry_service_keeps_current_history_when_not_degraded():
    now = datetime(2026, 5, 5, 1, 10, 0)
    service = NodeTelemetryService(now_factory=lambda: now, stale_after_seconds=300)
    fresh_history = _history(
        timestamps=[
            (now - timedelta(seconds=20)).isoformat(timespec="seconds"),
            now.isoformat(timespec="seconds"),
        ]
    )

    selection = service.select_for_node_history("r1node", fresh_history)

    assert selection.source == "node_history"
    assert selection.history is fresh_history
    assert selection.fallback_reason is None


def test_node_telemetry_service_keeps_updating_stats_backed_plots():
    service = NodeTelemetryService()
    first = _stats(cpu=10.0, sampled_at=datetime(2026, 5, 5, 1, 0, 0))
    second = _stats(cpu=20.0, sampled_at=datetime(2026, 5, 5, 1, 0, 10))

    first_selection = service.select_for_docker_stats(
        "r1node",
        first,
        current_history=None,
        current_source=None,
    )
    second_selection = service.select_for_docker_stats(
        "r1node",
        second,
        current_history=first_selection.history,
        current_source="docker_stats",
    )

    assert first_selection.updated_ui
    assert second_selection.updated_ui
    assert second_selection.history.cpu_load == [10.0, 20.0]
