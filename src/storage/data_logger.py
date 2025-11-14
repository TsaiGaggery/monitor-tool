#!/usr/bin/env python3
"""Data logger for storing monitoring data to SQLite database."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import os


class DataLogger:
    """Log monitoring data to SQLite database."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to ~/.monitor-tool/data.db
            home = os.path.expanduser('~')
            data_dir = os.path.join(home, '.monitor-tool')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'monitor_data.db')
        
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database schema."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Create monitoring data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
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
        """Log monitoring data to database."""
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
        """Get recent monitoring data."""
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
        """Get statistics for the specified time period."""
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
    
    def cleanup_old_data(self, days: int = 7):
        """Remove data older than specified days."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                DELETE FROM monitoring_data
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            ''', (days,))
            self.conn.commit()
            print(f"Cleaned up data older than {days} days")
        except Exception as e:
            print(f"Error cleaning up data: {e}")
    
    def close(self):
        """Close database connection."""
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
