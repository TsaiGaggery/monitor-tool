#!/usr/bin/env python3
"""Data logger for storing monitoring data to SQLite database."""

import sqlite3
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional
import os
from pathlib import Path

# Import LogEntry for log storage
try:
    from monitors.log_monitor import LogEntry
except ImportError:
    # Fallback for testing or standalone usage
    from dataclasses import dataclass
    from datetime import datetime
    from typing import Optional, List
    
    @dataclass
    class LogEntry:
        timestamp: datetime
        source_file: str
        severity: Optional[str]
        facility: Optional[str]
        message: str
        raw_line: str
        process_context: Optional[List[int]] = None


class DataLogger:
    """Log monitoring data to SQLite database."""
    
    def __init__(self, db_path: str = None, auto_cleanup_days: int = 3):
        """Initialize data logger.
        
        Args:
            db_path: Path to SQLite database file
            auto_cleanup_days: Automatically delete data older than this many days (default: 3)
        """
        if db_path is None:
            # Default to ~/.monitor-tool/data.db
            home = os.path.expanduser('~')
            data_dir = os.path.join(home, '.monitor-tool')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'monitor_data.db')
        
        self.db_path = db_path
        self.conn = None
        self.db_lock = threading.Lock()  # Thread-safe database access
        self.auto_cleanup_days = auto_cleanup_days
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")  # Generate session ID
        self.init_database()
        
        # Auto cleanup old data on initialization
        if auto_cleanup_days > 0:
            self.cleanup_old_data(days=auto_cleanup_days)
    
    def init_database(self):
        """Initialize database schema - UNIFIED schema matching SSH/Android format."""
        # Check if database exists and validate schema
        db_exists = os.path.exists(self.db_path)
        
        # Allow connection to be used from multiple threads
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Validate schema if database already exists
        if db_exists:
            try:
                # Check for required columns that are in the new schema
                cursor.execute("PRAGMA table_info(monitoring_data)")
                columns = {row[1] for row in cursor.fetchall()}
                required_columns = {'timestamp_ms', 'monitor_cpu_utime', 'monitor_cpu_stime', 'cpu_usage', 'session_id'}
                
                # If any required column is missing, the schema is outdated
                if not required_columns.issubset(columns):
                    print(f"⚠️  Database schema is outdated. Recreating database...")
                    self.conn.close()
                    os.remove(self.db_path)
                    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    cursor = self.conn.cursor()
            except sqlite3.OperationalError:
                # Table doesn't exist yet, no need to validate
                pass
        
        # Create monitoring data table - UNIFIED SCHEMA (matches linux_monitor_remote.sh)
        # Stores RAW data for consistent processing across all modes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp INTEGER NOT NULL,
                cpu_usage REAL,
                memory_percent REAL,
                gpu_usage REAL,
                gpu_temp REAL,
                gpu_memory INTEGER,
                npu_usage REAL,
                timestamp_ms INTEGER,
                cpu_user INTEGER,
                cpu_nice INTEGER,
                cpu_sys INTEGER,
                cpu_idle INTEGER,
                cpu_iowait INTEGER,
                cpu_irq INTEGER,
                cpu_softirq INTEGER,
                cpu_steal INTEGER,
                per_core_raw TEXT,
                per_core_freq_khz TEXT,
                cpu_temp_millideg INTEGER,
                mem_total_kb INTEGER,
                mem_free_kb INTEGER,
                mem_available_kb INTEGER,
                gpu_driver TEXT,
                gpu_freq_mhz INTEGER,
                gpu_runtime_ms INTEGER,
                gpu_memory_used_bytes INTEGER,
                gpu_memory_total_bytes INTEGER,
                npu_info TEXT,
                net_rx_bytes INTEGER,
                net_tx_bytes INTEGER,
                disk_read_sectors INTEGER,
                disk_write_sectors INTEGER,
                ctxt INTEGER,
                load_avg_1m REAL,
                load_avg_5m REAL,
                load_avg_15m REAL,
                procs_running INTEGER,
                procs_blocked INTEGER,
                per_core_irq_pct TEXT,
                per_core_softirq_pct TEXT,
                interrupt_data TEXT,
                monitor_cpu_utime INTEGER,
                monitor_cpu_stime INTEGER
            )
        ''')
        
        # Create index on timestamp
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON monitoring_data(timestamp)
        ''')

        # Create index on session_id
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_id 
            ON monitoring_data(session_id)
        ''')

        # v1.1 Tables
        # Create schema_version table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        ''')

        # Create process_data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS process_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                session_id TEXT NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_rss INTEGER NOT NULL,
                memory_vms INTEGER,
                cmdline TEXT,
                status TEXT,
                num_threads INTEGER,
                create_time REAL
            )
        ''')
        
        # Create indexes for process_data
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_process_timestamp ON process_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_process_session ON process_data(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_process_cpu ON process_data(cpu_percent DESC)')
        
        # Create log_entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                source_file TEXT NOT NULL,
                severity TEXT,
                facility TEXT,
                message TEXT NOT NULL,
                raw_line TEXT,
                process_context TEXT
            )
        ''')
        
        # Create indexes for log_entries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log_entries(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_session ON log_entries(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_severity ON log_entries(severity)')
        
        # Create process_log_correlation table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS process_log_correlation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_id INTEGER NOT NULL,
                log_entry_id INTEGER NOT NULL,
                correlation_type TEXT,
                confidence REAL,
                FOREIGN KEY (process_id) 
                    REFERENCES process_data(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (log_entry_id) 
                    REFERENCES log_entries(id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Create report_insights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                provider TEXT,
                insights TEXT,
                prompt_used TEXT
            )
        ''')
        
        # Create session_metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_metadata (
                session_id TEXT PRIMARY KEY,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                source_type TEXT NOT NULL,
                source_name TEXT,
                log_collection_enabled BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def log_data(self, cpu_info: Dict, memory_info: Dict, 
                 gpu_info: Dict = None, npu_info: Dict = None, network_info: Dict = None, disk_info: Dict = None, tier1_info: Dict = None):
        """Log monitoring data to database in RAW format (thread-safe).
        
        Stores RAW system data to match SSH/Android format for consistent export processing.
        """
        with self.db_lock:
            try:
                import time
                import psutil
                
                cursor = self.conn.cursor()
                
                # Timestamp (Unix timestamp in seconds and milliseconds)
                timestamp = int(time.time())
                timestamp_ms = int(time.time() * 1000)
                
                # CPU stats - get RAW values from /proc/stat
                cpu_stats = psutil.cpu_times()
                cpu_user = int(cpu_stats.user * 100)  # Convert to clock ticks (approximate)
                cpu_nice = int(cpu_stats.nice * 100)
                cpu_sys = int(cpu_stats.system * 100)
                cpu_idle = int(cpu_stats.idle * 100)
                cpu_iowait = int(getattr(cpu_stats, 'iowait', 0) * 100)
                cpu_irq = int(getattr(cpu_stats, 'irq', 0) * 100)
                cpu_softirq = int(getattr(cpu_stats, 'softirq', 0) * 100)
                cpu_steal = int(getattr(cpu_stats, 'steal', 0) * 100)
                
                # Per-core raw CPU stats (JSON string matching bash format)
                per_core_stats = []
                for core_cpu_times in psutil.cpu_times(percpu=True):
                    per_core_stats.append({
                        'user': int(core_cpu_times.user * 100),
                        'nice': int(core_cpu_times.nice * 100),
                        'sys': int(core_cpu_times.system * 100),
                        'idle': int(core_cpu_times.idle * 100),
                        'iowait': int(getattr(core_cpu_times, 'iowait', 0) * 100),
                        'irq': int(getattr(core_cpu_times, 'irq', 0) * 100),
                        'softirq': int(getattr(core_cpu_times, 'softirq', 0) * 100),
                        'steal': int(getattr(core_cpu_times, 'steal', 0) * 100)
                    })
                per_core_raw = json.dumps(per_core_stats)
                
                # Per-core frequencies (kHz) as comma-separated string
                freq_data = cpu_info.get('frequency', {})
                per_core_freq = freq_data.get('per_core', [])
                # Convert MHz to kHz and format as comma-separated string
                per_core_freq_khz = ','.join(str(int(f * 1000)) for f in per_core_freq)
                
                # CPU temperature (millidegrees)
                cpu_temp_millideg = 0
                temp_data = cpu_info.get('temperature', {})
                if temp_data:
                    first_sensor = next(iter(temp_data.values()), [])
                    if first_sensor:
                        cpu_temp_millideg = int(first_sensor[0].get('current', 0) * 1000)
                
                # Memory (kB)
                mem = memory_info.get('memory', {})
                mem_total_kb = int(mem.get('total', 0) * 1024 * 1024)  # GB to kB
                mem_free_kb = int(mem.get('free', 0) * 1024 * 1024)
                mem_available_kb = int(mem.get('available', 0) * 1024 * 1024)
                
                # GPU info
                gpu_driver = 'none'
                gpu_freq_mhz = 0
                gpu_runtime_ms = 0
                gpu_memory_used_bytes = 0
                gpu_memory_total_bytes = 0
                if gpu_info and gpu_info.get('available'):
                    gpus = gpu_info.get('gpus', [])
                    if gpus:
                        gpu = gpus[0]
                        gpu_driver = 'local'  # Placeholder
                        gpu_freq_mhz = int(gpu.get('gpu_clock', 0))
                        gpu_memory_used_bytes = int(gpu.get('memory_used', 0) * 1024 * 1024)  # MB to bytes
                        gpu_memory_total_bytes = int(gpu.get('memory_total', 0) * 1024 * 1024)
                        # For runtime, we'd need to track cumulative GPU time (not implemented in local mode yet)
                
                # NPU info (JSON string)
                npu_info_str = 'none'
                if npu_info and npu_info.get('available'):
                    npu_info_str = json.dumps({'utilization': npu_info.get('utilization', 0)})
                
                # Network stats (cumulative bytes)
                net_rx_bytes = 0
                net_tx_bytes = 0
                if network_info:
                    io_stats = network_info.get('io_stats', {})
                    # psutil gives us rates, but we need cumulative - use net_io_counters
                    net_io = psutil.net_io_counters()
                    net_rx_bytes = net_io.bytes_recv
                    net_tx_bytes = net_io.bytes_sent
                
                # Disk stats (cumulative sectors)
                disk_read_sectors = 0
                disk_write_sectors = 0
                if disk_info:
                    # psutil gives us bytes, convert to sectors (512 bytes each)
                    disk_io = psutil.disk_io_counters()
                    if disk_io:
                        disk_read_sectors = disk_io.read_bytes // 512
                        disk_write_sectors = disk_io.write_bytes // 512
                
                # Tier 1 metrics
                if tier1_info:
                    ctxt = tier1_info.get('context_switches', 0)
                    
                    load_avg_data = tier1_info.get('load_avg', {})
                    load_avg_1m = load_avg_data.get('1min', 0.0)
                    load_avg_5m = load_avg_data.get('5min', 0.0)
                    load_avg_15m = load_avg_data.get('15min', 0.0)
                    
                    procs_data = tier1_info.get('process_counts', {})
                    procs_running = procs_data.get('running', 0)
                    procs_blocked = procs_data.get('blocked', 0)
                    
                    # Per-core IRQ/SoftIRQ percentages as comma-separated strings
                    per_core_irq_list = tier1_info.get('per_core_irq_pct', [])
                    per_core_softirq_list = tier1_info.get('per_core_softirq_pct', [])
                    per_core_irq_pct = ','.join(str(round(v, 2)) for v in per_core_irq_list)
                    per_core_softirq_pct = ','.join(str(round(v, 2)) for v in per_core_softirq_list)
                    
                    # Interrupt distribution as JSON string
                    interrupts = tier1_info.get('interrupts', {})
                    interrupt_data = json.dumps(interrupts) if interrupts else 'null'
                else:
                    # Fallback to extracting from cpu_info (old behavior)
                    stats = cpu_info.get('stats', {})
                    ctxt = stats.get('ctx_switches', 0)
                    
                    load_avg = cpu_info.get('usage', {}).get('load_avg', (0, 0, 0))
                    load_avg_1m = load_avg[0] if len(load_avg) > 0 else 0.0
                    load_avg_5m = load_avg[1] if len(load_avg) > 1 else 0.0
                    load_avg_15m = load_avg[2] if len(load_avg) > 2 else 0.0
                    
                    procs_running = 0
                    procs_blocked = 0
                    try:
                        for proc in psutil.process_iter(['status']):
                            status = proc.info.get('status', '')
                            if status == psutil.STATUS_RUNNING:
                                procs_running += 1
                            elif status in [psutil.STATUS_DISK_SLEEP, psutil.STATUS_STOPPED]:
                                procs_blocked += 1
                    except:
                        pass
                    
                    per_core_irq_pct = ''
                    per_core_softirq_pct = ''
                    interrupt_data = 'null'
                
                # Monitor CPU usage (from cpu_info)
                monitor_cpu_usage = cpu_info.get('monitor_cpu_usage', 0)
                # Convert percentage to ticks (approximate)
                monitor_cpu_utime = int(monitor_cpu_usage * 100)
                monitor_cpu_stime = 0
                
                # Calculated metrics for backward compatibility and easier querying
                cpu_usage = cpu_info.get('usage', {}).get('total', 0.0)
                memory_percent = memory_info.get('memory', {}).get('percent', 0.0)
                
                gpu_usage = 0.0
                gpu_temp = 0.0
                gpu_memory = 0
                if gpu_info and gpu_info.get('available'):
                    gpus = gpu_info.get('gpus', [])
                    if gpus:
                        gpu = gpus[0]
                        gpu_usage = float(gpu.get('gpu_util', 0))
                        gpu_temp = float(gpu.get('temperature', 0))
                        gpu_memory = int(gpu.get('memory_used', 0))
                
                npu_usage = 0.0
                if npu_info and npu_info.get('available'):
                    npu_usage = float(npu_info.get('utilization', 0))
                
                # Insert into database
                cursor.execute('''
                    INSERT INTO monitoring_data 
                    (session_id, timestamp, timestamp_ms, cpu_usage, memory_percent, gpu_usage, gpu_temp, gpu_memory, npu_usage,
                     cpu_user, cpu_nice, cpu_sys, cpu_idle, 
                     cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz,
                     cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb,
                     gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes,
                     npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors,
                     ctxt, load_avg_1m, load_avg_5m, load_avg_15m, procs_running, procs_blocked,
                     per_core_irq_pct, per_core_softirq_pct, interrupt_data,
                     monitor_cpu_utime, monitor_cpu_stime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.session_id, timestamp, timestamp_ms, cpu_usage, memory_percent, gpu_usage, gpu_temp, gpu_memory, npu_usage,
                      cpu_user, cpu_nice, cpu_sys, cpu_idle,
                      cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz,
                      cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb,
                      gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes,
                      npu_info_str, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors,
                      ctxt, load_avg_1m, load_avg_5m, load_avg_15m, procs_running, procs_blocked,
                      per_core_irq_pct, per_core_softirq_pct, interrupt_data,
                      monitor_cpu_utime, monitor_cpu_stime))
                
                self.conn.commit()
            except Exception as e:
                print(f"Error logging data: {e}")
                import traceback
                traceback.print_exc()

    def log_entries(self, log_entries: List[LogEntry], batch_size: int = 100) -> int:
        """Store log entries in batch for performance (thread-safe).
        
        Args:
            log_entries: List of LogEntry objects
            batch_size: Number of entries per batch insert
        
        Returns:
            Number of entries inserted
        """
        if not log_entries:
            return 0
        
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                inserted = 0
                
                # Batch insert for performance
                for i in range(0, len(log_entries), batch_size):
                    batch = log_entries[i:i+batch_size]
                    
                    values = []
                    for entry in batch:
                        # Convert process PIDs to JSON array
                        pids_json = json.dumps(entry.process_context) if entry.process_context else '[]'
                        
                        # Ensure timestamp is string
                        timestamp_str = entry.timestamp.isoformat() if hasattr(entry.timestamp, 'isoformat') else str(entry.timestamp)
                        
                        values.append((
                            self.session_id,
                            timestamp_str,
                            entry.source_file,
                            entry.severity,
                            entry.facility,
                            entry.message,
                            entry.raw_line,
                            pids_json
                        ))
                    
                    cursor.executemany('''
                        INSERT INTO log_entries 
                        (session_id, timestamp, source_file, severity, facility, 
                         message, raw_line, process_context)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', values)
                    
                    inserted += len(values)
                
                self.conn.commit()
                return inserted
            except Exception as e:
                print(f"Error logging log entries: {e}")
                import traceback
                traceback.print_exc()
                return 0
    
    def set_session_metadata(self, start_time: datetime, end_time: datetime = None,
                           source_type: str = 'local', source_name: str = None,
                           log_collection_enabled: bool = False):
        """Store session metadata (thread-safe).
        
        Args:
            start_time: Session start time
            end_time: Session end time (optional)
            source_type: Type of data source ('local', 'ssh', 'adb')
            source_name: Name/identifier of source (hostname, IP, device ID)
            log_collection_enabled: Whether logs were collected
        """
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                
                # Convert to ISO format strings
                start_str = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
                end_str = end_time.isoformat() if end_time and hasattr(end_time, 'isoformat') else (str(end_time) if end_time else None)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO session_metadata 
                    (session_id, start_time, end_time, source_type, source_name, log_collection_enabled)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.session_id, start_str, end_str, source_type, source_name, log_collection_enabled))
                
                self.conn.commit()
            except Exception as e:
                print(f"Error setting session metadata: {e}")
    
    def get_session_metadata(self, session_id: str = None) -> Optional[Dict]:
        """Get session metadata (thread-safe).
        
        Args:
            session_id: Session ID to query, or use current session
        
        Returns:
            Dictionary with session metadata or None
        """
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                sid = session_id or self.session_id
                
                cursor.execute('''
                    SELECT session_id, start_time, end_time, source_type, 
                           source_name, log_collection_enabled, created_at
                    FROM session_metadata
                    WHERE session_id = ?
                ''', (sid,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'session_id': row[0],
                        'start_time': row[1],
                        'end_time': row[2],
                        'source_type': row[3],
                        'source_name': row[4],
                        'log_collection_enabled': bool(row[5]),
                        'created_at': row[6]
                    }
                return None
            except Exception as e:
                print(f"Error getting session metadata: {e}")
                return None
    
    def get_log_entries(self, session_id: str = None, severity: str = None,
                       start_time: datetime = None, end_time: datetime = None,
                       limit: int = 1000) -> List[Dict]:
        """Get log entries from database (thread-safe).
        
        Args:
            session_id: Session ID to query, or use current session
            severity: Filter by severity level
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of entries to return
        
        Returns:
            List of log entry dictionaries
        """
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                sid = session_id or self.session_id
                
                query = 'SELECT * FROM log_entries WHERE session_id = ?'
                params = [sid]
                
                if severity:
                    query += ' AND severity = ?'
                    params.append(severity)
                
                if start_time:
                    start_str = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
                    query += ' AND timestamp >= ?'
                    params.append(start_str)
                
                if end_time:
                    end_str = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
                    query += ' AND timestamp <= ?'
                    params.append(end_str)
                
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                print(f"Error getting log entries: {e}")
                return []
    
    def log_process_data(self, processes: List):
        """Log process data to database (thread-safe)."""
        if not processes:
            return
            
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                timestamp = datetime.now()
                
                data_to_insert = []
                for p in processes:
                    # Handle both ProcessInfo objects and dicts
                    if hasattr(p, 'pid'):
                        pid = p.pid
                        name = p.name
                        cpu = p.cpu_percent
                        mem_rss = p.memory_rss
                        mem_vms = p.memory_vms
                        cmdline = p.cmdline
                        status = p.status
                        threads = p.num_threads
                        create_time = p.create_time
                    else:
                        pid = p.get('pid')
                        name = p.get('name')
                        cpu = p.get('cpu_percent', 0.0)
                        mem_rss = p.get('memory_rss', 0)
                        mem_vms = p.get('memory_vms', 0)
                        cmdline = p.get('cmdline', '')
                        status = p.get('status', '')
                        threads = p.get('num_threads', 0)
                        create_time = p.get('create_time', 0.0)
                        
                    data_to_insert.append((
                        timestamp, self.session_id, pid, name, cpu, 
                        mem_rss, mem_vms, cmdline, status, threads, create_time
                    ))
                
                cursor.executemany('''
                    INSERT INTO process_data 
                    (timestamp, session_id, pid, name, cpu_percent, memory_rss, 
                     memory_vms, cmdline, status, num_threads, create_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data_to_insert)
                
                self.conn.commit()
            except Exception as e:
                print(f"Error logging process data: {e}")
    
    def get_recent_data(self, hours: int = 1, limit: int = 1000) -> List[Dict]:
        """Get recent monitoring data (thread-safe)."""
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT * FROM monitoring_data
                    WHERE timestamp >= CAST(strftime('%s', 'now', '-' || ? || ' hours') AS INTEGER)
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (hours, limit))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                print(f"Error getting recent data: {e}")
                return []
    
    def get_statistics(self, hours: int = 24) -> Dict:
        """Get statistics for the specified time period (thread-safe)."""
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT 
                        AVG(cpu_usage) as avg_cpu,
                        MAX(cpu_usage) as max_cpu,
                        AVG(memory_percent) as avg_memory,
                        MAX(memory_percent) as max_memory,
                        AVG(gpu_usage) as avg_gpu,
                        MAX(gpu_usage) as max_gpu,
                        COUNT(*) as sample_count
                    FROM monitoring_data
                    WHERE timestamp >= CAST(strftime('%s', 'now', '-' || ? || ' hours') AS INTEGER)
                ''', (hours,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'avg_cpu': row[0] or 0,
                        'max_cpu': row[1] or 0,
                        'avg_memory': row[2] or 0,
                        'max_memory': row[3] or 0,
                        'avg_gpu': row[4] or 0,
                        'max_gpu': row[5] or 0,
                        'sample_count': row[6] or 0
                    }
            except Exception as e:
                print(f"Error getting statistics: {e}")
        
        return {}
    
    def cleanup_old_data(self, days: int = 7) -> int:
        """Remove data older than specified days (thread-safe).
        
        Args:
            days: Delete data older than this many days
            
        Returns:
            Number of records deleted
        """
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                
                # Count records to be deleted
                cursor.execute('''
                    SELECT COUNT(*) FROM monitoring_data
                    WHERE timestamp < CAST(strftime('%s', 'now', '-' || ? || ' days') AS INTEGER)
                ''', (days,))
                count_before = cursor.fetchone()[0]
                
                if count_before == 0:
                    return 0
                
                # Delete old records
                cursor.execute('''
                    DELETE FROM monitoring_data
                    WHERE timestamp < CAST(strftime('%s', 'now', '-' || ? || ' days') AS INTEGER)
                ''', (days,))
                self.conn.commit()
                
                deleted_count = cursor.rowcount
                print(f"🗑️  Cleaned up {deleted_count:,} records older than {days} days")
                
                # Vacuum to reclaim space
                cursor.execute('VACUUM')
                
                return deleted_count
            except Exception as e:
                print(f"Error cleaning up data: {e}")
                return 0
    
    def close(self):
        """Close database connection (thread-safe)."""
        with self.db_lock:
            if self.conn:
                self.conn.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


if __name__ == '__main__':
    # Test the logger
    logger = DataLogger()
    print(f"Database initialized at: {logger.db_path}")
    stats = logger.get_statistics()
    print(f"Statistics: {stats}")
