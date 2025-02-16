from dataclasses import dataclass
from typing import List, Optional

@dataclass
class NodeHistory:
    address: str
    alias: str
    cpu_load: List[float]
    cpu_temp: List[float]
    current_epoch: int
    current_epoch_avail: float
    eth_address: str
    gpu_load: Optional[List[float]]
    gpu_occupied_memory: Optional[List[float]]
    gpu_temp: Optional[List[float]]
    gpu_total_memory: Optional[List[float]]
    last_epochs: List[int]
    last_save_time: str
    occupied_memory: List[float]
    timestamps: List[str]
    total_memory: List[float]
    uptime: str
    version: str

    @classmethod
    def from_dict(cls, data: dict) -> 'NodeHistory':
        # Clean up GPU-related lists - if all values are None, set the whole list to None
        gpu_fields = ['gpu_load', 'gpu_occupied_memory', 'gpu_total_memory', 'gpu_temp']
        for field in gpu_fields:
            if field in data and all(v is None for v in data[field]):
                data[field] = None

        return cls(
            address=data['address'],
            alias=data['alias'],
            cpu_load=data['cpu_load'],
            cpu_temp=data['cpu_temp'],
            current_epoch=data['current_epoch'],
            current_epoch_avail=data['current_epoch_avail'],
            eth_address=data['eth_address'],
            gpu_load=data.get('gpu_load'),
            gpu_occupied_memory=data.get('gpu_occupied_memory'),
            gpu_temp=data.get('gpu_temp'),
            gpu_total_memory=data.get('gpu_total_memory'),
            last_epochs=data['last_epochs'],
            last_save_time=data['last_save_time'],
            occupied_memory=data['occupied_memory'],
            timestamps=data['timestamps'],
            total_memory=data['total_memory'],
            uptime=data['uptime'],
            version=data['version']
        )