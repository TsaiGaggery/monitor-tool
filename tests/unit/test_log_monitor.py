"""
Unit tests for LogMonitor class.
"""

import pytest
from datetime import datetime, timedelta
from src.monitors.log_monitor import LogMonitor, LogEntry


class TestLogMonitorInit:
    """Test LogMonitor initialization."""
    
    def test_default_initialization(self):
        """Test LogMonitor initializes with default config."""
        config = {'enabled': True}
        monitor = LogMonitor(config)
        
        assert monitor.enabled == True
        assert monitor.sources == []
        assert monitor.keywords == []
        assert monitor.max_lines == 1000
        assert monitor.context_lines == 2
        assert monitor.anonymize_enabled == True
        assert monitor.mode == 'local'
    
    def test_custom_configuration(self):
        """Test LogMonitor with custom configuration."""
        config = {
            'enabled': False,
            'sources': ['/var/log/syslog', '/var/log/auth.log'],
            'keywords': ['ERROR', 'WARNING', 'Failed'],
            'max_log_lines': 500,
            'include_context_lines': 5,
            'anonymize': {
                'enabled': False,
                'patterns': ['ip_addresses']
            }
        }
        monitor = LogMonitor(config)
        
        assert monitor.enabled == False
        assert len(monitor.sources) == 2
        assert monitor.keywords == ['error', 'warning', 'failed']
        assert monitor.max_lines == 500
        assert monitor.context_lines == 5
        assert monitor.anonymize_enabled == False
    
    def test_ssh_mode_initialization(self):
        """Test LogMonitor with SSH mode."""
        config = {'enabled': True}
        ssh_client = "mock_ssh_client"
        monitor = LogMonitor(config, mode='ssh', ssh_client=ssh_client)
        
        assert monitor.mode == 'ssh'
        assert monitor.ssh_client == ssh_client
    
    def test_adb_mode_initialization(self):
        """Test LogMonitor with ADB mode."""
        config = {'enabled': True}
        adb_device = "172.25.65.70:5555"
        monitor = LogMonitor(config, mode='adb', adb_device=adb_device)
        
        assert monitor.mode == 'adb'
        assert monitor.adb_device == adb_device


