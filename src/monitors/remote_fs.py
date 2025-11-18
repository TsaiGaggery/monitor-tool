"""Remote file system wrapper for SSH.

Provides file system operations over SSH to allow local monitors
to work transparently with remote systems.
"""

import paramiko
from typing import Optional, List
import io


class RemoteFileSystem:
    """Wrapper to access remote file system via SSH."""
    
    def __init__(self, ssh_client: paramiko.SSHClient, sudo_password: Optional[str] = None, sudo_nopasswd: bool = False):
        """Initialize remote file system.
        
        Args:
            ssh_client: Connected SSH client
            sudo_password: Password for sudo commands
            sudo_nopasswd: Whether sudo requires no password
        """
        self.ssh = ssh_client
        self.sudo_password = sudo_password
        self.sudo_nopasswd = sudo_nopasswd
    
    def read_file(self, path: str, use_sudo: bool = False) -> str:
        """Read a file from remote system.
        
        Args:
            path: File path on remote system
            use_sudo: Whether to use sudo
            
        Returns:
            File contents as string
        """
        if use_sudo:
            if self.sudo_nopasswd:
                command = f"sudo cat {path}"
            else:
                command = f"sudo -S cat {path}"
        else:
            command = f"cat {path}"
        
        stdin, stdout, stderr = self.ssh.exec_command(command, timeout=5)
        
        if use_sudo and not self.sudo_nopasswd:
            stdin.write(self.sudo_password + '\n')
            stdin.flush()
        
        return stdout.read().decode('utf-8')
    
    def exists(self, path: str) -> bool:
        """Check if file or directory exists.
        
        Args:
            path: Path to check
            
        Returns:
            True if exists
        """
        stdin, stdout, stderr = self.ssh.exec_command(f"test -e {path} && echo 'exists' || echo 'not_exists'", timeout=5)
        result = stdout.read().decode('utf-8').strip()
        return result == 'exists'
    
    def glob(self, pattern: str, use_sudo: bool = False) -> List[str]:
        """Find files matching pattern.
        
        Args:
            pattern: Glob pattern
            use_sudo: Whether to use sudo
            
        Returns:
            List of matching file paths
        """
        if use_sudo:
            if self.sudo_nopasswd:
                command = f"sudo ls -1 {pattern} 2>/dev/null || true"
            else:
                command = f"sudo -S ls -1 {pattern} 2>/dev/null || true"
        else:
            command = f"ls -1 {pattern} 2>/dev/null || true"
        
        stdin, stdout, stderr = self.ssh.exec_command(command, timeout=5)
        
        if use_sudo and not self.sudo_nopasswd:
            stdin.write(self.sudo_password + '\n')
            stdin.flush()
        
        result = stdout.read().decode('utf-8').strip()
        if result:
            return result.split('\n')
        return []
    
    def exec_command(self, command: str, use_sudo: bool = False, timeout: int = 10) -> tuple:
        """Execute command on remote system.
        
        Args:
            command: Command to execute
            use_sudo: Whether to use sudo
            timeout: Command timeout
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        if use_sudo:
            if self.sudo_nopasswd:
                command = f"sudo {command}"
            else:
                command = f"sudo -S {command}"
        
        stdin, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
        
        if use_sudo and not self.sudo_nopasswd:
            stdin.write(self.sudo_password + '\n')
            stdin.flush()
        
        stdout_data = stdout.read().decode('utf-8')
        stderr_data = stderr.read().decode('utf-8')
        exit_code = stdout.channel.recv_exit_status()
        
        return stdout_data, stderr_data, exit_code
