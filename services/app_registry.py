from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from services.app_deployment_models import (
    APP_REGISTRY_SCHEMA_VERSION,
    ManagedAppRecord,
    utc_now_iso,
)
from utils.const import CONFIG_DIR


class AppRegistry:
    """Schema-versioned local registry for launcher-owned SDK apps."""

    def __init__(self, registry_file: str | Path | None = None):
        if registry_file is None:
            registry_file = Path.home() / CONFIG_DIR / "apps.json"
        self.registry_file = Path(registry_file)
        os.makedirs(self.registry_file.parent, exist_ok=True)
        self._records: list[ManagedAppRecord] = []
        self.load()

    def load(self) -> list[ManagedAppRecord]:
        if not self.registry_file.exists():
            self._records = []
            return self._records
        try:
            with self.registry_file.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            apps = payload.get("apps", []) if isinstance(payload, dict) else []
            self._records = [ManagedAppRecord.from_dict(item) for item in apps]
        except Exception as exc:
            logging.error("Error loading SDK app registry: %s", exc)
            self._records = []
        return self._records

    def save(self) -> bool:
        try:
            payload = {
                "schema_version": APP_REGISTRY_SCHEMA_VERSION,
                "apps": [record.to_dict(redact=True) for record in self._records],
            }
            with self.registry_file.open("w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
            return True
        except Exception as exc:
            logging.error("Error saving SDK app registry: %s", exc)
            return False

    def list_apps(self) -> list[ManagedAppRecord]:
        return list(self._records)

    def get(self, app_id: str) -> ManagedAppRecord | None:
        for record in self._records:
            if record.app_id == app_id:
                return record
        return None

    def upsert(self, record: ManagedAppRecord) -> bool:
        record.updated_at = utc_now_iso()
        for index, existing in enumerate(self._records):
            if existing.app_id == record.app_id:
                if not record.created_at:
                    record.created_at = existing.created_at
                self._records[index] = record
                return self.save()
        self._records.append(record)
        return self.save()

    def remove(self, app_id: str) -> bool:
        self._records = [record for record in self._records if record.app_id != app_id]
        return self.save()
