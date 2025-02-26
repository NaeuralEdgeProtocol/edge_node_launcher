import os
import yaml
from pathlib import Path

class AnsibleHostsManager:
    def __init__(self):
        self.hosts_file = os.path.expanduser('~/.ansible/collections/ansible_collections/vitalii_t12/multi_node_launcher/hosts.yml')
        self.hosts = {}
        self.load_hosts()

    def load_hosts(self):
        """Load hosts from the Ansible hosts file."""
        try:
            if os.path.exists(self.hosts_file):
                with open(self.hosts_file, 'r') as f:
                    config = yaml.safe_load(f)
                    if config and 'all' in config and 'children' in config['all'] and 'gpu_nodes' in config['all']['children']:
                        self.hosts = config['all']['children']['gpu_nodes'].get('hosts', {})
        except Exception as e:
            print(f"Error loading hosts file: {e}")
            self.hosts = {}

    def get_host_list(self):
        """Return a list of host names."""
        return list(self.hosts.keys())

    def get_host_config(self, hostname):
        """Get configuration for a specific host."""
        return self.hosts.get(hostname, {})

    def get_ssh_command_prefix(self, hostname):
        """Generate SSH command prefix for a host."""
        host_config = self.get_host_config(hostname)
        if not host_config:
            return None

        cmd_parts = ['ssh']
        
        # Add common SSH arguments
        if 'ansible_ssh_common_args' in host_config:
            cmd_parts.extend(host_config['ansible_ssh_common_args'].split())

        # Add private key if specified
        if 'ansible_ssh_private_key_file' in host_config:
            key_path = os.path.expanduser(host_config['ansible_ssh_private_key_file'])
            cmd_parts.extend(['-i', key_path])

        # Add user and host
        user = host_config.get('ansible_user', '')
        host = host_config.get('ansible_host', '')
        if user and host:
            cmd_parts.append(f"{user}@{host}")
        elif host:
            cmd_parts.append(host)
        else:
            return None

        return cmd_parts 