from dataclasses import dataclass
from typing import List, Optional

@dataclass
class NodeInfo:
    address: str
    alias: str
    eth_address: str
    version_long: str
    version_short: str
    whitelist: List[str]

    @classmethod
    def from_dict(cls, data: dict) -> 'NodeInfo':
        return cls(
            address=data['address'],
            alias=data.get('alias', ''),
            eth_address=data.get('eth_address', ''),
            version_long=data.get('version_long', ''),
            version_short=data.get('version_short', ''),
            whitelist=data.get('info', {}).get('whitelist', [])
        )

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'alias': self.alias,
            'eth_address': self.eth_address,
            'version_long': self.version_long,
            'version_short': self.version_short,
            'info': {
                'whitelist': self.whitelist
            }
        }