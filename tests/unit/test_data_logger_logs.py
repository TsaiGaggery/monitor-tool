#!/usr/bin/env python3
"""Unit tests for DataLogger log storage functionality."""

import unittest
import tempfile
import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path

from storage.data_logger import DataLogger, LogEntry


class TestDataLoggerLogStorage(unittest.TestCase):
    """Test log storage functionality in DataLogger."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_session.db')
        self.logger = DataLogger(db_path=self.db_path, auto_cleanup_days=0)
    
    def tearDown(self):
        """Clean up test database."""
        self.logger.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_log_entries_table_created(self):
        """Test that log_entries table is created."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='log_entries'
        """)
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'log_entries')
    
    def test_session_metadata_table_created(self):
        """Test that session_metadata table is created."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='session_metadata'
        """)
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'session_metadata')
    
    def test_log_entries_indexes_created(self):
        """Test that log_entries indexes are created."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check for indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='log_entries'
        """)
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        self.assertIn('idx_log_timestamp', indexes)
        self.assertIn('idx_log_session', indexes)
        self.assertIn('idx_log_severity', indexes)
    
    def test_store_single_log_entry(self):
        """Test storing a single log entry."""
        log_entry = LogEntry(
            timestamp=datetime(2025, 11, 21, 14, 30, 0),
            source_file='/var/log/syslog',
            severity='error',
            facility='kernel',
            message='Test error message',
            raw_line='Nov 21 14:30:00 kernel: Test error message',
            process_context=[1234]
        )
        
        count = self.logger.log_entries([log_entry])
        
        self.assertEqual(count, 1)
        
        # Verify data in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM log_entries")
        rows = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[2], '2025-11-21T14:30:00')  # timestamp
        self.assertEqual(row[3], '/var/log/syslog')  # source_file
        self.assertEqual(row[4], 'error')  # severity
        self.assertEqual(row[5], 'kernel')  # facility
        self.assertEqual(row[6], 'Test error message')  # message
        self.assertEqual(row[8], '[1234]')  # process_context as JSON
    
    def test_store_multiple_log_entries(self):
        """Test storing multiple log entries."""
        log_entries = [
            LogEntry(
                timestamp=datetime(2025, 11, 21, 14, 30, i),
                source_file=f'/var/log/syslog',
                severity='error' if i % 2 == 0 else 'warning',
                facility='kernel',
                message=f'Test message {i}',
                raw_line=f'Nov 21 14:30:{i:02d} kernel: Test message {i}',
                process_context=[i * 100]
            )
            for i in range(10)
        ]
        
        count = self.logger.log_entries(log_entries)
        
        self.assertEqual(count, 10)
        
        # Verify count in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        db_count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(db_count, 10)
    
    def test_batch_insert_large_dataset(self):
        """Test batch insert with large dataset."""
        log_entries = [
            LogEntry(
                timestamp=datetime(2025, 11, 21, 14, 30, 0),
                source_file='/var/log/syslog',
                severity='info',
                facility='systemd',
                message=f'Batch message {i}',
                raw_line=f'Nov 21 14:30:00 systemd: Batch message {i}',
                process_context=[i]
            )
            for i in range(250)  # More than batch_size (100)
        ]
        
        count = self.logger.log_entries(log_entries, batch_size=100)
        
        self.assertEqual(count, 250)
        
        # Verify all entries stored
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        db_count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(db_count, 250)
    
    def test_log_entry_without_process_context(self):
        """Test storing log entry without process context."""
        log_entry = LogEntry(
            timestamp=datetime(2025, 11, 21, 14, 30, 0),
            source_file='/var/log/syslog',
            severity='info',
            facility=None,
            message='Simple message',
            raw_line='Nov 21 14:30:00 Simple message',
            process_context=None
        )
        
        count = self.logger.log_entries([log_entry])
        
        self.assertEqual(count, 1)
        
        # Verify process_context stored as empty JSON array
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT process_context FROM log_entries")
        result = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(result, '[]')
    
    def test_set_session_metadata(self):
        """Test setting session metadata."""
        start_time = datetime(2025, 11, 21, 14, 0, 0)
        end_time = datetime(2025, 11, 21, 15, 0, 0)
        
        self.logger.set_session_metadata(
            start_time=start_time,
            end_time=end_time,
            source_type='ssh',
            source_name='user@server.com',
            log_collection_enabled=True
        )
        
        # Verify in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM session_metadata WHERE session_id = ?", 
                      (self.logger.session_id,))
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[1], '2025-11-21T14:00:00')  # start_time
        self.assertEqual(row[2], '2025-11-21T15:00:00')  # end_time
        self.assertEqual(row[3], 'ssh')  # source_type
        self.assertEqual(row[4], 'user@server.com')  # source_name
        self.assertEqual(row[5], 1)  # log_collection_enabled (True)
    
    def test_get_session_metadata(self):
        """Test retrieving session metadata."""
        start_time = datetime(2025, 11, 21, 14, 0, 0)
        end_time = datetime(2025, 11, 21, 15, 0, 0)
        
        self.logger.set_session_metadata(
            start_time=start_time,
            end_time=end_time,
            source_type='adb',
            source_name='192.168.1.68:5555',
            log_collection_enabled=False
        )
        
        metadata = self.logger.get_session_metadata()
        
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['session_id'], self.logger.session_id)
        self.assertEqual(metadata['start_time'], '2025-11-21T14:00:00')
        self.assertEqual(metadata['end_time'], '2025-11-21T15:00:00')
        self.assertEqual(metadata['source_type'], 'adb')
        self.assertEqual(metadata['source_name'], '192.168.1.68:5555')
        self.assertEqual(metadata['log_collection_enabled'], False)
    
    def test_get_log_entries(self):
        """Test retrieving log entries."""
        # Store test entries
        log_entries = [
            LogEntry(
                timestamp=datetime(2025, 11, 21, 14, 30, i),
                source_file='/var/log/syslog',
                severity='error' if i < 3 else 'warning',
                facility='kernel',
                message=f'Message {i}',
                raw_line=f'Raw line {i}',
                process_context=[i]
            )
            for i in range(5)
        ]
        self.logger.log_entries(log_entries)
        
        # Retrieve all entries
        results = self.logger.get_log_entries()
        
        self.assertEqual(len(results), 5)
        
        # Test severity filter
        error_results = self.logger.get_log_entries(severity='error')
        self.assertEqual(len(error_results), 3)
        
        # Test limit
        limited_results = self.logger.get_log_entries(limit=2)
        self.assertEqual(len(limited_results), 2)
    
    def test_get_log_entries_with_time_filter(self):
        """Test retrieving log entries with time range filter."""
        # Store entries with different timestamps
        log_entries = [
            LogEntry(
                timestamp=datetime(2025, 11, 21, 14, i, 0),
                source_file='/var/log/syslog',
                severity='info',
                facility='kernel',
                message=f'Message at 14:{i:02d}',
                raw_line=f'Raw line {i}',
                process_context=None
            )
            for i in range(10, 50, 10)  # 14:10, 14:20, 14:30, 14:40
        ]
        self.logger.log_entries(log_entries)
        
        # Filter by time range
        start_time = datetime(2025, 11, 21, 14, 20, 0)
        end_time = datetime(2025, 11, 21, 14, 35, 0)
        
        results = self.logger.get_log_entries(
            start_time=start_time,
            end_time=end_time
        )
        
        # Should get 14:20 and 14:30
        self.assertEqual(len(results), 2)
    
    def test_empty_log_entries_list(self):
        """Test handling of empty log entries list."""
        count = self.logger.log_entries([])
        
        self.assertEqual(count, 0)
        
        # Verify no entries in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        db_count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(db_count, 0)
    
    def test_session_id_consistency(self):
        """Test that all entries use the same session_id."""
        log_entries = [
            LogEntry(
                timestamp=datetime(2025, 11, 21, 14, 30, i),
                source_file='/var/log/syslog',
                severity='info',
                facility='kernel',
                message=f'Message {i}',
                raw_line=f'Raw line {i}',
                process_context=None
            )
            for i in range(3)
        ]
        self.logger.log_entries(log_entries)
        
        # Verify all use same session_id
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM log_entries")
        session_ids = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(session_ids), 1)
        self.assertEqual(session_ids[0][0], self.logger.session_id)


if __name__ == '__main__':
    unittest.main()
