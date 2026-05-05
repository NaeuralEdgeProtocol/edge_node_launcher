from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from utils.const import CONFIG_DIR


LAUNCHER_SDK_ALIAS = "edge-node-launcher"


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
            try:
                from ratio1 import Session
            except Exception as exc:
                raise SdkIdentityError(f"Ratio1 SDK import failed: {exc}") from exc
            session_class = Session

        kwargs = {
            "silent": True,
            "name": LAUNCHER_SDK_ALIAS,
            "local_cache_base_folder": str(self.base_dir),
            "local_cache_app_folder": "sdk",
            "use_home_folder": False,
        }
        kwargs.update(self.session_kwargs)
        return session_class(**kwargs)


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
