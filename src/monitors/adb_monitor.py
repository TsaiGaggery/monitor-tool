"""ADB Monitor - Receive streaming data from Android device via ADB.

This module provides the same interface as local monitors (CPUMonitor, MemoryMonitor, etc.)
but receives data from Android device via ADB streaming.
"""

import subprocess
import json
import threading
import time
from typing import Dict, Optional, List


class ADBMonitor:
    """Monitor Android device via ADB streaming."""
    
    def __init__(self, device_ip: str, port: int = 5555):
        """Initialize ADB monitor.
        
        Args:
            device_ip: Android device IP address
            port: ADB port (default: 5555)
        """
        self.device_ip = device_ip
        self.port = port
        self.device_id = f"{device_ip}:{port}"
        
        # Latest data from Android (thread-safe)
        self._data_lock = threading.Lock()
        self._latest_data = {}
        
        # ADB streaming process
        self._stream_process = None
        self._stream_thread = None
        self._running = False
        
        # Connect to device
        self._connect()
        
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
        """Push monitoring script to Android device."""
        script_path = "scripts/android_monitor_stream.sh"
        device_path = "/data/local/tmp/android_monitor_stream.sh"
        
        print(f"📤 Pushing monitor script to device...")
        
        subprocess.run(
            ["adb", "-s", self.device_id, "push", script_path, device_path],
            capture_output=True
        )
        
        subprocess.run(
            ["adb", "-s", self.device_id, "shell", f"chmod +x {device_path}"],
            capture_output=True
        )
        
        print(f"✅ Monitor script ready")
    
    def _stream_worker(self):
        """Background thread that reads streaming data from ADB."""
        device_script = "/data/local/tmp/android_monitor_stream.sh"
        
        # Start ADB shell command that streams JSON data
        self._stream_process = subprocess.Popen(
            ["adb", "-s", self.device_id, "shell", device_script, "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print(f"🚀 Streaming started from Android device")
        
        # Buffer for incomplete JSON lines
        json_buffer = ""
        
        while self._running:
            try:
                # Read character by character to handle line wrapping
                char = self._stream_process.stdout.read(1)
                
                if not char:
                    break
                
                # Add to buffer
                json_buffer += char
                
                # Check if we have a complete JSON (ends with }\n)
                if char == '\n' and json_buffer.strip().endswith('}'):
                    # Remove any newlines within the JSON (from terminal wrapping)
                    json_str = json_buffer.replace('\n', '').replace('\r', '').strip()
                    
                    # Parse JSON data
                    try:
                        data = json.loads(json_str)
                        
                        # Update latest data (thread-safe)
                        with self._data_lock:
                            self._latest_data = data
                            
                    except json.JSONDecodeError as e:
                        # Skip invalid JSON
                        print(f"⚠️  JSON parse error: {e}")
                        print(f"    Buffer length: {len(json_str)}")
                        print(f"    Buffer: {json_str}")
                    
                    # Reset buffer
                    json_buffer = ""
                    
            except Exception as e:
                print(f"⚠️  Stream error: {e}")
                break
        
        # Cleanup
        if self._stream_process:
            self._stream_process.terminate()
            self._stream_process.wait()
    
    def start_streaming(self):
        """Start receiving data from Android device."""
        if self._running:
            return
        
        # Push script to device
        self._push_script()
        
        # Start streaming thread
        self._running = True
        self._stream_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._stream_thread.start()
        
        # Wait for first data
        print("⏳ Waiting for first data...")
        for _ in range(50):  # 5 seconds timeout
            with self._data_lock:
                if self._latest_data:
                    print("✅ Receiving data from Android")
                    return
            time.sleep(0.1)
        
        print("⚠️  No data received yet, continuing anyway...")
    
    def stop_streaming(self):
        """Stop receiving data from Android device."""
        self._running = False
        
        if self._stream_thread:
            self._stream_thread.join(timeout=2.0)
        
        if self._stream_process:
            self._stream_process.terminate()
            self._stream_process.wait()
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information (mimics CPUMonitor.get_all_info())."""
        with self._data_lock:
            data = self._latest_data.copy()
        
        if not data:
            return self._empty_cpu_info()
        
        # Convert ADB data to CPUMonitor format
        per_core_usage = data.get('per_core_usage', [])
        per_core_freq = data.get('per_core_freq', [])
        
        return {
            'cpu_count': len(per_core_usage),
            'physical_count': len(per_core_usage),  # Assume all physical for Android
            'usage': {
                'total': data.get('cpu_usage', 0),
                'per_core': per_core_usage
            },
            'frequency': {
                'average': data.get('cpu_freq', 0),
                'per_core': per_core_freq
            },
            'temperature': {
                'Package': [{
                    'label': 'Package',
                    'current': data.get('cpu_temp', 0),
                    'high': 100.0,
                    'critical': 105.0
                }]
            } if data.get('cpu_temp', 0) > 0 else {}
        }
    
    def _empty_cpu_info(self) -> Dict:
        """Return empty CPU info when no data available."""
        return {
            'cpu_count': 0,
            'physical_count': 0,
            'usage': {'total': 0, 'per_core': []},
            'frequency': {'average': 0, 'per_core': []},
            'temperature': {}
        }
    
    def get_memory_info(self) -> Dict:
        """Get memory information (mimics MemoryMonitor.get_all_info())."""
        with self._data_lock:
            data = self._latest_data.copy()
        
        if not data:
            return self._empty_memory_info()
        
        # Convert KB to GB
        mem_total_kb = data.get('mem_total', 0)
        mem_used_kb = data.get('mem_used', 0)
        mem_available_kb = data.get('mem_available', 0)
        
        mem_total_gb = mem_total_kb / 1024 / 1024
        mem_used_gb = mem_used_kb / 1024 / 1024
        mem_available_gb = mem_available_kb / 1024 / 1024
        mem_free_gb = mem_available_gb
        
        return {
            'memory': {
                'total': mem_total_gb,
                'used': mem_used_gb,
                'free': mem_free_gb,
                'available': mem_available_gb,
                'percent': data.get('mem_percent', 0),
                'speed': 0  # Not available on Android
            },
            'swap': {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0
            }
        }
    
    def _empty_memory_info(self) -> Dict:
        """Return empty memory info when no data available."""
        return {
            'memory': {'total': 0, 'used': 0, 'free': 0, 'available': 0, 'percent': 0, 'speed': 0},
            'swap': {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
        }
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information (mimics GPUMonitor.get_all_info())."""
        with self._data_lock:
            data = self._latest_data.copy()
        
        if not data:
            return {'available': False, 'gpus': []}
        
        gpu_freq = data.get('gpu_freq', 0)
        
        return {
            'available': True,
            'gpu_type': 'Intel' if gpu_freq > 0 else 'Unknown',
            'gpus': [{
                'name': 'Android GPU',
                'gpu_util': 0,  # Not available without root
                'gpu_clock': gpu_freq,
                'memory_used': 0,
                'memory_total': 0,
                'temperature': 0,
                'clock_graphics': gpu_freq,
                'clock_memory': 0
            }]
        }
    
    def get_network_info(self) -> Dict:
        """Get network information (mimics NetworkMonitor.get_all_info())."""
        with self._data_lock:
            data = self._latest_data.copy()
        
        if not data:
            return self._empty_network_info()
        
        return {
            'io_stats': {
                'upload_speed': data.get('net_tx', 0),
                'download_speed': data.get('net_rx', 0),
                'packets_sent': 0,
                'packets_recv': 0
            },
            'interfaces': [],
            'interface_stats': {}
        }
    
    def _empty_network_info(self) -> Dict:
        """Return empty network info when no data available."""
        return {
            'io_stats': {'upload_speed': 0, 'download_speed': 0, 'packets_sent': 0, 'packets_recv': 0},
            'interfaces': [],
            'interface_stats': {}
        }
    
    def get_disk_info(self) -> Dict:
        """Get disk information (mimics DiskMonitor.get_all_info())."""
        with self._data_lock:
            data = self._latest_data.copy()
        
        if not data:
            return self._empty_disk_info()
        
        # Convert sectors to bytes (512 bytes per sector)
        disk_read_bytes = data.get('disk_read', 0) * 512
        disk_write_bytes = data.get('disk_write', 0) * 512
        
        # Convert to MB/s
        disk_read_mb = disk_read_bytes / 1024 / 1024
        disk_write_mb = disk_write_bytes / 1024 / 1024
        
        return {
            'io_stats': {
                'read_speed': disk_read_bytes,
                'write_speed': disk_write_bytes,
                'read_speed_mb': disk_read_mb,
                'write_speed_mb': disk_write_mb,
                'read_iops': 0,
                'write_iops': 0
            },
            'partition_usage': []
        }
    
    def _empty_disk_info(self) -> Dict:
        """Return empty disk info when no data available."""
        return {
            'io_stats': {
                'read_speed': 0, 'write_speed': 0,
                'read_speed_mb': 0, 'write_speed_mb': 0,
                'read_iops': 0, 'write_iops': 0
            },
            'partition_usage': []
        }
    
    def get_npu_info(self) -> Dict:
        """Get NPU information (not available on most Android devices)."""
        return {'available': False}
