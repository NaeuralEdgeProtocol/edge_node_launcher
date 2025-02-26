import subprocess
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class SSHConfig:
    host: str
    user: str
    password: Optional[str] = None
    private_key: Optional[str] = None
    ssh_args: Optional[List[str]] = None

class SSHService:
    def __init__(self):
        self.ssh_command: List[str] = []
        self.config: Optional[SSHConfig] = None

    def configure(self, config: SSHConfig) -> None:
        """Configure SSH connection parameters."""
        self.config = config
        cmd = ['ssh']
        
        if config.ssh_args:
            cmd.extend(config.ssh_args)
            
        if config.private_key:
            cmd.extend(['-i', config.private_key])
            
        cmd.extend([f'{config.user}@{config.host}'])
        self.ssh_command = cmd

    def clear_configuration(self) -> None:
        """Clear SSH configuration."""
        self.ssh_command = []
        self.config = None

    def execute_command(self, command: List[str], sudo: bool = False) -> Tuple[str, str, int]:
        """Execute a command on the remote host.
        
        Args:
            command: Command to execute as list of arguments
            sudo: Whether the command requires sudo
            
        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        if not self.ssh_command:
            raise RuntimeError("SSH not configured")

        full_command = self.ssh_command.copy()
        
        if sudo and self.config and self.config.password:
            full_command.extend(['sudo', '-S'])
            full_command.extend(command)
            
            process = subprocess.Popen(
                full_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate(input=self.config.password + '\n')
        else:
            full_command.extend(command)
            
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()

        return stdout, stderr, process.returncode

    def check_connection(self, timeout: int = 3) -> bool:
        """Check if SSH connection can be established.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            cmd = self.ssh_command + ['-o', f'ConnectTimeout={timeout}', 'exit']
            process = subprocess.run(cmd, capture_output=True, timeout=timeout)
            return process.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
        except Exception:
            return False 