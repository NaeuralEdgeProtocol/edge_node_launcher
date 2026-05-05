import pytest

from services.sdk_identity_service import (
    SdkIdentityError,
    SdkIdentityService,
    SdkSessionFactory,
    _load_sdk_session_class,
)


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
