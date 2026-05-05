import pytest

from services.sdk_identity_service import (
    SdkIdentityError,
    SdkIdentityService,
    SdkSessionFactory,
    _copy_legacy_env_config_if_missing,
    _load_sdk_session_class,
    _neutralize_launcher_version_for_sdk_dauth,
)
from utils.edge_image_config import configure_edge_node_image


class FakeBcEngine:
    eth_address = "0xeth"
    evm_network = "devnet"


class FakeSession:
    created_kwargs = []

    def __init__(self, **kwargs):
        self.created_kwargs.append(kwargs)
        self.name = kwargs["name"]
        self.bc_engine = FakeBcEngine()
        self.closed_kwargs = None

    def get_client_address(self):
        return "0xai_launcher"

    def close(self, close_pipelines=False, wait_close=True):
        self.closed_kwargs = {
            "close_pipelines": close_pipelines,
            "wait_close": wait_close,
        }


def test_sdk_identity_service_loads_address_from_injected_session(tmp_path):
    FakeSession.created_kwargs = []
    factory = SdkSessionFactory(base_dir=tmp_path, session_class=FakeSession)
    service = SdkIdentityService(factory)

    identity = service.load_identity()

    assert identity.sdk_address == "0xai_launcher"
    assert identity.eth_address == "0xeth"
    assert identity.evm_network == "devnet"
    assert identity.alias == "edge-node-launcher"
    assert identity.local_cache_base_folder == str(tmp_path)
    assert FakeSession.created_kwargs[0]["local_cache_base_folder"] == str(tmp_path)
    assert FakeSession.created_kwargs[0]["local_cache_app_folder"] == "sdk"
    assert FakeSession.created_kwargs[0]["use_home_folder"] is False
    assert FakeSession.created_kwargs[0]["evm_network"] == "mainnet"


def test_sdk_session_factory_uses_active_edge_image_network(tmp_path):
    configure_edge_node_image(cli_image="ratio1/edge_node:devnet", production_mode=False)
    FakeSession.created_kwargs = []
    factory = SdkSessionFactory(base_dir=tmp_path, session_class=FakeSession)

    factory.create_session()

    assert FakeSession.created_kwargs[0]["evm_network"] == "devnet"


def test_sdk_session_factory_allows_explicit_network_override(tmp_path):
    configure_edge_node_image(cli_image="ratio1/edge_node:devnet", production_mode=False)
    FakeSession.created_kwargs = []
    factory = SdkSessionFactory(
        base_dir=tmp_path,
        session_class=FakeSession,
        session_kwargs={"evm_network": "testnet"},
    )

    factory.create_session()

    assert FakeSession.created_kwargs[0]["evm_network"] == "testnet"


def test_sdk_dauth_version_context_is_classified_as_sdk_client():
    import ratio1.bc.base as bc_base

    original_app_version = bc_base.app_version
    original_core_version = bc_base.core_version
    try:
        bc_base.app_version = "1.1.10"
        bc_base.core_version = "9.9.9"

        _neutralize_launcher_version_for_sdk_dauth()

        assert bc_base.app_version is None
        assert bc_base.core_version is None
    finally:
        bc_base.app_version = original_app_version
        bc_base.core_version = original_core_version


def test_sdk_config_init_copies_existing_home_env_without_overwrite(tmp_path):
    config_file = tmp_path / "config"
    legacy_env_file = tmp_path / ".env"
    legacy_env_file.write_text("EE_EVM_NET=devnet\nEE_MQTT_USER=user\n", encoding="utf-8")

    assert _copy_legacy_env_config_if_missing(config_file)
    assert config_file.read_text(encoding="utf-8") == legacy_env_file.read_text(encoding="utf-8")

    config_file.write_text("EE_EVM_NET=mainnet\n", encoding="utf-8")

    assert not _copy_legacy_env_config_if_missing(config_file)
    assert config_file.read_text(encoding="utf-8") == "EE_EVM_NET=mainnet\n"


def test_sdk_session_loader_falls_back_to_ratio1_sdk_package():
    calls = []

    def fake_import_module(module_name):
        calls.append(module_name)
        if module_name == "ratio1":
            raise ModuleNotFoundError("No module named 'ratio1'")
        return type("FakeRatio1SdkModule", (), {"Session": FakeSession})

    assert _load_sdk_session_class(fake_import_module) is FakeSession
    assert calls == ["ratio1", "ratio1_sdk"]


def test_sdk_session_loader_reports_checked_import_paths():
    def fake_import_module(module_name):
        raise ModuleNotFoundError(f"No module named '{module_name}'")

    with pytest.raises(SdkIdentityError) as exc_info:
        _load_sdk_session_class(fake_import_module)

    message = str(exc_info.value)
    assert "Tried ratio1, ratio1_sdk" in message
    assert "ratio1: ModuleNotFoundError" in message
    assert "ratio1_sdk: ModuleNotFoundError" in message
