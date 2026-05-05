import json

from services.app_deployment_models import ManagedAppRecord
from services.app_registry import AppRegistry
from services.app_secret_redaction import REDACTED_SECRET


def test_app_registry_persists_records_with_schema_and_redacted_metadata(tmp_path):
    registry_file = tmp_path / "apps.json"
    registry = AppRegistry(registry_file)
    record = ManagedAppRecord(
        app_id="node:pipeline:CAR",
        app_name="car_runner",
        app_type="CAR",
        node_address="0xai_123456789",
        pipeline_name="car_runner",
        plugin_signature="CONTAINER_APP_RUNNER",
        metadata={"registry_password": "secret", "image": "nginx:alpine"},
    )

    assert registry.upsert(record)

    payload = json.loads(registry_file.read_text())
    assert payload["schema_version"] == 1
    assert payload["apps"][0]["metadata"]["registry_password"] == REDACTED_SECRET
    assert payload["apps"][0]["metadata"]["image"] == "nginx:alpine"

    reloaded = AppRegistry(registry_file)
    assert reloaded.get("node:pipeline:CAR").app_name == "car_runner"


def test_app_registry_upsert_replaces_existing_and_remove_deletes(tmp_path):
    registry = AppRegistry(tmp_path / "apps.json")
    first = ManagedAppRecord(
        app_id="app-1",
        app_name="old",
        app_type="CAR",
        node_address="0xai_123456789",
        pipeline_name="old",
        plugin_signature="CONTAINER_APP_RUNNER",
    )
    second = ManagedAppRecord(
        app_id="app-1",
        app_name="new",
        app_type="CAR",
        node_address="0xai_123456789",
        pipeline_name="new",
        plugin_signature="CONTAINER_APP_RUNNER",
    )

    assert registry.upsert(first)
    assert registry.upsert(second)
    assert len(registry.list_apps()) == 1
    assert registry.get("app-1").app_name == "new"

    assert registry.remove("app-1")
    assert registry.get("app-1") is None
