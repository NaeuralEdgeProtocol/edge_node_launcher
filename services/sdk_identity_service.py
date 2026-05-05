from __future__ import annotations

import importlib
import inspect
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from utils.const import CONFIG_DIR
from utils.edge_image_config import get_edge_node_image_config


LAUNCHER_SDK_ALIAS = "edge-node-launcher"
SDK_SESSION_MODULES = ("ratio1", "ratio1_sdk")
SDK_RUNTIME_PRIME_MODULES = (
    "asyncio.base_events",
    "asyncio.coroutines",
    "asyncio.events",
    "asyncio.futures",
    "asyncio.tasks",
    "asyncio.transports",
)


class SdkIdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class SdkIdentity:
    sdk_address: str
    eth_address: str = ""
    evm_network: str = ""
    alias: str = LAUNCHER_SDK_ALIAS
    local_cache_base_folder: str = ""
    local_cache_app_folder: str = "sdk"


class SdkSessionFactory:
    """Lazy Ratio1 SDK session factory with injectable session class for tests."""

    def __init__(
        self,
        *,
        base_dir: str | Path | None = None,
        session_class: Callable[..., Any] | None = None,
        session_kwargs: dict[str, Any] | None = None,
    ):
        self.base_dir = Path(base_dir) if base_dir is not None else Path.home() / CONFIG_DIR
        self.session_class = session_class
        self.session_kwargs = session_kwargs or {}

    def create_session(self):
        session_class = self.session_class
        if session_class is None:
            _initialize_sdk_config_if_needed()
            session_class = _load_sdk_session_class()
            _neutralize_launcher_version_for_sdk_dauth()

        kwargs = {
            "silent": True,
            "name": LAUNCHER_SDK_ALIAS,
            "local_cache_base_folder": str(self.base_dir),
            "local_cache_app_folder": "sdk",
            "use_home_folder": False,
        }
        sdk_network = _resolve_default_sdk_network()
        if sdk_network:
            kwargs["evm_network"] = sdk_network
        kwargs.update(self.session_kwargs)
        return session_class(**kwargs)


def _load_sdk_session_class(import_module: Callable[[str], Any] | None = None):
    _prime_sdk_runtime_imports()
    import_module = import_module or importlib.import_module
    errors = []
    for module_name in SDK_SESSION_MODULES:
        try:
            module = import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
            continue

        session_class = getattr(module, "Session", None)
        if session_class is None:
            errors.append(f"{module_name}: Session class was not found")
            continue
        return session_class

    details = "; ".join(errors) if errors else "no modules were checked"
    raise SdkIdentityError(
        f"Ratio1 SDK import failed. Tried {', '.join(SDK_SESSION_MODULES)}. {details}"
    )


def _prime_sdk_runtime_imports() -> None:
    module_names = SDK_RUNTIME_PRIME_MODULES
    if sys.platform == "win32":
        module_names = (*module_names, "asyncio.windows_events")

    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except Exception:
            continue


def _initialize_sdk_config_if_needed() -> None:
    try:
        config_module = importlib.import_module("ratio1.utils.config")
        config_file = Path(config_module.get_user_config_file())

        if _copy_legacy_env_config_if_missing(config_file):
            return

        config_module.maybe_init_config()
    except Exception as exc:
        raise SdkIdentityError(f"Ratio1 SDK config initialization failed: {exc}") from exc


def _copy_legacy_env_config_if_missing(config_file: Path) -> bool:
    legacy_env_file = config_file.parent / ".env"
    if config_file.exists() or not legacy_env_file.exists():
        return False

    config_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(legacy_env_file, config_file)
    return True


def _neutralize_launcher_version_for_sdk_dauth() -> None:
    try:
        bc_base = importlib.import_module("ratio1.bc.base")
    except Exception:
        return

    # The SDK imports `ver` without a package prefix. In the launcher repo that
    # resolves to the launcher's own ver.py, so dAuth sees the launcher as an old
    # Edge Node app. Clearing the app/core versions lets dAuth classify this as
    # an SDK client and use the SDK version instead.
    bc_base.app_version = None
    bc_base.core_version = None


def _resolve_default_sdk_network() -> str:
    try:
        return get_edge_node_image_config().environment_key
    except Exception:
        return "mainnet"


class SdkIdentityService:
    def __init__(self, session_factory: SdkSessionFactory | None = None):
        self.session_factory = session_factory or SdkSessionFactory()

    def load_identity(self) -> SdkIdentity:
        session = self.session_factory.create_session()
        try:
            sdk_address = _read_client_address(session)
            if not sdk_address:
                raise SdkIdentityError("Ratio1 SDK did not return a client address.")
            bc_engine = getattr(session, "bc_engine", None)
            return SdkIdentity(
                sdk_address=sdk_address,
                eth_address=str(getattr(bc_engine, "eth_address", "") or ""),
                evm_network=str(
                    getattr(bc_engine, "evm_network", "")
                    or getattr(bc_engine, "network", "")
                    or ""
                ),
                alias=str(getattr(session, "name", LAUNCHER_SDK_ALIAS) or LAUNCHER_SDK_ALIAS),
                local_cache_base_folder=str(self.session_factory.base_dir),
            )
        finally:
            close_sdk_session(session)


def _read_client_address(session) -> str:
    if hasattr(session, "get_client_address"):
        return str(session.get_client_address() or "")
    return str(getattr(session, "client_address", "") or "")


def close_sdk_session(session) -> None:
    close = getattr(session, "close", None)
    if close is None:
        return
    try:
        signature = inspect.signature(close)
        kwargs = {}
        if "wait_close" in signature.parameters:
            kwargs["wait_close"] = False
        if "close_pipelines" in signature.parameters:
            kwargs["close_pipelines"] = False
        close(**kwargs)
    except (TypeError, ValueError):
        close()
