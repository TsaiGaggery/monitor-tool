#!/usr/bin/env python3
"""Data export module for saving monitoring data to various formats."""

import json
import csv
import os
import subprocess
import time
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# Import for session database and log collection
from storage.data_logger import DataLogger
try:
    from monitors.log_monitor import LogMonitor, LogEntry
except ImportError:
    LogMonitor = None
    LogEntry = None


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
        
        # Cache for database queries (to avoid repeated expensive queries)
        self._db_cache = {
            'ssh': None,
            'android': None,
            'local': None
        }
        
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
        # Invalidate cache when new data is added
        self._invalidate_cache()
    
    def _invalidate_cache(self):
        """Invalidate all database caches when new data arrives."""
        self._db_cache = {
            'ssh': None,
            'android': None,
            'local': None
        }
    
    def _pull_ssh_db_data(self) -> List[Dict]:
        """Pull data from remote Linux SQLite database for export.
        
        Returns:
            List of processed data samples from remote Linux DB
        """
        # Return cached data if available
        if self._db_cache['ssh'] is not None:
            print(f"📦 Using cached SSH database data ({len(self._db_cache['ssh'])} samples)")
            return self._db_cache['ssh']
        
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
            
            # Query remote database directly via SSH
            # Use .mode json for easy parsing and .timeout to handle locks
            sql_query = f"SELECT * FROM monitoring_data WHERE timestamp >= {start_timestamp} ORDER BY timestamp ASC"
            query_cmd = f"sqlite3 -json {remote_db_path} \".timeout 5000\" \"{sql_query}\""
            
            stdout_content = ""
            stderr_content = ""
            
            # Try to use existing paramiko client from data source first
            used_paramiko = False
            if hasattr(self.data_source, 'ssh_monitor') and self.data_source.ssh_monitor and self.data_source.ssh_monitor.ssh_client:
                try:
                    print("🔌 Using existing SSH connection for export...")
                    stdin, stdout, stderr = self.data_source.ssh_monitor.ssh_client.exec_command(query_cmd, timeout=60)
                    stdout_content = stdout.read().decode()
                    stderr_content = stderr.read().decode()
                    used_paramiko = True
                except Exception as e:
                    print(f"⚠️  Failed to use existing SSH connection: {e}")
            
            # If existing connection failed or not available, try creating a new paramiko client if we have credentials
            if not used_paramiko and hasattr(self.data_source, 'password') and self.data_source.password:
                try:
                    print("🔑 Creating new SSH connection for export (using password)...")
                    import paramiko
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(
                        ssh_host, 
                        port=ssh_port, 
                        username=ssh_user, 
                        password=self.data_source.password,
                        timeout=10,
                        look_for_keys=False,
                        allow_agent=False
                    )
                    
                    stdin, stdout, stderr = client.exec_command(query_cmd, timeout=60)
                    stdout_content = stdout.read().decode()
                    stderr_content = stderr.read().decode()
                    client.close()
                    used_paramiko = True
                except Exception as e:
                    print(f"⚠️  Failed to create new SSH connection: {e}")

            # Fallback to system ssh command if paramiko failed
            if not used_paramiko:
                print("⚠️  Falling back to system SSH command (may prompt for password)...")
                ssh_cmd = ["ssh"]
                if self.data_source.key_path:
                    ssh_cmd.extend(["-i", self.data_source.key_path])
                if ssh_port != 22:
                    ssh_cmd.extend(["-p", str(ssh_port)])
                ssh_cmd.append(f"{ssh_user}@{ssh_host}")
                ssh_cmd.append(query_cmd)
                
                print(" Querying remote database via SSH...")
                result = subprocess.run(
                    ssh_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    print(f"⚠️  Failed to query remote database: {result.stderr}")
                    return []
                stdout_content = result.stdout
            
            # Parse JSON output
            try:
                rows = json.loads(stdout_content) if stdout_content.strip() else []
            except json.JSONDecodeError as e:
                print(f"⚠️  Failed to parse query result: {e}")
                print(f"Output: {stdout_content[:200]}")
                return []
            
            if not rows:
                print(f"⚠️  No data found in specified time range")
                return []
            
            print(f"✅ Retrieved {len(rows)} samples from remote Linux database")
            
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
                    'cpu_power_uj': row.get('cpu_power_uj', 0),
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
                    'disk_write_sectors': row['disk_write_sectors'],
                    # Tier 1 metrics (optional)
                    'ctxt': row.get('ctxt'),
                    'load_avg_1m': row.get('load_avg_1m'),
                    'load_avg_5m': row.get('load_avg_5m'),
                    'load_avg_15m': row.get('load_avg_15m'),
                    'procs_running': row.get('procs_running'),
                    'procs_blocked': row.get('procs_blocked'),
                    'per_core_irq_pct': row.get('per_core_irq_pct', ''),
                    'per_core_softirq_pct': row.get('per_core_softirq_pct', ''),
                    'interrupt_data': row.get('interrupt_data', 'null')
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
            
            # Cache the result before returning
            self._db_cache['ssh'] = processed_samples
            return processed_samples
            
        except Exception as e:
            print(f"⚠️  Error processing remote Linux database: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _pull_local_db_data(self) -> List[Dict]:
        """Pull data from local SQLite database for export.
        
        Returns:
            List of processed data samples from local DB (~/.monitor-tool/monitor_data.db)
        """
        # Return cached data if available
        if self._db_cache['local'] is not None:
            print(f"📦 Using cached local database data ({len(self._db_cache['local'])} samples)")
            return self._db_cache['local']
        
        import os
        import subprocess
        import json
        
        # Local database path
        home = os.path.expanduser('~')
        local_db_path = os.path.join(home, '.monitor-tool', 'monitor_data.db')
        
        if not os.path.exists(local_db_path):
            print(f"⚠️  Local database not found: {local_db_path}")
            return []
        
        print(f"📥 Fetching local database records from {local_db_path}...")
        
        try:
            # Use session start time
            start_timestamp = self.session_start_timestamp
            print(f"📅 Exporting data from timestamp >= {start_timestamp}")
            
            # Query local database (same schema as SSH now)
            sql_query = f"SELECT * FROM monitoring_data WHERE timestamp >= {start_timestamp} ORDER BY timestamp ASC"
            
            result = subprocess.run(
                ['sqlite3', '-json', local_db_path, sql_query],
                capture_output=True,
                text=True,
                timeout=120  # Increase timeout to 120 seconds for large databases
            )
            
            if result.returncode != 0:
                print(f"⚠️  Failed to query local database: {result.stderr}")
                return []
            
            # Parse JSON output
            try:
                rows = json.loads(result.stdout) if result.stdout.strip() else []
            except json.JSONDecodeError as e:
                print(f"⚠️  Failed to parse query result: {e}")
                return []
            
            if not rows:
                print(f"⚠️  No data found in specified time range")
                return []
            
            print(f"✅ Retrieved {len(rows)} samples from local database")
            
            # Process raw data into monitoring samples (same as SSH)
            processed_samples = []
            prev_raw = None
            
            for idx, row in enumerate(rows):
                # Parse per_core_raw JSON string
                per_core_raw = []
                if row.get('per_core_raw'):
                    try:
                        per_core_raw = json.loads(row['per_core_raw'])
                    except:
                        pass
                
                # Parse per_core_freq_khz comma-separated string
                per_core_freq_khz = []
                if row.get('per_core_freq_khz'):
                    try:
                        per_core_freq_khz = [int(f) for f in row['per_core_freq_khz'].split(',') if f]
                    except:
                        pass
                
                raw_data = {
                    'timestamp': row['timestamp'],
                    'timestamp_ms': row.get('timestamp_ms', row['timestamp'] * 1000),
                    'cpu_raw': {
                        'user': row.get('cpu_user', 0),
                        'nice': row.get('cpu_nice', 0),
                        'sys': row.get('cpu_sys', 0),
                        'idle': row.get('cpu_idle', 0),
                        'iowait': row.get('cpu_iowait', 0),
                        'irq': row.get('cpu_irq', 0),
                        'softirq': row.get('cpu_softirq', 0),
                        'steal': row.get('cpu_steal', 0)
                    },
                    'per_core_raw': per_core_raw,
                    'per_core_freq_khz': per_core_freq_khz,
                    'cpu_temp_millideg': row.get('cpu_temp_millideg', 0),
                    'mem_total_kb': row.get('mem_total_kb', 0),
                    'mem_free_kb': row.get('mem_free_kb', 0),
                    'mem_available_kb': row.get('mem_available_kb', 0),
                    'gpu_driver': row.get('gpu_driver', 'none'),
                    'gpu_freq_mhz': row.get('gpu_freq_mhz', 0),
                    'gpu_runtime_ms': row.get('gpu_runtime_ms', 0),
                    'gpu_memory_used_bytes': row.get('gpu_memory_used_bytes', 0),
                    'gpu_memory_total_bytes': row.get('gpu_memory_total_bytes', 0),
                    'npu_info': row.get('npu_info', ''),
                    'net_rx_bytes': row['net_rx_bytes'],
                    'net_tx_bytes': row['net_tx_bytes'],
                    'disk_read_sectors': row['disk_read_sectors'],
                    'disk_write_sectors': row['disk_write_sectors'],
                    # Tier 1 metrics
                    'ctxt': row.get('ctxt'),
                    'load_avg_1m': row.get('load_avg_1m'),
                    'load_avg_5m': row.get('load_avg_5m'),
                    'load_avg_15m': row.get('load_avg_15m'),
                    'procs_running': row.get('procs_running'),
                    'procs_blocked': row.get('procs_blocked'),
                    'per_core_irq_pct': row.get('per_core_irq_pct', ''),
                    'per_core_softirq_pct': row.get('per_core_softirq_pct', ''),
                    'interrupt_data': row.get('interrupt_data', 'null'),
                    'monitor_cpu_utime': row.get('monitor_cpu_utime', 0),
                    'monitor_cpu_stime': row.get('monitor_cpu_stime', 0)
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
            
            # Cache the result before returning
            self._db_cache['local'] = processed_samples
            return processed_samples
            
        except Exception as e:
            print(f"⚠️  Error processing local database: {e}")
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
        # Return cached data if available
        if self._db_cache['android'] is not None:
            print(f"📦 Using cached Android database data ({len(self._db_cache['android'])} samples)")
            return self._db_cache['android']
        
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
                    'cpu_power_uj': row.get('cpu_power_uj', 0),
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
                    'disk_write_sectors': row['disk_write_sectors'],
                    # Tier 1 metrics (optional)
                    'ctxt': row.get('ctxt'),
                    'load_avg_1m': row.get('load_avg_1m'),
                    'load_avg_5m': row.get('load_avg_5m'),
                    'load_avg_15m': row.get('load_avg_15m'),
                    'procs_running': row.get('procs_running'),
                    'procs_blocked': row.get('procs_blocked'),
                    'per_core_irq_pct': row.get('per_core_irq_pct', ''),
                    'per_core_softirq_pct': row.get('per_core_softirq_pct', ''),
                    'interrupt_data': row.get('interrupt_data', 'null')
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
            
            # Cache the result before returning
            self._db_cache['android'] = processed_samples
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
                } if raw_data['cpu_temp_millideg'] > 0 else {},
                'power_watts': 0.0  # First sample, no previous data for power calculation
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
            
        # Check for duplicate timestamp (prevent divide by zero or zero-delta glitches)
        timestamp_ms = raw_data.get('timestamp_ms', timestamp * 1000)
        prev_timestamp_ms = prev_raw.get('timestamp_ms', timestamp_ms)
        
        if timestamp_ms <= prev_timestamp_ms:
            # FIX: Don't skip - use time delta = 1 second as fallback
            print(f"⚠️  Duplicate timestamp {timestamp_ms}, using 1s fallback")
            # Continue processing with assumed 1s interval
        
        # Calculate CPU usage
        cpu_usage = self._calculate_cpu_usage(raw_data['cpu_raw'], prev_raw['cpu_raw'])

        # FIX: Hold previous value if calculation failed
        if cpu_usage < 0:
            if self.session_data:  # Has previous samples
                cpu_usage = self.session_data[-1]['cpu']['usage']['total']
            else:
                cpu_usage = 0.0
                        
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
        
        # CPU power (Intel RAPL - calculate from energy delta)
        cpu_power_uj = raw_data.get('cpu_power_uj', 0)
        prev_cpu_power_uj = prev_raw.get('cpu_power_uj', cpu_power_uj)
        timestamp_ms = raw_data.get('timestamp_ms', timestamp * 1000)
        prev_timestamp_ms = prev_raw.get('timestamp_ms', timestamp_ms)
        
        cpu_power_watts = 0.0
        if cpu_power_uj > 0:
            # Calculate energy delta (handle counter wrap-around)
            energy_delta_uj = cpu_power_uj - prev_cpu_power_uj
            if energy_delta_uj < 0:
                # Counter wrapped around (assume 32-bit counter)
                energy_delta_uj += (1 << 32)
            
            # Calculate time delta in seconds
            time_delta_ms = timestamp_ms - prev_timestamp_ms
            time_delta_sec = time_delta_ms / 1000.0 if time_delta_ms > 0 else 1.0
            
            # Power (Watts) = Energy (J) / Time (s)
            # Energy (J) = energy_uj / 1,000,000
            cpu_power_watts = (energy_delta_uj / 1_000_000.0) / time_delta_sec
        
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
        prev_gpu_runtime_ms = prev_raw.get('gpu_runtime_ms', gpu_runtime_ms)
        
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
                    'Thermal': [{
                        'label': 'CPU',
                        'current': raw_data['cpu_temp_millideg'] / 1000.0,
                        'high': 100.0,
                        'critical': 105.0
                    }]
                } if raw_data['cpu_temp_millideg'] > 0 else {},
                'power_watts': cpu_power_watts
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
        
        # Tier 1 metrics (optional, may be NULL/None if disabled)
        if 'ctxt' in raw_data and raw_data['ctxt'] is not None:
            # Context switches (delta from previous)
            prev_ctxt = prev_raw.get('ctxt', 0) or 0
            curr_ctxt = raw_data.get('ctxt', 0) or 0
            delta_ctxt = max(0, curr_ctxt - prev_ctxt)
            
            # Load average
            load_1m = raw_data.get('load_avg_1m', 0) or 0
            load_5m = raw_data.get('load_avg_5m', 0) or 0
            load_15m = raw_data.get('load_avg_15m', 0) or 0
            
            # Process counts
            procs_running = raw_data.get('procs_running', 0) or 0
            procs_blocked = raw_data.get('procs_blocked', 0) or 0
            
            # Per-core IRQ/softirq percentages (comma-separated strings -> list of floats)
            per_core_irq_pct_str = raw_data.get('per_core_irq_pct', '')
            per_core_softirq_pct_str = raw_data.get('per_core_softirq_pct', '')
            
            per_core_irq_pct = []
            per_core_softirq_pct = []
            
            if per_core_irq_pct_str and per_core_irq_pct_str != 'NULL':
                per_core_irq_pct = [float(x) for x in per_core_irq_pct_str.split(',') if x]
            if per_core_softirq_pct_str and per_core_softirq_pct_str != 'NULL':
                per_core_softirq_pct = [float(x) for x in per_core_softirq_pct_str.split(',') if x]
            
            # Process interrupt data (stored as JSON string in database)
            interrupt_stats = None
            interrupt_data_str = raw_data.get('interrupt_data')
            
            # Check if we have interrupt data (not null/None)
            if interrupt_data_str and interrupt_data_str != 'null' and interrupt_data_str != 'NULL':
                try:
                    interrupt_json = json.loads(interrupt_data_str)
                    
                    if interrupt_json and 'interrupts' in interrupt_json:
                        # Calculate interrupt rates (deltas from previous sample)
                        interrupt_list = []
                        
                        # Get previous interrupt data
                        prev_interrupt_str = prev_raw.get('interrupt_data') if prev_raw else None
                        if prev_interrupt_str and prev_interrupt_str != 'null' and prev_interrupt_str != 'NULL':
                            try:
                                prev_interrupt_json = json.loads(prev_interrupt_str)
                                prev_interrupts = {irq['name']: irq for irq in prev_interrupt_json.get('interrupts', [])}
                            except:
                                prev_interrupts = {}
                        else:
                            prev_interrupts = {}
                        
                        # Build interrupt stats with rates
                        for irq in interrupt_json['interrupts']:
                            name = irq['name']
                            total = irq['total']
                            prev_total = prev_interrupts.get(name, {}).get('total', total)
                            rate = max(0, total - prev_total)  # interrupts since last sample
                            
                            interrupt_list.append({
                                'name': name,
                                'irq': irq['irq'],
                                'total': total,
                                'rate': rate,
                                'cpu': irq['cpu'],
                                'per_cpu': irq['per_cpu']
                            })
                        
                        # Sort by rate (descending) - most active interrupts first
                        interrupt_list.sort(key=lambda x: x.get('rate', 0), reverse=True)
                        
                        # Use the same nested structure as local data source
                        interrupt_stats = {'interrupts': interrupt_list}
                except json.JSONDecodeError as e:
                    # If JSON parsing fails, print error
                    print(f"⚠️  JSON parse error for interrupt_data: {e}")
                except Exception as e:
                    print(f"⚠️  Error processing interrupt data: {e}")
            
            # Add tier1 section to sample
            sample['tier1'] = {
                'context_switches': delta_ctxt,
                'load_avg': {
                    '1min': load_1m,
                    '5min': load_5m,
                    '15min': load_15m
                },
                'process_counts': {
                    'running': procs_running,
                    'blocked': procs_blocked
                },
                'per_core_irq_pct': per_core_irq_pct,
                'per_core_softirq_pct': per_core_softirq_pct,
                'interrupts': interrupt_stats  # Add interrupt data
            }
        
        return sample
    
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
                } if raw_data['cpu_temp_millideg'] > 0 else {},
                'power_watts': 0.0  # First sample, no previous data for power calculation
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
            },
            # Add tier1 placeholder (empty interrupts for first sample)
            'tier1': {
                'context_switches': 0.0,
                'load_avg_1m': raw_data.get('load_avg_1m', 0.0),
                'load_avg_5m': raw_data.get('load_avg_5m', 0.0),
                'load_avg_15m': raw_data.get('load_avg_15m', 0.0),
                'procs_running': raw_data.get('procs_running', 0),
                'procs_blocked': raw_data.get('procs_blocked', 0),
                'per_core_irq_pct': [],
                'per_core_softirq_pct': [],
                'interrupts': {}  # Empty for first sample (no deltas)
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
        
        # Check for duplicate timestamp (prevent divide by zero or zero-delta glitches)
        timestamp_ms = raw_data.get('timestamp_ms', timestamp * 1000)
        prev_timestamp_ms = prev_raw.get('timestamp_ms', timestamp_ms)
        
        if timestamp_ms <= prev_timestamp_ms:
            return None  # Skip duplicate or out-of-order samples
        
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
        
        # CPU power (Intel RAPL - calculate from energy delta)
        cpu_power_uj = raw_data.get('cpu_power_uj', 0)
        prev_cpu_power_uj = prev_raw.get('cpu_power_uj', cpu_power_uj)
        timestamp_ms = raw_data.get('timestamp_ms', timestamp * 1000)
        prev_timestamp_ms = prev_raw.get('timestamp_ms', timestamp_ms)
        
        cpu_power_watts = 0.0
        if cpu_power_uj > 0:
            # Calculate energy delta (handle counter wrap-around)
            energy_delta_uj = cpu_power_uj - prev_cpu_power_uj
            if energy_delta_uj < 0:
                # Counter wrapped around (assume 32-bit counter)
                energy_delta_uj += (1 << 32)
            
            # Calculate time delta in seconds
            time_delta_ms = timestamp_ms - prev_timestamp_ms
            time_delta_sec = time_delta_ms / 1000.0 if time_delta_ms > 0 else 1.0
            
            # Power (Watts) = Energy (J) / Time (s)
            # Energy (J) = energy_uj / 1,000,000
            cpu_power_watts = (energy_delta_uj / 1_000_000.0) / time_delta_sec
            
            # DEBUG: Trace why power is 0
            if cpu_power_watts == 0 and prev_raw is not None:
                 print(f"DEBUG: Zero Power at {timestamp}: PowerUJ={cpu_power_uj}, PrevUJ={prev_cpu_power_uj}, DeltaUJ={energy_delta_uj}, TimeDelta={time_delta_sec}")
        
        # Calculate monitor script's own CPU usage
        monitor_cpu_pct = 0.0
        monitor_utime = raw_data.get('monitor_cpu_utime', 0)
        monitor_stime = raw_data.get('monitor_cpu_stime', 0)
        prev_monitor_utime = prev_raw.get('monitor_cpu_utime', 0)
        prev_monitor_stime = prev_raw.get('monitor_cpu_stime', 0)
        
        if monitor_utime is not None and monitor_stime is not None:
            # CPU ticks used by monitor script since last sample
            delta_utime = monitor_utime - prev_monitor_utime
            delta_stime = monitor_stime - prev_monitor_stime
            delta_monitor_ticks = delta_utime + delta_stime
            
            # Total system ticks
            curr_total = sum([raw_data['cpu_raw'][k] for k in ['user', 'nice', 'sys', 'idle', 'iowait', 'irq', 'softirq', 'steal']])
            prev_total = sum([prev_raw['cpu_raw'][k] for k in ['user', 'nice', 'sys', 'idle', 'iowait', 'irq', 'softirq', 'steal']])
            delta_total_ticks = curr_total - prev_total
            
            # Monitor CPU% = (monitor ticks / system ticks) * 100
            if delta_total_ticks > 0:
                monitor_cpu_pct = (delta_monitor_ticks * 100.0) / delta_total_ticks
        
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
                } if raw_data['cpu_temp_millideg'] > 0 else {},
                'monitor_cpu_usage': monitor_cpu_pct,  # Monitor script's own CPU usage
                'power_watts': cpu_power_watts
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
        
        # Tier 1 metrics (optional, may be NULL/None if disabled)
        if 'ctxt' in raw_data and raw_data['ctxt'] is not None:
            # Context switches (delta from previous)
            prev_ctxt = prev_raw.get('ctxt', 0) or 0
            curr_ctxt = raw_data.get('ctxt', 0) or 0
            delta_ctxt = max(0, curr_ctxt - prev_ctxt)
            
            # Load average
            load_1m = raw_data.get('load_avg_1m', 0) or 0
            load_5m = raw_data.get('load_avg_5m', 0) or 0
            load_15m = raw_data.get('load_avg_15m', 0) or 0
            
            # Process counts
            procs_running = raw_data.get('procs_running', 0) or 0
            procs_blocked = raw_data.get('procs_blocked', 0) or 0
            
            # Per-core IRQ/softirq percentages (comma-separated strings -> list of floats)
            per_core_irq_pct_str = raw_data.get('per_core_irq_pct', '')
            per_core_softirq_pct_str = raw_data.get('per_core_softirq_pct', '')
            
            per_core_irq_pct = []
            per_core_softirq_pct = []
            
            if per_core_irq_pct_str and per_core_irq_pct_str != 'NULL':
                per_core_irq_pct = [float(x) for x in per_core_irq_pct_str.split(',') if x]
            if per_core_softirq_pct_str and per_core_softirq_pct_str != 'NULL':
                per_core_softirq_pct = [float(x) for x in per_core_softirq_pct_str.split(',') if x]
            
            # Process interrupt data (stored as JSON string in database)
            interrupt_stats = None
            interrupt_data_str = raw_data.get('interrupt_data')
            
            # Check if we have interrupt data (not null/None)
            if interrupt_data_str and interrupt_data_str != 'null' and interrupt_data_str != 'NULL':
                try:
                    interrupt_json = json.loads(interrupt_data_str)
                    
                    if interrupt_json and 'interrupts' in interrupt_json:
                        # Calculate interrupt rates (deltas from previous sample)
                        interrupt_list = []
                        
                        # Get previous interrupt data
                        prev_interrupt_str = prev_raw.get('interrupt_data') if prev_raw else None
                        if prev_interrupt_str and prev_interrupt_str != 'null' and prev_interrupt_str != 'NULL':
                            try:
                                prev_interrupt_json = json.loads(prev_interrupt_str)
                                prev_interrupts = {irq['name']: irq for irq in prev_interrupt_json.get('interrupts', [])}
                            except:
                                prev_interrupts = {}
                        else:
                            prev_interrupts = {}
                        
                        # Build interrupt stats with rates
                        for irq in interrupt_json['interrupts']:
                            name = irq['name']
                            total = irq['total']
                            prev_total = prev_interrupts.get(name, {}).get('total', total)
                            rate = max(0, total - prev_total)  # interrupts since last sample
                            
                            interrupt_list.append({
                                'name': name,
                                'irq': irq['irq'],
                                'total': total,
                                'rate': rate,
                                'cpu': irq['cpu'],
                                'per_cpu': irq['per_cpu']
                            })
                        
                        # Sort by rate (descending) - most active interrupts first
                        interrupt_list.sort(key=lambda x: x.get('rate', 0), reverse=True)
                        
                        # Use the same nested structure as local data source
                        interrupt_stats = {'interrupts': interrupt_list}
                except json.JSONDecodeError as e:
                    # If JSON parsing fails, print error
                    print(f"⚠️  JSON parse error for interrupt_data: {e}")
                except Exception as e:
                    print(f"⚠️  Error processing interrupt data: {e}")
            
            # Add tier1 section to sample
            sample['tier1'] = {
                'context_switches': delta_ctxt,
                'load_avg': {
                    '1min': load_1m,
                    '5min': load_5m,
                    '15min': load_15m
                },
                'process_counts': {
                    'running': procs_running,
                    'blocked': procs_blocked
                },
                'per_core_irq_pct': per_core_irq_pct,
                'per_core_softirq_pct': per_core_softirq_pct,
                'interrupts': interrupt_stats  # Add interrupt data
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
        
        # FIX: Return -1.0 if no ticks elapsed (duplicate sample or too fast)
        if d_total <= 0:
            return -1.0  # Signal: hold previous value
        
        return (d_active * 100.0 / d_total)

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
        
        # Priority for data sources:
        # 1. SSH DB (remote Linux)
        # 2. Android DB (Android device)  
        # 3. Local DB (~/.monitor-tool/monitor_data.db)
        # 4. Session data (in-memory fallback)
        export_data = None
        
        # Priority: SSH DB > Android DB > Local DB > Session data
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
        
        # Try local database for LocalDataSource
        if export_data is None and not self._is_remote_source():
            local_data = self._pull_local_db_data()
            if local_data:
                export_data = local_data
                print(f"📊 Exporting {len(export_data)} samples from local database")
        
        # Fallback to session_data
        if export_data is None:
            export_data = self.session_data
            if export_data:
                print(f"📊 Exporting {len(export_data)} samples from session data (in-memory)")
        
        if not export_data:
            raise ValueError("No data to export - no database or session data available")
        
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
        
        # Priority for data sources:
        # 1. SSH DB (remote Linux)
        # 2. Android DB (Android device)  
        # 3. Local DB (~/.monitor-tool/monitor_data.db)
        # 4. Session data (in-memory fallback)
        export_samples = None
        
        # Priority: SSH DB > Android DB > Local DB > Session data
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
        
        # Try local database for LocalDataSource
        if export_samples is None and not self._is_remote_source():
            local_data = self._pull_local_db_data()
            if local_data:
                export_samples = local_data
                print(f"📊 Exporting {len(export_samples)} samples from local database")
        
        # Fallback to session_data
        if export_samples is None:
            export_samples = self.session_data
            if export_samples:
                print(f"📊 Exporting {len(export_samples)} samples from session data (in-memory)")
        
        if not export_samples:
            raise ValueError("No data to export - no database or session data available")
        
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
    
    def export_html(self, filename: str = None, use_android_db: bool = True, use_ssh_db: bool = True,
                   collect_logs: bool = None, config: Dict = None) -> str:
        """Export session data to HTML report format with optional log collection.
        
        Args:
            filename: Output filename. Auto-generated if None.
            use_android_db: If True and data source is Android, pull from Android DB
            use_ssh_db: If True and data source is SSH, pull from remote Linux DB
            collect_logs: Whether to collect system logs. If None, read from config.
            config: Configuration dict with log_collection settings. If None, loads from default.yaml.
            
        Returns:
            Path to the exported file
        """
        # Load config if not provided
        if config is None:
            config_path = Path('config/default.yaml')
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
            else:
                config = {}
        
        # Determine if we should collect logs
        if collect_logs is None:
            log_config = config.get('log_collection', {})
            collect_logs = log_config.get('enabled', False)
        
        # Generate session ID and create session directory
        session_id = self.start_time.strftime('%Y%m%d_%H%M%S')
        if self.data_source:
            source_name = self.data_source.get_source_name().replace(' ', '_').replace('(', '').replace(')', '').replace(':', '_')
            session_id = f"{source_name}_{session_id}"
        
        session_dir = self.base_output_dir / f'session_{session_id}'
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session database
        session_db_path = session_dir / 'monitoring_data.db'
        session_logger = DataLogger(db_path=str(session_db_path))
        
        if filename is None:
            filename = f'report.html'
        
        filepath = session_dir / filename
        
        # Priority for data sources:
        # 1. SSH DB (remote Linux)
        # 2. Android DB (Android device)  
        # 3. Local DB (~/.monitor-tool/monitor_data.db)
        # 4. Session data (in-memory fallback)
        export_samples = None
        source_type = 'local'
        source_name = 'localhost'
        
        # Priority: SSH DB > Android DB > Local DB > Session data
        if use_ssh_db:
            ssh_data = self._pull_ssh_db_data()
            if ssh_data:
                export_samples = ssh_data
                source_type = 'ssh'
                if hasattr(self.data_source, 'ssh_host'):
                    source_name = f"{self.data_source.username}@{self.data_source.ssh_host}"
                print(f"📊 Exporting {len(export_samples)} samples from remote Linux database")
        
        if use_android_db and export_samples is None:  # Only if SSH didn't provide data
            android_data = self._pull_android_db_data()
            if android_data:
                export_samples = android_data
                source_type = 'adb'
                if hasattr(self.data_source, 'adb_device'):
                    source_name = self.data_source.adb_device
                print(f"📊 Exporting {len(export_samples)} samples from Android database")
        
        # Try local database for LocalDataSource
        if export_samples is None and not self._is_remote_source():
            local_data = self._pull_local_db_data()
            if local_data:
                export_samples = local_data
                source_type = 'local'
                source_name = 'localhost'
                print(f"📊 Exporting {len(export_samples)} samples from local database")
        
        # Fallback to session_data
        if export_samples is None:
            export_samples = self.session_data
            if export_samples:
                print(f"📊 Exporting {len(export_samples)} samples from session data (in-memory)")
        
        if not export_samples:
            raise ValueError("No data to export - no database or session data available")
        
        # Store monitoring data in session database
        print(f"💾 Storing {len(export_samples)} samples in session database...")
        self._store_monitoring_data_in_session_db(session_logger, export_samples)
        
        # Determine time range from data - convert timestamps to integers
        timestamps = []
        for s in export_samples:
            if 'timestamp' in s:
                ts = s.get('timestamp', 0)
                if isinstance(ts, str):
                    try:
                        # Parse datetime string
                        dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                        timestamps.append(int(dt.timestamp()))
                    except:
                        try:
                            timestamps.append(int(float(ts)))
                        except:
                            pass
                else:
                    try:
                        timestamps.append(int(ts))
                    except:
                        pass
        
        if timestamps:
            start_timestamp = min(timestamps)
            end_timestamp = max(timestamps)
            start_time = datetime.fromtimestamp(start_timestamp)
            end_time = datetime.fromtimestamp(end_timestamp)
        else:
            start_time = self.start_time
            end_time = datetime.now()
        
        # Store session metadata
        session_logger.set_session_metadata(
            start_time=start_time,
            end_time=end_time,
            source_type=source_type,
            source_name=source_name,
            log_collection_enabled=collect_logs
        )
        
        # Collect logs if enabled
        log_count = 0
        if collect_logs and LogMonitor is not None:
            print(f"📋 Collecting logs from {start_time} to {end_time}...")
            try:
                log_entries = self._collect_logs_for_session(
                    start_time, end_time, source_type, config
                )
                
                if log_entries:
                    log_count = session_logger.log_entries(log_entries)
                    print(f"✓ Stored {log_count} log entries in session database")
                else:
                    print("ℹ️  No log entries collected")
            except Exception as e:
                print(f"⚠️  Error collecting logs: {e}")
                import traceback
                traceback.print_exc()
        
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
        
        # Print summary
        print(f"\n📊 Report Generation Summary:")
        print(f"   Session ID: {session_id}")
        print(f"   Time Range: {start_time} to {end_time}")
        print(f"   Data Samples: {len(export_samples)}")
        print(f"   Log Entries: {log_count}")
        print(f"   Database: {session_db_path}")
        print(f"   Report: {filepath}")
        
        return str(filepath)
    
    def _store_monitoring_data_in_session_db(self, session_logger: DataLogger, samples: List[Dict]):
        """Store monitoring data samples in session database.
        
        Args:
            session_logger: DataLogger instance for session database
            samples: List of monitoring data samples (can be nested or flat format)
        
        Note:
            This method handles both formats:
            1. Nested format (from in-memory session_data): Extracts values from nested dict
            2. Flat/raw format (from remote DB): Uses values directly
            
            Stores in raw/flat format matching the monitoring_data table schema,
            ensuring compatibility with future re-exports.
        """
        if not samples:
            return
        
        # Use direct SQL insert
        conn = session_logger.conn
        cursor = conn.cursor()
        
        for sample in samples:
            try:
                # Handle both nested and flat formats
                # Try to detect format by checking for nested structure
                is_nested = 'cpu' in sample and isinstance(sample.get('cpu'), dict)
                
                if is_nested:
                    # Extract from nested format (in-memory session data)
                    cpu = sample.get('cpu', {})
                    memory = sample.get('memory', {})
                    gpu_info = sample.get('gpu', {})
                    network = sample.get('network', {})
                    disk = sample.get('disk', {})
                    
                    # Get timestamp - ensure it's an integer
                    timestamp = sample.get('timestamp', sample.get('time_seconds', 0))
                    if isinstance(timestamp, str):
                        try:
                            # Parse datetime string to timestamp
                            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                            timestamp = int(dt.timestamp())
                        except:
                            try:
                                # Try alternative formats or just convert to int
                                timestamp = int(float(timestamp))
                            except:
                                timestamp = 0
                    else:
                        # Ensure numeric timestamp is an integer
                        timestamp = int(timestamp) if timestamp else 0
                    
                    # Extract CPU usage
                    cpu_usage = cpu.get('usage', {})
                    if isinstance(cpu_usage, dict):
                        cpu_total = cpu_usage.get('total', 0)
                    else:
                        cpu_total = cpu_usage or 0
                    
                    # Extract memory percent
                    mem_percent = memory.get('percent', 0)
                    
                    # Extract GPU usage
                    gpu_usage = 0
                    if gpu_info.get('available') and gpu_info.get('gpus'):
                        first_gpu = gpu_info['gpus'][0]
                        gpu_usage = first_gpu.get('usage', first_gpu.get('gpu_util', 0))
                    
                    # Extract NPU usage  
                    npu_usage = sample.get('npu', {}).get('usage', 0)
                    
                    # Get timestamp_ms - ensure it's an integer
                    timestamp_ms = sample.get('timestamp_ms')
                    if timestamp_ms is None:
                        timestamp_ms = timestamp * 1000 if timestamp else 0
                    timestamp_ms = int(timestamp_ms) if timestamp_ms else 0
                    
                    # Build simplified values tuple with essential fields
                    values = (
                        session_logger.session_id,
                        timestamp,
                        cpu_total,  # cpu_usage
                        mem_percent,  # memory_percent
                        gpu_usage,  # gpu_usage
                        gpu_info.get('gpus', [{}])[0].get('temperature', 0) if gpu_info.get('gpus') else 0,  # gpu_temp
                        gpu_info.get('gpus', [{}])[0].get('memory_used', 0) if gpu_info.get('gpus') else 0,  # gpu_memory
                        npu_usage,  # npu_usage
                        timestamp_ms,
                        None,  # cpu_user
                        None,  # cpu_nice
                        None,  # cpu_sys
                        None,  # cpu_idle
                        None,  # cpu_iowait
                        None,  # cpu_irq
                        None,  # cpu_softirq
                        None,  # cpu_steal
                        None,  # per_core_raw
                        None,  # per_core_freq_khz
                        None,  # cpu_temp_millideg
                        int(memory.get('used', 0)),  # memory_total_kb
                        None,  # memory_free_kb
                        int(memory.get('available', 0)),  # memory_available_kb
                        None,  # gpu_driver
                        None,  # gpu_freq_mhz
                        None,  # gpu_runtime_ms
                        None,  # gpu_memory_used_bytes
                        None,  # gpu_memory_total_bytes
                        None,  # npu_info
                        network.get('net_io', {}).get('bytes_recv', 0),  # net_rx_bytes
                        network.get('net_io', {}).get('bytes_sent', 0),  # net_tx_bytes
                        disk.get('disk_io', {}).get('read_bytes', 0),  # disk_read_sectors
                        disk.get('disk_io', {}).get('write_bytes', 0),  # disk_write_sectors
                        None,  # ctxt
                        None,  # load_avg_1m
                        None,  # load_avg_5m
                        None,  # load_avg_15m
                        None,  # procs_running
                        None,  # procs_blocked
                        None,  # per_core_irq_pct
                        None,  # per_core_softirq_pct
                        None,  # interrupt_data
                        None,  # monitor_cpu_utime
                        None   # monitor_cpu_stime
                    )
                else:
                    # Use flat/raw format directly (from remote DB)
                    values = (
                        session_logger.session_id,
                        sample.get('timestamp'),
                        sample.get('cpu_usage'),
                        sample.get('memory_percent'),
                        sample.get('gpu_usage'),
                        sample.get('gpu_temp'),
                        sample.get('gpu_memory'),
                        sample.get('npu_usage'),
                        sample.get('timestamp_ms'),
                        sample.get('cpu_user'),
                        sample.get('cpu_nice'),
                        sample.get('cpu_sys'),
                        sample.get('cpu_idle'),
                        sample.get('cpu_iowait'),
                        sample.get('cpu_irq'),
                        sample.get('cpu_softirq'),
                        sample.get('cpu_steal'),
                        sample.get('per_core_raw'),
                        sample.get('per_core_freq_khz'),
                        sample.get('cpu_temp_millideg'),
                        sample.get('mem_total_kb'),
                        sample.get('mem_free_kb'),
                        sample.get('mem_available_kb'),
                        sample.get('gpu_driver'),
                        sample.get('gpu_freq_mhz'),
                        sample.get('gpu_runtime_ms'),
                        sample.get('gpu_memory_used_bytes'),
                        sample.get('gpu_memory_total_bytes'),
                        sample.get('npu_info'),
                        sample.get('net_rx_bytes'),
                        sample.get('net_tx_bytes'),
                        sample.get('disk_read_sectors'),
                        sample.get('disk_write_sectors'),
                        sample.get('ctxt'),
                        sample.get('load_avg_1m'),
                        sample.get('load_avg_5m'),
                        sample.get('load_avg_15m'),
                        sample.get('procs_running'),
                        sample.get('procs_blocked'),
                        sample.get('per_core_irq_pct'),
                        sample.get('per_core_softirq_pct'),
                        sample.get('interrupt_data'),
                        sample.get('monitor_cpu_utime'),
                        sample.get('monitor_cpu_stime')
                    )
                
                cursor.execute('''
                    INSERT INTO monitoring_data (
                        session_id, timestamp, cpu_usage, memory_percent, gpu_usage, gpu_temp,
                        gpu_memory, npu_usage, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle,
                        cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz,
                        cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb,
                        gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes,
                        npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors,
                        ctxt, load_avg_1m, load_avg_5m, load_avg_15m, procs_running, procs_blocked,
                        per_core_irq_pct, per_core_softirq_pct, interrupt_data,
                        monitor_cpu_utime, monitor_cpu_stime
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
                
            except Exception as e:
                # Silently skip problematic samples
                pass
        
        conn.commit()
    
    def _collect_logs_for_session(self, start_time: datetime, end_time: datetime,
                                  source_type: str, config: Dict) -> List:
        """Collect system logs for the session time range.
        
        Args:
            start_time: Session start time
            end_time: Session end time
            source_type: Type of data source ('local', 'ssh', 'adb')
            config: Configuration dictionary
        
        Returns:
            List of LogEntry objects
        """
        if LogMonitor is None:
            print("⚠️  LogMonitor not available, skipping log collection")
            return []
        
        log_config = config.get('log_collection', {})
        
        # Determine mode based on source type
        mode = source_type  # 'local', 'ssh', or 'adb'
        
        # Get SSH client or ADB device if available
        ssh_client = None
        adb_device = None
        
        if mode == 'ssh' and hasattr(self.data_source, 'ssh_client'):
            ssh_client = self.data_source.ssh_client
        elif mode == 'adb' and hasattr(self.data_source, 'adb_device'):
            adb_device = self.data_source.adb_device
        
        # Create LogMonitor instance
        try:
            log_monitor = LogMonitor(
                config=log_config,
                mode=mode,
                ssh_client=ssh_client,
                adb_device=adb_device
            )
            
            # Collect logs for time range
            log_entries = log_monitor.collect_logs(start_time, end_time)
            return log_entries
            
        except Exception as e:
            print(f"⚠️  Error initializing LogMonitor: {e}")
            import traceback
            traceback.print_exc()
            return []
    
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
        
        # Tier 1 data arrays
        tier1_context_switches = []
        tier1_load_avg_1m = []
        tier1_load_avg_5m = []
        tier1_load_avg_15m = []
        tier1_procs_running = []
        tier1_procs_blocked = []
        tier1_per_core_irq = []
        tier1_per_core_softirq = []
        
        # Interrupt distribution data
        # Store all interrupt samples to build per-interrupt timeseries
        interrupt_samples = []  # List of {timestamp_idx, interrupts_dict}
        
        # Track max cores/temps for consistent array sizes
        max_cpu_cores = 0
        max_temp_sensors = 0
        
        # CPU power consumption array
        cpu_power = []
        
        for idx, sample in enumerate(self.session_data):
            # Extract timestamp
            if 'timestamp' in sample:
                timestamps.append(sample['timestamp'])
            else:
                timestamps.append(len(timestamps))
            
            # CPU data extraction
            # Support both nested format (live monitoring) and flat format (database export)
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
                    
                    # CPU power consumption (Intel RAPL)
                    power_watts = cpu_data.get('power_watts')
                    cpu_power.append(power_watts)
            elif 'cpu_usage' in sample:
                # Flat format from database - extract directly
                cpu_usage_total.append(sample.get('cpu_usage', 0))
                cpu_usage_per_core.append([])
                cpu_freq_avg.append(0)
                cpu_freq_per_core.append([])
                cpu_temps.append([])
                cpu_power.append(None)
            
            # GPU data extraction
            # Support both nested format (live monitoring) and flat format (database export)
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
            elif 'gpu_usage' in sample:
                # Flat format from database
                gpu_usage.append(sample.get('gpu_usage', 0) or 0)
                gpu_memory_used.append(sample.get('gpu_memory', 0) or 0)
                gpu_memory_util.append(0)
                gpu_freq.append(sample.get('gpu_freq_mhz', 0) or 0)
                gpu_temp.append(sample.get('gpu_temp', 0) or 0)
                gpu_power.append(0)
            else:
                gpu_usage.append(0)
                gpu_memory_used.append(0)
                gpu_memory_util.append(0)
                gpu_freq.append(0)
                gpu_temp.append(0)
                gpu_power.append(0)
            
            # Memory data extraction
            # Support both nested format (live monitoring) and flat format (database export)
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
            elif 'memory_percent' in sample:
                # Flat format from database
                memory_percent.append(sample.get('memory_percent', 0) or 0)
                memory_used.append(0)
                memory_available.append(sample.get('mem_available_kb', 0) or 0)
                swap_percent.append(0)
            
            # NPU data extraction
            # Support both nested format (live monitoring) and flat format (database export)
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
            elif 'npu_usage' in sample:
                # Flat format from database
                npu_usage.append(sample.get('npu_usage', 0) or 0)
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
            
            # Tier 1 data extraction
            if 'tier1' in sample:
                tier1_data = sample['tier1']
                if isinstance(tier1_data, dict):
                    tier1_context_switches.append(tier1_data.get('context_switches') or 0)
                    
                    # Load average
                    load_avg = tier1_data.get('load_avg', {})
                    if isinstance(load_avg, dict):
                        tier1_load_avg_1m.append(load_avg.get('1min') or 0)
                        tier1_load_avg_5m.append(load_avg.get('5min') or 0)
                        tier1_load_avg_15m.append(load_avg.get('15min') or 0)
                    else:
                        tier1_load_avg_1m.append(0)
                        tier1_load_avg_5m.append(0)
                        tier1_load_avg_15m.append(0)
                    
                    # Processes
                    procs = tier1_data.get('process_counts', {})
                    if isinstance(procs, dict):
                        tier1_procs_running.append(procs.get('running') or 0)
                        tier1_procs_blocked.append(procs.get('blocked') or 0)
                    else:
                        tier1_procs_running.append(0)
                        tier1_procs_blocked.append(0)
                    
                    # Per-core IRQ/SoftIRQ
                    tier1_per_core_irq.append(tier1_data.get('per_core_irq_pct', []))
                    tier1_per_core_softirq.append(tier1_data.get('per_core_softirq_pct', []))
                    
                    # Interrupt data - convert from list format to dict format
                    interrupts_data = tier1_data.get('interrupts', None)
                    if interrupts_data and isinstance(interrupts_data, dict):
                        # Check if it's in list format: {'interrupts': [list]}
                        if 'interrupts' in interrupts_data and isinstance(interrupts_data['interrupts'], list):
                            # Convert list format to dict format for exporter
                            # Dict format: {interrupt_name: {rate, cpu, per_cpu}}
                            interrupts_dict = {}
                            for irq in interrupts_data['interrupts']:
                                # Use 'name' field as key, fallback to 'irq' if no name
                                key = irq.get('name', irq.get('irq', 'unknown'))
                                interrupts_dict[key] = {
                                    'rate': irq.get('rate', irq.get('total', 0)),  # Use rate if available, else total
                                    'total': irq.get('total', 0),
                                    'cpu': irq.get('cpu', -1),
                                    'per_cpu': irq.get('per_cpu', [])
                                }
                            
                            # Store the converted dict for this timestamp
                            interrupt_samples.append({
                                'timestamp_idx': idx,
                                'interrupts': interrupts_dict
                            })
                        else:
                            # Already in dict format (legacy format)
                            interrupt_samples.append({
                                'timestamp_idx': idx,
                                'interrupts': interrupts_data
                            })
                else:
                    tier1_context_switches.append(0)
                    tier1_load_avg_1m.append(0)
                    tier1_load_avg_5m.append(0)
                    tier1_load_avg_15m.append(0)
                    tier1_procs_running.append(0)
                    tier1_procs_blocked.append(0)
                    tier1_per_core_irq.append([])
                    tier1_per_core_softirq.append([])
            else:
                # No Tier 1 data - append zeros to keep arrays aligned
                tier1_context_switches.append(0)
                tier1_load_avg_1m.append(0)
                tier1_load_avg_5m.append(0)
                tier1_load_avg_15m.append(0)
                tier1_procs_running.append(0)
                tier1_procs_blocked.append(0)
                tier1_per_core_irq.append([])
                tier1_per_core_softirq.append([])
        
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
                'max_temp_sensors': max_temp_sensors,
                'power': cpu_power
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
            },
            'tier1': {
                'context_switches': tier1_context_switches,
                'load_avg_1m': tier1_load_avg_1m,
                'load_avg_5m': tier1_load_avg_5m,
                'load_avg_15m': tier1_load_avg_15m,
                'procs_running': tier1_procs_running,
                'procs_blocked': tier1_procs_blocked,
                'per_core_irq': tier1_per_core_irq,
                'per_core_softirq': tier1_per_core_softirq
            }
        }
        
        # Process interrupt data to build per-interrupt timeseries
        interrupt_timeseries = {}  # {interrupt_name: {'rates': [...], 'cpus': [...], ...}}
        if interrupt_samples:
            # Find all unique interrupt names across all samples
            all_interrupt_names = set()
            for sample in interrupt_samples:
                all_interrupt_names.update(sample['interrupts'].keys())
            
            # Build timeseries for each interrupt
            for name in all_interrupt_names:
                rates = [0] * len(timestamps)  # Initialize with zeros for all timestamps
                totals = [0] * len(timestamps)  # Store cumulative totals for delta calculation
                per_cpu_timeseries = []  # Per-CPU distribution over time
                cpus = []  # Primary CPU affinity
                
                # First pass: collect total counts
                for sample in interrupt_samples:
                    idx = sample['timestamp_idx']
                    if name in sample['interrupts']:
                        irq_data = sample['interrupts'][name]
                        # Store cumulative total
                        totals[idx] = irq_data.get('total', 0)
                        if not cpus:  # Store CPU affinity from first occurrence
                            cpus = [irq_data.get('cpu', -1)]
                        # Store per-CPU interrupt distribution
                        if 'per_cpu' in irq_data:
                            per_cpu_timeseries.append(irq_data['per_cpu'])
                
                # Second pass: calculate rates (delta between samples)
                # Rate = (total[i] - total[i-1]) / (time[i] - time[i-1])
                # CRITICAL: Use timestamp_ms from tier1 data (device time) NOT host time_seconds
                # Interrupt counts are collected on the device at device time, so we must use
                # device timestamp for accurate rate calculation
                
                # Skip first sample - need at least 2 valid samples to calculate a rate
                # Start from index 2 to avoid initial spike from cumulative count starting at 0
                for i in range(2, len(timestamps)):
                    if totals[i] > 0 and totals[i-1] > 0 and i < len(self.session_data):
                        # Get timestamp_ms from tier1 data for accurate device-time delta
                        curr_tier1 = self.session_data[i].get('tier1', {})
                        prev_tier1 = self.session_data[i-1].get('tier1', {})
                        
                        curr_time_ms = curr_tier1.get('timestamp_ms') if isinstance(curr_tier1, dict) else None
                        prev_time_ms = prev_tier1.get('timestamp_ms') if isinstance(prev_tier1, dict) else None
                        
                        # Check if timestamp hasn't changed (duplicate sample from same device data)
                        if curr_time_ms is not None and prev_time_ms is not None:
                            if curr_time_ms == prev_time_ms:
                                # Same device sample logged twice - no time elapsed, rate = 0
                                # This happens when PC logging interval and device sample interval are out of sync
                                rates[i] = 0
                                continue
                            elif curr_time_ms > prev_time_ms:
                                # Valid timestamp delta - calculate rate
                                delta_time = (curr_time_ms - prev_time_ms) / 1000.0
                            else:
                                # Timestamp went backwards? Use fallback
                                delta_time = 1.0
                        else:
                            # Fallback: use configured update interval (usually 1 second)
                            delta_time = 1.0
                        
                        # Calculate delta interrupts
                        delta_interrupts = totals[i] - totals[i-1]
                        
                        if delta_time > 0 and delta_interrupts >= 0:
                            # Calculate interrupts per second
                            rates[i] = int(delta_interrupts / delta_time)
                        else:
                            rates[i] = 0
                    else:
                        rates[i] = 0
                
                # First two samples: set to 0 (not enough history for accurate rate)
                # This avoids the huge spike from initial cumulative count
                rates[0] = 0
                if len(rates) > 1:
                    rates[1] = 0
                
                interrupt_timeseries[name] = {
                    'rates': rates,
                    'cpu': cpus[0] if cpus else -1,
                    'per_cpu': per_cpu_timeseries
                }
        
        # Only add Tier 1 data if it exists (check if any non-zero values)
        # For arrays of arrays (per_core_irq), check if any inner array is non-empty
        has_tier1_data = (
            any(tier1_context_switches) or
            any(tier1_load_avg_1m) or
            any(tier1_load_avg_5m) or
            any(tier1_load_avg_15m) or
            any(tier1_procs_running) or
            any(tier1_procs_blocked) or
            any(len(arr) > 0 for arr in tier1_per_core_irq if isinstance(arr, list)) or
            any(len(arr) > 0 for arr in tier1_per_core_softirq if isinstance(arr, list)) or
            len(interrupt_timeseries) > 0
        )
        
        if has_tier1_data:
            chart_data['tier1'] = {
                'context_switches': tier1_context_switches,
                'load_avg_1m': tier1_load_avg_1m,
                'load_avg_5m': tier1_load_avg_5m,
                'load_avg_15m': tier1_load_avg_15m,
                'procs_running': tier1_procs_running,
                'procs_blocked': tier1_procs_blocked,
                'per_core_irq': tier1_per_core_irq,
                'per_core_softirq': tier1_per_core_softirq,
                'interrupts': interrupt_timeseries
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
        
        # Determine data source method based on which cache was populated
        if self._db_cache['ssh']:
            data_source_method = "Remote SSH Database"
        elif self._db_cache['android']:
            data_source_method = "Android Device Database"
        elif self._db_cache['local']:
            data_source_method = "Local Database"
        else:
            data_source_method = "In-Memory Session Data"
        
        # Replace template variables
        html = template.replace('{{ start_time }}', self.start_time.strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{ duration }}', str(duration))
        html = html.replace('{{ data_points }}', str(len(self.session_data)))
        html = html.replace('{{ source_name }}', source_name)
        html = html.replace('{{ data_source_method }}', data_source_method)
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
