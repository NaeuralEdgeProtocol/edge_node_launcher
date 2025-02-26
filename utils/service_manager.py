from typing import Optional, Tuple
from .ssh_service import SSHService

class ServiceManager:
    """Manages Edge Node service operations."""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        
    def restart_service(self, service_name: str) -> Tuple[bool, Optional[str]]:
        """Restart a service on the remote host.
        
        Args:
            service_name: Name of the service to restart
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            stdout, stderr, return_code = self.ssh_service.execute_command(
                ['service', service_name, 'restart'],
                sudo=True
            )
            
            if return_code != 0:
                error_msg = stderr if stderr else stdout
                return False, f"Service restart failed: {error_msg}"
                
            return True, None
            
        except Exception as e:
            return False, f"Service restart failed: {str(e)}"
    
    def get_service_status(self, service_name: str) -> Tuple[bool, Optional[str]]:
        """Get the status of a service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            Tuple of (is_running, error_message)
        """
        try:
            stdout, stderr, return_code = self.ssh_service.execute_command(
                ['systemctl', 'is-active', service_name],
                sudo=True
            )
            
            if return_code != 0:
                return False, stderr if stderr else "Service not running"
                
            return stdout.strip() == "active", None
            
        except Exception as e:
            return False, f"Failed to get service status: {str(e)}" 