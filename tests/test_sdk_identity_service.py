from services.sdk_identity_service import SdkIdentityService, SdkSessionFactory


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
