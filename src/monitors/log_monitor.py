"""
System log monitoring and collection module.

This module provides functionality to collect, filter, and analyze system logs
from various sources (local files, SSH remote, Android ADB) with support for:
- Keyword-based filtering
- Time-range extraction  
- Log rotation handling
- Compression support (gzip)
- Data anonymization
- Process correlation
"""

import re
import gzip
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import subprocess


@dataclass
class LogEntry:
    """Data class for a single log entry.
    
    Attributes:
        timestamp: When the log entry was created
        source_file: Path to the log file source
        severity: Log severity level (critical, error, warning, info, debug)
        facility: Log facility (syslog, kernel, auth, etc.)
        message: The log message content
        raw_line: Original unprocessed log line
        process_context: List of related process IDs (PIDs)
    """
    timestamp: datetime
    source_file: str
    severity: str
    facility: str
    message: str
    raw_line: str
    process_context: List[int]


class LogMonitor:
    """
    Monitor and collect system logs for a specified time period.
    
    Features:
    - Keyword-based filtering for relevant logs
    - Time-range extraction
    - Log rotation handling (syslog, syslog.1, syslog.2.gz)
    - Compression support (gzip)
    - Data anonymization (IPs, hostnames, paths)
    - Process correlation (PID extraction)
    - Support for local, SSH, and ADB modes
    """
    
    # Log severity patterns (case-insensitive)
    SEVERITY_PATTERNS = {
        'critical': re.compile(r'\b(critical|crit|fatal|panic|emerg)\b', re.IGNORECASE),
        'error': re.compile(r'\b(error|err|failed|failure)\b', re.IGNORECASE),
        'warning': re.compile(r'\b(warning|warn)\b', re.IGNORECASE),
        'info': re.compile(r'\b(info|information|notice)\b', re.IGNORECASE),
        'debug': re.compile(r'\b(debug)\b', re.IGNORECASE)
    }
    
    # PID extraction pattern - matches [1234], pid=1234, pid:1234, (1234)
    PID_PATTERN = re.compile(r'\[(\d+)\]|pid[=:\s]+(\d+)|\((\d+)\)', re.IGNORECASE)
    
    # Common timestamp patterns for log parsing
    TIMESTAMP_PATTERNS = [
        # ISO 8601 simple: 2025-01-21T10:00:00
        (re.compile(r'(\d{4}-\d{2}-\d{2}[T]\d{2}:\d{2}:\d{2})'),
         '%Y-%m-%dT%H:%M:%S'),
        # ISO 8601 with timezone: 2025-11-21T14:30:45.123Z or +00:00
        (re.compile(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'), 
         '%Y-%m-%dT%H:%M:%S.%f%z'),
        # Syslog: Nov 21 14:30:45
        (re.compile(r'([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'),
         '%b %d %H:%M:%S'),
        # Apache/Nginx: 21/Nov/2025:14:30:45 +0000
        (re.compile(r'(\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2}\s+[+-]\d{4})'),
         '%d/%b/%Y:%H:%M:%S %z'),
        # Simple: 2025-11-21 14:30:45
        (re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'),
         '%Y-%m-%d %H:%M:%S'),
    ]
    
    def __init__(self, config: dict, mode: str = 'local',
                 ssh_client=None, adb_device=None):
        """
        Initialize LogMonitor.
        
        Args:
            config: Configuration dictionary from tier2.log_collection
            mode: Operation mode ('local', 'ssh', 'adb')
            ssh_client: SSH client for remote monitoring (optional)
            adb_device: ADB device for Android monitoring (optional)
        """
        self.enabled = config.get('enabled', False)
        self.sources = config.get('sources', [])
        self.keywords = [kw.lower() for kw in config.get('keywords', [])]
        self.max_lines = config.get('max_lines', config.get('max_log_lines', 1000))
        self.context_lines = config.get('include_context_lines', 2)
        
        # Anonymization settings
        anonymize_config = config.get('anonymize', {})
        self.anonymize_enabled = anonymize_config.get('enabled', True)
        self.anonymize_patterns = anonymize_config.get('patterns', [
            'ip_addresses', 'home_directories', 'hostnames'
        ])
        
        self.mode = mode
        self.ssh_client = ssh_client
        self.adb_device = adb_device
        
        # Anonymization regex patterns
        self._init_anonymization_patterns()
    
    def _init_anonymization_patterns(self):
        """Initialize regex patterns for data anonymization."""
        self.anonymize_regexes = {}
        
        if 'ip_addresses' in self.anonymize_patterns:
            # Match IPv4 addresses
            self.anonymize_regexes['ip'] = re.compile(
                r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
            )
        
        if 'home_directories' in self.anonymize_patterns:
            # Match /home/username or /Users/username
            self.anonymize_regexes['home'] = re.compile(
                r'(/home/|/Users/)([^/\s]+)'
            )
        
        if 'hostnames' in self.anonymize_patterns:
            # Match common hostname patterns (simplified)
            self.anonymize_regexes['hostname'] = re.compile(
                r'@([a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9])'
            )
    
    def collect_logs(self, start_time: datetime, 
                    end_time: datetime) -> List[LogEntry]:
        """
        Collect logs for specified time period.
        
        Args:
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects matching filters and time range
        """
        if not self.enabled:
            return []
        
        all_entries = []
        
        for source in self.sources:
            if self.mode == 'local':
                entries = self._collect_local_logs(source, start_time, end_time)
            elif self.mode == 'ssh':
                entries = self._collect_ssh_logs(source, start_time, end_time)
            elif self.mode == 'adb':
                entries = self._collect_adb_logs(start_time, end_time)
            else:
                continue
            
            all_entries.extend(entries)
        
        # Sort by timestamp
        all_entries.sort(key=lambda e: e.timestamp)
        
        # Limit total entries
        if len(all_entries) > self.max_lines:
            all_entries = all_entries[:self.max_lines]
        
        return all_entries
    
    def _parse_log_timestamp(self, line: str) -> Optional[datetime]:
        """
        Extract timestamp from log line using multiple format patterns.
        
        Args:
            line: Raw log line
        
        Returns:
            Parsed datetime or None if no timestamp found
        """
        for pattern, fmt in self.TIMESTAMP_PATTERNS:
            match = pattern.search(line)
            if match:
                timestamp_str = match.group(1)
                try:
                    # Handle special cases for syslog (no year)
                    if fmt == '%b %d %H:%M:%S':
                        # Add current year
                        current_year = datetime.now().year
                        timestamp_str = f"{timestamp_str} {current_year}"
                        fmt = '%b %d %H:%M:%S %Y'
                    
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    # Try next pattern
                    continue
        
        return None
    
    def _parse_log_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        """
        Parse a single log line into a LogEntry.
        
        Args:
            line: Raw log line
            source_file: Path to source log file
        
        Returns:
            LogEntry object or None if parsing fails
        """
        # Extract timestamp
        timestamp = self._parse_log_timestamp(line)
        if timestamp is None:
            timestamp = datetime.now()  # Fallback to current time
        
        # Detect severity
        severity = 'info'  # default
        for sev, pattern in self.SEVERITY_PATTERNS.items():
            if pattern.search(line):
                severity = sev
                break
        
        # Extract facility (simplified - from source file name)
        facility = Path(source_file).stem
        
        # Extract PIDs
        pids = []
        for match in self.PID_PATTERN.finditer(line):
            for group in match.groups():
                if group:
                    pids.append(int(group))
        
        # Remove duplicates
        pids = list(set(pids))
        
        # Anonymize if enabled
        message = line
        if self.anonymize_enabled:
            message = self._anonymize_text(line)
        
        return LogEntry(
            timestamp=timestamp,
            source_file=source_file,
            severity=severity,
            facility=facility,
            message=message,
            raw_line=line,
            process_context=pids
        )
    
    def _anonymize_text(self, text: str) -> str:
        """
        Anonymize sensitive data in text.
        
        Args:
            text: Original text
        
        Returns:
            Anonymized text
        """
        result = text
        
        # Replace IP addresses
        if 'ip' in self.anonymize_regexes:
            result = self.anonymize_regexes['ip'].sub('xxx.xxx.xxx.xxx', result)
        
        # Replace home directories
        if 'home' in self.anonymize_regexes:
            result = self.anonymize_regexes['home'].sub(r'\1USER', result)
        
        # Replace hostnames
        if 'hostname' in self.anonymize_regexes:
            result = self.anonymize_regexes['hostname'].sub('@<hostname>', result)
        
        return result
    
    def _matches_keywords(self, line: str) -> bool:
        """
        Check if log line matches any configured keywords.
        
        Args:
            line: Log line to check
        
        Returns:
            True if matches keywords or no keywords configured
        """
        if not self.keywords:
            return True  # No filtering if no keywords
        
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in self.keywords)
    
    def _collect_local_logs(self, source: str, 
                           start_time: datetime,
                           end_time: datetime) -> List[LogEntry]:
        """
        Collect logs from local file system.
        
        Args:
            source: Path to log file or directory
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects from local logs
        """
        entries = []
        
        # Find all log files (including rotated ones)
        log_files = self._find_rotated_logs(source)
        
        for log_file in log_files:
            try:
                file_entries = self._read_log_file(log_file, start_time, end_time)
                entries.extend(file_entries)
            except PermissionError:
                # Log permission error but continue with other files
                continue
            except Exception as e:
                # Log error but continue
                continue
        
        return entries
    
    def _find_rotated_logs(self, source: str) -> List[str]:
        """
        Find all log files including rotated ones.
        
        Args:
            source: Path to log file or pattern
        
        Returns:
            List of log file paths sorted by modification time (newest first)
        
        Examples:
            /var/log/syslog -> [/var/log/syslog, /var/log/syslog.1, /var/log/syslog.2.gz]
        """
        from pathlib import Path
        import glob
        
        log_files = []
        source_path = Path(source)
        
        if source_path.is_file():
            # Single file - find rotated versions
            log_files.append(str(source_path))
            
            # Look for numbered rotations
            for i in range(1, 10):  # Check up to .9
                rotated = Path(f"{source}.{i}")
                if rotated.exists():
                    log_files.append(str(rotated))
                
                # Check gzipped version
                rotated_gz = Path(f"{source}.{i}.gz")
                if rotated_gz.exists():
                    log_files.append(str(rotated_gz))
        
        elif source_path.is_dir():
            # Directory - find all .log files
            log_files = glob.glob(str(source_path / "*.log"))
            log_files.extend(glob.glob(str(source_path / "*.log.*")))
        
        else:
            # Pattern - use glob
            log_files = glob.glob(source)
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda f: Path(f).stat().st_mtime, reverse=True)
        
        return log_files
    
    def _read_log_file(self, file_path: str,
                       start_time: datetime,
                       end_time: datetime) -> List[LogEntry]:
        """
        Read and parse a log file with streaming support.
        
        Args:
            file_path: Path to log file
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects from the file
        """
        import gzip
        from pathlib import Path
        
        entries = []
        file_path_obj = Path(file_path)
        
        # Determine if file is gzipped
        is_gzipped = file_path_obj.suffix == '.gz'
        
        # Open file with appropriate handler
        open_func = gzip.open if is_gzipped else open
        
        try:
            with open_func(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
                # Stream file line by line to avoid loading entire file
                for line in f:
                    line = line.rstrip('\n')
                    
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # Check keyword filtering
                    if not self._matches_keywords(line):
                        continue
                    
                    # Parse the line
                    entry = self._parse_log_line(line, str(file_path_obj))
                    if not entry:
                        continue
                    
                    # Filter by time range
                    if entry.timestamp:
                        if entry.timestamp < start_time or entry.timestamp > end_time:
                            continue
                    
                    entries.append(entry)
                    
                    # Limit number of entries to prevent memory issues
                    if len(entries) >= self.max_lines:
                        break
        
        except Exception as e:
            # Re-raise to be handled by caller
            raise
        
        return entries
    
    def _collect_ssh_logs(self, source: str,
                         start_time: datetime,
                         end_time: datetime) -> List[LogEntry]:
        """
        Collect logs from remote system via SSH.
        
        Placeholder - will be implemented in TASK-011
        """
        # TODO: Implement in TASK-011
        return []
    
    def _collect_adb_logs(self, start_time: datetime,
                         end_time: datetime) -> List[LogEntry]:
        """
        Collect logs from Android device via ADB (logcat).
        
        Placeholder - will be implemented in TASK-012
        """
        # TODO: Implement in TASK-012
        return []
