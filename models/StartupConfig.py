from typing import List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class BlockchainConfig:
    PEM_FILE: str
    PASSWORD: Optional[str]
    PEM_LOCATION: str

@dataclass
class CaptureEnvironment:
    FORCE_CAP_RESOLUTION: int
    DEFAULT_PLUGIN: bool
    DISALLOWED_URL_DUPLICATES: List[str]

@dataclass
class ModelZooConfig:
    endpoint: str
    access_key: str
    secret_key: str
    secure: str
    bucket_name: str

@dataclass
class ServingEnvironment:
    LOG_TIMEOUTS_PERIOD: int
    COMM_ENGINE: str
    USE_AMP: bool
    MAX_WAIT_TIME_MULTIPLIER: int
    SERVER_COLLECTOR_TIMEDELTA: int
    AUTO_WARMUPS: Dict
    COMM_METHOD: str
    SHM_MAX_IMAGE_SHAPE: List[int]
    SHM_MAX_LEN: int
    SERVING_IN_PROCESS: bool
    SERVING_TIMERS_IDLE_DUMP: int
    SERVING_TIMERS_PREDICT_DUMP: int
    CHECK_BLOCKED_INPROCESS_SERVING: bool
    MODEL_ZOO_CONFIG: ModelZooConfig

@dataclass
class PluginsEnvironment:
    DEMO_MODE: bool
    DEBUG_OBJECTS: bool
    SEND_MANIFEST_EACH: int
    ADD_ORIGINAL_IMAGE: bool
    DEBUG_CONFIG_CHANGES: bool

@dataclass
class EmailConfig:
    COMMENT1: str
    USER: str
    PASSWORD: str
    SERVER: str
    PORT: int
    COMMENT2: str
    DESTINATION: str

@dataclass
class StartupConfig:
    EE_ID: str
    SECURED: bool
    IO_FORMATTER: str
    MAIN_LOOP_RESOLUTION: int
    SYSTEM_TEMPERATURE_CHECK: bool
    COMPRESS_HEARTBEAT: bool
    MIN_AVAIL_MEM_THR: float
    MIN_AVAIL_DISK_SIZE_GB: int
    CRITICAL_RESTART_LOW_MEM: float
    CHECK_RAM_ON_SHUTDOWN: bool
    SECONDS_HEARTBEAT: int
    HEARTBEAT_TIMERS: bool
    HEARTBEAT_LOG: bool
    PLUGINS_ON_THREADS: bool
    CAPTURE_STATS_DISPLAY: int
    SHUTDOWN_NO_STREAMS: bool
    TIMERS_DUMP_INTERVAL: int
    EXTENDED_TIMERS_DUMP: bool
    PLUGINS_DEBUG_CONFIG_CHANGES: bool
    BLOCKCHAIN_CONFIG: BlockchainConfig
    CAPTURE_ENVIRONMENT: CaptureEnvironment
    SERVING_ENVIRONMENT: ServingEnvironment
    PLUGINS_ENVIRONMENT: PluginsEnvironment
    ADMIN_PIPELINE: Dict[str, Any]
    COMMUNICATION_ENVIRONMENT: Dict[str, Any]
    HEAVY_OPS_CONFIG: Dict[str, Any]
    CONFIG_RETRIEVE: List[Dict[str, str]]

    @classmethod
    def from_dict(cls, data: dict) -> 'StartupConfig':
        # Filter out keys starting with '#'
        filtered_data = {k: v for k, v in data.items() if not k.startswith('#')}
        
        # Convert nested structures
        blockchain_config = BlockchainConfig(**filtered_data['BLOCKCHAIN_CONFIG'])
        capture_env = CaptureEnvironment(**filtered_data['CAPTURE_ENVIRONMENT'])
        
        serving_env_data = filtered_data['SERVING_ENVIRONMENT'].copy()
        serving_env_data['MODEL_ZOO_CONFIG'] = ModelZooConfig(**serving_env_data['MODEL_ZOO_CONFIG'])
        serving_env = ServingEnvironment(**serving_env_data)
        
        plugins_env = PluginsEnvironment(**filtered_data['PLUGINS_ENVIRONMENT'])

        # Create main config with original keys
        return cls(
            BLOCKCHAIN_CONFIG=blockchain_config,
            CAPTURE_ENVIRONMENT=capture_env,
            SERVING_ENVIRONMENT=serving_env,
            PLUGINS_ENVIRONMENT=plugins_env,
            **{k: v for k, v in filtered_data.items() if k not in [
                'BLOCKCHAIN_CONFIG', 'CAPTURE_ENVIRONMENT',
                'SERVING_ENVIRONMENT', 'PLUGINS_ENVIRONMENT'
            ]}
        ) 