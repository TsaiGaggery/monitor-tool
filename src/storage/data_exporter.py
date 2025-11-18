#!/usr/bin/env python3
"""Data export module for saving monitoring data to various formats."""

import json
import csv
import os
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path


class DataExporter:
    """Export monitoring data to CSV, JSON, or HTML formats."""
    
    def __init__(self, output_dir: str = None, data_source=None, session_start_time: datetime = None):
        """Initialize data exporter.
        
        Args:
            output_dir: Base directory to save exported files. Defaults to ./reports/
            data_source: Data source for monitoring (needed for Android DB exports)
            session_start_time: Session start time (defaults to now)
        """
        if output_dir is None:
            # Use reports directory in project root
            output_dir = 'reports'
        
        self.base_output_dir = Path(output_dir)
        self.session_data = []
        self.start_time = session_start_time if session_start_time else datetime.now()
        self.data_source = data_source
        
        # Track session time range for Android DB exports
        self.session_start_timestamp = int(self.start_time.timestamp())
        
        # Create date-based subdirectory (YYYY-MM-DD format)
        date_str = self.start_time.strftime('%Y-%m-%d')
        self.output_dir = self.base_output_dir / date_str
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def add_sample(self, data: Dict):
        """Add a monitoring sample to the session.
        
        Args:
            data: Dictionary containing monitoring data with timestamp
        """
        self.session_data.append(data.copy())
    
    def _pull_ssh_db_data(self) -> List[Dict]:
        """Pull data from remote Linux SQLite database for export.
        
        Returns:
            List of processed data samples from remote Linux DB
        """
        # Check if data source is SSH-based (RemoteLinuxDataSource)
        if self.data_source is None:
            return []
        
        # Check if data source has ssh_host attribute (RemoteLinuxDataSource)
        if not hasattr(self.data_source, 'ssh_host'):
            return []
        
        ssh_host = self.data_source.ssh_host
        ssh_user = self.data_source.username
        ssh_port = self.data_source.port
        remote_db_path = f"/tmp/monitor_tool_{ssh_user}.db"
        
        print(f"📥 Fetching remote Linux database records from {ssh_user}@{ssh_host}:{ssh_port}...")
        
        try:
            # Use session start time from data_source (when monitoring actually started)
            if hasattr(self.data_source, 'session_start_time') and self.data_source.session_start_time:
                start_timestamp = int(self.data_source.session_start_time.timestamp())
                print(f"📅 Using data source session start time: {self.data_source.session_start_time}")
            else:
                start_timestamp = self.session_start_timestamp
                print(f"📅 Using exporter session start time: {datetime.fromtimestamp(start_timestamp)}")
            
            print(f"📅 Exporting data from timestamp >= {start_timestamp}")
            
            # Query remote database directly via SSH (no backup needed)
            # Use .mode json for easy parsing and .timeout to handle locks
            sql_query = f"SELECT * FROM raw_samples WHERE timestamp >= {start_timestamp} ORDER BY timestamp ASC"
            print(f"🔍 DEBUG: SQL query = {sql_query}")
            
            query_cmd = f"sqlite3 -json {remote_db_path} \".timeout 5000\" \"{sql_query}\""
            ssh_cmd = ["ssh"]
            if self.data_source.key_path:
                ssh_cmd.extend(["-i", self.data_source.key_path])
            if ssh_port != 22:
                ssh_cmd.extend(["-p", str(ssh_port)])
            ssh_cmd.append(f"{ssh_user}@{ssh_host}")
            ssh_cmd.append(query_cmd)
            
            print("� Querying remote database via SSH...")
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"⚠️  Failed to query remote database: {result.stderr}")
                return []
            
            # Parse JSON output
            try:
                rows = json.loads(result.stdout) if result.stdout.strip() else []
            except json.JSONDecodeError as e:
                print(f"⚠️  Failed to parse query result: {e}")
                print(f"Output: {result.stdout[:200]}")
                return []
            
            if not rows:
                print(f"⚠️  No data found in specified time range")
                return []
            
            print(f"✅ Retrieved {len(rows)} samples from remote Linux database")
            print(f"🔍 DEBUG: First row timestamp = {rows[0].get('timestamp')}, Last row timestamp = {rows[-1].get('timestamp')}")
            
            # Process raw data into monitoring samples
            processed_samples = []
            prev_raw = None
            
            for idx, row in enumerate(rows):
                # Reconstruct raw_data dict from database row (now a dict from JSON)
                raw_data = {
                    'timestamp': row['timestamp'],
                    'timestamp_ms': row.get('timestamp_ms', 0),
                    'cpu_raw': {
                        'user': row['cpu_user'],
                        'nice': row['cpu_nice'],
                        'sys': row['cpu_sys'],
                        'idle': row['cpu_idle'],
                        'iowait': row['cpu_iowait'],
                        'irq': row['cpu_irq'],
                        'softirq': row['cpu_softirq'],
                        'steal': row['cpu_steal']
                    },
                    'per_core_raw': json.loads(f"[{row['per_core_raw']}]") if row.get('per_core_raw') else [],
                    'per_core_freq_khz': json.loads(f"[{row['per_core_freq_khz']}]") if row.get('per_core_freq_khz') else [],
                    'cpu_temp_millideg': row.get('cpu_temp_millideg', 0),
                    'mem_total_kb': row['mem_total_kb'],
                    'mem_free_kb': row['mem_free_kb'],
                    'mem_available_kb': row['mem_available_kb'],
                    'gpu_driver': row.get('gpu_driver', 'none'),
                    'gpu_freq_mhz': row.get('gpu_freq_mhz', 0),
                    'gpu_runtime_ms': row.get('gpu_runtime_ms', 0),
                    'gpu_memory_used_bytes': row.get('gpu_memory_used_bytes', 0),
                    'gpu_memory_total_bytes': row.get('gpu_memory_total_bytes', 0),
                    'npu_info': row.get('npu_info', ''),
                    'net_rx_bytes': row['net_rx_bytes'],
                    'net_tx_bytes': row['net_tx_bytes'],
                    'disk_read_sectors': row['disk_read_sectors'],
                    'disk_write_sectors': row['disk_write_sectors']
                }
                
                # For first sample, create placeholder with 0% utilizations
                if idx == 0:
                    processed = self._create_first_sample_ssh(raw_data, row['timestamp'])
                    processed_samples.append(processed)
                else:
                    # Process using same logic as ssh_monitor_raw.py
                    processed = self._process_ssh_raw_data(raw_data, prev_raw, row['timestamp'])
                    if processed:
                        processed_samples.append(processed)
                
                prev_raw = raw_data
            
            return processed_samples
            
        except Exception as e:
            print(f"⚠️  Error processing remote Linux database: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _is_remote_source(self) -> bool:
        """Determine if current data source is remote (SSH or Android)."""
        if not self.data_source:
            return False
        return hasattr(self.data_source, 'ssh_host') or hasattr(self.data_source, 'device_ip')
    def get_export_sample_count(self, use_android_db: bool = True, use_ssh_db: bool = True) -> int:
        """Get the count of samples that will be exported.
        
        This is useful for UI to show the correct count before actual export.
        
        Args:
            use_android_db: Whether to use Android database
            use_ssh_db: Whether to use SSH database
            
        Returns:
            Number of samples that will be exported
        """
        # Same logic as export functions
        if use_ssh_db:
            ssh_data = self._pull_ssh_db_data()
            if ssh_data:
                return len(ssh_data)
        
        if use_android_db:
            android_data = self._pull_android_db_data()
            if android_data:
                return len(android_data)
        
        # Fallback to session_data for local sources
        if self.session_data:
            return len(self.session_data)
        
        return 0
    
    def _pull_android_db_data(self) -> List[Dict]:
        """Pull data from Android SQLite database for export.
        
        Returns:
            List of processed data samples from Android DB
        """
        # Check if data source is Android-based
        if self.data_source is None:
            return []
        
        # Check if data source has device_ip attribute (AndroidDataSource)
        if not hasattr(self.data_source, 'device_ip'):
            return []
        
        device_id = f"{self.data_source.device_ip}:{self.data_source.port}"
        android_db_path = "/data/local/tmp/monitor.db"
        
        print(f"📥 Fetching Android database records from {device_id}...")
        
        try:
            # Determine time range from actual session data (client-side timestamps)
            # This ensures we get all data that was collected during the session
            if self.session_data and len(self.session_data) > 0:
                # Use first and last sample timestamps from session data
                first_sample = self.session_data[0]
                last_sample = self.session_data[-1]
                
                # Try to get utc_timestamp first (from device with get_timestamp_ms)
                start_timestamp = first_sample.get('utc_timestamp')
                end_timestamp = last_sample.get('utc_timestamp')
                
                # Fallback to time_seconds if utc_timestamp not available
                if start_timestamp is None or end_timestamp is None:
                    start_timestamp = first_sample.get('time_seconds')
                    end_timestamp = last_sample.get('time_seconds')
                
                # Fallback to parsing timestamp string if time_seconds not available
                if start_timestamp is None or end_timestamp is None:
                    first_ts = first_sample.get('timestamp', '')
                    last_ts = last_sample.get('timestamp', '')
                    if first_ts and last_ts:
                        start_timestamp = int(datetime.strptime(first_ts, '%Y-%m-%d %H:%M:%S').timestamp())
                        end_timestamp = int(datetime.strptime(last_ts, '%Y-%m-%d %H:%M:%S').timestamp())
                    else:
                        # Ultimate fallback: use session_start_timestamp
                        start_timestamp = self.session_start_timestamp
                        end_timestamp = int(datetime.now().timestamp())
            else:
                # No session data yet, use session_start_timestamp
                start_timestamp = self.session_start_timestamp
                end_timestamp = int(datetime.now().timestamp())
            
            # Fetch data as JSON directly via sqlite3 (faster than pulling entire DB)
            # Filter by session time range: from first sample to last sample (client time)
            # Note: Put SQL directly in command args (stdin doesn't work through adb shell su)
            sql_query = f"SELECT * FROM raw_samples WHERE timestamp >= {start_timestamp} AND timestamp <= {end_timestamp} ORDER BY timestamp ASC"
            
            print(f"📅 Time range: {datetime.fromtimestamp(start_timestamp)} to {datetime.fromtimestamp(end_timestamp)}")
            
            # Build command
            cmd = ["adb", "-s", device_id, "shell", f"su 0 sqlite3 -json {android_db_path} '{sql_query}'"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"⚠️  Failed to fetch Android database records: {result.stderr}")
                return []
            
            # Parse JSON output from sqlite3
            # Handle empty result (no data in time range)
            if not result.stdout.strip():
                print(f"⚠️  No data found in specified time range")
                return []
            
            rows = json.loads(result.stdout)
            
            print(f"✅ Retrieved {len(rows)} samples from Android database")
            
            # Process raw data into monitoring samples
            processed_samples = []
            prev_raw = None
            
            for idx, row in enumerate(rows):
                # Reconstruct raw_data dict from database row (now a dict from JSON)
                raw_data = {
                    'timestamp_ms': row.get('timestamp_ms', 0),  # Millisecond timestamp for GPU calc
                    'cpu_raw': {
                        'user': row['cpu_user'],
                        'nice': row['cpu_nice'],
                        'sys': row['cpu_sys'],
                        'idle': row['cpu_idle'],
                        'iowait': row['cpu_iowait'],
                        'irq': row['cpu_irq'],
                        'softirq': row['cpu_softirq'],
                        'steal': row['cpu_steal']
                    },
                    'per_core_raw': json.loads(f"[{row['per_core_raw']}]") if row['per_core_raw'] else [],
                    'per_core_freq_khz': json.loads(f"[{row['per_core_freq_khz']}]") if row['per_core_freq_khz'] else [],
                    'cpu_temp_millideg': row['cpu_temp_millideg'],
                    'mem_total_kb': row['mem_total_kb'],
                    'mem_free_kb': row['mem_free_kb'],
                    'mem_available_kb': row['mem_available_kb'],
                    'gpu_freq_mhz': row['gpu_freq_mhz'],
                    'gpu_runtime_ms': row['gpu_runtime_ms'],
                    'gpu_memory_used_bytes': row.get('gpu_memory_used_bytes', 0),
                    'gpu_memory_total_bytes': row.get('gpu_memory_total_bytes', 0),
                    'net_rx_bytes': row['net_rx_bytes'],
                    'net_tx_bytes': row['net_tx_bytes'],
                    'disk_read_sectors': row['disk_read_sectors'],
                    'disk_write_sectors': row['disk_write_sectors']
                }
                
                # For first sample, create placeholder with 0% utilizations
                if idx == 0:
                    processed = self._create_first_sample_android(raw_data, row['timestamp'])
                    processed_samples.append(processed)
                else:
                    # Process using same logic as adb_monitor_raw.py
                    processed = self._process_android_raw_data(raw_data, prev_raw, row['timestamp'])
                    if processed:
                        processed_samples.append(processed)
                
                prev_raw = raw_data
            
            return processed_samples
            
        except Exception as e:
            print(f"⚠️  Error processing Android database: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _create_first_sample_android(self, raw_data: Dict, timestamp: int) -> Dict:
        """Create first Android sample with 0% utilizations (no prev_raw for deltas).
        
        Args:
            raw_data: Raw data from Android database
            timestamp: Unix timestamp
            
        Returns:
            Processed monitoring sample with zero utilizations
        """
        # CPU count and freq
        cpu_count = len(raw_data['per_core_raw'])
        per_core_freq = [freq_khz / 1000 for freq_khz in raw_data['per_core_freq_khz']]
        avg_freq = sum(per_core_freq) / len(per_core_freq) if per_core_freq else 0
        
        # Memory
        mem_total_gb = raw_data['mem_total_kb'] / 1024 / 1024
        mem_available_gb = raw_data['mem_available_kb'] / 1024 / 1024
        mem_free_gb = raw_data['mem_free_kb'] / 1024 / 1024
        mem_used_gb = mem_total_gb - mem_available_gb
        mem_percent = (mem_used_gb * 100.0 / mem_total_gb) if mem_total_gb > 0 else 0
        
        # GPU info
        gpu_freq_mhz = raw_data.get('gpu_freq_mhz', 0)
        gpu_memory_used_bytes = raw_data.get('gpu_memory_used_bytes', 0)
        gpu_memory_total_bytes = raw_data.get('gpu_memory_total_bytes', 0)
        gpu_available = gpu_freq_mhz > 0
        
        gpu_memory_used_mb = gpu_memory_used_bytes / 1024 / 1024
        gpu_memory_total_mb = gpu_memory_total_bytes / 1024 / 1024
        
        # Construct monitoring sample with zero utilizations
        sample = {
            'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'time_seconds': timestamp,
            'utc_timestamp': timestamp,  # Android uses UTC timestamps
            'cpu': {
                'cpu_count': cpu_count,
                'physical_count': cpu_count,
                'usage': {
                    'total': 0.0,
                    'per_core': [0.0] * cpu_count
                },
                'frequency': {
                    'average': avg_freq,
                    'per_core': per_core_freq
                },
                'temperature': {
                    'cpu_thermal': [{
                        'label': 'CPU',
                        'current': raw_data['cpu_temp_millideg'] / 1000.0,
                        'high': 95.0,
                        'critical': 105.0
                    }]
                } if raw_data['cpu_temp_millideg'] > 0 else {}
            },
            'memory': {
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
            },
            'gpu': {
                'available': gpu_available,
                'gpus': [{
                    'name': 'Adreno GPU',
                    'gpu_clock': gpu_freq_mhz,
                    'clock_graphics': gpu_freq_mhz,
                    'gpu_util': 0,
                    'memory_used': gpu_memory_used_mb,
                    'memory_total': gpu_memory_total_mb,
                    'memory_util': round((gpu_memory_used_mb / gpu_memory_total_mb) * 100, 1) if gpu_memory_total_mb > 0 else 0,
                    'temperature': 0
                }] if gpu_available else []
            },
            'npu': {
                'available': False,
                'util': 0
            },
            'network': {
                'rx_MB_per_s': 0.0,
                'tx_MB_per_s': 0.0
            },
            'disk': {
                'read_MB_per_s': 0.0,
                'write_MB_per_s': 0.0
            }
        }
        
        return sample
    
    def _process_android_raw_data(self, raw_data: Dict, prev_raw: Optional[Dict], timestamp: int) -> Optional[Dict]:
        """Process raw Android data into monitoring sample format.
        
        Args:
            raw_data: Raw data from Android database
            prev_raw: Previous raw data sample for delta calculations
            timestamp: Unix timestamp
            
        Returns:
            Processed monitoring sample or None if no previous data
        """
        if prev_raw is None:
            return None  # Skip first sample (no delta calculation possible)
        
        # Calculate CPU usage
        cpu_usage = self._calculate_cpu_usage(raw_data['cpu_raw'], prev_raw['cpu_raw'])
        
        # Per-core usage and freq
        per_core_usage = []
        per_core_freq = []
        cpu_count = len(raw_data['per_core_raw'])
        
        for i in range(cpu_count):
            prev_core = prev_raw['per_core_raw'][i] if i < len(prev_raw['per_core_raw']) else {}
            core = raw_data['per_core_raw'][i]
            core_usage = self._calculate_cpu_usage(core, prev_core)
            per_core_usage.append(core_usage)
            
            core_freq_mhz = raw_data['per_core_freq_khz'][i] / 1000
            per_core_freq.append(core_freq_mhz)
        
        avg_freq = sum(per_core_freq) / len(per_core_freq) if per_core_freq else 0
        
        # Memory
        mem_total_gb = raw_data['mem_total_kb'] / 1024 / 1024
        mem_available_gb = raw_data['mem_available_kb'] / 1024 / 1024
        mem_free_gb = raw_data['mem_free_kb'] / 1024 / 1024
        mem_used_gb = mem_total_gb - mem_available_gb
        mem_percent = (mem_used_gb * 100.0 / mem_total_gb) if mem_total_gb > 0 else 0
        
        # GPU utilization - use ACTUAL time delta from millisecond timestamps
        # Support both i915 (runtime) and Xe (idle_residency) drivers
        gpu_driver = raw_data.get('gpu_driver', 'i915')  # Default to i915 for backward compatibility
        gpu_runtime_ms = raw_data.get('gpu_runtime_ms', 0)
        timestamp_ms = raw_data.get('timestamp_ms', 0)
        prev_gpu_runtime_ms = prev_raw.get('gpu_runtime_ms', gpu_runtime_ms)
        prev_timestamp_ms = prev_raw.get('timestamp_ms', timestamp_ms)
        
        gpu_util = 0
        if all([gpu_runtime_ms, prev_gpu_runtime_ms, timestamp_ms, prev_timestamp_ms]):
            runtime_delta = gpu_runtime_ms - prev_gpu_runtime_ms
            time_delta = timestamp_ms - prev_timestamp_ms  # Actual measured time
            
            if time_delta > 0:
                if gpu_driver == 'xe':
                    # For Xe: runtime_ms is idle_residency_ms
                    # Utilization = 100 - (idle_delta / time_delta * 100)
                    idle_percentage = (runtime_delta / time_delta) * 100
                    gpu_util = int(max(0, min(100, 100 - idle_percentage)))
                else:
                    # For i915: runtime_ms is active time
                    gpu_util = int((runtime_delta / time_delta) * 100)
                    gpu_util = max(0, min(100, gpu_util))
        
        # Network deltas
        SECTOR_SIZE = 512
        delta_rx = max(0, raw_data['net_rx_bytes'] - prev_raw['net_rx_bytes'])
        delta_tx = max(0, raw_data['net_tx_bytes'] - prev_raw['net_tx_bytes'])
        
        # Disk deltas
        delta_read_sectors = max(0, raw_data['disk_read_sectors'] - prev_raw['disk_read_sectors'])
        delta_write_sectors = max(0, raw_data['disk_write_sectors'] - prev_raw['disk_write_sectors'])
        
        read_mb_s = (delta_read_sectors * SECTOR_SIZE) / (1024 * 1024)
        write_mb_s = (delta_write_sectors * SECTOR_SIZE) / (1024 * 1024)
        
        # Construct monitoring sample (match format from main_window.py add_sample)
        return {
            'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'time_seconds': timestamp,
            'cpu': {
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
                } if raw_data['cpu_temp_millideg'] > 0 else {}
            },
            'memory': {
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
            },
            'gpu': {
                'available': raw_data['gpu_freq_mhz'] > 0,
                'gpus': [{
                    'name': 'Android GPU',
                    'gpu_clock': raw_data['gpu_freq_mhz'],
                    'clock_graphics': raw_data['gpu_freq_mhz'],
                    'gpu_util': gpu_util,
                    'memory_used': raw_data.get('gpu_memory_used_bytes', 0) // (1024 * 1024),  # From i915_gem_objects or xe fdinfo
                    'memory_total': raw_data.get('gpu_memory_total_bytes', 0) // (1024 * 1024),  # From i915_gem_objects or xe fdinfo
                    'memory_util': round((raw_data.get('gpu_memory_used_bytes', 0) / raw_data.get('gpu_memory_total_bytes', 1)) * 100, 1) if raw_data.get('gpu_memory_total_bytes', 0) > 0 else 0,  # Keep one decimal place
                    'temperature': 0
                }] if raw_data['gpu_freq_mhz'] > 0 else []
            },
            'network': {
                'upload_speed': delta_tx,
                'download_speed': delta_rx,
                'interfaces': [],
                'interface_stats': {},
                'io_stats': {
                    'upload_speed': delta_tx,
                    'download_speed': delta_rx,
                    'packets_sent': 0,
                    'packets_recv': 0
                },
                'connections': {'total': 0, 'tcp_established': 0}
            },
            'disk': {
                'read_speed_mb': read_mb_s,
                'write_speed_mb': write_mb_s,
                'partitions': {},
                'disks': [],
                'io_stats': {
                    'read_speed': read_mb_s * 1024 * 1024,
                    'write_speed': write_mb_s * 1024 * 1024,
                    'read_speed_mb': read_mb_s,
                    'write_speed_mb': write_mb_s,
                    'read_iops': delta_read_sectors,
                    'write_iops': delta_write_sectors
                },
                'partition_usage': []
            }
        }
    
    def _create_first_sample_ssh(self, raw_data: Dict, timestamp: int) -> Dict:
        """Create first SSH sample with 0% utilizations (no prev_raw for deltas).
        
        Args:
            raw_data: Raw data from remote Linux database
            timestamp: Unix timestamp
            
        Returns:
            Processed monitoring sample with zero utilizations
        """
        # CPU count and freq
        cpu_count = len(raw_data['per_core_raw'])
        per_core_freq = [freq_khz / 1000 for freq_khz in raw_data['per_core_freq_khz']]
        avg_freq = sum(per_core_freq) / len(per_core_freq) if per_core_freq else 0
        
        # Memory
        mem_total_gb = raw_data['mem_total_kb'] / 1024 / 1024
        mem_available_gb = raw_data['mem_available_kb'] / 1024 / 1024
        mem_free_gb = raw_data['mem_free_kb'] / 1024 / 1024
        mem_used_gb = mem_total_gb - mem_available_gb
        mem_percent = (mem_used_gb * 100.0 / mem_total_gb) if mem_total_gb > 0 else 0
        
        # GPU info
        gpu_driver = raw_data.get('gpu_driver', 'none')
        gpu_freq_mhz = raw_data.get('gpu_freq_mhz', 0)
        gpu_memory_used_bytes = raw_data.get('gpu_memory_used_bytes', 0)
        gpu_memory_total_bytes = raw_data.get('gpu_memory_total_bytes', 0)
        
        # GPU is available if driver is not 'none' (freq can be 0 when idle)
        gpu_available = gpu_driver not in ['none', '', 'N/A']
        
        gpu_name = 'N/A'
        gpu_memory_used_mb = gpu_memory_used_bytes / 1024 / 1024
        gpu_memory_total_mb = gpu_memory_total_bytes / 1024 / 1024
        
        if gpu_available:
            gpu_name = f'Remote GPU ({gpu_driver.upper()})'
        
        # NPU info
        npu_info_str = raw_data.get('npu_info', '')
        npu_available = npu_info_str and npu_info_str != 'N/A'
        
        # Construct monitoring sample with zero utilizations
        sample = {
            'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'time_seconds': timestamp,
            'cpu': {
                'cpu_count': cpu_count,
                'physical_count': cpu_count,
                'usage': {
                    'total': 0.0,
                    'per_core': [0.0] * cpu_count
                },
                'frequency': {
                    'average': avg_freq,
                    'per_core': per_core_freq
                },
                'temperature': {
                    'cpu_thermal': [{
                        'label': 'Package id 0',
                        'current': raw_data['cpu_temp_millideg'] / 1000.0,
                        'high': 100.0,
                        'critical': 105.0
                    }]
                } if raw_data['cpu_temp_millideg'] > 0 else {}
            },
            'memory': {
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
            },
            'gpu': {
                'available': gpu_available,
                'gpus': [{
                    'name': gpu_name,
                    'gpu_clock': gpu_freq_mhz,
                    'clock_graphics': gpu_freq_mhz,
                    'gpu_util': 0,
                    'memory_used': gpu_memory_used_mb,
                    'memory_total': gpu_memory_total_mb,
                    'memory_util': round((gpu_memory_used_mb / gpu_memory_total_mb) * 100, 1) if gpu_memory_total_mb > 0 else 0,
                    'temperature': 0
                }] if gpu_available else []
            },
            'npu': {
                'available': npu_available,
                'npus': [{
                    'name': 'Intel NPU',
                    'npu_util': 0
                }] if npu_available else []
            },
            'network': {
                'rx_MB_per_s': 0.0,
                'tx_MB_per_s': 0.0
            },
            'disk': {
                'read_MB_per_s': 0.0,
                'write_MB_per_s': 0.0
            }
        }
        
        return sample
    
    def _process_ssh_raw_data(self, raw_data: Dict, prev_raw: Optional[Dict], timestamp: int) -> Optional[Dict]:
        """Process raw SSH/Linux data into monitoring sample format.
        
        Args:
            raw_data: Raw data from remote Linux database
            prev_raw: Previous raw data sample for delta calculations
            timestamp: Unix timestamp
            
        Returns:
            Processed monitoring sample or None if no previous data
        """
        if prev_raw is None:
            return None  # Skip first sample (no delta calculation possible)
        
        # Calculate CPU usage
        cpu_usage = self._calculate_cpu_usage(raw_data['cpu_raw'], prev_raw['cpu_raw'])
        
        # Per-core usage and freq
        per_core_usage = []
        per_core_freq = []
        cpu_count = len(raw_data['per_core_raw'])
        
        for i in range(cpu_count):
            prev_core = prev_raw['per_core_raw'][i] if i < len(prev_raw['per_core_raw']) else {}
            core = raw_data['per_core_raw'][i]
            core_usage = self._calculate_cpu_usage(core, prev_core)
            per_core_usage.append(core_usage)
            
            core_freq_mhz = raw_data['per_core_freq_khz'][i] / 1000
            per_core_freq.append(core_freq_mhz)
        
        avg_freq = sum(per_core_freq) / len(per_core_freq) if per_core_freq else 0
        
        # Memory
        mem_total_gb = raw_data['mem_total_kb'] / 1024 / 1024
        mem_available_gb = raw_data['mem_available_kb'] / 1024 / 1024
        mem_free_gb = raw_data['mem_free_kb'] / 1024 / 1024
        mem_used_gb = mem_total_gb - mem_available_gb
        mem_percent = (mem_used_gb * 100.0 / mem_total_gb) if mem_total_gb > 0 else 0
        
        # GPU info (new schema: individual fields)
        gpu_driver = raw_data.get('gpu_driver', 'none')
        gpu_freq_mhz = raw_data.get('gpu_freq_mhz', 0)
        gpu_runtime_ms = raw_data.get('gpu_runtime_ms', 0)
        gpu_memory_used_bytes = raw_data.get('gpu_memory_used_bytes', 0)
        gpu_memory_total_bytes = raw_data.get('gpu_memory_total_bytes', 0)
        
        prev_gpu_runtime_ms = prev_raw.get('gpu_runtime_ms', 0)
        
        # GPU is available if driver is not 'none' (freq can be 0 when GPU is idle)
        gpu_available = gpu_driver not in ['none', '', 'N/A']
        gpu_name = 'N/A'
        gpu_util = 0
        gpu_memory_used_mb = gpu_memory_used_bytes / 1024 / 1024
        gpu_memory_total_mb = gpu_memory_total_bytes / 1024 / 1024
        
        if gpu_available:
            # Use same naming as ssh_monitor_raw.py
            gpu_name = f'Remote GPU ({gpu_driver.upper()})'
            
            # Calculate GPU utilization from runtime delta
            # gpu_runtime_ms is idle_residency_ms (Xe) or rc6_residency_ms (i915)
            prev_timestamp = prev_raw.get('timestamp', timestamp)
            time_delta_ms = (timestamp - prev_timestamp) * 1000  # Convert to milliseconds
            
            if time_delta_ms > 0 and gpu_runtime_ms >= prev_gpu_runtime_ms:
                runtime_delta = gpu_runtime_ms - prev_gpu_runtime_ms
                # Utilization = 100 - (idle_time / total_time * 100)
                gpu_util = int(max(0, min(100, 100 - (runtime_delta / time_delta_ms * 100))))
            else:
                gpu_util = 0
        
        # Parse NPU info (format: "driver:id:device_id:product_id:util")
        npu_info_str = raw_data.get('npu_info', '')
        npu_available = False
        npu_util = 0
        
        if npu_info_str and npu_info_str != 'N/A':
            parts = npu_info_str.split(':')
            if len(parts) >= 5:
                npu_util = int(parts[4])
                npu_available = True
        
        # Network deltas
        SECTOR_SIZE = 512
        delta_rx = max(0, raw_data['net_rx_bytes'] - prev_raw['net_rx_bytes'])
        delta_tx = max(0, raw_data['net_tx_bytes'] - prev_raw['net_tx_bytes'])
        
        # Disk deltas
        delta_read_sectors = max(0, raw_data['disk_read_sectors'] - prev_raw['disk_read_sectors'])
        delta_write_sectors = max(0, raw_data['disk_write_sectors'] - prev_raw['disk_write_sectors'])
        
        read_mb_s = (delta_read_sectors * SECTOR_SIZE) / (1024 * 1024)
        write_mb_s = (delta_write_sectors * SECTOR_SIZE) / (1024 * 1024)
        
        # Construct monitoring sample (match format from main_window.py add_sample)
        sample = {
            'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'time_seconds': timestamp,
            'cpu': {
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
                    'cpu_thermal': [{
                        'label': 'Package id 0',
                        'current': raw_data['cpu_temp_millideg'] / 1000.0,
                        'high': 100.0,
                        'critical': 105.0
                    }]
                } if raw_data['cpu_temp_millideg'] > 0 else {}
            },
            'memory': {
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
            },
            'gpu': {
                'available': gpu_available,
                'gpus': [{
                    'name': gpu_name,
                    'gpu_clock': gpu_freq_mhz,
                    'clock_graphics': gpu_freq_mhz,
                    'gpu_util': gpu_util,
                    'memory_used': gpu_memory_used_mb,
                    'memory_total': gpu_memory_total_mb,
                    'memory_util': round((gpu_memory_used_mb / gpu_memory_total_mb) * 100, 1) if gpu_memory_total_mb > 0 else 0,
                    'temperature': 0
                }] if gpu_available else []
            },
            'npu': {
                'available': npu_available,
                'npus': [{
                    'name': 'Intel NPU',
                    'npu_util': npu_util
                }] if npu_available else []
            },
            'network': {
                'upload_speed': delta_tx,
                'download_speed': delta_rx,
                'connections': {'total': 0, 'tcp_established': 0},
                'interfaces': [],
                'interface_stats': {},
                'io_stats': {
                    'upload_speed': delta_tx,
                    'download_speed': delta_rx,
                    'packets_sent': 0,
                    'packets_recv': 0
                }
            },
            'disk': {
                'read_speed_mb': read_mb_s,
                'write_speed_mb': write_mb_s,
                'partitions': {},
                'disks': [],
                'io_stats': {
                    'read_speed': read_mb_s * 1024 * 1024,
                    'write_speed': write_mb_s * 1024 * 1024,
                    'read_speed_mb': read_mb_s,
                    'write_speed_mb': write_mb_s,
                    'read_iops': delta_read_sectors,
                    'write_iops': delta_write_sectors
                },
                'partition_usage': []
            }
        }
        
        return sample
    
    def _calculate_cpu_usage(self, curr, prev):
        """Calculate CPU usage from raw /proc/stat values."""
        if not prev:
            return 0.0
        
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
    
    def export_csv(self, filename: str = None, use_android_db: bool = True, use_ssh_db: bool = True) -> str:
        """Export session data to CSV format.
        
        Args:
            filename: Output filename. Auto-generated if None.
            use_android_db: If True and data source is Android, pull from Android DB
            use_ssh_db: If True and data source is SSH, pull from remote Linux DB
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            filename = f'monitoring_data_{timestamp}.csv'
        
        filepath = self.output_dir / filename
        
        # For remote sources (SSH/Android), ONLY use remote database
        # Do NOT mix with session_data (host-side streaming data)
        export_data = None
        
        # Priority: SSH DB > Android DB > Session data (local only)
        if use_ssh_db:
            ssh_data = self._pull_ssh_db_data()
            if ssh_data:
                export_data = ssh_data
                print(f"📊 Exporting {len(export_data)} samples from remote Linux database")
        
        if use_android_db and export_data is None:  # Only if SSH didn't provide data
            android_data = self._pull_android_db_data()
            if android_data:
                export_data = android_data
                print(f"📊 Exporting {len(export_data)} samples from Android database")
        
        # Fallback to session_data only for true local sources
        if export_data is None:
            if self._is_remote_source():
                raise ValueError("Remote data source has no database samples available for export")
            export_data = self.session_data
            if export_data:
                print(f"📊 Exporting {len(export_data)} samples from session data (local source)")
        
        if not export_data:
            raise ValueError("No data to export")
        
        # Extract all unique keys from all samples
        all_keys = set()
        for sample in export_data:
            all_keys.update(self._flatten_dict(sample).keys())
        
        all_keys = sorted(all_keys)
        
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=all_keys)
            writer.writeheader()
            
            for sample in export_data:
                flat_data = self._flatten_dict(sample)
                writer.writerow(flat_data)
        
        return str(filepath)
    
    def export_json(self, filename: str = None, use_android_db: bool = True, use_ssh_db: bool = True) -> str:
        """Export session data to JSON format.
        
        Args:
            filename: Output filename. Auto-generated if None.
            use_android_db: If True and data source is Android, pull from Android DB
            use_ssh_db: If True and data source is SSH, pull from remote Linux DB
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            filename = f'monitoring_data_{timestamp}.json'
        
        filepath = self.output_dir / filename
        
        # For remote sources (SSH/Android), ONLY use remote database
        # Do NOT mix with session_data (host-side streaming data)
        export_samples = None
        
        # Priority: SSH DB > Android DB > Session data (local only)
        if use_ssh_db:
            ssh_data = self._pull_ssh_db_data()
            if ssh_data:
                export_samples = ssh_data
                print(f"📊 Exporting {len(export_samples)} samples from remote Linux database")
        
        if use_android_db and export_samples is None:  # Only if SSH didn't provide data
            android_data = self._pull_android_db_data()
            if android_data:
                export_samples = android_data
                print(f"📊 Exporting {len(export_samples)} samples from Android database")
        
        # Fallback to session data only for local sources
        if export_samples is None:
            if self._is_remote_source():
                raise ValueError("Remote data source has no database samples available for export")
            export_samples = self.session_data
            if export_samples:
                print(f"📊 Exporting {len(export_samples)} samples from session data (local source)")
        
        if not export_samples:
            raise ValueError("No data to export")
        
        export_data = {
            'session_info': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'sample_count': len(export_samples)
            },
            'data': export_samples
        }
        
        with open(filepath, 'w') as jsonfile:
            json.dump(export_data, jsonfile, indent=2)
        
        return str(filepath)
    
    def export_html(self, filename: str = None, use_android_db: bool = True, use_ssh_db: bool = True) -> str:
        """Export session data to HTML report format.
        
        Args:
            filename: Output filename. Auto-generated if None.
            use_android_db: If True and data source is Android, pull from Android DB
            use_ssh_db: If True and data source is SSH, pull from remote Linux DB
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            # Include source information in filename
            if self.data_source:
                source_name = self.data_source.get_source_name().replace(' ', '_').replace('(', '').replace(')', '').replace(':', '_')
                filename = f'monitoring_report_{source_name}_{timestamp}.html'
            else:
                filename = f'monitoring_report_{timestamp}.html'
        
        filepath = self.output_dir / filename
        
        # For remote sources (SSH/Android), ONLY use remote database
        # Do NOT mix with session_data (host-side streaming data)
        export_samples = None
        
        # Priority: SSH DB > Android DB > Session data (local only)
        if use_ssh_db:
            ssh_data = self._pull_ssh_db_data()
            if ssh_data:
                export_samples = ssh_data
                print(f"📊 Exporting {len(export_samples)} samples from remote Linux database")
        
        if use_android_db and export_samples is None:  # Only if SSH didn't provide data
            android_data = self._pull_android_db_data()
            if android_data:
                export_samples = android_data
                print(f"📊 Exporting {len(export_samples)} samples from Android database")
        
        # Fallback to session data only for local sources
        if export_samples is None:
            if self._is_remote_source():
                raise ValueError("Remote data source has no database samples available for export")
            export_samples = self.session_data
            if export_samples:
                print(f"📊 Exporting {len(export_samples)} samples from session data (local source)")
        
        if not export_samples:
            raise ValueError("No data to export")
        
        # Temporarily replace session_data for statistics calculation
        original_session_data = self.session_data
        self.session_data = export_samples
        
        # Calculate statistics
        stats = self._calculate_statistics()
        
        html_content = self._generate_html_report(stats)
        
        # Restore original session_data
        self.session_data = original_session_data
        
        with open(filepath, 'w') as htmlfile:
            htmlfile.write(html_content)
        
        return str(filepath)
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten nested dictionary.
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key for nested items
            sep: Separator between parent and child keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert list to string representation
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _calculate_statistics(self) -> Dict:
        """Calculate statistics from session data.
        
        Returns:
            Dictionary containing min, max, avg for various metrics
        """
        stats = {}
        
        if not self.session_data:
            return stats
        
        # Extract numeric values for each key
        numeric_data = {}
        for sample in self.session_data:
            flat_sample = self._flatten_dict(sample)
            for key, value in flat_sample.items():
                if isinstance(value, (int, float)):
                    if key not in numeric_data:
                        numeric_data[key] = []
                    numeric_data[key].append(value)
        
        # Calculate min, max, avg
        for key, values in numeric_data.items():
            if values:
                stats[key] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'samples': len(values)
                }
        
        return stats
    
    def _generate_html_report(self, stats: Dict) -> str:
        """Generate interactive HTML report with charts.
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            HTML string with interactive charts
        """
        # Calculate duration from actual data timestamps
        if self.session_data and len(self.session_data) >= 2:
            try:
                # Use time_seconds if available (more accurate)
                first_time_sec = self.session_data[0].get('time_seconds')
                last_time_sec = self.session_data[-1].get('time_seconds')
                
                if first_time_sec is not None and last_time_sec is not None:
                    # Calculate duration from time_seconds (actual elapsed time)
                    duration_seconds = last_time_sec - first_time_sec
                    duration = timedelta(seconds=duration_seconds)
                else:
                    # Fallback: parse timestamp strings
                    first_ts = self.session_data[0].get('timestamp', '')
                    last_ts = self.session_data[-1].get('timestamp', '')
                    
                    if first_ts and last_ts:
                        first_time = datetime.strptime(first_ts, '%Y-%m-%d %H:%M:%S')
                        last_time = datetime.strptime(last_ts, '%Y-%m-%d %H:%M:%S')
                        duration = last_time - first_time
                    else:
                        duration = datetime.now() - self.start_time
            except:
                duration = datetime.now() - self.start_time
        else:
            duration = datetime.now() - self.start_time
        
        # Prepare chart data - extract ALL available data
        timestamps = []
        
        # CPU data arrays
        cpu_usage_total = []
        cpu_usage_per_core = []  # List of lists for each core
        cpu_freq_avg = []
        cpu_freq_per_core = []  # List of lists for each core
        cpu_temps = []  # List of lists for each temp sensor
        
        # GPU data arrays
        gpu_usage = []
        gpu_memory_used = []
        gpu_memory_util = []
        gpu_freq = []
        gpu_temp = []
        gpu_power = []
        
        # Memory data arrays
        memory_percent = []
        memory_used = []
        memory_available = []
        swap_percent = []
        
        # NPU data arrays
        npu_usage = []
        
        # Network data arrays
        network_upload = []
        network_download = []
        
        # Disk data arrays
        disk_read = []
        disk_write = []
        
        # Track max cores/temps for consistent array sizes
        max_cpu_cores = 0
        max_temp_sensors = 0
        
        for sample in self.session_data:
            # Extract timestamp
            if 'timestamp' in sample:
                timestamps.append(sample['timestamp'])
            else:
                timestamps.append(len(timestamps))
            
            # CPU data extraction
            if 'cpu' in sample:
                cpu_data = sample['cpu']
                if isinstance(cpu_data, dict):
                    # Total CPU usage
                    usage = cpu_data.get('usage', {})
                    if isinstance(usage, dict):
                        cpu_usage_total.append(usage.get('total', 0))
                        # Per-core usage
                        per_core = usage.get('per_core', [])
                        if per_core:
                            max_cpu_cores = max(max_cpu_cores, len(per_core))
                            cpu_usage_per_core.append(per_core)
                    else:
                        cpu_usage_total.append(usage if usage else 0)
                        cpu_usage_per_core.append([])
                    
                    # CPU frequency
                    freq = cpu_data.get('frequency', {})
                    if isinstance(freq, dict):
                        cpu_freq_avg.append(freq.get('average', 0))
                        # Per-core frequency - keep full objects
                        per_core_freq = freq.get('per_core', [])
                        if per_core_freq:
                            cpu_freq_per_core.append(per_core_freq)
                        else:
                            cpu_freq_per_core.append([])
                    else:
                        cpu_freq_avg.append(freq if freq else 0)
                        cpu_freq_per_core.append([])
                    
                    # CPU temperature
                    temp = cpu_data.get('temperature', {})
                    if isinstance(temp, dict):
                        # Try different temp sensor names (local: coretemp, android: Thermal, ssh: cpu_thermal)
                        coretemp = temp.get('coretemp', []) or temp.get('Thermal', []) or temp.get('cpu_thermal', [])
                        if coretemp:
                            max_temp_sensors = max(max_temp_sensors, len(coretemp))
                            # Keep full sensor info (label + current)
                            cpu_temps.append(coretemp)
                        else:
                            cpu_temps.append([])
                    else:
                        cpu_temps.append([])
            
            # GPU data extraction
            if 'gpu' in sample:
                gpu_data = sample['gpu']
                if isinstance(gpu_data, dict):
                    if 'gpus' in gpu_data and isinstance(gpu_data['gpus'], list) and len(gpu_data['gpus']) > 0:
                        first_gpu = gpu_data['gpus'][0]
                        gpu_usage.append(first_gpu.get('gpu_util', 0))
                        gpu_memory_used.append(first_gpu.get('memory_used', 0))
                        gpu_memory_util.append(first_gpu.get('memory_util', 0))
                        gpu_freq.append(first_gpu.get('gpu_clock', 0))
                        gpu_temp.append(first_gpu.get('temperature', 0))
                        gpu_power.append(first_gpu.get('power', 0))
                    else:
                        gpu_usage.append(gpu_data.get('gpu_util', 0))
                        gpu_memory_used.append(gpu_data.get('memory_used', 0))
                        gpu_memory_util.append(gpu_data.get('memory_util', 0))
                        gpu_freq.append(gpu_data.get('gpu_clock', 0))
                        gpu_temp.append(gpu_data.get('temperature', 0))
                        gpu_power.append(gpu_data.get('power', 0))
            else:
                gpu_usage.append(0)
                gpu_memory_used.append(0)
                gpu_memory_util.append(0)
                gpu_freq.append(0)
                gpu_temp.append(0)
                gpu_power.append(0)
            
            # Memory data extraction
            if 'memory' in sample:
                mem_data = sample['memory']
                if isinstance(mem_data, dict):
                    if 'memory' in mem_data and isinstance(mem_data['memory'], dict):
                        mem_info = mem_data['memory']
                        memory_percent.append(mem_info.get('percent', 0))
                        memory_used.append(mem_info.get('used', 0))
                        memory_available.append(mem_info.get('available', 0))
                    else:
                        memory_percent.append(mem_data.get('percent', 0))
                        memory_used.append(mem_data.get('used', 0))
                        memory_available.append(mem_data.get('available', 0))
                    
                    # Swap data
                    if 'swap' in mem_data and isinstance(mem_data['swap'], dict):
                        swap_percent.append(mem_data['swap'].get('percent', 0))
                    else:
                        swap_percent.append(0)
            
            # NPU data extraction
            if 'npu' in sample:
                npu_data = sample['npu']
                if isinstance(npu_data, dict):
                    # Try 'utilization' first (old format)
                    if 'utilization' in npu_data:
                        npu_usage.append(npu_data.get('utilization', 0))
                    # Try 'npus' array (new format from SSH/Android)
                    elif 'npus' in npu_data and npu_data['npus']:
                        first_npu = npu_data['npus'][0]
                        npu_usage.append(first_npu.get('npu_util', 0))
                    else:
                        npu_usage.append(0)
                else:
                    npu_usage.append(0)
            else:
                # No NPU data in this sample, append 0 to keep arrays aligned
                npu_usage.append(0)
            
            # Network data extraction
            if 'network' in sample:
                net_data = sample['network']
                if isinstance(net_data, dict):
                    # Try io_stats first, then top-level
                    io_stats = net_data.get('io_stats', {})
                    if io_stats:
                        network_upload.append(io_stats.get('upload_speed', 0) / (1024 * 1024))  # MB/s
                        network_download.append(io_stats.get('download_speed', 0) / (1024 * 1024))  # MB/s
                    else:
                        network_upload.append(net_data.get('upload_speed', 0) / (1024 * 1024))  # MB/s
                        network_download.append(net_data.get('download_speed', 0) / (1024 * 1024))  # MB/s
                else:
                    network_upload.append(0)
                    network_download.append(0)
            else:
                network_upload.append(0)
                network_download.append(0)
            
            # Disk data extraction
            if 'disk' in sample:
                disk_data = sample['disk']
                if isinstance(disk_data, dict):
                    # Try io_stats first
                    io_stats = disk_data.get('io_stats', {})
                    if io_stats:
                        disk_read.append(io_stats.get('read_speed_mb', 0))  # MB/s
                        disk_write.append(io_stats.get('write_speed_mb', 0))  # MB/s
                    else:
                        disk_read.append(disk_data.get('read_speed_mb', 0))  # MB/s
                        disk_write.append(disk_data.get('write_speed_mb', 0))  # MB/s
                else:
                    disk_read.append(0)
                    disk_write.append(0)
            else:
                disk_read.append(0)
                disk_write.append(0)
        
        # Convert to JSON for JavaScript
        import json
        chart_data = {
            'timestamps': timestamps,
            'cpu': {
                'usage_total': cpu_usage_total,
                'usage_per_core': cpu_usage_per_core,
                'freq_avg': cpu_freq_avg,
                'freq_per_core': cpu_freq_per_core,
                'temps': cpu_temps,
                'max_cores': max_cpu_cores,
                'max_temp_sensors': max_temp_sensors
            },
            'gpu': {
                'usage': gpu_usage,
                'memory_used': gpu_memory_used,
                'memory_util': gpu_memory_util,
                'freq': gpu_freq,
                'temp': gpu_temp,
                'power': gpu_power
            },
            'memory': {
                'percent': memory_percent,
                'used': memory_used,
                'available': memory_available,
                'swap_percent': swap_percent
            },
            'network': {
                'upload': network_upload,
                'download': network_download
            },
            'disk': {
                'read': disk_read,
                'write': disk_write
            },
            'npu': {
                'usage': npu_usage
            }
        }
        
        # Calculate statistics
        stats = self._calculate_statistics()
        
        # Generate NPU section if data exists (even if all zeros)
        npu_section = ''
        if npu_usage:  # Check if array has any values
            npu_section = '<h3 style="color: #14ffec; margin-top: 30px;">🤖 NPU Metrics</h3><div class="chart-container"><div class="chart-title">NPU Usage (%)</div><canvas id="npuUsageChart"></canvas></div>'
        
        # Generate Network section if data exists
        network_section = ''
        if network_upload or network_download:
            network_section = '''
            <h3 style="color: #3b82f6; margin-top: 30px;">🌐 Network I/O</h3>
            <div class="chart-container">
                <div class="chart-title">Network Speed (MB/s)</div>
                <canvas id="networkChart"></canvas>
            </div>
            '''
        
        # Generate Disk section if data exists
        disk_section = ''
        if disk_read or disk_write:
            disk_section = '''
            <h3 style="color: #f59e0b; margin-top: 30px;">💿 Disk I/O</h3>
            <div class="chart-container">
                <div class="chart-title">Disk Speed (MB/s)</div>
                <canvas id="diskChart"></canvas>
            </div>
            '''
        
        # Generate statistics table rows
        stats_rows = ''
        sorted_metrics = sorted(stats.items())
        for metric, values in sorted_metrics:
            stats_rows += f'''                <tr>
                    <td class="metric-name">{metric}</td>
                    <td class="value-min">{values['min']:.2f}</td>
                    <td class="value-max">{values['max']:.2f}</td>
                    <td class="value-avg">{values['avg']:.2f}</td>
                    <td>{values['samples']}</td>
                </tr>
'''
        
        # Load HTML template
        template_path = Path(__file__).parent.parent.parent / 'templates' / 'report.html'
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Template not found at {template_path}")
        
        # Get source name for the report
        source_name = self.data_source.get_source_name() if self.data_source else "Local System"
        
        # Replace template variables
        html = template.replace('{{ start_time }}', self.start_time.strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{ duration }}', str(duration))
        html = html.replace('{{ data_points }}', str(len(self.session_data)))
        html = html.replace('{{ source_name }}', source_name)
        html = html.replace('{{ chart_data_json }}', json.dumps(chart_data).replace("'", "\\'"))
        html = html.replace('{{ npu_section }}', npu_section)
        html = html.replace('{{ network_section }}', network_section)
        html = html.replace('{{ disk_section }}', disk_section)
        html = html.replace('{{ stats_rows }}', stats_rows)
        html = html.replace('{{ report_time }}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        return html
    
    def clear_session(self):
        """Clear current session data and start a new session."""
        self.session_data = []
        self.start_time = datetime.now()
        
        # Update output directory to new date
        date_str = self.start_time.strftime('%Y-%m-%d')
        self.output_dir = self.base_output_dir / date_str
        self.output_dir.mkdir(parents=True, exist_ok=True)


if __name__ == '__main__':
    # Test the exporter
    exporter = DataExporter()
    
    # Add some test samples
    for i in range(10):
        exporter.add_sample({
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'usage': 50 + i,
                'temp': 60 + i * 0.5
            },
            'gpu': {
                'usage': 30 + i * 2,
                'memory': 2000 + i * 100
            }
        })
    
    # Export to all formats
    print("CSV:", exporter.export_csv())
    print("JSON:", exporter.export_json())
    print("HTML:", exporter.export_html())
