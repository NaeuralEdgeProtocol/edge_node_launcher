from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Optional


_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b|[kmgt]?b|b)\s*$", re.IGNORECASE)


def _parse_percent(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def _parse_size_to_gib(value: Any) -> Optional[float]:
    if value is None:
        return None

    match = _SIZE_RE.match(str(value))
    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2).lower()
    binary_units = {
        "b": 1 / (1024 ** 3),
        "kib": 1 / (1024 ** 2),
        "mib": 1 / 1024,
        "gib": 1,
        "tib": 1024,
    }
    decimal_units = {
        "kb": 1_000 / (1024 ** 3),
        "mb": 1_000_000 / (1024 ** 3),
        "gb": 1_000_000_000 / (1024 ** 3),
        "tb": 1_000_000_000_000 / (1024 ** 3),
    }
    multiplier = binary_units.get(unit, decimal_units.get(unit))
    if multiplier is None:
        return None
    return number * multiplier


@dataclass
class ContainerStats:
    container: str
    name: str
    cpu_percent: Optional[float]
    memory_used_gib: Optional[float]
    memory_limit_gib: Optional[float]
    memory_percent: Optional[float]
    pids: Optional[int]
    net_io: str
    block_io: str
    sampled_at: datetime

    @classmethod
    def from_docker_stats(cls, data: dict, sampled_at: Optional[datetime] = None) -> "ContainerStats":
        mem_usage = str(data.get("MemUsage", ""))
        memory_used = None
        memory_limit = None
        if "/" in mem_usage:
            used_text, limit_text = mem_usage.split("/", 1)
            memory_used = _parse_size_to_gib(used_text)
            memory_limit = _parse_size_to_gib(limit_text)

        pids = None
        try:
            if data.get("PIDs") not in (None, ""):
                pids = int(str(data.get("PIDs")).strip())
        except (TypeError, ValueError):
            pids = None

        return cls(
            container=str(data.get("Container") or data.get("ID") or ""),
            name=str(data.get("Name") or data.get("Container") or ""),
            cpu_percent=_parse_percent(data.get("CPUPerc")),
            memory_used_gib=memory_used,
            memory_limit_gib=memory_limit,
            memory_percent=_parse_percent(data.get("MemPerc")),
            pids=pids,
            net_io=str(data.get("NetIO") or ""),
            block_io=str(data.get("BlockIO") or ""),
            sampled_at=sampled_at or datetime.now(),
        )

    def has_cpu_memory(self) -> bool:
        return self.cpu_percent is not None and self.memory_used_gib is not None

    def memory_summary(self) -> str:
        if self.memory_used_gib is None:
            return "memory unavailable"
        if self.memory_limit_gib is None:
            return f"{self.memory_used_gib:.2f} GiB"
        return f"{self.memory_used_gib:.2f}/{self.memory_limit_gib:.2f} GiB"
