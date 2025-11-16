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
        """Initialize database schema."""
        # Allow connection to be used from multiple threads
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Create monitoring data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                cpu_usage REAL,
                cpu_freq REAL,
                cpu_temp REAL,
                memory_usage REAL,
                memory_percent REAL,
                swap_usage REAL,
                gpu_usage REAL,
                gpu_temp REAL,
                gpu_memory REAL,
                npu_usage REAL,
                data_json TEXT
            )
        ''')
        
        # Create index on timestamp
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON monitoring_data(timestamp)
        ''')
        
        self.conn.commit()
    
    def log_data(self, cpu_info: Dict, memory_info: Dict, 
                 gpu_info: Dict = None, npu_info: Dict = None):
        """Log monitoring data to database (thread-safe)."""
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                
                # Extract key metrics
                cpu_usage = cpu_info.get('usage', {}).get('total', 0)
                cpu_freq = cpu_info.get('frequency', {}).get('average', 0)
                
                # Get CPU temperature (first sensor, first core)
                cpu_temp = 0
                temp_data = cpu_info.get('temperature', {})
                if temp_data:
                    first_sensor = next(iter(temp_data.values()), [])
                    if first_sensor:
                        cpu_temp = first_sensor[0].get('current', 0)
                
                mem = memory_info.get('memory', {})
                memory_usage = mem.get('used', 0)
                memory_percent = mem.get('percent', 0)
                
                swap = memory_info.get('swap', {})
                swap_usage = swap.get('used', 0)
                
                # GPU data
                gpu_usage = 0
                gpu_temp = 0
                gpu_memory = 0
                if gpu_info and gpu_info.get('available'):
                    gpus = gpu_info.get('gpus', [])
                    if gpus:
                        gpu = gpus[0]
                        gpu_usage = gpu.get('gpu_util', 0)
                        gpu_temp = gpu.get('temperature', 0)
                        gpu_memory = gpu.get('memory_used', 0)
                
                # NPU data
                npu_usage = 0
                if npu_info and npu_info.get('available'):
                    npu_usage = npu_info.get('utilization', 0)
                
                # Store full data as JSON
                full_data = {
                    'cpu': cpu_info,
                    'memory': memory_info,
                    'gpu': gpu_info,
                    'npu': npu_info
                }
                
                cursor.execute('''
                    INSERT INTO monitoring_data 
                    (cpu_usage, cpu_freq, cpu_temp, memory_usage, memory_percent,
                     swap_usage, gpu_usage, gpu_temp, gpu_memory, npu_usage, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cpu_usage, cpu_freq, cpu_temp, memory_usage, memory_percent,
                      swap_usage, gpu_usage, gpu_temp, gpu_memory, npu_usage,
                      json.dumps(full_data)))
                
                self.conn.commit()
            except Exception as e:
                print(f"Error logging data: {e}")
    
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
