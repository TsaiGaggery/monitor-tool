"""Unit tests for DataLogger with mocked database."""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


# Add src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from storage.data_logger import DataLogger


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def logger(temp_db):
    """Create a DataLogger instance with temporary database."""
    # Disable auto cleanup for controlled testing
    return DataLogger(db_path=temp_db, auto_cleanup_days=0)


class TestDataLoggerInit:
    """Test DataLogger initialization."""
    
    def test_creates_database_file(self, temp_db):
        """Test that database file is created."""
        logger = DataLogger(db_path=temp_db, auto_cleanup_days=0)
        assert os.path.exists(temp_db)
        logger.close()
    
    def test_creates_default_location(self):
        """Test that default database location is created."""
        logger = DataLogger(auto_cleanup_days=0)
        assert logger.db_path.endswith('monitor_data.db')
        assert os.path.exists(logger.db_path)
        logger.close()
    
    def test_creates_schema(self, logger):
        """Test that database schema is created."""
        cursor = logger.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert 'monitoring_data' in tables
    
    def test_creates_index(self, logger):
        """Test that timestamp index is created."""
        cursor = logger.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        assert 'idx_timestamp' in indexes


class TestDataLoggerLogging:
    """Test data logging functionality."""
    
    def test_log_data_basic(self, logger):
        """Test basic data logging."""
        cpu_info = {
            'usage': {'total': 50.0},
            'frequency': {'average': 2400},
            'temperature': {}
        }
        memory_info = {
            'memory': {'used': 8000000000, 'percent': 50.0},
            'swap': {'used': 0}
        }
        
        logger.log_data(cpu_info, memory_info)
        
        # Verify data was inserted
        cursor = logger.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM monitoring_data")
        count = cursor.fetchone()[0]
        assert count == 1
    
    def test_log_data_with_gpu(self, logger):
        """Test logging with GPU data."""
        cpu_info = {'usage': {'total': 50.0}, 'frequency': {'average': 2400}, 'temperature': {}}
        memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
        gpu_info = {
            'available': True,
            'gpus': [{
                'gpu_util': 75.0,
                'temperature': 60.0,
                'memory_used': 4000
            }]
        }
        
        logger.log_data(cpu_info, memory_info, gpu_info=gpu_info)
        
        cursor = logger.conn.cursor()
        cursor.execute("SELECT gpu_usage, gpu_temp, gpu_memory FROM monitoring_data")
        row = cursor.fetchone()
        assert row[0] == 75.0  # gpu_usage
        assert row[1] == 60.0  # gpu_temp
        assert row[2] == 4000  # gpu_memory
    
    def test_log_data_with_npu(self, logger):
        """Test logging with NPU data."""
        cpu_info = {'usage': {'total': 50.0}, 'frequency': {'average': 2400}, 'temperature': {}}
        memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
        npu_info = {
            'available': True,
            'utilization': 30.0
        }
        
        logger.log_data(cpu_info, memory_info, npu_info=npu_info)
        
        cursor = logger.conn.cursor()
        cursor.execute("SELECT npu_usage FROM monitoring_data")
        row = cursor.fetchone()
        assert row[0] == 30.0
    
    @pytest.mark.parametrize("cpu_usage,expected", [
        (0.0, 0.0),
        (50.0, 50.0),
        (100.0, 100.0),
    ])
    def test_log_data_various_cpu_usage(self, logger, cpu_usage, expected):
        """Test logging various CPU usage values."""
        cpu_info = {'usage': {'total': cpu_usage}, 'frequency': {'average': 2400}, 'temperature': {}}
        memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
        
        logger.log_data(cpu_info, memory_info)
        
        cursor = logger.conn.cursor()
        cursor.execute("SELECT cpu_usage FROM monitoring_data")
        row = cursor.fetchone()
        assert row[0] == expected