class TestTimestampParsing:
    """Test log timestamp parsing."""
    
    def test_parse_iso8601_timestamp(self):
        """Test parsing ISO 8601 timestamp."""
        monitor = LogMonitor({'enabled': True})
        
        line = "2025-11-21T14:30:45.123Z [ERROR] Test message"
        timestamp = monitor._parse_log_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.year == 2025
        assert timestamp.month == 11
        assert timestamp.day == 21
    
    def test_parse_syslog_timestamp(self):
        """Test parsing syslog timestamp."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 hostname kernel: Test message"
        timestamp = monitor._parse_log_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.month == 11
        assert timestamp.day == 21
        assert timestamp.hour == 14
        assert timestamp.minute == 30
    
    def test_parse_apache_timestamp(self):
        """Test parsing Apache/Nginx timestamp."""
        monitor = LogMonitor({'enabled': True})
        
        line = '192.168.1.1 - - [21/Nov/2025:14:30:45 +0000] "GET /index.html HTTP/1.1" 200'
        timestamp = monitor._parse_log_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.year == 2025
        assert timestamp.month == 11
        assert timestamp.day == 21
    
    def test_parse_simple_timestamp(self):
        """Test parsing simple timestamp format."""
        monitor = LogMonitor({'enabled': True})
        
        line = "2025-11-21 14:30:45 ERROR: Connection failed"
        timestamp = monitor._parse_log_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.year == 2025
        assert timestamp.month == 11
        assert timestamp.day == 21
    
    def test_parse_no_timestamp_returns_none(self):
        """Test line without timestamp returns None."""
        monitor = LogMonitor({'enabled': True})
        
        line = "This is a line with no timestamp"
        timestamp = monitor._parse_log_timestamp(line)
        
        # Should fallback to current time in _parse_log_line
        assert timestamp is None


class TestLogLineParsing:
    """Test log line parsing."""
    
    def test_parse_basic_log_line(self):
        """Test parsing basic log line."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host kernel: Test message"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert entry is not None
        assert entry.source_file == "/var/log/syslog"
        assert entry.facility == "syslog"
        assert entry.raw_line == line
    
    def test_severity_detection_critical(self):
        """Test critical severity detection."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host kernel: CRITICAL error occurred"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert entry.severity == 'critical'
    
    def test_severity_detection_error(self):
        """Test error severity detection."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host app[1234]: Error: Connection failed"
        entry = monitor._parse_log_line(line, "/var/log/app.log")
        
        assert entry.severity == 'error'
    
    def test_severity_detection_warning(self):
        """Test warning severity detection."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host app: Warning: Low disk space"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert entry.severity == 'warning'
    
    def test_severity_default_info(self):
        """Test default severity is info."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host app: Normal operation"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert entry.severity == 'info'
    
    def test_pid_extraction_bracket_format(self):
        """Test PID extraction from [1234] format."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host app[1234]: Test message"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert 1234 in entry.process_context
    
    def test_pid_extraction_pid_equals_format(self):
        """Test PID extraction from pid=1234 format."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host app: Process started pid=5678"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert 5678 in entry.process_context
    
    def test_pid_extraction_multiple_pids(self):
        """Test extracting multiple PIDs from one line."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host app[1234]: Forked child pid:5678"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert 1234 in entry.process_context
        assert 5678 in entry.process_context
        assert len(entry.process_context) == 2
    
    def test_no_pids_extracted(self):
        """Test log line with no PIDs."""
        monitor = LogMonitor({'enabled': True})
        
        line = "Nov 21 14:30:45 host kernel: System startup"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert entry.process_context == []


class TestAnonymization:
    """Test data anonymization."""
    
    def test_anonymize_ip_addresses(self):
        """Test IP address anonymization."""
        config = {
            'enabled': True,
            'anonymize': {
                'enabled': True,
                'patterns': ['ip_addresses']
            }
        }
        monitor = LogMonitor(config)
        
        text = "Connection from 192.168.1.100 to 10.0.0.5"
        anonymized = monitor._anonymize_text(text)
        
        assert '192.168.1.100' not in anonymized
        assert '10.0.0.5' not in anonymized
        assert 'xxx.xxx.xxx.xxx' in anonymized
    
    def test_anonymize_home_directories(self):
        """Test home directory anonymization."""
        config = {
            'enabled': True,
            'anonymize': {
                'enabled': True,
                'patterns': ['home_directories']
            }
        }
        monitor = LogMonitor(config)
        
        text = "File not found: /home/john/documents/file.txt"
        anonymized = monitor._anonymize_text(text)
        
        assert 'john' not in anonymized
        assert '/home/USER' in anonymized
    
    def test_anonymize_hostnames(self):
        """Test hostname anonymization."""
        config = {
            'enabled': True,
            'anonymize': {
                'enabled': True,
                'patterns': ['hostnames']
            }
        }
        monitor = LogMonitor(config)
        
        text = "user@myserver connected"
        anonymized = monitor._anonymize_text(text)
        
        assert 'myserver' not in anonymized
        assert '@<hostname>' in anonymized
    
    def test_anonymization_disabled(self):
        """Test anonymization when disabled."""
        config = {
            'enabled': True,
            'anonymize': {
                'enabled': False
            }
        }
        monitor = LogMonitor(config)
        
        line = "Nov 21 14:30:45 host app: Connection from 192.168.1.100"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert '192.168.1.100' in entry.message
    
    def test_anonymization_in_parsed_line(self):
        """Test anonymization applied to parsed log line."""
        config = {
            'enabled': True,
            'anonymize': {
                'enabled': True,
                'patterns': ['ip_addresses']
            }
        }
        monitor = LogMonitor(config)
        
        line = "Nov 21 14:30:45 host app: Connection from 192.168.1.100"
        entry = monitor._parse_log_line(line, "/var/log/syslog")
        
        assert '192.168.1.100' not in entry.message
        assert 'xxx.xxx.xxx.xxx' in entry.message
        # Raw line should remain unchanged
        assert '192.168.1.100' in entry.raw_line


class TestKeywordFiltering:
    """Test keyword filtering."""
    
    def test_matches_single_keyword(self):
        """Test matching single keyword."""
        config = {
            'enabled': True,
            'keywords': ['error']
        }
        monitor = LogMonitor(config)
        
        assert monitor._matches_keywords("This is an error message") == True
        assert monitor._matches_keywords("Normal operation") == False
    
    def test_matches_multiple_keywords(self):
        """Test matching multiple keywords."""
        config = {
            'enabled': True,
            'keywords': ['error', 'warning', 'failed']
        }
        monitor = LogMonitor(config)
        
        assert monitor._matches_keywords("Connection failed") == True
        assert monitor._matches_keywords("Warning: low memory") == True
        assert monitor._matches_keywords("ERROR occurred") == True
        assert monitor._matches_keywords("Success") == False
    
    def test_case_insensitive_matching(self):
        """Test keyword matching is case-insensitive."""
        config = {
            'enabled': True,
            'keywords': ['ERROR']
        }
        monitor = LogMonitor(config)
        
        assert monitor._matches_keywords("error message") == True
        assert monitor._matches_keywords("ERROR MESSAGE") == True
        assert monitor._matches_keywords("Error Message") == True
    
    def test_no_keywords_matches_all(self):
        """Test no keywords configured matches all lines."""
        config = {'enabled': True}
        monitor = LogMonitor(config)
        
        assert monitor._matches_keywords("Any message") == True
        assert monitor._matches_keywords("Another message") == True


class TestCollectLogs:
    """Test log collection."""
    
    def test_collect_logs_disabled(self):
        """Test collect_logs returns empty when disabled."""
        config = {'enabled': False}
        monitor = LogMonitor(config)
        
        start = datetime.now()
        end = datetime.now() + timedelta(hours=1)
        logs = monitor.collect_logs(start, end)
        
        assert logs == []
    
    def test_collect_logs_no_sources(self):
        """Test collect_logs with no sources configured."""
        config = {'enabled': True, 'sources': []}
        monitor = LogMonitor(config)
        
        start = datetime.now()
        end = datetime.now() + timedelta(hours=1)
        logs = monitor.collect_logs(start, end)
        
        assert logs == []


class TestFileReading:
    """Test log file reading and rotation handling."""
    
    def test_read_plain_text_log(self, tmp_path):
        """Test reading plain text log file."""
        # Create test log file
        log_file = tmp_path / "test.log"
        log_content = """2025-01-21T10:00:00 INFO Test message 1
