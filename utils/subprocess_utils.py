"""
Subprocess Utilities

This module provides helper functions to run subprocess commands
without showing terminal windows on Windows.
"""

import os
import sys
import subprocess
from typing import List, Dict, Any, Optional, Union, Tuple

FORCE_EXIT_TIMEOUT_SECONDS = 5


def run_process_no_window(
    cmd: Union[str, List[str]],
    shell: bool = False,
    capture_output: bool = False,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run a subprocess without showing a terminal window on Windows.
    
    Args:
        cmd: Command to run (string or list of strings)
        shell: Whether to use shell execution
        capture_output: Whether to capture stdout/stderr
        cwd: Working directory
        env: Environment variables
        timeout: Timeout in seconds
        check: Whether to raise an exception on non-zero exit
        
    Returns:
        CompletedProcess instance with results
    """
    # Initialize kwargs for subprocess.run
    kwargs = {
        "shell": shell,
        "cwd": cwd,
        "env": env,
        "timeout": timeout,
    }
    
    # Set up output capture if requested
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["universal_newlines"] = True  # Return strings instead of bytes
    
    # Windows-specific: hide console window
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        # STARTF_USESHOWWINDOW: Tells Windows to use the wShowWindow flag
        # SW_HIDE: Hides the window and activates another window
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
        # CREATE_NO_WINDOW flag prevents command prompt window from appearing
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    
    # Run the process
    result = subprocess.run(cmd, **kwargs)
    
    # Check if requested
    if check and result.returncode != 0:
        error_message = f"Command '{cmd}' returned non-zero exit status {result.returncode}"
        if capture_output:
            error_message += f"\nStdout: {result.stdout}\nStderr: {result.stderr}"
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    
    return result


def terminate_process_by_pid(pid: int, timeout: int = FORCE_EXIT_TIMEOUT_SECONDS) -> bool:
    """Request OS-level termination for a process without opening a console window."""
    try:
        if os.name == 'nt':
            run_process_no_window(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True,
                timeout=timeout,
            )
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
