#!/usr/bin/env python3
"""SSH Frequency controller for remote Linux systems."""

import os
import subprocess
from typing import List, Optional
import paramiko


class SSHFrequencyController:
    """Control CPU/GPU frequencies on remote Linux system via SSH."""
    
    def __init__(self, host: str, port: int = 22, user: str = None, password: str = None, key_path: str = None):
        """Initialize SSH frequency controller.
        
        Args:
            host: Remote host IP or hostname
            port: SSH port (default: 22)
            user: SSH username (default: current user)
            password: SSH password (optional)
            key_path: Path to SSH private key (optional)
        """
        self.host = host
        self.port = port
        self.user = user or os.getenv('USER', 'user')
        self.password = password
        self.key_path = key_path
        self.remote_id = f"{self.user}@{self.host}"
        
        # Path to the controller script (will be uploaded to remote)
        self.local_script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "scripts", "linux_freq_controller.sh"
        )
        self.remote_script_path = "/tmp/linux_freq_controller.sh"
        
        self.has_sudo = False  # Will be checked
        self.is_available = False  # Will be set after verification
        self.cpu_count = 0
        
        # Upload script and verify availability
        self._upload_script()
        self._verify_availability()
    
    def _upload_script(self):
        """Upload frequency controller script to remote system."""
        # Use paramiko if password or key is provided
        if self.password or self.key_path:
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_kwargs = {
                    'hostname': self.host,
                    'port': self.port,
                    'username': self.user,
                    'timeout': 10,
                    'allow_agent': False,
                    'look_for_keys': False
                }
                
                if self.password:
                    connect_kwargs['password'] = self.password
                
                if self.key_path:
                    connect_kwargs['key_filename'] = self.key_path
                
                client.connect(**connect_kwargs)
                
                sftp = client.open_sftp()
                sftp.put(self.local_script_path, self.remote_script_path)
                sftp.close()
                client.close()
                
                # Make it executable
                self._run_ssh_command("chmod +x " + self.remote_script_path, timeout=2)
                return
                
            except Exception as e:
                print(f"⚠️  Error uploading script (paramiko): {e}")
                return

        try:
            # Upload script to /tmp
            result = subprocess.run(
                ["scp", "-P", str(self.port), 
                 self.local_script_path, 
                 f"{self.remote_id}:{self.remote_script_path}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Make it executable
                self._run_ssh_command("chmod +x " + self.remote_script_path, timeout=2)
            else:
                print(f"⚠️  Failed to upload frequency controller script: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️  Error uploading script: {e}")
    
    def _verify_availability(self):
        """Verify that frequency control is available on remote system.
        
        Checks:
        1. Sudo access (sudo -n true)
        2. Script exists and is executable
        3. Can read CPU frequency info
        """
        try:
            # Quick test: try to get CPU governor (requires sudo for setting)
            # Use short timeout (2s) for fast failure
            result = self._run_ssh_command(
                f"bash {self.remote_script_path} get_cpu_governor",
                timeout=2
            )
            
            if result and result not in ["", "ERROR:", "N/A"]:
                # Check if we have passwordless sudo for frequency control
                self.has_sudo = self.check_has_passwordless_sudo(
                    self.host, self.port, self.user, self.password, self.key_path
                )
                
                # Script works, mark as available
                self.is_available = True
                
                # Get full device info
                self._init_device_info()
                
                if not self.has_sudo:
                    print(f"⚠️  SSH frequency control available but requires passwordless sudo")
                    print(f"    Run 'sudo visudo' on {self.host} and add:")
                    print(f"    {self.user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/devices/system/cpu/*/cpufreq/*")
                    print(f"    {self.user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/device/tile*/gt*/freq*/*")
                    print(f"    {self.user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/gt_*_freq_mhz")
            else:
                # No cpufreq support or script not working
                self.has_sudo = False
                self.is_available = False
                print(f"⚠️  SSH frequency control unavailable on {self.host} (no cpufreq or script error)")
                
        except Exception as e:
            self.has_sudo = False
            self.is_available = False
            print(f"⚠️  SSH frequency control unavailable: {e}")
    
    def _init_device_info(self):
        """Get device information like CPU count (called after verification)."""
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all", timeout=3)
        if result:
            for line in result.split('\n'):
                if line.startswith('CPU Count:'):
                    try:
                        self.cpu_count = int(line.split(':')[1].strip())
                    except:
                        self.cpu_count = 0
    
    def _run_ssh_command(self, command: str, timeout: int = 5) -> Optional[str]:
        """Run command on remote system via SSH.
        
        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds (default: 5)
            
        Returns:
            Command output or None if failed
        """
        # Use paramiko if password or key is provided
        if self.password or self.key_path:
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_kwargs = {
                    'hostname': self.host,
                    'port': self.port,
                    'username': self.user,
                    'timeout': timeout,
                    'allow_agent': False,
                    'look_for_keys': False
                }
                
                if self.password:
                    connect_kwargs['password'] = self.password
                
                if self.key_path:
                    connect_kwargs['key_filename'] = self.key_path
                
                client.connect(**connect_kwargs)
                
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                output = stdout.read().decode('utf-8').strip()
                client.close()
                return output
                
            except Exception as e:
                print(f"⚠️  Error running SSH command (paramiko): {e}")
                return None

        try:
            result = subprocess.run(
                ["ssh", "-p", str(self.port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 self.remote_id, 
                 command],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
                
        except subprocess.TimeoutExpired:
            print(f"⚠️  SSH command timeout (>{timeout}s)")
            return None
        except Exception as e:
            print(f"⚠️  Error running SSH command: {e}")
            return None
    
    def get_available_cpu_governors(self) -> List[str]:
        """Get list of available CPU governors."""
        if not self.is_available:
            return []
            
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Available Governors:'):
                    governors = line.split(':', 1)[1].strip()
                    if governors != "N/A":
                        return governors.split()
        return []
    
    def get_current_cpu_governor(self, cpu_id: int = 0) -> Optional[str]:
        """Get current CPU governor."""
        if not self.is_available:
            return None
            
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Current Governor:'):
                    governor = line.split(':', 1)[1].strip()
                    return governor if governor != "N/A" else None
        return None
    
    def set_cpu_governor(self, governor: str, cpu_id: Optional[int] = None) -> bool:
        """Set CPU governor for all CPUs.
        
        Args:
            governor: Governor name (e.g., "performance", "powersave")
            cpu_id: Ignored (always sets all CPUs)
            
        Returns:
            True if successful
        """
        if not self.is_available or not self.has_sudo:
            print("⚠️  Cannot set governor: no sudo access or not available")
            return False
            
        result = self._run_ssh_command(
            f"bash {self.remote_script_path} set_cpu_governor {governor}",
            timeout=10
        )
        return result is not None and result.startswith("OK:")
    
    def set_cpu_performance_mode(self) -> bool:
        """Set CPU to performance mode (max frequency)."""
        return self.set_cpu_governor('performance')
    
    def set_cpu_powersave_mode(self) -> bool:
        """Set CPU to powersave mode."""
        return self.set_cpu_governor('powersave')
    
    def get_available_cpu_epp(self) -> List[str]:
        """Get list of available CPU EPP preferences."""
        if not self.is_available:
            return []
            
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Available EPP:'):
                    epp = line.split(':', 1)[1].strip()
                    if epp != "N/A":
                        return epp.split()
        return []
    
    def get_current_cpu_epp(self, cpu_id: int = 0) -> Optional[str]:
        """Get current CPU EPP preference."""
        if not self.is_available:
            return None
            
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Current EPP:'):
                    epp = line.split(':', 1)[1].strip()
                    return epp if epp != "N/A" else None
        return None
    
    def set_cpu_epp(self, epp: str, cpu_id: Optional[int] = None) -> bool:
        """Set CPU EPP preference for all CPUs.
        
        Args:
            epp: EPP name (e.g., "performance", "balance_performance", "default")
            cpu_id: Ignored (always sets all CPUs)
            
        Returns:
            True if successful
        """
        if not self.is_available or not self.has_sudo:
            print("⚠️  Cannot set EPP: no sudo access or not available")
            return False
            
        result = self._run_ssh_command(
            f"bash {self.remote_script_path} set_cpu_epp {epp}",
            timeout=10
        )
        return result is not None and result.startswith("OK:")
    
    def get_cpu_freq_range(self, cpu_id: int = 0) -> dict:
        """Get min/max frequency range for CPUs.
        
        Returns:
            dict with keys: hw_min, hw_max, scaling_min, scaling_max (all in MHz)
        """
        if not self.is_available:
            return {}
            
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('CPU Freq Range:'):
                    freq_info = line.split(':', 1)[1].strip()
                    if freq_info == "N/A":
                        return {}
                    
                    # Parse: HW_MIN:300 HW_MAX:5000 SCALING_MIN:800 SCALING_MAX:5000
                    freq_dict = {}
                    for part in freq_info.split():
                        if ':' in part:
                            key, val = part.split(':')
                            freq_dict[key.lower()] = int(val)
                    
                    return {
                        'hardware_min': freq_dict.get('hw_min', 0),
                        'hardware_max': freq_dict.get('hw_max', 0),
                        'scaling_min': freq_dict.get('scaling_min', 0),
                        'scaling_max': freq_dict.get('scaling_max', 0)
                    }
        return {}
    
    def set_cpu_freq_range(self, min_mhz: int, max_mhz: int, cpu_id: Optional[int] = None) -> bool:
        """Set CPU frequency range for all CPUs.
        
        Args:
            min_mhz: Minimum frequency in MHz
            max_mhz: Maximum frequency in MHz
            cpu_id: Ignored (always sets all CPUs)
            
        Returns:
            True if successful
        """
        if not self.is_available or not self.has_sudo:
            print("⚠️  Cannot set frequency: no sudo access or not available")
            return False
            
        result = self._run_ssh_command(
            f"bash {self.remote_script_path} set_cpu_freq_range {min_mhz} {max_mhz}",
            timeout=10
        )
        return result is not None and result.startswith("OK:")
    
    def get_gpu_freq_range(self) -> dict:
        """Get min/max frequency range for GPU.
        
        Returns:
            dict with keys: hardware_min, hardware_max, scaling_min, scaling_max (all in MHz)
        """
        if not self.is_available:
            return {}
            
        result = self._run_ssh_command(f"bash {self.remote_script_path} get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('GPU Freq Range:'):
                    freq_info = line.split(':', 1)[1].strip()
                    if freq_info == "N/A":
                        return {}
                    
                    # Parse: TYPE:intel_xe HW_MIN:300 HW_MAX:2050 SCALING_MIN:300 SCALING_MAX:2050
                    freq_dict = {}
                    for part in freq_info.split():
                        if ':' in part:
                            key, val = part.split(':')
                            if key == 'TYPE':
                                freq_dict['type'] = val
                            else:
                                freq_dict[key.lower()] = int(val)
                    
                    return {
                        'type': freq_dict.get('type', 'unknown'),
                        'hardware_min': freq_dict.get('hw_min', 0),
                        'hardware_max': freq_dict.get('hw_max', 0),
                        'scaling_min': freq_dict.get('scaling_min', 0),
                        'scaling_max': freq_dict.get('scaling_max', 0)
                    }
        return {}
    
    def set_gpu_freq_range(self, min_mhz: int, max_mhz: int) -> bool:
        """Set GPU frequency range.
        
        Args:
            min_mhz: Minimum frequency in MHz
            max_mhz: Maximum frequency in MHz
            
        Returns:
            True if successful
        """
        if not self.is_available or not self.has_sudo:
            print("⚠️  Cannot set GPU frequency: no sudo access or not available")
            return False
            
        result = self._run_ssh_command(
            f"bash {self.remote_script_path} set_gpu_freq_range {min_mhz} {max_mhz}",
            timeout=10
        )
        return result is not None and result.startswith("OK:")
    
    def get_all_info(self) -> dict:
        """Get all frequency control information.
        
        Returns:
            dict with cpu_count, governors, current_governor, cpu_freq, gpu_freq
        """
        if not self.is_available:
            return {
                'available': False,
                'has_sudo': False,
                'cpu_count': 0,
                'governors': [],
                'current_governor': None,
                'epp_available': [],
                'current_epp': None,
                'cpu_freq': {},
                'gpu_freq': {}
            }
        
        return {
            'available': self.is_available,
            'has_sudo': self.has_sudo,
            'cpu_count': self.cpu_count,
            'governors': self.get_available_cpu_governors(),
            'current_governor': self.get_current_cpu_governor(),
            'epp_available': self.get_available_cpu_epp(),
            'current_epp': self.get_current_cpu_epp(),
            'cpu_freq': self.get_cpu_freq_range(),
            'gpu_freq': self.get_gpu_freq_range()
        }
    
    @staticmethod
    def setup_passwordless_sudo(host: str, port: int, user: str, password: str) -> tuple[bool, str]:
        """Setup passwordless sudo using provided password.
        
        This creates a sudoers file that allows the user to modify frequency
        control files without entering a password.
        
        Args:
            host: Remote host IP or hostname
            port: SSH port
            user: SSH username
            password: User's sudo password (only used for setup, not stored)
            
        Returns:
            (success: bool, message: str) - Success status and message
        """
        try:
            # Create sudoers rules
            sudoers_content = f"""# Monitor Tool - Frequency Control
# Allow {user} to modify CPU/GPU frequency settings without password
{user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/devices/system/cpu/*/cpufreq/*
{user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/device/tile*/gt*/freq*/*
{user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/gt_*_freq_mhz
"""
            
            # Connect via paramiko for better password/sudo handling
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                client.connect(host, port=port, username=user, password=password, timeout=10, 
                             allow_agent=False, look_for_keys=False)
            except paramiko.AuthenticationException:
                return False, "Authentication failed. Please check your password."
            except Exception as e:
                return False, f"Connection failed: {e}"
            
            # Create temporary file with sudoers content
            temp_file = "/tmp/monitor-tool-sudoers"
            
            # Step 1: Create temp file
            stdin, stdout, stderr = client.exec_command(f"cat > {temp_file}")
            stdin.write(sudoers_content)
            stdin.channel.shutdown_write()
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                client.close()
                return False, f"Failed to create temp file: {stderr.read().decode()}"
            
            # Step 2: Move to sudoers.d with sudo (using password via stdin)
            cmd = f"sudo -S mv {temp_file} /etc/sudoers.d/monitor-tool"
            stdin, stdout, stderr = client.exec_command(cmd)
            stdin.write(password + '\n')
            stdin.flush()
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                error_msg = stderr.read().decode()
                client.close()
                # Clean up temp file
                if "incorrect password" in error_msg.lower():
                    return False, "Incorrect sudo password."
                return False, f"Failed to install sudoers file: {error_msg}"
            
            # Step 3: Set correct ownership (must be root)
            cmd = "sudo -S chown root:root /etc/sudoers.d/monitor-tool"
            stdin, stdout, stderr = client.exec_command(cmd)
            stdin.write(password + '\n')
            stdin.flush()
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                client.close()
                return False, f"Failed to set ownership: {stderr.read().decode()}"
            
            # Step 4: Set correct permissions
            cmd = "sudo -S chmod 440 /etc/sudoers.d/monitor-tool"
            stdin, stdout, stderr = client.exec_command(cmd)
            stdin.write(password + '\n')
            stdin.flush()
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                client.close()
                return False, f"Failed to set permissions: {stderr.read().decode()}"
            
            client.close()
            
            # Step 5: Verify setup worked (test actual frequency control)
            # Wait a moment for sudoers to be reloaded
            import time
            time.sleep(1)
            
            # Test by temporarily changing governor and changing it back
            # 1. Read current governor
            result = subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return True, "Setup completed. Unable to verify (no cpufreq support?)."
            
            original_governor = result.stdout.strip()
            
            # 2. Get available governors
            result = subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return True, "Setup completed. Unable to verify."
            
            available_governors = result.stdout.strip().split()
            if len(available_governors) < 2:
                return True, "Setup completed. Unable to verify (only one governor available)."
            
            # 3. Pick a different governor to test
            test_governor = None
            for gov in available_governors:
                if gov != original_governor:
                    test_governor = gov
                    break
            
            if not test_governor:
                return True, "Setup completed. Unable to verify."
            
            # 4. Try to change to test governor
            test_cmd = f"echo '{test_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
            result = subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 test_cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return True, "Setup completed. Please reconnect to verify."
            
            # 5. Restore original governor
            restore_cmd = f"echo '{original_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
            subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 restore_cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return True, "Passwordless sudo configured and verified successfully!"
            
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    @staticmethod
    def check_has_passwordless_sudo(host: str, port: int, user: str, password: str = None, key_path: str = None) -> bool:
        """Check if passwordless sudo is already configured.
        
        Args:
            host: Remote host IP or hostname
            port: SSH port
            user: SSH username
            password: SSH password (optional)
            key_path: Path to SSH private key (optional)
            
        Returns:
            True if passwordless sudo is available for frequency control
        """
        try:
            # Use paramiko if password or key is provided
            if password or key_path:
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    connect_kwargs = {
                        'hostname': host,
                        'port': port,
                        'username': user,
                        'timeout': 5,
                        'allow_agent': False,
                        'look_for_keys': False
                    }
                    
                    if password:
                        connect_kwargs['password'] = password
                    
                    if key_path:
                        connect_kwargs['key_filename'] = key_path
                    
                    client.connect(**connect_kwargs)
                    
                    # 1. Read current governor
                    stdin, stdout, stderr = client.exec_command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null")
                    original_governor = stdout.read().decode('utf-8').strip()
                    
                    if not original_governor:
                        client.close()
                        return False
                    
                    # 2. Get available governors
                    stdin, stdout, stderr = client.exec_command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null")
                    available_governors = stdout.read().decode('utf-8').strip().split()
                    
                    if len(available_governors) < 2:
                        # Only one governor, can't really test switching
                        # Fallback: try to write same value back
                        test_cmd = f"echo '{original_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
                        stdin, stdout, stderr = client.exec_command(test_cmd)
                        exit_code = stdout.channel.recv_exit_status()
                        client.close()
                        return exit_code == 0
                    
                    # 3. Pick a different governor to test
                    test_governor = None
                    for gov in available_governors:
                        if gov != original_governor:
                            test_governor = gov
                            break
                    
                    if not test_governor:
                        client.close()
                        return False
                    
                    # 4. Try to change to test governor (using sudo -n)
                    test_cmd = f"echo '{test_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
                    stdin, stdout, stderr = client.exec_command(test_cmd)
                    exit_code = stdout.channel.recv_exit_status()
                    
                    if exit_code != 0:
                        client.close()
                        return False
                    
                    # 5. Restore original governor
                    restore_cmd = f"echo '{original_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
                    client.exec_command(restore_cmd)
                    
                    client.close()
                    return True
                    
                except Exception as e:
                    print(f"⚠️  Error checking sudo (paramiko): {e}")
                    return False

            # Fallback to subprocess if no password/key provided (assumes ssh agent or passwordless ssh)
            # 1. Read current governor
            result = subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return False  # No cpufreq support
            
            original_governor = result.stdout.strip()
            
            # 2. Get available governors
            result = subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False
            
            available_governors = result.stdout.strip().split()
            if len(available_governors) < 2:
                # Only one governor, can't really test switching
                # Fallback: try to write same value back
                test_cmd = f"echo '{original_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
                result = subprocess.run(
                    ["ssh", "-p", str(port), 
                     "-o", "StrictHostKeyChecking=no",
                     "-o", "ConnectTimeout=5",
                     f"{user}@{host}", 
                     test_cmd],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0
            
            # 3. Pick a different governor to test
            test_governor = None
            for gov in available_governors:
                if gov != original_governor:
                    test_governor = gov
                    break
            
            if not test_governor:
                return False
            
            # 4. Try to change to test governor
            test_cmd = f"echo '{test_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
            result = subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 test_cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False
            
            # 5. Restore original governor
            restore_cmd = f"echo '{original_governor}' | sudo -n tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1"
            subprocess.run(
                ["ssh", "-p", str(port), 
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{host}", 
                 restore_cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return True
            
        except:
            return False
