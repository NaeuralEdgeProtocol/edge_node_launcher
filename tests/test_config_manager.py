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
