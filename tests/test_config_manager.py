from utils import config_manager
from utils.config_manager import ConfigManager, ContainerConfig


def test_container_config_roundtrip_preserves_fields():
    config = ContainerConfig(
        name="r1node",
        volume="ratio1_vol",
        created_at="2026-05-03T01:00:00",
        last_used="2026-05-03T01:10:00",
        node_address="0xnode",
        eth_address="0xeth",
        node_alias="edge-one",
    )

    restored = ContainerConfig.from_dict(config.to_dict())

    assert restored.to_dict() == config.to_dict()


def test_config_manager_adds_updates_and_persists_container(tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))

    assert manager.add_container(ContainerConfig(name="r1node", volume="ratio1_vol"))
    assert manager.update_node_address("r1node", "0xnode")
    assert manager.update_eth_address("r1node", "0xeth")
    assert manager.update_node_alias("r1node", "edge-one")

    reloaded = ConfigManager(config_dir=str(tmp_path))
    container = reloaded.get_container("r1node")

    assert container is not None
    assert container.volume == "ratio1_vol"
    assert container.node_address == "0xnode"
    assert container.eth_address == "0xeth"
    assert container.node_alias == "edge-one"


def test_config_manager_updates_existing_container_without_losing_addresses(tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))

    assert manager.add_container(
        ContainerConfig(
            name="r1node",
            volume="old_vol",
            node_address="0xnode",
            eth_address="0xeth",
        )
    )
    assert manager.add_container(ContainerConfig(name="r1node", volume="new_vol"))

    container = manager.get_container("r1node")

    assert container.volume == "new_vol"
    assert container.node_address == "0xnode"
    assert container.eth_address == "0xeth"


def test_config_manager_persists_dashboard_splitter_sizes(tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))

    assert manager.set_dashboard_splitter_sizes([640, 180])

    reloaded = ConfigManager(config_dir=str(tmp_path))

    assert reloaded.get_dashboard_splitter_sizes() == [640, 180]


def test_config_manager_ignores_invalid_dashboard_splitter_sizes(tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))
    manager.settings["dashboard_splitter_sizes"] = ["wide", -10]

    assert manager.get_dashboard_splitter_sizes() is None


def test_config_manager_persists_main_window_geometry(tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))

    assert manager.set_main_window_geometry(
        {"x": 40, "y": 50, "width": 1200, "height": 800}
    )

    reloaded = ConfigManager(config_dir=str(tmp_path))

    assert reloaded.get_main_window_geometry() == {
        "x": 40,
        "y": 50,
        "width": 1200,
        "height": 800,
    }


def test_config_manager_ignores_invalid_main_window_geometry(tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))
    manager.settings["main_window_geometry"] = {
        "x": "left",
        "y": 50,
        "width": 0,
        "height": -10,
    }

    assert manager.get_main_window_geometry() is None


def test_config_manager_volume_check_uses_timeout_and_hides_windows_console(monkeypatch, tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))
    calls = []
    create_no_window = 0x08000000

    class FakeResult:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return FakeResult()

    monkeypatch.setattr(config_manager.os, "name", "nt")
    monkeypatch.setattr(
        config_manager.subprocess,
        "CREATE_NO_WINDOW",
        create_no_window,
        raising=False,
    )
    monkeypatch.setattr(config_manager.subprocess, "run", fake_run)

    assert manager.volume_exists_in_docker("r1vol") is True
    assert calls == [
        (
            ["docker", "volume", "inspect", "r1vol"],
            {
                "capture_output": True,
                "text": True,
                "timeout": config_manager.DOCKER_VOLUME_CHECK_TIMEOUT,
                "creationflags": create_no_window,
            },
        )
    ]


def test_config_manager_volume_check_returns_false_on_timeout(monkeypatch, tmp_path):
    manager = ConfigManager(config_dir=str(tmp_path))

    def fake_run(command, **kwargs):
        raise config_manager.subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(config_manager.subprocess, "run", fake_run)

    assert manager.volume_exists_in_docker("r1vol") is False
