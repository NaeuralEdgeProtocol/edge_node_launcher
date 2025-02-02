from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class CommunicationInstance:
    RECV_FROM: str = None
    SEND_TO: str = None

@dataclass
class LocalParams:
    HOST: str
    PASS: str
    PORT: int
    QOS: int
    SECURED: int
    USER: str

@dataclass
class ChannelConfig:
    TOPIC: str

@dataclass
class CommunicationParams:
    CERT_PATH: str
    CONFIG_CHANNEL: ChannelConfig
    CTRL_CHANNEL: ChannelConfig
    HOST: str
    NOTIF_CHANNEL: ChannelConfig
    PASS: str
    PAYLOADS_CHANNEL: ChannelConfig
    PORT: str
    QOS: int
    SECURED: int
    SUBTOPIC: str
    USER: str

@dataclass
class Communication:
    INSTANCES: Dict[str, CommunicationInstance]
    LOCAL_PARAMS: LocalParams
    PARAMS: CommunicationParams
    TYPE: str

@dataclass
class ConfigUploader:
    ACCESS_KEY: str
    BUCKET_NAME: str
    ENDPOINT: str
    SECRET_KEY: str
    SECURE: str

@dataclass
class FileUpload:
    CONFIG_UPLOADER: ConfigUploader
    TYPE: str

@dataclass
class ConfigApp:
    COMMUNICATION: Communication
    FILE_UPLOAD: FileUpload
    PAYLOAD_TYPE: str
    SECONDS_HEARTBEAT: int
    SERVING_IN_PROCESS: bool

    @classmethod
    def from_dict(cls, data: dict) -> 'ConfigApp':
        # Process COMMUNICATION section
        instances = {
            name: CommunicationInstance(**instance_data)
            for name, instance_data in data['COMMUNICATION']['INSTANCES'].items()
        }
        
        local_params = LocalParams(**data['COMMUNICATION']['LOCAL_PARAMS'])
        
        params_data = data['COMMUNICATION']['PARAMS'].copy()
        params_data['CONFIG_CHANNEL'] = ChannelConfig(**params_data['CONFIG_CHANNEL'])
        params_data['CTRL_CHANNEL'] = ChannelConfig(**params_data['CTRL_CHANNEL'])
        params_data['NOTIF_CHANNEL'] = ChannelConfig(**params_data['NOTIF_CHANNEL'])
        params_data['PAYLOADS_CHANNEL'] = ChannelConfig(**params_data['PAYLOADS_CHANNEL'])
        params = CommunicationParams(**params_data)
        
        communication = Communication(
            INSTANCES=instances,
            LOCAL_PARAMS=local_params,
            PARAMS=params,
            TYPE=data['COMMUNICATION']['TYPE']
        )

        # Process FILE_UPLOAD section
        config_uploader = ConfigUploader(**data['FILE_UPLOAD']['CONFIG_UPLOADER'])
        file_upload = FileUpload(
            CONFIG_UPLOADER=config_uploader,
            TYPE=data['FILE_UPLOAD']['TYPE']
        )

        return cls(
            COMMUNICATION=communication,
            FILE_UPLOAD=file_upload,
            PAYLOAD_TYPE=data['PAYLOAD_TYPE'],
            SECONDS_HEARTBEAT=data['SECONDS_HEARTBEAT'],
            SERVING_IN_PROCESS=data['SERVING_IN_PROCESS']
        ) 