from pathlib import Path

from utils.system_resources import _SystemResourcesMixin


class SystemResourcesHarness(_SystemResourcesMixin):
    pass


def _ram_info(can_add_node=True):
    return {
        "total_ram_gb": 32.0,
        "max_nodes_supported": 2,
        "current_node_count": 1 if can_add_node else 2,
        "can_add_node": can_add_node,
        "min_required_gb": 16,
    }


def test_ram_capacity_message_uses_ascii_copy_when_node_can_be_added():
    resources = SystemResourcesHarness()

    message = resources._get_ram_check_message(_ram_info(can_add_node=True), can_add=True)

    assert message == (
        "Node can be created. System supports 2 nodes total "
        "(32.0 GB / 16 GB per node), currently running 1 nodes"
    )
    assert "\u00f7" not in message
    assert "\u00c3" not in message
    assert "\u00e2" not in message


def test_ram_capacity_message_uses_ascii_copy_at_node_capacity():
    resources = SystemResourcesHarness()

    message = resources._get_ram_check_message(_ram_info(can_add_node=False), can_add=False)

    assert message == (
        "Maximum node capacity reached. System supports 2 nodes "
        "(32.0 GB / 16 GB per node), currently running 2 nodes"
    )
    assert "\u00f7" not in message
    assert "\u00c3" not in message
    assert "\u00e2" not in message


def test_compact_resource_formatting_removes_sidebar_only_filler():
    resources = SystemResourcesHarness()
    resources.get_system_resources = lambda use_cache=True: {
        "memory": {
            "available": 40 * 1024**3,
            "total": 64 * 1024**3,
            "percent": 37.5,
        },
        "cpu": {"count": 14, "usage": 20.5},
        "storage": {
            "free": 162 * 1024**3,
            "total": 299 * 1024**3,
            "percent": 45.6,
        },
    }

    assert resources.get_formatted_memory_info() == "40.0 GB / 64.0 GB (37.5% used)"
    assert resources.get_formatted_cpu_info() == "14 cores (20.5% used)"
    assert resources.get_formatted_storage_info() == "162.0 GB / 299.0 GB (45.6% used)"
    assert resources.get_formatted_memory_info(compact=True) == "40.0 GB/64.0 GB (37.5%)"
    assert resources.get_formatted_cpu_info(compact=True) == "14 cores (20.5%)"
    assert resources.get_formatted_storage_info(compact=True) == "162.0 GB/299.0 GB (45.6%)"


def test_user_visible_source_copy_does_not_contain_common_mojibake_or_typographic_symbols():
    repo_root = Path(__file__).resolve().parents[1]
    source_roots = ("app_forms", "utils", "widgets", "tools", "main.py")
    suspicious_chars = (
        "\u00c3",
        "\u00c2",
        "\u00e2",
        "\ufffd",
        "\u00f7",
        "\u2022",
        "\u2026",
        "\u2013",
        "\u2014",
        "\u2018",
        "\u2019",
        "\u201c",
        "\u201d",
        "\u00f0",
        "\u0178",
        "\U0001f4cb",
        "\U0001f5d1",
    )
    violations = []

    for source_root in source_roots:
        root_path = repo_root / source_root
        paths = [root_path] if root_path.is_file() else root_path.rglob("*.py")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            found = sorted({char for char in suspicious_chars if char in text})
            if found:
                violations.append(f"{path.relative_to(repo_root)}: {found}")

    assert violations == []