2025-01-21T10:05:00 ERROR Test error message
2025-01-21T10:10:00 WARNING Test warning
"""
        log_file.write_text(log_content)
        
        config = {'enabled': True}
        monitor = LogMonitor(config)
        
        start = datetime(2025, 1, 21, 10, 0, 0)
        end = datetime(2025, 1, 21, 10, 15, 0)
        
        entries = monitor._read_log_file(str(log_file), start, end)
        
        assert len(entries) == 3
        assert entries[0].severity == 'info'
        assert entries[1].severity == 'error'
        assert entries[2].severity == 'warning'
    
    def test_read_gzipped_log(self, tmp_path):
        """Test reading gzip-compressed log file."""
        import gzip
        
        log_file = tmp_path / "test.log.gz"
        log_content = b"2025-01-21T10:00:00 INFO Compressed message\n"
        
        with gzip.open(log_file, 'wb') as f:
            f.write(log_content)
        
        config = {'enabled': True}
        monitor = LogMonitor(config)
        
        start = datetime(2025, 1, 21, 9, 0, 0)
        end = datetime(2025, 1, 21, 11, 0, 0)
        
        entries = monitor._read_log_file(str(log_file), start, end)
        
        assert len(entries) == 1
        assert 'Compressed' in entries[0].message
    
    def test_find_rotated_logs(self, tmp_path):
        """Test finding rotated log files."""
        # Create log rotation sequence
        (tmp_path / "syslog").write_text("current\n")
        (tmp_path / "syslog.1").write_text("rotated 1\n")
        (tmp_path / "syslog.2.gz").write_bytes(b"rotated 2\n")
        
        config = {'enabled': True}
        monitor = LogMonitor(config)
        
        log_files = monitor._find_rotated_logs(str(tmp_path / "syslog"))
        
        assert len(log_files) >= 2  # At least syslog and syslog.1
        assert str(tmp_path / "syslog") in log_files
        assert str(tmp_path / "syslog.1") in log_files
    
    def test_time_range_filtering(self, tmp_path):
        """Test log entries are filtered by time range."""
        log_file = tmp_path / "test.log"
        log_content = """2025-01-21T09:00:00 INFO Before range
