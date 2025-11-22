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
from datetime import datetime, timezone
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
        
        # Timezone handling: 'utc', 'local', or timezone name (e.g. 'US/Pacific')
        # Default: assume logs are in local timezone unless specified
        self.log_timezone = config.get('log_timezone', 'local')
        
        # Anonymization settings
        anonymize_config = config.get('anonymize', {})
        self.anonymize_enabled = anonymize_config.get('enabled', True)
        self.anonymize_patterns = anonymize_config.get('patterns', [
            'ip_addresses', 'home_directories', 'hostnames'
        ])
        
        self.mode = mode
        self.ssh_client = ssh_client
        self.adb_device = adb_device
        self.adb_timezone_offset = None  # Cache for ADB device timezone offset
        
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
            start_time: Start of monitoring period (timezone-aware or naive)
            end_time: End of monitoring period (timezone-aware or naive)
        
        Returns:
            List of LogEntry objects matching filters and time range
        
        Note:
            If start_time/end_time are naive (no timezone), they are assumed
            to be in local timezone and converted to UTC for comparison.
        """
        if not self.enabled:
            print(f"⚠️  LogMonitor disabled in config")
            return []
        
        # Ensure start/end times are timezone-aware (UTC)
        if start_time.tzinfo is None:
            # Naive datetime - assume local time, convert to UTC
            start_time = start_time.replace(tzinfo=timezone.utc).astimezone()
            start_time = start_time.astimezone(timezone.utc)
        else:
            # Already has timezone, normalize to UTC
            start_time = start_time.astimezone(timezone.utc)
        
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc).astimezone()
            end_time = end_time.astimezone(timezone.utc)
        else:
            end_time = end_time.astimezone(timezone.utc)
        
        all_entries = []
        
        # ADB mode doesn't use sources (it reads from logcat)
        if self.mode == 'adb':
            entries = self._collect_adb_logs(start_time, end_time)
            all_entries.extend(entries)
        else:
            # Local and SSH modes iterate over sources
            for source in self.sources:
                if self.mode == 'local':
                    entries = self._collect_local_logs(source, start_time, end_time)
                elif self.mode == 'ssh':
                    entries = self._collect_ssh_logs(source, start_time, end_time)
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
        Returns timezone-aware datetime normalized to UTC.
        
        Args:
            line: Raw log line
        
        Returns:
            Timezone-aware datetime in UTC, or None if no timestamp found
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
                    
                    dt = datetime.strptime(timestamp_str, fmt)
                    
                    # Make timezone-aware if naive (no timezone info in log)
                    if dt.tzinfo is None:
                        if self.log_timezone == 'utc':
                            dt = dt.replace(tzinfo=timezone.utc)
                        elif self.log_timezone == 'local':
                            # Assume local timezone, convert to UTC
                            import time
                            local_offset = time.timezone if time.daylight == 0 else time.altzone
                            dt = dt.replace(tzinfo=timezone.utc).astimezone()
                            dt = dt.astimezone(timezone.utc)
                        else:
                            # Custom timezone specified
                            # For now, treat as UTC (would need pytz for full support)
                            dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        # Already has timezone, convert to UTC
                        dt = dt.astimezone(timezone.utc)
                    
                    return dt
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
    
    def _normalize_datetime(self, dt: datetime) -> datetime:
        """
        Normalize datetime to timezone-aware UTC for comparisons.
        
        Args:
            dt: Datetime to normalize (naive or aware)
        
        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            # Naive - assume local time, convert to UTC
            dt = dt.replace(tzinfo=timezone.utc).astimezone()
            dt = dt.astimezone(timezone.utc)
        else:
            # Already aware, convert to UTC
            dt = dt.astimezone(timezone.utc)
        return dt
    
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
            start_time: Start of monitoring period (naive or aware)
            end_time: End of monitoring period (naive or aware)
        
        Returns:
            List of LogEntry objects from the file
        """
        import gzip
        from pathlib import Path
        
        entries = []
        file_path_obj = Path(file_path)
        
        # Normalize input times to UTC for comparison
        start_time_utc = self._normalize_datetime(start_time)
        end_time_utc = self._normalize_datetime(end_time)
        
        # Determine if file is gzipped
        is_gzipped = file_path_obj.suffix == '.gz'
        
        # Open file with appropriate handler
        open_func = gzip.open if is_gzipped else open
        
        # Track if we've entered and exited the time window
        in_time_window = False
        lines_after_window = 0
        max_lines_after_window = 100  # Stop after this many lines past end_time
        
        try:
            with open_func(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
                # Stream file line by line to avoid loading entire file
                for line in f:
                    line = line.rstrip('\n')
                    
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # Parse the line to get timestamp
                    entry = self._parse_log_line(line, str(file_path_obj))
                    if not entry:
                        continue
                    
                    # Early termination: if we have a timestamp and we've gone far past end_time
                    if entry.timestamp:
                        # Normalize entry timestamp for comparison
                        entry_time_utc = self._normalize_datetime(entry.timestamp)
                        
                        if entry_time_utc > end_time_utc:
                            lines_after_window += 1
                            # If we've seen many lines past our window, stop reading
                            # (assumes logs are chronologically ordered)
                            if in_time_window and lines_after_window > max_lines_after_window:
                                break
                            continue
                        elif entry_time_utc < start_time_utc:
                            # Haven't reached our window yet
                            continue
                        else:
                            # We're in the time window
                            in_time_window = True
                            lines_after_window = 0
                    
                    # Check keyword filtering (only for entries in time range)
                    if not self._matches_keywords(line):
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
        
        Uses journalctl if available, otherwise falls back to cat.
        
        Args:
            source: Path to log file on remote system
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects from remote logs
        """
        if not self.ssh_client:
            return []
        
        entries = []
        
        try:
            # Check if journalctl is available
            stdin, stdout, stderr = self.ssh_client.exec_command('which journalctl')
            has_journalctl = stdout.read().decode().strip() != ''
            
            if has_journalctl and source in ['/var/log/syslog', '/var/log/messages', 'systemd']:
                # Use journalctl for systemd logs
                entries = self._collect_ssh_journalctl(start_time, end_time)
            else:
                # Use cat for traditional log files
                entries = self._collect_ssh_cat(source, start_time, end_time)
        
        except Exception as e:
            # Log error but don't crash
            pass
        
        return entries
    
    def _collect_ssh_journalctl(self, start_time: datetime, 
                                end_time: datetime) -> List[LogEntry]:
        """
        Collect logs using journalctl on remote system.
        
        Args:
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects from journalctl
        """
        entries = []
        
        # Format timestamps for journalctl
        since = start_time.strftime('%Y-%m-%d %H:%M:%S')
        until = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Build journalctl command
        cmd = f'journalctl --since "{since}" --until "{until}" --no-pager -n {self.max_lines}'
        
        # Add keyword filtering if configured
        if self.keywords:
            grep_pattern = '|'.join(self.keywords)
            cmd += f' | grep -iE "{grep_pattern}"'
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            output = stdout.read().decode('utf-8', errors='ignore')
            
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                
                # Parse journalctl line
                entry = self._parse_log_line(line, 'journalctl')
                if entry:
                    entries.append(entry)
                    
                if len(entries) >= self.max_lines:
                    break
        
        except Exception:
            pass
        
        return entries
    
    def _collect_ssh_cat(self, source: str,
                        start_time: datetime,
                        end_time: datetime) -> List[LogEntry]:
        """
        Collect logs using cat on remote system.
        
        Uses grep with time-based filtering when possible,
        otherwise uses a combination of head/tail heuristics.
        
        Args:
            source: Path to log file on remote system
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects from remote file
        """
        entries = []
        
        # Try to use grep with date filtering for efficiency
        # This works if timestamps are in a predictable format
        start_date_str = start_time.strftime('%Y-%m-%d')
        start_hour = start_time.strftime('%H:%M')
        
        # Build a grep command to filter by date first, then process
        # This is more efficient than transferring entire file
        # Example: grep -E "2025-11-21 (13:[23-27]|14:)" /var/log/syslog
        cmd = f'grep -E "{start_date_str}" {source} | tail -n {self.max_lines * 5}'
        
        # Try with sudo if normal grep fails
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            error_msg = stderr.read().decode()
            
            if 'Permission denied' in error_msg:
                # Retry with sudo
                cmd = f'sudo grep -E "{start_date_str}" {source} | tail -n {self.max_lines * 5}'
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                error_msg = stderr.read().decode()
            
            # If grep found nothing, fall back to tail
            output = stdout.read().decode('utf-8', errors='ignore')
            
            if not output or len(output.strip()) == 0:
                # Grep found nothing, use tail as last resort
                # This means the time period might not be in the log file
                cmd = f'tail -n {self.max_lines} {source}'
                if 'Permission denied' in error_msg:
                    cmd = f'sudo tail -n {self.max_lines} {source}'
                
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                output = stdout.read().decode('utf-8', errors='ignore')
            
            # Process the output
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                
                # Parse the line to get timestamp
                entry = self._parse_log_line(line, source)
                if not entry:
                    continue
                
                # Filter by time range
                if entry.timestamp:
                    entry_time_utc = self._normalize_datetime(entry.timestamp)
                    start_time_utc = self._normalize_datetime(start_time)
                    end_time_utc = self._normalize_datetime(end_time)
                    
                    if entry_time_utc < start_time_utc:
                        continue
                    if entry_time_utc > end_time_utc:
                        continue
                
                # Check keyword filtering
                if not self._matches_keywords(line):
                    continue
                
                entries.append(entry)
                
                if len(entries) >= self.max_lines:
                    break
            
        except Exception:
            pass
        
        return entries
    
    def _collect_adb_logs(self, start_time: datetime,
                         end_time: datetime) -> List[LogEntry]:
        """
        Collect logs from Android device via ADB (logcat).
        
        Args:
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects from Android logcat
        """
        if not self.adb_device:
            return []
        
        entries = []
        
        try:
            # Get device timezone offset if not already cached
            if self.adb_timezone_offset is None:
                try:
                    tz_res = subprocess.run(
                        ['adb', '-s', self.adb_device, 'shell', 'date', '+%z'],
                        capture_output=True, text=True, timeout=5
                    )
                    if tz_res.returncode == 0:
                        # Parse +HHMM or -HHMM
                        tz_str = tz_res.stdout.strip()
                        if re.match(r'^[+-]\d{4}$', tz_str):
                            hours = int(tz_str[0:3])
                            minutes = int(tz_str[3:5])
                            # Adjust sign for minutes
                            if hours < 0:
                                minutes = -minutes
                            from datetime import timedelta
                            self.adb_timezone_offset = timedelta(hours=hours, minutes=minutes)
                except Exception:
                    pass

            # Adjust start_time to device local time for -T argument
            # start_time is UTC (ensured by collect_logs)
            device_start_time = start_time
            if self.adb_timezone_offset:
                device_start_time = start_time + self.adb_timezone_offset

            # Use -T to specify start time (format: 'MM-DD HH:MM:SS.mmm')
            # This ensures we get logs from the monitoring period, not just last N lines
            # -d dumps and exits (non-blocking)
            # -v time shows timestamps
            cmd = ['logcat', '-d', '-v', 'time']
            
            # Use -T to filter from start_time (Device Local Time)
            # Format: MM-DD HH:MM:SS.mmm
            time_str = device_start_time.strftime('%m-%d %H:%M:%S.000')
            cmd.extend(['-T', time_str])
            
            # Add keyword filtering
            if self.keywords:
                # Use grep filter in logcat
                grep_pattern = '|'.join(self.keywords)
                cmd.extend(['-e', grep_pattern])
            
            # Build adb command with device selector
            adb_cmd = ['adb', '-s', self.adb_device] + cmd
            
            result = subprocess.run(
                adb_cmd,
                capture_output=True,
                text=True,
                timeout=30  # Increased timeout for potentially large dumps
            )
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse Android logcat line
                    entry = self._parse_android_logcat(line)
                    if not entry:
                        continue
                    
                    # Filter by end time (start time already filtered by -T)
                    if entry.timestamp:
                        entry_time_utc = self._normalize_datetime(entry.timestamp)
                        end_time_utc = self._normalize_datetime(end_time)
                        if entry_time_utc > end_time_utc:
                            continue
                    
                    entries.append(entry)
                    
                    # Respect max_lines limit
                    if len(entries) >= self.max_lines:
                        break
        
        except Exception:
            pass
        
        return entries
    
    def _parse_android_logcat(self, line: str) -> Optional[LogEntry]:
        """
        Parse Android logcat line.
        
        Format: MM-DD HH:MM:SS.mmm LEVEL/TAG (PID): message
        Example: 11-21 15:30:45.123 I/ActivityManager (1234): Starting activity
        
        Args:
            line: Raw logcat line
        
        Returns:
            LogEntry object or None if parsing fails
        """
        import re
        
        # Skip separator lines
        if line.startswith('-----'):
            return None
        
        # Logcat time format pattern for -v time output
        # MM-DD HH:MM:SS.mmm LEVEL/TAG (PID): message
        # Note: TAG can contain spaces, so we use non-greedy match until the PID part
        pattern = re.compile(
            r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+'  # timestamp
            r'([VDIWEF])/'  # level/
            r'(.*?)\s*'     # TAG (non-greedy match until PID)
            r'\(\s*(\d+)\):\s*'  # (PID):
            r'(.*)$'  # message
        )
        
        match = pattern.match(line)
        if not match:
            return None
        
        timestamp_str, level_char, tag, pid_str, message = match.groups()
        
        # Parse timestamp (add current year since logcat doesn't include it)
        try:
            current_year = datetime.now().year
            timestamp_str_with_year = f"{current_year}-{timestamp_str}"
            timestamp = datetime.strptime(timestamp_str_with_year, '%Y-%m-%d %H:%M:%S.%f')
            
            # If we know the device timezone, convert this local timestamp to UTC
            if self.adb_timezone_offset:
                # timestamp is naive (Device Local Time)
                # We need to subtract the offset to get UTC
                # UTC = Local - Offset
                timestamp = timestamp - self.adb_timezone_offset
                # Mark as UTC
                timestamp = timestamp.replace(tzinfo=timezone.utc)
                
        except ValueError:
            timestamp = datetime.now()
        
        # Map Android log levels to standard severity
        severity_map = {
            'V': 'debug',    # Verbose
            'D': 'debug',    # Debug
            'I': 'info',     # Info
            'W': 'warning',  # Warning
            'E': 'error',    # Error
            'F': 'critical'  # Fatal
        }
        severity = severity_map.get(level_char, 'info')
        
        # Extract PIDs
        pids = [int(pid_str)]
        
        # Anonymize if enabled
        final_message = message
        if self.anonymize_enabled:
            final_message = self._anonymize_text(message)
        
        return LogEntry(
            timestamp=timestamp,
            source_file='logcat',
            severity=severity,
            facility=tag,
            message=final_message,
            raw_line=line,
            process_context=pids
        )
