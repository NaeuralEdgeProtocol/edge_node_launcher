from services.app_deployment_models import (
    APP_TYPE_CONTAINER,
    APP_TYPE_WORKER,
    ContainerAppSpec,
    FileVolumeSpec,
    WorkerAppSpec,
    pipeline_name_from_app_name,
)
from services.app_secret_redaction import REDACTED_SECRET


NODE_ADDRESS = "0xai_A9OqTV_iFqmwj1SV7AKbdyr66NLkhSQHPpzp40c7jaLn"


def test_pipeline_name_matches_sdk_normalization_shape():
    assert pipeline_name_from_app_name("My App 01") == "my_app_01"
    assert pipeline_name_from_app_name("car_runner") == "car_runner"


def test_container_app_spec_maps_to_direct_sdk_kwargs_and_redacted_metadata():
    spec = ContainerAppSpec(
        app_name="car_runner",
        node_address=NODE_ADDRESS,
        image="nginx:alpine",
        port=8080,
        registry_username="user",
        registry_password="secret",
        env={"PUBLIC": "1"},
        file_volumes={
            "settings": FileVolumeSpec(content="enabled=true", mounting_point="/app/settings.ini")
        },
    )

    kwargs = spec.to_sdk_kwargs()
    metadata = spec.to_record_metadata()

    assert spec.app_type == APP_TYPE_CONTAINER
    assert kwargs["node"] == NODE_ADDRESS
    assert kwargs["name"] == "car_runner"
    assert kwargs["image"] == "nginx:alpine"
    assert kwargs["port"] == 8080
    assert kwargs["container_resources"] == {"cpu": 1, "gpu": 0, "memory": "512m", "ports": []}
    assert kwargs["cr"] == "docker.io"
    assert kwargs["cr_user"] == "user"
    assert kwargs["cr_password"] == "secret"
    assert kwargs["file_volumes"]["settings"]["mounting_point"] == "/app/settings.ini"
    assert metadata["registry_password"] == REDACTED_SECRET
    assert metadata["env"] == {"PUBLIC": "1"}
    assert metadata["file_volumes"]["settings"]["content"] == REDACTED_SECRET
    assert metadata["file_volumes"]["settings"]["mounting_point"] == "/app/settings.ini"


def test_worker_app_spec_maps_github_repo_and_secret_fields():
    spec = WorkerAppSpec(
        app_name="worker_runner",
        node_address=NODE_ADDRESS,
        repo_url="https://github.com/Ratio1/example-app.git",
        branch="devnet",
        github_username="octo",
        github_token="ghp_secret",
        registry_password="registry-secret",
        commands=["npm install", "npm run build", "npm run serve"],
    )

    kwargs = spec.to_sdk_kwargs()
    metadata = spec.to_record_metadata()

    assert spec.app_type == APP_TYPE_WORKER
    assert kwargs["vcs_data"] == {
        "PROVIDER": "github",
        "USERNAME": "octo",
        "TOKEN": "ghp_secret",
        "REPO_OWNER": "Ratio1",
        "REPO_NAME": "example-app",
        "BRANCH": "devnet",
    }
    assert kwargs["cr_data"]["PASSWORD"] == "registry-secret"
    assert kwargs["build_and_run_commands"][-1] == "npm run serve"
    assert kwargs["env"]["PORT"] == "4173"
    assert metadata["env"]["PORT"] == "4173"
    assert metadata["github_token"] == REDACTED_SECRET
    assert metadata["registry_password"] == REDACTED_SECRET


def test_worker_app_spec_preserves_explicit_port_environment_value():
    spec = WorkerAppSpec(
        app_name="worker_runner",
        node_address=NODE_ADDRESS,
        repo_url="https://github.com/Ratio1/example-app",
        port=4173,
        env={"PORT": "3000"},
    )

    kwargs = spec.to_sdk_kwargs()

    assert kwargs["env"]["PORT"] == "3000"