class TestDataLoggerCleanup:
    """Test data cleanup functionality."""
    
    def test_cleanup_old_data_empty_db(self, logger):
        """Test cleanup on empty database."""
        deleted = logger.cleanup_old_data(days=7)
        assert deleted == 0
    
    def test_cleanup_old_data_with_old_records(self, logger):
        """Test cleanup removes old records."""
        # Insert old record (manually set timestamp)
        cursor = logger.conn.cursor()
        old_timestamp = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO monitoring_data (timestamp, cpu_usage, cpu_freq, cpu_temp,
                                        memory_usage, memory_percent, swap_usage,
                                        gpu_usage, gpu_temp, gpu_memory, npu_usage, data_json)
            VALUES (?, 50, 2400, 50, 8000000000, 50, 0, 0, 0, 0, 0, '{}')
        ''', (old_timestamp,))
        logger.conn.commit()
        
        # Insert recent record
        cpu_info = {'usage': {'total': 50.0}, 'frequency': {'average': 2400}, 'temperature': {}}
        memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
        logger.log_data(cpu_info, memory_info)
        
        # Cleanup data older than 7 days
        deleted = logger.cleanup_old_data(days=7)
        
        assert deleted == 1
        
        # Verify only recent record remains
        cursor.execute("SELECT COUNT(*) FROM monitoring_data")
        count = cursor.fetchone()[0]
        assert count == 1
    
    def test_auto_cleanup_on_init(self, temp_db):
        """Test auto cleanup runs on initialization."""
        # Create logger and insert old data
        logger1 = DataLogger(db_path=temp_db, auto_cleanup_days=0)
        cursor = logger1.conn.cursor()
        old_timestamp = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO monitoring_data (timestamp, cpu_usage, cpu_freq, cpu_temp,
                                        memory_usage, memory_percent, swap_usage,
                                        gpu_usage, gpu_temp, gpu_memory, npu_usage, data_json)
            VALUES (?, 50, 2400, 50, 8000000000, 50, 0, 0, 0, 0, 0, '{}')
        ''', (old_timestamp,))
        logger1.conn.commit()
        logger1.close()
        
        # Create new logger with auto_cleanup_days=3
        with patch('builtins.print'):  # Suppress cleanup message
            logger2 = DataLogger(db_path=temp_db, auto_cleanup_days=3)
        
        # Old record should be deleted
        cursor = logger2.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM monitoring_data")
        count = cursor.fetchone()[0]
        assert count == 0
        
        logger2.close()


class TestDataLoggerThreadSafety:
    """Test thread-safe operations."""
    
    def test_log_data_is_thread_safe(self, logger):
        """Test that log_data uses lock."""
        with patch.object(logger, 'db_lock') as mock_lock:
            cpu_info = {'usage': {'total': 50.0}, 'frequency': {'average': 2400}, 'temperature': {}}
            memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
            
            logger.log_data(cpu_info, memory_info)
            
            # Verify lock was used
            mock_lock.__enter__.assert_called()
            mock_lock.__exit__.assert_called()
    
    def test_get_recent_data_is_thread_safe(self, logger):
        """Test that get_recent_data uses lock."""
        with patch.object(logger, 'db_lock') as mock_lock:
            logger.get_recent_data(hours=1)
            
            mock_lock.__enter__.assert_called()
            mock_lock.__exit__.assert_called()


class TestDataLoggerQueries:
    """Test data query methods."""
    
    def test_get_recent_data_empty(self, logger):
        """Test get_recent_data on empty database."""
        data = logger.get_recent_data(hours=1)
        assert data == []
    
    def test_get_recent_data_with_records(self, logger):
        """Test get_recent_data returns records."""
        cpu_info = {'usage': {'total': 50.0}, 'frequency': {'average': 2400}, 'temperature': {}}
        memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
        logger.log_data(cpu_info, memory_info)
        
        data = logger.get_recent_data(hours=24)  # Use 24 hours to ensure we get the record
        assert len(data) >= 1
        assert 'cpu_usage' in data[0]
    
    def test_get_statistics_empty(self, logger):
        """Test get_statistics on empty database."""
        stats = logger.get_statistics(hours=24)
        # Empty database returns dict with 0 values, not empty dict
        assert stats['sample_count'] == 0
    
    def test_get_statistics_with_data(self, logger):
        """Test get_statistics calculates correctly."""
        cpu_info = {'usage': {'total': 50.0}, 'frequency': {'average': 2400}, 'temperature': {}}
        memory_info = {'memory': {'used': 8000000000, 'percent': 50.0}, 'swap': {'used': 0}}
        logger.log_data(cpu_info, memory_info)
        
        stats = logger.get_statistics(hours=24)
        assert stats['avg_cpu'] == 50.0
        assert stats['max_cpu'] == 50.0
        assert stats['sample_count'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
