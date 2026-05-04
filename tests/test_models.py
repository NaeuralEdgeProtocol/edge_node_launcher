from models.AllowedAddress import AllowedAddressList
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