2025-01-21T10:00:00 INFO In range
2025-01-21T11:00:00 INFO After range
"""
        log_file.write_text(log_content)
        
        config = {'enabled': True}
        monitor = LogMonitor(config)
        
        start = datetime(2025, 1, 21, 9, 30, 0)
        end = datetime(2025, 1, 21, 10, 30, 0)
        
        entries = monitor._read_log_file(str(log_file), start, end)
        
        assert len(entries) == 1
        assert 'In range' in entries[0].message
    
    def test_max_lines_limit(self, tmp_path):
        """Test max_lines limit prevents memory issues."""
        log_file = tmp_path / "large.log"
        
        # Create log with many lines in time range
        lines = [f"2025-01-21T10:{i//60:02d}:{i%60:02d} INFO Message {i}\n" for i in range(100)]
        log_file.write_text(''.join(lines))
        
        config = {'enabled': True, 'max_lines': 10}
        monitor = LogMonitor(config)
        
        # Wide time range to include all lines
        start = datetime(2025, 1, 21, 9, 0, 0)
        end = datetime(2025, 1, 21, 12, 0, 0)
        
        entries = monitor._read_log_file(str(log_file), start, end)
        
        assert len(entries) == 10  # Should stop at max_lines
    
    def test_permission_error_handling(self, tmp_path, monkeypatch):
        """Test graceful handling of permission errors."""
        log_file = tmp_path / "protected.log"
        log_file.write_text("2025-01-21T10:00:00 INFO Test\n")
        
        config = {'enabled': True, 'sources': [str(log_file)]}
        monitor = LogMonitor(config)
        
        # Mock open to raise PermissionError
        original_open = open
        def mock_open(*args, **kwargs):
            raise PermissionError("Access denied")
        
        start = datetime(2025, 1, 21, 9, 0, 0)
        end = datetime(2025, 1, 21, 11, 0, 0)
        
        with monkeypatch.context() as m:
            m.setattr('builtins.open', mock_open)
            # Should not raise, just return empty list
            entries = monitor._collect_local_logs(str(log_file), start, end)
            assert entries == []
    
    def test_keyword_filtering_in_file(self, tmp_path):
        """Test keyword filtering works when reading files."""
        log_file = tmp_path / "filtered.log"
        log_content = """2025-01-21T10:00:00 INFO Normal message
2025-01-21T10:01:00 ERROR Critical error occurred
2025-01-21T10:02:00 INFO Another normal message
"""
        log_file.write_text(log_content)
        
        config = {
            'enabled': True,
            'keywords': ['error', 'critical']
        }
        monitor = LogMonitor(config)
        
        start = datetime(2025, 1, 21, 9, 0, 0)
        end = datetime(2025, 1, 21, 11, 0, 0)
        
        entries = monitor._read_log_file(str(log_file), start, end)
        
        # Only the error line should match
        assert len(entries) == 1
        assert 'error' in entries[0].message.lower()

