from datetime import datetime

from models.AllowedAddress import AllowedAddressList
from models.ContainerStats import ContainerStats
from models.NodeHistory import NodeHistory
from models.NodeInfo import NodeInfo


def test_node_info_from_dict_accepts_missing_optional_fields():
    info = NodeInfo.from_dict(
        {
            "address": "0xnode",
            "info": {"whitelist": ["0xallowed"]},
        }
    )

    assert info.address == "0xnode"
    assert info.alias == ""
    assert info.eth_address == ""
    assert info.version_long == ""
    assert info.version_short == ""
    assert info.whitelist == ["0xallowed"]


def test_node_history_from_dict_collapses_empty_gpu_metrics_to_none():
    history = NodeHistory.from_dict(
        {
            "address": "0xnode",
            "alias": "edge-one",
            "cpu_load": [12.5],
            "cpu_temp": [45.0],
            "current_epoch": 7,
            "current_epoch_avail": 0.9,
            "eth_address": "0xeth",
            "gpu_load": [None, None],
            "gpu_occupied_memory": [None],
            "gpu_temp": [None],
            "gpu_total_memory": [None],
            "last_epochs": [5, 6, 7],
            "last_save_time": "2026-05-03T01:00:00",
            "occupied_memory": [512.0],
            "timestamps": ["2026-05-03T01:00:00"],
            "total_memory": [1024.0],
            "uptime": "1h",
            "version": "1.0.0",
        }
    )

    assert history.gpu_load is None
    assert history.gpu_occupied_memory is None
    assert history.gpu_temp is None
    assert history.gpu_total_memory is None


def test_container_stats_parses_docker_stats_output():
    sampled_at = datetime(2026, 5, 5, 1, 0, 0)
    stats = ContainerStats.from_docker_stats(
        {
            "Container": "abc123",
            "Name": "r1devnode",
            "CPUPerc": "56.48%",
            "MemUsage": "1.746GiB / 15.62GiB",
            "MemPerc": "11.18%",
            "NetIO": "151MB / 5.32MB",
            "BlockIO": "2.1MB / 0B",
            "PIDs": "162",
        },
        sampled_at=sampled_at,
    )

    assert stats.container == "abc123"
    assert stats.name == "r1devnode"
    assert stats.cpu_percent == 56.48
    assert stats.memory_used_gib == 1.746
    assert stats.memory_limit_gib == 15.62
    assert stats.memory_percent == 11.18
    assert stats.pids == 162
    assert stats.sampled_at == sampled_at


def test_container_stats_parses_binary_and_decimal_memory_units():
    stats = ContainerStats.from_docker_stats(
        {
            "Name": "r1node",
            "CPUPerc": "1.0%",
            "MemUsage": "512MiB / 16GB",
            "MemPerc": "3.2%",
            "PIDs": "4",
        }
    )

    assert stats.memory_used_gib == 0.5
    assert round(stats.memory_limit_gib, 3) == 14.901


def test_allowed_address_list_batch_format_matches_update_payload():
    allowed = AllowedAddressList.from_dict(
        {
            "0xone": "first",
            "0xtwo": "second",
        }
    )

    assert allowed.to_batch_format() == [
        {"address": "0xone", "alias": "first"},
        {"address": "0xtwo", "alias": "second"},
    ]
