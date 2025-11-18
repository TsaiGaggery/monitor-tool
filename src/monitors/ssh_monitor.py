"""SSH Monitor - Remote Linux System Monitoring via SSH
Monitors remote Linux systems using SSH connection with sudo support.
"""

import paramiko
import json
import time
from typing import Dict, Optional, Tuple
import getpass


class SSHMonitor:
    """Monitor remote Linux system via SSH."""
    
    def __init__(self, host: str, username: str, port: int = 22, 
                 password: Optional[str] = None, key_path: Optional[str] = None):
        """Initialize SSH monitor.
        
        Args:
            host: Remote host address
            username: SSH username
            port: SSH port (default: 22)
            password: SSH password (optional, will prompt if needed)
            key_path: Path to SSH private key (optional)
        """
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.key_path = key_path
        
        self.ssh_client = None
        self.sudo_password = None  # May be different from SSH password
        self.sudo_nopasswd = None  # Cache whether sudo needs password
        
        # Latest monitoring data
        self._cpu_info = self._empty_cpu_info()
        self._memory_info = self._empty_memory_info()
        self._gpu_info = self._empty_gpu_info()
        self._network_info = self._empty_network_info()
        self._disk_info = self._empty_disk_info()
        
        # Previous data for delta calculations
        self._previous_data = {}
    
    def connect(self) -> bool:
        """Connect to remote Linux system via SSH.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Try to connect with provided credentials
            connect_kwargs = {
                'hostname': self.host,
                'username': self.username,
                'port': self.port,
                'timeout': 10
            }
            
            # Use SSH key if provided
            if self.key_path:
                connect_kwargs['key_filename'] = self.key_path
            elif self.password:
                connect_kwargs['password'] = self.password
            else:
                # Prompt for password
                self.password = getpass.getpass(f"SSH password for {self.username}@{self.host}: ")
                connect_kwargs['password'] = self.password
            
            self.ssh_client.connect(**connect_kwargs)
            print(f"✅ Connected to {self.host}")
            
            # Check sudo capabilities
            self._check_sudo()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to {self.host}: {e}")
            if self.ssh_client:
                self.ssh_client.close()
            return False
    
    def _check_sudo(self):
        """Check if sudo requires password and cache the result."""
        try:
            # Try sudo without password first
            stdin, stdout, stderr = self.ssh_client.exec_command(
                "sudo -n true 2>&1",
                timeout=5
            )
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                self.sudo_nopasswd = True
                print("✅ Sudo available without password (NOPASSWD)")
            else:
                self.sudo_nopasswd = False
                # Try with SSH password
                stdin, stdout, stderr = self.ssh_client.exec_command("sudo -S true")
                stdin.write(self.password + '\n')
                stdin.flush()
                exit_code = stdout.channel.recv_exit_status()
                
                if exit_code == 0:
                    self.sudo_password = self.password
                    print("✅ Sudo works with SSH password")
                else:
                    # Need different sudo password
                    self.sudo_password = getpass.getpass(f"Sudo password for {self.username}@{self.host}: ")
                    print("⚠️  Sudo requires different password")
                    
        except Exception as e:
            print(f"⚠️  Sudo check failed: {e}")
            self.sudo_nopasswd = False
    
    def _exec_command(self, command: str, use_sudo: bool = False, timeout: int = 10) -> Tuple[str, str, int]:
        """Execute command on remote system.
        
        Args:
            command: Command to execute
            use_sudo: Whether to use sudo
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        if not self.ssh_client:
            return "", "Not connected", 1
        
        try:
            if use_sudo:
                if self.sudo_nopasswd:
                    # Use sudo without password
                    command = f"sudo {command}"
                else:
                    # Use sudo with password
                    command = f"sudo -S {command}"
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            
            if use_sudo and not self.sudo_nopasswd:
                # Send password if needed
                password = self.sudo_password if self.sudo_password else self.password
                stdin.write(password + '\n')
                stdin.flush()
            
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            return stdout_data, stderr_data, exit_code
            
        except Exception as e:
            return "", str(e), 1
    
    def disconnect(self):
        """Disconnect from remote system."""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            print(f"🔌 Disconnected from {self.host}")
    
    def is_connected(self) -> bool:
        """Check if connected to remote system."""
        if not self.ssh_client:
            return False
        try:
            transport = self.ssh_client.get_transport()
            return transport is not None and transport.is_active()
        except:
            return False
    
    def update_all_info(self):
        """Update all monitoring information from remote system."""
        if not self.is_connected():
            return
        
        # Collect all data in one go to minimize SSH round trips
        current_time = time.time()
        
        # Get CPU info
        self._update_cpu_info()
        
        # Get memory info
        self._update_memory_info()
        
        # Get GPU info (if available)
        self._update_gpu_info()
        
        # Get network info
        self._update_network_info(current_time)
        
        # Get disk info
        self._update_disk_info(current_time)
    
    def _update_cpu_info(self):
        """Update CPU information."""
        # Read /proc/stat for CPU usage
        stdout, _, _ = self._exec_command("cat /proc/stat")
        
        # Read CPU frequency
        freq_out, _, _ = self._exec_command(
            "cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null || echo '0'"
        )
        
        # Read CPU count
        cpu_count_out, _, _ = self._exec_command("nproc")
        
        # Read CPU temperature (may need sudo)
        temp_out, _, _ = self._exec_command(
            "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null",
            use_sudo=True
        )
        
        # Parse CPU stats
        cpu_lines = stdout.strip().split('\n')
        cpu_count = int(cpu_count_out.strip()) if cpu_count_out.strip().isdigit() else 0
        
        # Parse overall CPU stats
        overall_usage = 0
        per_core_usage = []
        
        for line in cpu_lines:
            if line.startswith('cpu '):
                # Overall CPU
                parts = line.split()
                curr_stats = {
                    'user': int(parts[1]),
                    'nice': int(parts[2]),
                    'system': int(parts[3]),
                    'idle': int(parts[4]),
                    'iowait': int(parts[5]) if len(parts) > 5 else 0,
                    'irq': int(parts[6]) if len(parts) > 6 else 0,
                    'softirq': int(parts[7]) if len(parts) > 7 else 0,
                }
                
                if 'cpu_overall' in self._previous_data:
                    overall_usage = self._calculate_cpu_usage(curr_stats, self._previous_data['cpu_overall'])
                
                self._previous_data['cpu_overall'] = curr_stats
                
            elif line.startswith('cpu'):
                # Per-core CPU
                parts = line.split()
                curr_stats = {
                    'user': int(parts[1]),
                    'nice': int(parts[2]),
                    'system': int(parts[3]),
                    'idle': int(parts[4]),
                    'iowait': int(parts[5]) if len(parts) > 5 else 0,
                    'irq': int(parts[6]) if len(parts) > 6 else 0,
                    'softirq': int(parts[7]) if len(parts) > 7 else 0,
                }
                
                core_id = int(parts[0].replace('cpu', ''))
                prev_key = f'cpu{core_id}'
                
                if prev_key in self._previous_data:
                    usage = self._calculate_cpu_usage(curr_stats, self._previous_data[prev_key])
                else:
                    usage = 0
                
                per_core_usage.append(usage)
                self._previous_data[prev_key] = curr_stats
        
        # Parse CPU frequencies
        per_core_freq = []
        if freq_out.strip() and freq_out.strip() != '0':
            for freq_khz in freq_out.strip().split('\n'):
                if freq_khz.strip().isdigit():
                    per_core_freq.append(int(freq_khz.strip()) / 1000)  # Convert to MHz
        
        # Fill with zeros if no frequency data
        if not per_core_freq:
            per_core_freq = [0] * cpu_count
        
        avg_freq = sum(per_core_freq) / len(per_core_freq) if per_core_freq else 0
        
        # Parse temperatures
        temperatures = {}
        if temp_out.strip():
            temp_values = []
            for temp_millideg in temp_out.strip().split('\n'):
                if temp_millideg.strip().isdigit():
                    temp_c = int(temp_millideg.strip()) / 1000.0
                    if 0 < temp_c < 150:  # Sanity check
                        temp_values.append(temp_c)
            
            if temp_values:
                temperatures = {
                    'Thermal': [{
                        'label': 'CPU',
                        'current': max(temp_values),  # Use highest temp
                        'high': 80.0,
                        'critical': 100.0
                    }]
                }
        
        self._cpu_info = {
            'cpu_count': cpu_count,
            'physical_count': cpu_count,  # TODO: Could parse /proc/cpuinfo for actual physical count
            'usage': {
                'total': overall_usage,
                'per_core': per_core_usage
            },
            'frequency': {
                'average': avg_freq,
                'per_core': per_core_freq
            },
            'temperature': temperatures
        }
    
    def _calculate_cpu_usage(self, curr: dict, prev: dict) -> float:
        """Calculate CPU usage percentage from /proc/stat values.
        
        Args:
            curr: Current CPU stats
            prev: Previous CPU stats
            
        Returns:
            CPU usage percentage (0-100)
        """
        if not prev:
            return 0.0
        
        # Calculate deltas
        d_user = curr['user'] - prev['user']
        d_nice = curr['nice'] - prev['nice']
        d_system = curr['system'] - prev['system']
        d_idle = curr['idle'] - prev['idle']
        d_iowait = curr.get('iowait', 0) - prev.get('iowait', 0)
        d_irq = curr.get('irq', 0) - prev.get('irq', 0)
        d_softirq = curr.get('softirq', 0) - prev.get('softirq', 0)
        
        d_active = d_user + d_nice + d_system + d_irq + d_softirq + d_iowait
        d_total = d_active + d_idle
        
        if d_total == 0:
            return 0.0
        
        return (d_active / d_total) * 100.0
    
    def _update_memory_info(self):
        """Update memory information."""
        stdout, _, _ = self._exec_command("cat /proc/meminfo")
        
        # Parse memory info
        mem_info = {}
        for line in stdout.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                # Extract numeric value (in kB)
                value_kb = int(value.strip().split()[0])
                mem_info[key.strip()] = value_kb
        
        # Calculate memory values (convert kB to GB)
        mem_total_gb = mem_info.get('MemTotal', 0) / 1024 / 1024
        mem_free_gb = mem_info.get('MemFree', 0) / 1024 / 1024
        mem_available_gb = mem_info.get('MemAvailable', mem_free_gb * 1024 * 1024) / 1024 / 1024
        mem_buffers_gb = mem_info.get('Buffers', 0) / 1024 / 1024
        mem_cached_gb = mem_info.get('Cached', 0) / 1024 / 1024
        
        mem_used_gb = mem_total_gb - mem_available_gb
        mem_percent = (mem_used_gb / mem_total_gb * 100) if mem_total_gb > 0 else 0
        
        # Swap information
        swap_total_gb = mem_info.get('SwapTotal', 0) / 1024 / 1024
        swap_free_gb = mem_info.get('SwapFree', 0) / 1024 / 1024
        swap_used_gb = swap_total_gb - swap_free_gb
        swap_percent = (swap_used_gb / swap_total_gb * 100) if swap_total_gb > 0 else 0
        
        self._memory_info = {
            'memory': {
                'total': mem_total_gb,
                'used': mem_used_gb,
                'free': mem_free_gb,
                'available': mem_available_gb,
                'percent': mem_percent,
                'speed': 0  # Cannot easily detect from /proc/meminfo
            },
            'swap': {
                'total': swap_total_gb,
                'used': swap_used_gb,
                'free': swap_free_gb,
                'percent': swap_percent
            }
        }
    
    def _update_gpu_info(self):
        """Update GPU information."""
        gpus = []
        
        # Try nvidia-smi first
        stdout, _, exit_code = self._exec_command(
            "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.gr --format=csv,noheader,nounits"
        )
        
        if exit_code == 0 and stdout.strip():
            # Parse NVIDIA GPU data
            for line in stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 6:
                    try:
                        gpu_info = {
                            'index': int(parts[0]),
                            'name': parts[1],
                            'gpu_util': float(parts[2]) if parts[2] != '[N/A]' else 0,
                            'memory_used': float(parts[3]) if parts[3] != '[N/A]' else 0,
                            'memory_total': float(parts[4]) if parts[4] != '[N/A]' else 0,
                            'temperature': float(parts[5]) if parts[5] != '[N/A]' else 0,
                            'gpu_clock': float(parts[6]) if len(parts) > 6 and parts[6] != '[N/A]' else 0,
                            'clock_graphics': float(parts[6]) if len(parts) > 6 and parts[6] != '[N/A]' else 0,
                            'memory_util': 0,
                            'power': 0
                        }
                        
                        # Calculate memory utilization
                        if gpu_info['memory_total'] > 0:
                            gpu_info['memory_util'] = (gpu_info['memory_used'] / gpu_info['memory_total']) * 100
                        
                        gpus.append(gpu_info)
                    except (ValueError, IndexError):
                        continue
        
        # If no NVIDIA GPU, try Intel GPU
        if not gpus:
            # Try intel_gpu_top (may need sudo)
            stdout, _, exit_code = self._exec_command(
                "timeout 2 intel_gpu_top -l 2>/dev/null || echo ''",
                use_sudo=True
            )
            
            if exit_code == 0 and 'intel' in stdout.lower():
                # Basic Intel GPU detection (intel_gpu_top parsing is complex)
                # For now, just report as available with basic info
                gpu_info = {
                    'index': 0,
                    'name': 'Intel Integrated Graphics',
                    'gpu_util': 0,
                    'memory_used': 0,
                    'memory_total': 0,
                    'temperature': 0,
                    'gpu_clock': 0,
                    'clock_graphics': 0,
                    'memory_util': 0,
                    'power': 0
                }
                
                # Try to get frequency
                freq_out, _, _ = self._exec_command(
                    "cat /sys/class/drm/card0/gt_cur_freq_mhz 2>/dev/null || echo '0'",
                    use_sudo=True
                )
                if freq_out.strip().isdigit():
                    gpu_info['gpu_clock'] = float(freq_out.strip())
                    gpu_info['clock_graphics'] = float(freq_out.strip())
                
                gpus.append(gpu_info)
        
        self._gpu_info = {
            'available': len(gpus) > 0,
            'gpus': gpus
        }
    
    def _update_network_info(self, current_time: float):
        """Update network information."""
        stdout, _, _ = self._exec_command("cat /proc/net/dev")
        
        # Parse network interfaces
        total_rx_bytes = 0
        total_tx_bytes = 0
        
        for line in stdout.strip().split('\n'):
            if ':' not in line:
                continue
            
            parts = line.split(':')
            if len(parts) != 2:
                continue
            
            iface = parts[0].strip()
            
            # Skip loopback
            if iface == 'lo':
                continue
            
            stats = parts[1].split()
            if len(stats) < 10:
                continue
            
            try:
                rx_bytes = int(stats[0])
                tx_bytes = int(stats[8])
                
                total_rx_bytes += rx_bytes
                total_tx_bytes += tx_bytes
            except (ValueError, IndexError):
                continue
        
        # Calculate speeds (bytes/sec)
        upload_speed = 0
        download_speed = 0
        
        if 'network_rx' in self._previous_data and 'network_time' in self._previous_data:
            time_delta = current_time - self._previous_data['network_time']
            if time_delta > 0:
                rx_delta = total_rx_bytes - self._previous_data['network_rx']
                tx_delta = total_tx_bytes - self._previous_data['network_tx']
                
                download_speed = rx_delta / time_delta
                upload_speed = tx_delta / time_delta
        
        # Save for next calculation
        self._previous_data['network_rx'] = total_rx_bytes
        self._previous_data['network_tx'] = total_tx_bytes
        self._previous_data['network_time'] = current_time
        
        # Get connection count (optional, may fail without netstat/ss)
        conn_out, _, _ = self._exec_command(
            "ss -tan 2>/dev/null | wc -l || echo '0'"
        )
        total_connections = max(0, int(conn_out.strip()) - 1) if conn_out.strip().isdigit() else 0
        
        # Established connections
        est_out, _, _ = self._exec_command(
            "ss -tan state established 2>/dev/null | wc -l || echo '0'"
        )
        tcp_established = max(0, int(est_out.strip()) - 1) if est_out.strip().isdigit() else 0
        
        self._network_info = {
            'upload_speed': upload_speed,
            'download_speed': download_speed,
            'connections': {
                'total': total_connections,
                'tcp_established': tcp_established
            },
            'interfaces': [],
            'interface_stats': {},
            'io_stats': {
                'upload_speed': upload_speed,
                'download_speed': download_speed,
                'packets_sent': 0,
                'packets_recv': 0
            }
        }
    
    def _update_disk_info(self, current_time: float):
        """Update disk information."""
        # Get disk I/O stats
        stdout, _, _ = self._exec_command("cat /proc/diskstats")
        
        total_read_sectors = 0
        total_write_sectors = 0
        
        for line in stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) < 14:
                continue
            
            # Skip partition numbers (only get whole disks: sda, nvme0n1, etc)
            device = parts[2]
            if any(device.endswith(str(i)) for i in range(10)) and 'nvme' not in device:
                continue
            
            try:
                read_sectors = int(parts[5])
                write_sectors = int(parts[9])
                
                total_read_sectors += read_sectors
                total_write_sectors += write_sectors
            except (ValueError, IndexError):
                continue
        
        # Calculate speeds (sectors -> bytes -> MB/s)
        SECTOR_SIZE = 512
        read_speed_mb = 0
        write_speed_mb = 0
        
        if 'disk_read' in self._previous_data and 'disk_time' in self._previous_data:
            time_delta = current_time - self._previous_data['disk_time']
            if time_delta > 0:
                read_delta = total_read_sectors - self._previous_data['disk_read']
                write_delta = total_write_sectors - self._previous_data['disk_write']
                
                read_bytes_per_sec = (read_delta * SECTOR_SIZE) / time_delta
                write_bytes_per_sec = (write_delta * SECTOR_SIZE) / time_delta
                
                read_speed_mb = read_bytes_per_sec / (1024 * 1024)
                write_speed_mb = write_bytes_per_sec / (1024 * 1024)
        
        # Save for next calculation
        self._previous_data['disk_read'] = total_read_sectors
        self._previous_data['disk_write'] = total_write_sectors
        self._previous_data['disk_time'] = current_time
        
        # Get partition usage
        df_out, _, _ = self._exec_command("df -B1")
        
        partitions = {}
        partition_usage = []
        
        for line in df_out.strip().split('\n')[1:]:  # Skip header
            parts = line.split()
            if len(parts) < 6:
                continue
            
            try:
                filesystem = parts[0]
                total_bytes = int(parts[1])
                used_bytes = int(parts[2])
                mountpoint = parts[5]
                
                # Skip pseudo filesystems
                if filesystem.startswith(('tmpfs', 'devtmpfs', 'udev', 'none')):
                    continue
                
                total_gb = total_bytes / (1024**3)
                used_gb = used_bytes / (1024**3)
                free_gb = total_gb - used_gb
                percent = (used_gb / total_gb * 100) if total_gb > 0 else 0
                
                partition_info = {
                    'mountpoint': mountpoint,
                    'filesystem': filesystem,
                    'total': total_gb,
                    'used': used_gb,
                    'free': free_gb,
                    'percent': percent
                }
                
                partitions[mountpoint] = partition_info
                partition_usage.append(partition_info)
                
            except (ValueError, IndexError):
                continue
        
        self._disk_info = {
            'read_speed_mb': read_speed_mb,
            'write_speed_mb': write_speed_mb,
            'partitions': partitions,
            'disks': [],
            'io_stats': {
                'read_speed': read_speed_mb * 1024 * 1024,  # bytes/sec
                'write_speed': write_speed_mb * 1024 * 1024,
                'read_speed_mb': read_speed_mb,
                'write_speed_mb': write_speed_mb,
                'read_iops': 0,
                'write_iops': 0
            },
            'partition_usage': partition_usage
        }
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information."""
        return self._cpu_info.copy()
    
    def get_memory_info(self) -> Dict:
        """Get memory information."""
        return self._memory_info.copy()
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information."""
        return self._gpu_info.copy()
    
    def get_network_info(self) -> Dict:
        """Get network information."""
        return self._network_info.copy()
    
    def get_disk_info(self) -> Dict:
        """Get disk information."""
        return self._disk_info.copy()
    
    def _empty_cpu_info(self) -> Dict:
        return {
            'cpu_count': 0,
            'physical_count': 0,
            'usage': {'total': 0, 'per_core': []},
            'frequency': {'average': 0, 'per_core': []},
            'temperature': {}
        }
    
    def _empty_memory_info(self) -> Dict:
        return {
            'memory': {'total': 0, 'used': 0, 'free': 0, 'available': 0, 'percent': 0, 'speed': 0},
            'swap': {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
        }
    
    def _empty_gpu_info(self) -> Dict:
        return {'available': False, 'gpus': []}
    
    def _empty_network_info(self) -> Dict:
        return {
            'upload_speed': 0,
            'download_speed': 0,
            'connections': {'total': 0, 'tcp_established': 0},
            'interfaces': [],
            'interface_stats': {},
            'io_stats': {}
        }
    
    def _empty_disk_info(self) -> Dict:
        return {
            'read_speed_mb': 0,
            'write_speed_mb': 0,
            'partitions': {},
            'disks': [],
            'io_stats': {},
            'partition_usage': []
        }
