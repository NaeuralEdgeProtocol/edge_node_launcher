from dataclasses import dataclass
from typing import List, Dict


@dataclass
class AllowedAddress:
    address: str
    alias: str

    @classmethod
    def from_dict(cls, data: dict) -> 'AllowedAddress':
        return cls(
            address=data['address'],
            alias=data['alias']
        )

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'alias': self.alias
        }


@dataclass
class AllowedAddressList:
    addresses: List[AllowedAddress]

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'AllowedAddressList':
        """Convert from API response format {address: alias, ...} to AllowedAddressList"""
        addresses = [
            AllowedAddress(address=addr, alias=alias)
            for addr, alias in data.items()
        ]
        return cls(addresses=addresses)

    def to_batch_format(self) -> List[dict]:
        """Convert to format expected by update_allowed_batch"""
        return [addr.to_dict() for addr in self.addresses] 