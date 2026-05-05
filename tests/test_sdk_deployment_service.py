from services.app_deployment_models import ContainerAppSpec, WorkerAppSpec
from services.app_registry import AppRegistry
from services.sdk_deployment_service import Ratio1SdkDeploymentClient, map_sdk_app_rows
from services.sdk_identity_service import SdkSessionFactory


NODE_ADDRESS = "0xai_A9OqTV_iFqmwj1SV7AKbdyr66NLkhSQHPpzp40c7jaLn"


class FakePipeline:
    def __init__(self, name="sdk_pipeline", url="https://app.example"):
        self.name = name
        self.url = url
        self.deploy_calls = []

    def deploy(self, timeout=None):
        self.deploy_calls.append(timeout)
        return self.url


class FakeInstance:
    instance_id = "instance-1"


class FakeSession:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.container_calls = []
        self.worker_calls = []
        self.close_pipeline_calls = []
        self.closed = False
        FakeSession.instances.append(self)

    def create_container_web_app(self, **kwargs):
        self.container_calls.append(kwargs)
        return FakePipeline(name="car_runner"), FakeInstance()

    def create_worker_web_app(self, **kwargs):
        self.worker_calls.append(kwargs)
        return FakePipeline(name="worker_runner"), FakeInstance()

    def close_pipeline(self, node_address, pipeline_name):
        self.close_pipeline_calls.append((node_address, pipeline_name))

    def get_nodes_apps(self, **kwargs):
        return [
            {
                "Node": NODE_ADDRESS,
                "App": "car_runner",
                "Plugin": "CONTAINER_APP_RUNNER",
                "Id": "instance-1",
                "Owner": "0xai_launcher",
                "Data": {"status": "online", "url": "https://app.example"},
                "LastError": "",
            }
        ]

    def close(self, **kwargs):
        self.closed = True


def make_client(tmp_path):
    FakeSession.instances = []
    registry = AppRegistry(tmp_path / "apps.json")
    factory = SdkSessionFactory(base_dir=tmp_path, session_class=FakeSession)
    return Ratio1SdkDeploymentClient(
        session_factory=factory,
        app_registry=registry,
        deploy_timeout=3,
        status_timeout=4,
    ), registry


def test_launch_container_app_calls_sdk_and_persists_record(tmp_path):
    client, registry = make_client(tmp_path)
    spec = ContainerAppSpec(
        app_name="car_runner",
        node_address=NODE_ADDRESS,
        image="nginx:alpine",
        registry_password="secret",
    )

    result = client.launch_container_app(spec)
    session = FakeSession.instances[0]

    assert result.app_id == f"{NODE_ADDRESS}:car_runner:CAR"
    assert result.app_url == "https://app.example"
    assert session.container_calls[0]["image"] == "nginx:alpine"
    assert session.closed is True
    assert registry.get(result.app_id).metadata["registry_password"] == "***REDACTED***"


def test_launch_worker_app_maps_sdk_payload_and_persists_record(tmp_path):
    client, registry = make_client(tmp_path)
    spec = WorkerAppSpec(
        app_name="worker_runner",
        node_address=NODE_ADDRESS,
        repo_url="https://github.com/Ratio1/example-app",
        github_token="ghp_secret",
    )

    result = client.launch_worker_app(spec)
    session = FakeSession.instances[0]

    assert result.app_id == f"{NODE_ADDRESS}:worker_runner:WAR"
    assert session.worker_calls[0]["vcs_data"]["REPO_OWNER"] == "Ratio1"
    assert session.worker_calls[0]["vcs_data"]["TOKEN"] == "ghp_secret"
    assert registry.get(result.app_id).metadata["github_token"] == "***REDACTED***"


def test_stop_app_calls_sdk_close_pipeline(tmp_path):
    client, _registry = make_client(tmp_path)

    assert client.stop_app(NODE_ADDRESS, "car_runner") is True

    session = FakeSession.instances[0]
    assert session.close_pipeline_calls == [(NODE_ADDRESS, "car_runner")]
    assert session.closed is True


def test_list_node_apps_maps_sdk_status_rows(tmp_path):
    client, _registry = make_client(tmp_path)

    statuses = client.list_node_apps(NODE_ADDRESS)

    assert len(statuses) == 1
    assert statuses[0].app_name == "car_runner"
    assert statuses[0].status == "online"
    assert statuses[0].url == "https://app.example"


def test_map_sdk_app_rows_handles_dataframes_and_empty_rows():
    class FakeDataFrame:
        def to_dict(self, mode):
            assert mode == "records"
            return [{"Node": "n", "App": "a", "Plugin": "p", "Id": "i"}]

    assert map_sdk_app_rows(None) == []
    assert map_sdk_app_rows(FakeDataFrame())[0].app_name == "a"
