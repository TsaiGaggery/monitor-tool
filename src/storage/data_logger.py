#!/usr/bin/env python3
"""Data logger for storing monitoring data to SQLite database."""

import sqlite3
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional
import os


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
                required_columns = {'timestamp_ms', 'monitor_cpu_utime', 'monitor_cpu_stime'}
                
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
                timestamp INTEGER NOT NULL,
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
                    
                    load_avg_data = tier1_info.get('load_average', {})
                    load_avg_1m = load_avg_data.get('1min', 0.0)
                    load_avg_5m = load_avg_data.get('5min', 0.0)
                    load_avg_15m = load_avg_data.get('15min', 0.0)
                    
                    procs_data = tier1_info.get('processes', {})
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
                
                # Insert into database
                cursor.execute('''
                    INSERT INTO monitoring_data 
                    (timestamp, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle, 
                     cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz,
                     cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb,
                     gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes,
                     npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors,
                     ctxt, load_avg_1m, load_avg_5m, load_avg_15m, procs_running, procs_blocked,
                     per_core_irq_pct, per_core_softirq_pct, interrupt_data,
                     monitor_cpu_utime, monitor_cpu_stime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (timestamp, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle,
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
    
    def get_recent_data(self, hours: int = 1, limit: int = 1000) -> List[Dict]:
        """Get recent monitoring data (thread-safe)."""
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT * FROM monitoring_data
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
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
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
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
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                ''', (days,))
                count_before = cursor.fetchone()[0]
                
                if count_before == 0:
                    return 0
                
                # Delete old records
                cursor.execute('''
                    DELETE FROM monitoring_data
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
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
