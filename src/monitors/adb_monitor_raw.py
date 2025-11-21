"""ADB Monitor - Raw Data Version
Receives raw data from Android and performs all calculations on host side.
"""

import subprocess
import json
import threading
import time
from typing import Dict, Optional

class ADBMonitorRaw:
    """Monitor Android device via ADB - processes raw data."""
    
    def __init__(self, device_ip: str, port: int = 5555, enable_tier1: bool = False):
        """Initialize ADB monitor.
        
        Args:
            device_ip: Android device IP address
            port: ADB port (default: 5555)
            enable_tier1: Enable Tier 1 metrics (context switches, load avg, etc.)
        """
        self.device_ip = device_ip
        self.port = port
        self.device_id = f"{device_ip}:{port}"
        self.enable_tier1 = enable_tier1
        
        # Latest data from Android (thread-safe)
        self._data_lock = threading.Lock()
        self._latest_raw_data = {}
        self._previous_raw_data = {}
        
        # Process data buffer
        self._current_processes = []
        
        # Calculated results
        self._cpu_info = self._empty_cpu_info()
        self._memory_info = self._empty_memory_info()
        self._gpu_info = self._empty_gpu_info()
        self._npu_info = self._empty_npu_info()
        self._network_info = self._empty_network_info()
        self._disk_info = self._empty_disk_info()
        self._process_info = []
        
        # ADB streaming process
        self._stream_process = None
        self._stream_thread = None
        self._running = False
        
        # Connect to device and start streaming
        self._connect()
        self.start_streaming()
    
    def _connect(self):
        """Connect to Android device via ADB."""
        print(f"🔌 Connecting to Android device {self.device_id}...")
        
        result = subprocess.run(
            ["adb", "connect", self.device_id],
            capture_output=True,
            text=True
        )
        
        if "connected" in result.stdout.lower() or "already connected" in result.stdout.lower():
            print(f"✅ Connected to {self.device_id}")
        else:
            raise ConnectionError(f"Failed to connect to {self.device_id}: {result.stdout}")
    
    def _push_script(self):
        """Push monitoring and frequency control scripts to Android device."""
        scripts = [
            ("scripts/android_monitor_raw.sh", "/data/local/tmp/android_monitor_raw.sh"),
            ("scripts/android_freq_controller.sh", "/data/local/tmp/android_freq_controller.sh")
        ]
        
        print(f"📤 Pushing scripts to device...")
        
        for local_path, device_path in scripts:
            subprocess.run(
                ["adb", "-s", self.device_id, "push", local_path, device_path],
                capture_output=True
            )
            
            subprocess.run(
                ["adb", "-s", self.device_id, "shell", f"chmod 755 {device_path}"],
                capture_output=True
            )
        
        print(f"✅ Monitor and frequency control scripts ready")

    
    def _calculate_cpu_usage(self, curr, prev):
        """Calculate CPU usage from raw /proc/stat values."""
        if not prev:
            return 0.0
        
        # Calculate deltas
        d_user = curr['user'] - prev['user']
        d_nice = curr['nice'] - prev['nice']
        d_sys = curr['sys'] - prev['sys']
        d_idle = curr['idle'] - prev['idle']
        d_iowait = curr['iowait'] - prev['iowait']
        d_irq = curr['irq'] - prev['irq']
        d_softirq = curr['softirq'] - prev['softirq']
        d_steal = curr['steal'] - prev['steal']
        
        d_total = d_user + d_nice + d_sys + d_idle + d_iowait + d_irq + d_softirq + d_steal
        d_active = d_total - d_idle - d_iowait
        
        return (d_active * 100.0 / d_total) if d_total > 0 else 0.0
    
    def _process_raw_data(self, raw_data):
        """Process raw data and calculate metrics."""
        with self._data_lock:
            prev = self._previous_raw_data.copy()
            
            # CPU info
            cpu_usage = self._calculate_cpu_usage(raw_data['cpu_raw'], prev.get('cpu_raw', {}))
            
            # Per-core usage and freq
            per_core_usage = []
            per_core_freq = []
            cpu_count = len(raw_data['per_core_raw'])
            
            for i, core in enumerate(raw_data['per_core_raw']):
                prev_core = prev.get('per_core_raw', [{}])[i] if i < len(prev.get('per_core_raw', [])) else {}
                core_usage = self._calculate_cpu_usage(core, prev_core)
                per_core_usage.append(core_usage)
                
                # Frequency in MHz
                core_freq_mhz = raw_data['per_core_freq_khz'][i] / 1000
                per_core_freq.append(core_freq_mhz)
            
            avg_freq = sum(per_core_freq) / len(per_core_freq) if per_core_freq else 0
            
            # CPU power (Intel RAPL - calculate from energy delta)
            cpu_power_uj = raw_data.get('cpu_power_uj', 0)
            prev_cpu_power_uj = prev.get('cpu_power_uj', cpu_power_uj)
            timestamp_ms = raw_data.get('timestamp_ms', 0)
            
            cpu_power_watts = 0.0
            if cpu_power_uj > 0 and timestamp_ms > 0:
                # Calculate energy delta (handle counter wrap-around)
                energy_delta_uj = cpu_power_uj - prev_cpu_power_uj
                if energy_delta_uj < 0:
                    # Counter wrapped around (assume 32-bit counter)
                    energy_delta_uj += (1 << 32)
                
                # Calculate time delta in seconds
                time_delta_ms = timestamp_ms - prev.get('timestamp_ms', timestamp_ms)
                time_delta_sec = time_delta_ms / 1000.0 if time_delta_ms > 0 else 1.0
                
                # Power (Watts) = Energy (J) / Time (s)
                # Energy (J) = energy_uj / 1,000,000
                cpu_power_watts = (energy_delta_uj / 1_000_000.0) / time_delta_sec
            
            self._cpu_info = {
                'cpu_count': cpu_count,
                'physical_count': cpu_count,
                'usage': {
                    'total': cpu_usage,
                    'per_core': per_core_usage
                },
                'frequency': {
                    'average': avg_freq,
                    'per_core': per_core_freq
                },
                'temperature': {
                    'Thermal': [{
                        'label': 'CPU',
                        'current': raw_data['cpu_temp_millideg'] / 1000.0,
                        'high': 100.0,
                        'critical': 105.0
                    }]
                } if raw_data['cpu_temp_millideg'] > 0 else {},
                'power_watts': cpu_power_watts
            }
            
            # Memory info
            mem_total_gb = raw_data['mem_total_kb'] / 1024 / 1024
            mem_available_gb = raw_data['mem_available_kb'] / 1024 / 1024
            mem_free_gb = raw_data['mem_free_kb'] / 1024 / 1024
            mem_used_gb = mem_total_gb - mem_available_gb
            mem_percent = (mem_used_gb * 100.0 / mem_total_gb) if mem_total_gb > 0 else 0
            
            self._memory_info = {
                'memory': {
                    'total': mem_total_gb,
                    'used': mem_used_gb,
                    'free': mem_free_gb,
                    'available': mem_available_gb,
                    'percent': mem_percent,
                    'speed': 0
                },
                'swap': {
                    'total': 0,
                    'used': 0,
                    'free': 0,
                    'percent': 0
                }
            }
            
            # GPU info
            # Calculate GPU utilization from raw runtime/idle delta (host-side calculation)
            # Use ACTUAL time delta between samples, not assumed 1000ms
            # Support both i915 (runtime) and Xe (idle_residency) drivers
            gpu_driver = raw_data.get('gpu_driver', 'i915')  # Default to i915 for backward compatibility
            gpu_runtime_ms = raw_data.get('gpu_runtime_ms', 0)
            prev_gpu_runtime_ms = prev.get('gpu_runtime_ms', gpu_runtime_ms)
            prev_timestamp_ms = prev.get('timestamp_ms', timestamp_ms)
            
            gpu_util = 0
            if all([gpu_runtime_ms, prev_gpu_runtime_ms, timestamp_ms, prev_timestamp_ms]):
                runtime_delta = gpu_runtime_ms - prev_gpu_runtime_ms
                time_delta = timestamp_ms - prev_timestamp_ms
                
                if time_delta > 0:
                    if gpu_driver == 'xe':
                        # For Xe: runtime_ms is idle_residency_ms
                        # Utilization = 100 - (idle_delta / time_delta * 100)
                        idle_percentage = (runtime_delta / time_delta) * 100
                        gpu_util = int(max(0, min(100, 100 - idle_percentage)))
                    else:
                        # For i915: runtime_ms is active time
                        # Utilization = (runtime_delta / time_delta) * 100
                        gpu_util = int((runtime_delta / time_delta) * 100)
                        gpu_util = max(0, min(100, gpu_util))
            
            # GPU memory from i915_gem_objects or xe fdinfo
            gpu_mem_used_bytes = raw_data.get('gpu_memory_used_bytes', 0)
            gpu_mem_total_bytes = raw_data.get('gpu_memory_total_bytes', 0)
            gpu_mem_used_mb = gpu_mem_used_bytes // (1024 * 1024)
            gpu_mem_total_mb = gpu_mem_total_bytes // (1024 * 1024)
            gpu_mem_util = 0.0
            if gpu_mem_total_bytes > 0:
                # Keep one decimal place for low percentages (integrated GPU uses system RAM)
                gpu_mem_util = round((gpu_mem_used_bytes / gpu_mem_total_bytes) * 100, 1)
            
            self._gpu_info = {
                'available': raw_data['gpu_freq_mhz'] > 0,
                'gpus': [{
                    'name': 'Android GPU',
                    'gpu_clock': raw_data['gpu_freq_mhz'],
                    'clock_graphics': raw_data['gpu_freq_mhz'],
                    'gpu_util': gpu_util,  # Calculated on host from runtime delta
                    'memory_used': gpu_mem_used_mb,  # From i915_gem_objects
                    'memory_total': gpu_mem_total_mb,  # From i915_gem_objects
                    'memory_util': gpu_mem_util,  # Calculated from used/total
                    'temperature': 0
                }] if raw_data['gpu_freq_mhz'] > 0 else []
            }
            
            # Network info (calculate delta from previous sample)
            # raw_data contains cumulative bytes, need to calculate speed
            prev_net_rx = prev.get('net_rx_bytes', raw_data['net_rx_bytes'])
            prev_net_tx = prev.get('net_tx_bytes', raw_data['net_tx_bytes'])
            prev_timestamp_ms_net = prev.get('timestamp_ms', timestamp_ms)
            
            # Delta in bytes
            delta_rx = max(0, raw_data['net_rx_bytes'] - prev_net_rx)
            delta_tx = max(0, raw_data['net_tx_bytes'] - prev_net_tx)
            
            # Calculate actual time delta (in seconds)
            time_delta_ms = timestamp_ms - prev_timestamp_ms_net
            time_delta_sec = time_delta_ms / 1000.0 if time_delta_ms > 0 else 1.0
            
            # Calculate speed (bytes/sec) using actual time delta
            upload_speed = delta_tx / time_delta_sec
            download_speed = delta_rx / time_delta_sec
            
            # Match local monitor format - provide both top-level AND io_stats
            self._network_info = {
                'upload_speed': upload_speed,      # bytes/sec (top-level for DataSource)
                'download_speed': download_speed,  # bytes/sec (top-level for DataSource)
                'interfaces': [],
                'interface_stats': {},
                'io_stats': {
                    'upload_speed': upload_speed,      # bytes/sec
                    'download_speed': download_speed,  # bytes/sec
                    'packets_sent': 0,
                    'packets_recv': 0
                },
                'connections': {'total': 0, 'tcp_established': 0}
            }
            
            # Disk info (calculate delta from previous sample)
            # raw_data contains cumulative sectors
            SECTOR_SIZE = 512
            prev_read_sectors = prev.get('disk_read_sectors', raw_data['disk_read_sectors'])
            prev_write_sectors = prev.get('disk_write_sectors', raw_data['disk_write_sectors'])
            
            # Delta in sectors
            delta_read_sectors = max(0, raw_data['disk_read_sectors'] - prev_read_sectors)
            delta_write_sectors = max(0, raw_data['disk_write_sectors'] - prev_write_sectors)
            
            # Convert to bytes/sec using actual time delta
            read_bytes_per_sec = (delta_read_sectors * SECTOR_SIZE) / time_delta_sec
            write_bytes_per_sec = (delta_write_sectors * SECTOR_SIZE) / time_delta_sec
            
            # Convert to MB/s
            read_mb_s = read_bytes_per_sec / (1024 * 1024)
            write_mb_s = write_bytes_per_sec / (1024 * 1024)
            
            # Also calculate IOPS (operations per second)
            read_iops = delta_read_sectors / time_delta_sec
            write_iops = delta_write_sectors / time_delta_sec
            
            self._disk_info = {
                'read_speed_mb': read_mb_s,
                'write_speed_mb': write_mb_s,
                'partitions': {},
                'disks': [],
                'io_stats': {
                    'read_speed': read_bytes_per_sec,  # bytes/sec
                    'write_speed': write_bytes_per_sec,  # bytes/sec
                    'read_speed_mb': read_mb_s,
                    'write_speed_mb': write_mb_s,
                    'read_iops': read_iops,
                    'write_iops': write_iops
                },
                'partition_usage': []
            }
            
            # Save for next delta calculation
            self._latest_raw_data = raw_data
            self._previous_raw_data = raw_data
            
            # Process info (if available)
            if 'processes' in raw_data:
                self._process_info = raw_data['processes']
            
            # NPU info (parse from npu_info field, similar to SSH monitor)
            npu_info_str = raw_data.get('npu_info', 'none')
            if npu_info_str and npu_info_str != 'none':
                # Parse Intel NPU info (format: intel-npu:freq_mhz:max_freq_mhz:mem_mb:util)
                if npu_info_str.startswith('intel-npu:'):
                    parts = npu_info_str.split(':')
                    if len(parts) >= 5:
                        self._npu_info = {
                            'available': True,
                            'platform': 'Intel NPU',
                            'utilization': int(parts[4]),
                            'frequency': int(parts[1]),
                            'max_frequency': int(parts[2]),
                            'memory_used': int(parts[3]),
                            'power': 0
                        }
                else:
                    self._npu_info = self._empty_npu_info()
            else:
                self._npu_info = self._empty_npu_info()
    
    def start_streaming(self):
        """Start receiving data from Android device."""
        if self._running:
            return
        
        # Kill any existing monitor processes on device (cleanup zombies)
        print("🧹 Cleaning up any existing monitor processes...")
        try:
            subprocess.run(
                ["adb", "-s", self.device_id, "shell", "pkill -f android_monitor"],
                capture_output=True,
                timeout=2
            )
            time.sleep(0.5)  # Give it time to cleanup
        except Exception:
            pass  # Ignore errors if no processes exist
        
        # Push script to device
        self._push_script()
        
        # Start streaming thread
        self._running = True
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        
        # Wait for first data
        print("⏳ Waiting for first data...", end="", flush=True)
        for i in range(50):  # 5 seconds timeout
            with self._data_lock:
                if self._cpu_info['cpu_count'] > 0:
                    print("\n✅ Receiving and processing data from Android")
                    return
            print(".", end="", flush=True)
            time.sleep(0.1)
        
        print("\n⚠️  No data received yet, continuing anyway...")
    
    def stop_streaming(self):
        """Stop receiving data from Android device."""
        self._running = False
        
        if self._stream_thread:
            self._stream_thread.join(timeout=2.0)
        
        if self._stream_process:
            self._stream_process.terminate()
            self._stream_process.wait()
        
        # IMPORTANT: Kill the monitor script on Android device
        # This prevents zombie processes from accumulating
        print("🧹 Cleaning up Android monitor process...")
        try:
            subprocess.run(
                ["adb", "-s", self.device_id, "shell", "pkill -f android_monitor_raw.sh"],
                capture_output=True,
                timeout=2
            )
        except Exception as e:
            print(f"⚠️  Failed to cleanup Android process: {e}")
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information."""
        with self._data_lock:
            return self._cpu_info.copy()
    
    def get_memory_info(self) -> Dict:
        """Get memory information."""
        with self._data_lock:
            return self._memory_info.copy()
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information."""
        with self._data_lock:
            return self._gpu_info.copy()
    
    def get_npu_info(self) -> Dict:
        """Get NPU information."""
        with self._data_lock:
            return self._npu_info.copy()
    
    def get_network_info(self) -> Dict:
        """Get network information."""
        with self._data_lock:
            return self._network_info.copy()
    
    def get_disk_info(self) -> Dict:
        """Get disk information."""
        with self._data_lock:
            return self._disk_info.copy()
            
    def get_process_info(self) -> list:
        """Get process information."""
        with self._data_lock:
            return list(self._process_info)


    def get_timestamp_ms(self) -> int:
        """Get Android device timestamp in milliseconds."""
        with self._data_lock:
            return self._latest_raw_data.get('timestamp_ms', 0)

    # End of class ADBMonitorRaw
    
    def get_latest_data(self) -> Dict:
        """Get latest raw data from Android device (for tier1 metrics access)."""
        with self._data_lock:
            return self._latest_raw_data.copy()
    
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
    
    def _empty_npu_info(self) -> Dict:
        return {'available': False}
    
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
    
    def _stream_loop(self):
        """Background loop to read streaming JSON data."""
        try:
            # Pass interval and tier1 flag as arguments to shell script
            tier1_flag = "1" if self.enable_tier1 else "0"
            device_script = "/data/local/tmp/android_monitor_raw.sh"
            
            # IMPORTANT: Use "sh" with separate arguments, NOT a single string
            # This was the original working format
            cmd = ["adb", "-s", self.device_id, "shell", "sh", device_script, "1", tier1_flag, "0"]
            
            self._stream_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )
            
            # Skip "Starting" message from script
            self._stream_process.stdout.readline()
            
            while self._running:
                line = self._stream_process.stdout.readline()
                if not line:
                    break
                
                try:
                    line = line.strip()
                    if not line or not line.startswith('{'):
                        continue
                        
                    raw_data = json.loads(line)
                    
                    # Check if this is a process record or a full sample
                    if raw_data.get('type') == 'process':
                        # Store process data
                        proc_info = {
                            'pid': raw_data['pid'],
                            'name': raw_data['name'],
                            'cpu_percent': raw_data['cpu'],
                            'memory_rss': raw_data['mem'],
                            'cmdline': raw_data['cmd'],
                            'status': 'running',
                            'num_threads': 0,
                            'create_time': 0
                        }
                        with self._data_lock:
                            self._current_processes.append(proc_info)
                    else:
                        # Full sample - process it
                        # Attach process list if available
                        with self._data_lock:
                            if self._current_processes:
                                self._current_processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                                raw_data['processes'] = list(self._current_processes)
                                self._current_processes = []
                        
                        # Process data WITHOUT holding lock (to avoid deadlock)
                        try:
                            self._process_raw_data(raw_data)
                        except Exception as e:
                            print(f"⚠️  Error in _process_raw_data: {e}")
                            import traceback
                            traceback.print_exc()
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {str(e)[:100]}")
                    continue
                except KeyError as e:
                    print(f"⚠️  Missing key in raw data: {e}")
                    continue
                except Exception as e:
                    print(f"⚠️  Error processing stream: {e}")
                    
        except Exception as e:
            print(f"ADB stream error: {e}")
        finally:
            if self._stream_process:
                self._stream_process.terminate()
