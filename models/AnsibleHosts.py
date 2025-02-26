import os
import yaml
from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path

@dataclass
class AnsibleHost:
    name: str
    ansible_host: str
    ansible_user: str
    ansible_become_password: Optional[str]
    ansible_connection: str
    ansible_ssh_private_key_file: Optional[str]
    ansible_ssh_pass: Optional[str]
    ansible_ssh_common_args: Optional[str]

class AnsibleHostsManager:
    def __init__(self):
        self.hosts_file = os.path.expanduser("~/.ansible/collections/ansible_collections/vitalii_t12/multi_node_launcher/hosts.yml")
        self.hosts: Dict[str, AnsibleHost] = {}
        self.load_hosts()

    def load_hosts(self) -> None:
        """Load hosts from the Ansible hosts file."""
        try:
            with open(self.hosts_file, 'r') as f:
                config = yaml.safe_load(f)
                
            if config and 'all' in config and 'children' in config['all']:
                for group in config['all']['children'].values():
                    if 'hosts' in group:
                        for host_name, host_config in group['hosts'].items():
                            self.hosts[host_name] = AnsibleHost(
                                name=host_name,
                                ansible_host=host_config.get('ansible_host', ''),
                                ansible_user=host_config.get('ansible_user', ''),
                                ansible_become_password=host_config.get('ansible_become_password'),
                                ansible_connection=host_config.get('ansible_connection', 'ssh'),
                                ansible_ssh_private_key_file=host_config.get('ansible_ssh_private_key_file'),
                                ansible_ssh_pass=host_config.get('ansible_ssh_pass'),
                                ansible_ssh_common_args=host_config.get('ansible_ssh_common_args')
                            )
        except Exception as e:
            print(f"Error loading hosts file: {e}")
            self.hosts = {}

    def get_host_names(self) -> list[str]:
        """Get list of available host names."""
        return list(self.hosts.keys())

    def get_host(self, host_name: str) -> Optional[AnsibleHost]:
        """Get host configuration by name."""
        return self.hosts.get(host_name)

    def get_ssh_command(self, host_name: str) -> Optional[str]:
        """Generate SSH command for the given host."""
        host = self.get_host(host_name)
        if not host:
            return None
        
        cmd = ['ssh']
        
        if host.ansible_ssh_common_args:
            cmd.extend(host.ansible_ssh_common_args.split())
            
        if host.ansible_ssh_private_key_file:
            key_file = os.path.expanduser(host.ansible_ssh_private_key_file)
            cmd.extend(['-i', key_file])
            
        cmd.extend([f'{host.ansible_user}@{host.ansible_host}'])
        
        return ' '.join(cmd) 