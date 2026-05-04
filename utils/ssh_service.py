import os
import subprocess
from typing import List, Tuple, Optional
from dataclasses import dataclass

SSH_COMMAND_TIMEOUT = 120
WINDOWS_CREATE_NO_WINDOW = 0x08000000


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

    def _popen_kwargs(self):
        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "universal_newlines": True,
        }
        if os.name == 'nt':
            kwargs["creationflags"] = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                WINDOWS_CREATE_NO_WINDOW,
            )
        return kwargs

    def execute_command(
        self,
        command: List[str],
        sudo: bool = False,
        timeout: int = SSH_COMMAND_TIMEOUT,
    ) -> Tuple[str, str, int]:
        """Execute a command on the remote host.
        
        Args:
            command: Command to execute as list of arguments
            sudo: Whether the command requires sudo
            timeout: Maximum command duration in seconds
            
        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        if not self.ssh_command:
            raise RuntimeError("SSH not configured")

        full_command = self.ssh_command.copy()
        stdin_input = None
        
        if sudo and self.config and self.config.password:
            full_command.extend(['sudo', '-S'])
            full_command.extend(command)
            stdin_input = self.config.password + '\n'
        else:
            full_command.extend(command)

        popen_kwargs = self._popen_kwargs()
        if stdin_input is not None:
            popen_kwargs["stdin"] = subprocess.PIPE
        process = subprocess.Popen(full_command, **popen_kwargs)

        try:
            stdout, stderr = process.communicate(input=stdin_input, timeout=timeout)
            return stdout, stderr, process.returncode
        except subprocess.TimeoutExpired as exc:
            process.kill()
            stdout, stderr = process.communicate()
            timeout_message = f"SSH command timed out after {exc.timeout} seconds: {' '.join(full_command)}"
            if stderr:
                stderr = f"{stderr}\n{timeout_message}"
            else:
                stderr = timeout_message
            return stdout, stderr, 124

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
