from __future__ import annotations

from typing import Any

from services.app_deployment_models import (
    ContainerAppSpec,
    DeploymentResult,
    ManagedAppRecord,
    SdkAppStatus,
    WorkerAppSpec,
)
from services.app_registry import AppRegistry
from services.sdk_identity_service import SdkSessionFactory, close_sdk_session


DEFAULT_DEPLOY_TIMEOUT = 120
DEFAULT_STATUS_TIMEOUT = 15


class SdkDeploymentError(RuntimeError):
    pass


class Ratio1SdkDeploymentClient:
    """Thin boundary around Ratio1 SDK app deployment calls."""

    def __init__(
        self,
        *,
        session_factory: SdkSessionFactory | None = None,
        app_registry: AppRegistry | None = None,
        deploy_timeout: int = DEFAULT_DEPLOY_TIMEOUT,
        status_timeout: int = DEFAULT_STATUS_TIMEOUT,
    ):
        self.session_factory = session_factory or SdkSessionFactory()
        self.app_registry = app_registry
        self.deploy_timeout = deploy_timeout
        self.status_timeout = status_timeout

    def launch_container_app(self, spec: ContainerAppSpec) -> DeploymentResult:
        session = self.session_factory.create_session()
        try:
            pipeline, instance = session.create_container_web_app(**spec.to_sdk_kwargs())
            app_url = _deploy_pipeline(pipeline, self.deploy_timeout)
            result = _result_from_pipeline(spec, pipeline, instance, app_url)
            self._persist_result(result, spec.to_record_metadata())
            return result
        except Exception as exc:
            raise SdkDeploymentError(f"Container app deployment failed: {exc}") from exc
        finally:
            close_sdk_session(session)

    def launch_worker_app(self, spec: WorkerAppSpec) -> DeploymentResult:
        session = self.session_factory.create_session()
        try:
            pipeline, instance = session.create_worker_web_app(**spec.to_sdk_kwargs())
            app_url = _deploy_pipeline(pipeline, self.deploy_timeout)
            result = _result_from_pipeline(spec, pipeline, instance, app_url)
            self._persist_result(result, spec.to_record_metadata())
            return result
        except Exception as exc:
            raise SdkDeploymentError(f"Worker app deployment failed: {exc}") from exc
        finally:
            close_sdk_session(session)

    def stop_app(self, node_address: str, pipeline_name: str) -> bool:
        session = self.session_factory.create_session()
        try:
            session.close_pipeline(node_address, pipeline_name)
            return True
        except Exception as exc:
            raise SdkDeploymentError(f"App stop failed: {exc}") from exc
        finally:
            close_sdk_session(session)

    def list_node_apps(self, node_address: str) -> list[SdkAppStatus]:
        session = self.session_factory.create_session()
        try:
            rows = session.get_nodes_apps(
                node=node_address,
                as_json=False,
                timeout=self.status_timeout,
            )
            return map_sdk_app_rows(rows)
        except Exception as exc:
            raise SdkDeploymentError(f"App status refresh failed: {exc}") from exc
        finally:
            close_sdk_session(session)

    def _persist_result(self, result: DeploymentResult, metadata: dict[str, Any]) -> None:
        if self.app_registry is None:
            return
        self.app_registry.upsert(result.to_record(metadata=metadata))


def map_sdk_app_rows(rows: Any) -> list[SdkAppStatus]:
    if rows is None:
        return []
    if hasattr(rows, "to_dict"):
        try:
            rows = rows.to_dict("records")
        except TypeError:
            rows = rows.to_dict()
    if isinstance(rows, dict):
        rows = rows.get("apps", rows.get("data", [rows]))
    if not isinstance(rows, list):
        return []
    return [_status_from_row(row) for row in rows if isinstance(row, dict)]


def _status_from_row(row: dict[str, Any]) -> SdkAppStatus:
    data = row.get("Data") or row.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    probe = row.get("Probe") or row.get("probe") or {}
    if not isinstance(probe, dict):
        probe = {}
    url = data.get("url") or data.get("URL") or probe.get("url") or ""
    status = data.get("status") or data.get("STATUS") or row.get("Status") or "unknown"
    last_error = (
        row.get("LastError")
        or row.get("last_error")
        or data.get("LastError")
        or data.get("last_error")
        or data.get("error")
        or probe.get("LastError")
        or probe.get("last_error")
        or probe.get("error")
        or ""
    )
    return SdkAppStatus(
        node_address=str(row.get("Node") or row.get("node") or ""),
        app_name=str(row.get("App") or row.get("app") or ""),
        plugin_signature=str(row.get("Plugin") or row.get("plugin") or ""),
        instance_id=str(row.get("Id") or row.get("id") or ""),
        owner=str(row.get("Owner") or row.get("owner") or ""),
        status=str(status),
        url=str(url),
        last_error=str(last_error),
        raw=dict(row),
    )


def _deploy_pipeline(pipeline, timeout: int) -> str:
    deploy = getattr(pipeline, "deploy", None)
    if deploy is None:
        raise SdkDeploymentError("SDK did not return a deployable pipeline.")
    return str(deploy(timeout=timeout) or "")


def _result_from_pipeline(spec, pipeline, instance, app_url: str) -> DeploymentResult:
    pipeline_name = str(getattr(pipeline, "name", "") or spec.pipeline_name)
    instance_id = str(
        getattr(instance, "instance_id", "")
        or getattr(instance, "_instance_id", "")
        or ""
    )
    app_id = f"{spec.node_address}:{pipeline_name}:{spec.app_type}"
    return DeploymentResult(
        app_id=app_id,
        app_name=spec.app_name,
        app_type=spec.app_type,
        node_address=spec.node_address,
        pipeline_name=pipeline_name,
        plugin_signature=spec.plugin_signature,
        instance_id=instance_id,
        app_url=app_url,
        status="deployed",
    )
