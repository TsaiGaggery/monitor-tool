"""
SSH Remote Linux Monitor (Raw Data)
Similar to ADBMonitorRaw, streams JSON data from remote Linux host
Uses linux_monitor_remote.sh script for data collection
"""

import json
import threading
import time
import paramiko
from typing import Optional, Dict, Any, Callable
from queue import Queue
import os


class SSHMonitorRaw:
    """Monitor remote Linux system via SSH, streaming raw JSON data"""
    
    def __init__(self, host: str, user: str, password: Optional[str] = None,
                 key_path: Optional[str] = None, port: int = 22,
                 interval: int = 1, enable_tier1: bool = False):
        """
        Initialize SSH monitor
        
        Args:
            host: Remote host address
            user: SSH username
            password: SSH password (optional if using key)
            key_path: Path to SSH private key (optional if using password)
            port: SSH port (default 22)
            interval: Monitoring interval in seconds
            enable_tier1: Enable Tier 1 metrics (context switches, load avg, process counts, IRQ%)
        """
        self.host = host
        self.user = user
        self.password = password
        self.key_path = key_path
        self.port = port
        self.interval = interval
        self.enable_tier1 = enable_tier1
        
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.monitor_channel = None
        self.monitor_thread = None
        self.running = False
        
        # Store stdin/stdout/stderr for cleanup
        self._stdin = None
        self._stdout = None
        self._stderr = None
        
        # Use a queue to buffer samples instead of just storing "latest"
        # This prevents sample loss when UI polls slower than data arrives
        self._sample_queue: Queue = Queue(maxsize=100)  # Buffer up to 100 samples
        self._latest_raw_data: Optional[Dict[str, Any]] = None
        self._prev_raw_data: Optional[Dict[str, Any]] = None  # For delta calculation
        
        # Previous GPU runtime for utilization calculation (host-side)
        self._prev_gpu_runtime_ms: Optional[int] = None
        self._prev_gpu_timestamp_ms: Optional[int] = None
        self._data_callback: Optional[Callable] = None
        self._lock = threading.Lock()
        
        # Computed data (calculated from deltas)
        self._gpu_info: Optional[Dict[str, Any]] = None
        self._npu_info: Optional[Dict[str, Any]] = None
        
    def _check_remote_dependencies(self) -> tuple[bool, list[str]]:
        """
        Check if remote host has all required dependencies
        
        Returns:
            (success: bool, missing: list[str])
        """
        required_commands = {
            'bash': 'Bourne Again Shell',
            'awk': 'Text processing (gawk/mawk)',
            'grep': 'Pattern matching',
            'cat': 'File concatenation',
            'date': 'Date/time utilities',
            'sqlite3': 'SQLite database (REQUIRED for data storage)'
        }
        
        missing = []
        found = []
        
        for cmd, description in required_commands.items():
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    f'command -v {cmd} >/dev/null 2>&1 && echo "OK" || echo "MISSING"',
                    timeout=5
                )
                result = stdout.read().decode().strip()
                
                if result != "OK":
                    missing.append(f"{cmd:12} - {description}")
                else:
                    found.append(f"{cmd:12} ✓")
                    
            except Exception as e:
                print(f"⚠️  Warning: Failed to check {cmd}: {e}")
                missing.append(f"{cmd:12} - {description} (check failed)")
        
        # Print status
        if found:
            print("   Found:")
            for item in found:
                print(f"     {item}")
        
        return (len(missing) == 0, missing)
    
    def connect(self) -> bool:
        """Establish SSH connection and verify dependencies"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with password or key
            if self.key_path:
                # Try to load key (may require passphrase)
                key = None
                try:
                    key = paramiko.RSAKey.from_private_key_file(self.key_path)
                except paramiko.ssh_exception.PasswordRequiredException:
                    # Key is encrypted, try with password
                    if self.password:
                        key = paramiko.RSAKey.from_private_key_file(self.key_path, password=self.password)
                    else:
                        raise
                
                self.ssh_client.connect(
                    self.host, port=self.port, username=self.user,
                    pkey=key, timeout=10,
                    look_for_keys=False,  # Don't search for keys
                    allow_agent=False     # Don't use SSH agent
                )
            else:
                self.ssh_client.connect(
                    self.host, port=self.port, username=self.user,
                    password=self.password, timeout=10,
                    look_for_keys=False,  # Don't search for keys automatically
                    allow_agent=False     # Don't use SSH agent
                )
            
            print(f"✅ SSH connected to {self.user}@{self.host}:{self.port}")
            
            # Check dependencies on remote host
            print("🔍 Checking remote dependencies...")
            success, missing = self._check_remote_dependencies()
            
            if not success:
                print(f"\n❌ Missing required packages on remote host {self.host}:")
                for pkg in missing:
                    print(f"     {pkg}")
                print("\n📦 Install missing packages:")
                print("   Ubuntu/Debian:")
                print("     sudo apt-get install bash gawk grep coreutils sqlite3")
                print("   RHEL/CentOS:")
                print("     sudo yum install bash gawk grep coreutils sqlite")
                print("   Arch Linux:")
                print("     sudo pacman -S bash gawk grep coreutils sqlite")
                
                # Disconnect
                self.ssh_client.close()
                self.ssh_client = None
                return False
            
            print("✅ All dependencies satisfied\n")
            return True
            
        except Exception as e:
            print(f"❌ SSH connection failed: {e}")
            return False
    
    def start_monitoring(self, callback: Optional[Callable] = None):
        """
        Start monitoring in background thread
        
        Args:
            callback: Optional callback function to receive data updates
        """
        if self.running:
            return
        
        self._data_callback = callback
        self.running = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
    
    def _monitor_loop(self):
        """Background monitoring loop - streams JSON from remote script"""
        stdin = None
        stdout = None
        stderr = None
        
        try:
            # Get path to monitoring script
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'scripts', 'linux_monitor_remote.sh'
            )
            
            # Read script content
            with open(script_path, 'r') as f:
                script_content = f.read()
            
            # Execute remote script via SSH
            # Pass interval and tier1 flag as arguments to bash script
            tier1_flag = 1 if self.enable_tier1 else 0
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f'bash -s {self.interval} {tier1_flag}',
                get_pty=True
            )
            
            # Store references for cleanup
            self._stdin = stdin
            self._stdout = stdout
            self._stderr = stderr
            
            # Send script content to stdin
            stdin.write(script_content)
            stdin.flush()
            stdin.channel.shutdown_write()
            
            # Read JSON output line by line
            while self.running:
                line = stdout.readline()
                if not line:
                    break
                
                # Skip non-JSON lines (like "Starting remote Linux monitor...")
                line = line.strip()
                if not line.startswith('{'):
                    continue
                
                try:
                    # Parse JSON data
                    raw_data = json.loads(line)
                    self._process_raw_data(raw_data)
                    
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {e}")
                    continue
                
        except Exception as e:
            print(f"Monitor loop error: {e}")
        finally:
            self.running = False
            # Clean up streams
            if stdin:
                try:
                    stdin.close()
                except:
                    pass
            if stdout:
                try:
                    stdout.close()
                except:
                    pass
            if stderr:
                try:
                    stderr.close()
                except:
                    pass
    
    def _process_raw_data(self, raw_data: Dict[str, Any]):
        """Process received raw data and calculate deltas (similar to ADBMonitorRaw)"""
        with self._lock:
            prev = self._prev_raw_data if self._prev_raw_data else raw_data
            
            # Calculate GPU utilization from delta
            self._gpu_info = self._calculate_gpu_info(raw_data, prev)
            
            # Calculate NPU utilization from delta
            self._npu_info = self._calculate_npu_info(raw_data, prev)
            
            # Update stored data
            self._prev_raw_data = self._latest_raw_data
            self._latest_raw_data = raw_data
            
            # Add to queue for UI consumption (non-blocking)
            try:
                self._sample_queue.put_nowait(raw_data)
            except:
                # Queue full, drop oldest sample and retry
                try:
                    self._sample_queue.get_nowait()  # Remove oldest
                    self._sample_queue.put_nowait(raw_data)  # Add new
                except:
                    pass  # If still fails, just drop this sample
        
        # Call callback if registered
        if self._data_callback:
            self._data_callback(raw_data)
    
    def _calculate_gpu_info(self, raw_data: Dict[str, Any], prev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Calculate GPU utilization from raw runtime/idle delta (host-side calculation)
        
        Similar to adb_monitor_raw.py approach:
        - Remote sends RAW gpu_runtime_ms (idle_residency or rc6_residency)
        - Host calculates utilization from delta between samples
        """
        gpu_driver = raw_data.get('gpu_driver', 'none')
        if gpu_driver == 'none':
            return {'available': False}
        
        gpu_freq_mhz = raw_data.get('gpu_freq_mhz', 0)
        gpu_runtime_ms = raw_data.get('gpu_runtime_ms', 0)
        gpu_temp_celsius = raw_data.get('gpu_temp_celsius', 0)
        timestamp_ms = raw_data.get('timestamp_ms', 0)
        
        # Calculate GPU utilization from runtime delta
        gpu_util = 0
        if gpu_driver == 'nvidia':
            # For NVIDIA: gpu_runtime_ms is actually the utilization % (direct value from nvidia-smi)
            # No delta calculation needed
            gpu_util = int(gpu_runtime_ms)
        elif self._prev_gpu_runtime_ms is not None and self._prev_gpu_timestamp_ms is not None:
            runtime_delta = gpu_runtime_ms - self._prev_gpu_runtime_ms
            time_delta = timestamp_ms - self._prev_gpu_timestamp_ms
            
            if time_delta > 0:
                if gpu_driver == 'xe':
                    # For Xe: runtime_ms is idle_residency_ms
                    # Utilization = 100 - (idle_delta / time_delta * 100)
                    idle_percentage = (runtime_delta / time_delta) * 100
                    gpu_util = int(max(0, min(100, 100 - idle_percentage)))
                elif gpu_driver == 'i915':
                    # For i915: runtime_ms is rc6_residency_ms (idle time)
                    # Utilization = 100 - (rc6_delta / time_delta * 100)
                    idle_percentage = (runtime_delta / time_delta) * 100
                    gpu_util = int(max(0, min(100, 100 - idle_percentage)))
            elif self._gpu_info and self._gpu_info.get('available'):
                # If no time delta (duplicate sample), keep previous utilization
                gpu_util = self._gpu_info.get('gpu_util', 0)
        
        # Update previous values for next calculation (not needed for NVIDIA, but keep for consistency)
        self._prev_gpu_runtime_ms = gpu_runtime_ms
        self._prev_gpu_timestamp_ms = timestamp_ms
        
        # GPU memory
        gpu_mem_used_bytes = raw_data.get('gpu_memory_used_bytes', 0)
        gpu_mem_total_bytes = raw_data.get('gpu_memory_total_bytes', 0)
        gpu_mem_used_mb = gpu_mem_used_bytes // (1024 * 1024)
        gpu_mem_total_mb = gpu_mem_total_bytes // (1024 * 1024)
        
        # Calculate memory utilization percentage
        mem_util = 0
        if gpu_mem_total_mb > 0:
            mem_util = int((gpu_mem_used_mb / gpu_mem_total_mb) * 100)
        
        return {
            'available': gpu_driver not in ['none', '', 'N/A'],  # Check driver, not freq (freq can be 0 when idle)
            'name': f'Remote GPU ({gpu_driver.upper()})',
            'gpu_util': gpu_util,  # Calculated on host from runtime delta (or direct for NVIDIA)
            'memory_util': mem_util,
            'gpu_clock': gpu_freq_mhz,
            'memory_used': gpu_mem_used_mb,
            'memory_total': gpu_mem_total_mb,
            'temperature': gpu_temp_celsius
        }
    
    def _calculate_npu_info(self, raw_data: Dict[str, Any], prev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse NPU info from remote (utilization already calculated on host)"""
        npu_info_str = raw_data.get('npu_info', '')
        if not npu_info_str or npu_info_str == 'none':
            return {'available': False}
        
        # Parse Intel NPU info
        if npu_info_str.startswith('intel-npu:'):
            # Format: intel-npu:freq_mhz:max_freq_mhz:mem_mb:util (util calculated on host)
            parts = npu_info_str.split(':')
            if len(parts) >= 5:
                freq_mhz = int(parts[1])
                max_freq_mhz = int(parts[2])
                mem_mb = int(parts[3])
                utilization = int(parts[4])  # Already calculated on host
                
                return {
                    'available': True,
                    'platform': 'Intel NPU',
                    'utilization': utilization,
                    'frequency': freq_mhz,
                    'max_frequency': max_freq_mhz,
                    'memory_used': mem_mb,
                    'power': 0
                }
        
        return {'available': False}
    
    def get_gpu_info(self) -> Optional[Dict[str, Any]]:
        """Get computed GPU info (already calculated in _process_raw_data)"""
        with self._lock:
            return self._gpu_info.copy() if self._gpu_info else {'available': False}
    
    def get_npu_info(self) -> Optional[Dict[str, Any]]:
        """Get computed NPU info (already calculated in _process_raw_data)"""
        with self._lock:
            return self._npu_info.copy() if self._npu_info else {'available': False}
    
    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """Get latest monitoring data"""
        with self._lock:
            return self._latest_raw_data
    
    def get_queued_samples(self) -> list[Dict[str, Any]]:
        """Get all queued samples (for UI to process without loss)
        
        Returns:
            List of all samples currently in the queue
        """
        samples = []
        while not self._sample_queue.empty():
            try:
                samples.append(self._sample_queue.get_nowait())
            except:
                break
        return samples
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def disconnect(self):
        """Stop monitoring and disconnect SSH"""
        if self.running:
            self.running = False
            
            # Wait for monitor thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2)
            
            # Close SSH streams to terminate remote process
            if self._stdin:
                try:
                    self._stdin.close()
                except:
                    pass
                self._stdin = None
            
            if self._stdout:
                try:
                    self._stdout.close()
                except:
                    pass
                self._stdout = None
            
            if self._stderr:
                try:
                    self._stderr.close()
                except:
                    pass
                self._stderr = None
            
            # Close SSH connection
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except:
                    pass
                self.ssh_client = None
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
