# System Monitor Tool v1.1 - Technical Design Document

## Document Information

**Version**: 1.0  
**Date**: 2025-11-21  
**Author**: TsaiGaggery  
**Status**: Draft

## Architecture Overview

### Current System Architecture
```
monitor-tool/
├── src/
│   ├── monitors/           # Data collection modules
│   │   ├── cpu_monitor.py
│   │   ├── gpu_monitor.py
│   │   ├── npu_monitor.py
│   │   ├── memory_monitor.py
│   │   ├── network_monitor.py
│   │   └── disk_monitor.py
│   ├── controllers/
│   │   └── frequency_controller.py
│   ├── ui/
│   │   ├── main_window.py
│   │   └── widgets/
│   ├── storage/
│   │   ├── data_logger.py
│   │   └── data_exporter.py
│   └── main.py
├── config/
│   └── default.yaml
└── tests/
```

### Enhanced Architecture (v1.1)
```
monitor-tool/
├── src/
│   ├── monitors/
│   │   ├── [existing monitors...]
│   │   ├── process_monitor.py      [NEW - Feature 1]
│   │   └── log_monitor.py          [NEW - Feature 2]
│   ├── ai/                          [NEW - Feature 3]
│   │   ├── __init__.py
│   │   ├── report_analyzer.py
│   │   ├── insight_generator.py
│   │   └── rule_based_analyzer.py
│   ├── ui/
│   │   └── widgets/
│   │       └── process_table_widget.py  [NEW]
│   └── storage/
│       ├── data_logger.py          [MODIFIED]
│       └── data_exporter.py        [MODIFIED]
├── config/
│   └── default.yaml                [MODIFIED]
└── tests/
    ├── test_process_monitor.py     [NEW]
    ├── test_log_monitor.py         [NEW]
    └── test_ai_insights.py         [NEW]
```

---

## Feature 1: Top 5 Process Monitoring

### 1.1 Configuration Schema

**File**: `config/default.yaml`

```yaml
# Existing configuration...

# New Tier 2 configuration
tier2:
  process_monitoring:
    enabled: true
    update_interval: 1000  # milliseconds
    process_count: 5
    sort_by: cpu  # Options: cpu, memory, combined
    include_cmdline: true
    cmdline_max_length: 50
    thresholds:
      cpu_warning: 50.0    # percent
      cpu_critical: 80.0
      memory_warning: 1073741824  # 1GB in bytes
      memory_critical: 2147483648  # 2GB
```

### 1.2 Data Model

**Database Schema Addition**:

```sql
-- New table for process monitoring data
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
    create_time REAL,
    FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
);

CREATE INDEX IF NOT EXISTS idx_process_timestamp 
    ON process_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_process_session 
    ON process_data(session_id);
CREATE INDEX IF NOT EXISTS idx_process_cpu 
    ON process_data(cpu_percent DESC);
```

### 1.3 ProcessMonitor Class Design

**File**: `src/monitors/process_monitor.py`

```python
"""
Process monitoring module for tracking top CPU/memory consuming processes.
"""

import psutil
import time
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class ProcessInfo:
    """Data class for process information."""
    pid: int
    name: str
    cpu_percent: float
    memory_rss: int
    memory_vms: int
    cmdline: str
    status: str
    num_threads: int
    create_time: float
    timestamp: datetime

class ProcessMonitor:
    """
    Monitor top processes by CPU and memory usage.
    
    Features:
    - Real-time process tracking
    - Configurable number of processes
    - Multiple sort modes (CPU, memory, combined)
    - Thread-safe operation
    - Mode support: local, SSH, ADB
    """
    
    def __init__(self, config: dict, mode: str = 'local', 
                 ssh_client=None, adb_device=None):
        """
        Initialize ProcessMonitor.
        
        Args:
            config: Configuration dictionary from tier2.process_monitoring
            mode: Operation mode ('local', 'ssh', 'adb')
            ssh_client: SSH client for remote monitoring (optional)
            adb_device: ADB device for Android monitoring (optional)
        """
        self.enabled = config.get('enabled', True)
        self.update_interval = config.get('update_interval', 1000) / 1000.0
        self.process_count = config.get('process_count', 5)
        self.sort_by = config.get('sort_by', 'cpu')
        self.cmdline_max_length = config.get('cmdline_max_length', 50)
        self.thresholds = config.get('thresholds', {})
        
        self.mode = mode
        self.ssh_client = ssh_client
        self.adb_device = adb_device
        
        self._last_update = 0
        self._process_cache: List[ProcessInfo] = []
    
    def get_top_processes(self) -> List[ProcessInfo]:
        """
        Get top processes sorted by configured metric.
        
        Returns:
            List of ProcessInfo objects for top processes
        """
        current_time = time.time()
        if current_time - self._last_update < self.update_interval:
            return self._process_cache
        
        if self.mode == 'local':
            processes = self._get_local_processes()
        elif self.mode == 'ssh':
            processes = self._get_ssh_processes()
        elif self.mode == 'adb':
            processes = self._get_adb_processes()
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")
        
        # Sort and filter
        processes = self._sort_processes(processes)[:self.process_count]
        
        self._process_cache = processes
        self._last_update = current_time
        
        return processes
    
    def _get_local_processes(self) -> List[ProcessInfo]:
        """Get processes from local system using psutil."""
        processes = []
        now = datetime.now()
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 
                                         'memory_info', 'cmdline', 
                                         'status', 'num_threads', 'create_time']):
            try:
                info = proc.info
                cmdline = ' '.join(info['cmdline'] or [])
                if len(cmdline) > self.cmdline_max_length:
                    cmdline = cmdline[:self.cmdline_max_length] + '...'
                
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    cpu_percent=info['cpu_percent'] or 0.0,
                    memory_rss=info['memory_info'].rss,
                    memory_vms=info['memory_info'].vms,
                    cmdline=cmdline,
                    status=info['status'],
                    num_threads=info['num_threads'] or 0,
                    create_time=info['create_time'] or 0.0,
                    timestamp=now
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return processes
    
    def _get_ssh_processes(self) -> List[ProcessInfo]:
        """Get processes from remote Linux system via SSH."""
        # Command to get process info (pid, name, cpu%, mem, cmd)
        cmd = """ps aux --sort=-%cpu | head -n 20 | awk 'NR>1 {
            printf "%s|%s|%s|%s|", $2, $11, $3, $6;
            for(i=11;i<=NF;i++) printf "%s ", $i;
            printf "\\n"
        }'"""
        
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
        output = stdout.read().decode('utf-8')
        
        processes = []
        now = datetime.now()
        
        for line in output.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            if len(parts) < 4:
                continue
            
            try:
                pid = int(parts[0])
                name = parts[1]
                cpu_percent = float(parts[2])
                memory_kb = int(parts[3])
                cmdline = parts[4].strip() if len(parts) > 4 else ''
                
                if len(cmdline) > self.cmdline_max_length:
                    cmdline = cmdline[:self.cmdline_max_length] + '...'
                
                processes.append(ProcessInfo(
                    pid=pid,
                    name=name,
                    cpu_percent=cpu_percent,
                    memory_rss=memory_kb * 1024,  # Convert to bytes
                    memory_vms=0,  # Not available via ps
                    cmdline=cmdline,
                    status='unknown',
                    num_threads=0,
                    create_time=0.0,
                    timestamp=now
                ))
            except (ValueError, IndexError):
                continue
        
        return processes
    
    def _get_adb_processes(self) -> List[ProcessInfo]:
        """Get processes from Android device via ADB."""
        # Use 'top -n 1 -b' for batch mode output
        result = self.adb_device.shell("top -n 1 -b | head -n 20")
        
        processes = []
        now = datetime.now()
        
        # Parse Android top output
        # Format varies by Android version, basic parsing
        for line in result.split('\n'):
            if not line.strip() or 'PID' in line:
                continue
            
            parts = line.split()
            if len(parts) < 9:
                continue
            
            try:
                pid = int(parts[0])
                cpu_percent = float(parts[2].rstrip('%'))
                memory_kb = int(parts[5].rstrip('K'))
                name = parts[8]
                
                processes.append(ProcessInfo(
                    pid=pid,
                    name=name,
                    cpu_percent=cpu_percent,
                    memory_rss=memory_kb * 1024,
                    memory_vms=0,
                    cmdline=name,
                    status='unknown',
                    num_threads=0,
                    create_time=0.0,
                    timestamp=now
                ))
            except (ValueError, IndexError):
                continue
        
        return processes
    
    def _sort_processes(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Sort processes by configured metric."""
        if self.sort_by == 'cpu':
            return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)
        elif self.sort_by == 'memory':
            return sorted(processes, key=lambda p: p.memory_rss, reverse=True)
        elif self.sort_by == 'combined':
            # Normalize and combine both metrics
            if not processes:
                return []
            max_cpu = max(p.cpu_percent for p in processes) or 1.0
            max_mem = max(p.memory_rss for p in processes) or 1.0
            return sorted(processes, 
                         key=lambda p: (p.cpu_percent/max_cpu + p.memory_rss/max_mem),
                         reverse=True)
        else:
            return processes
    
    def get_severity(self, process: ProcessInfo) -> str:
        """
        Determine severity level based on thresholds.
        
        Returns:
            'critical', 'warning', or 'normal'
        """
        cpu_warning = self.thresholds.get('cpu_warning', 50.0)
        cpu_critical = self.thresholds.get('cpu_critical', 80.0)
        mem_warning = self.thresholds.get('memory_warning', 1073741824)
        mem_critical = self.thresholds.get('memory_critical', 2147483648)
        
        if (process.cpu_percent >= cpu_critical or 
            process.memory_rss >= mem_critical):
            return 'critical'
        elif (process.cpu_percent >= cpu_warning or 
              process.memory_rss >= mem_warning):
            return 'warning'
        else:
            return 'normal'
```

### 1.4 UI Integration

**File**: `src/ui/widgets/process_table_widget.py`

```python
"""
Widget for displaying top processes in a table.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                              QTableWidgetItem, QHeaderView, QLabel)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

class ProcessTableWidget(QWidget):
    """Table widget showing top CPU/memory consuming processes."""
    
    def __init__(self, process_monitor, parent=None):
        super().__init__(parent)
        self.process_monitor = process_monitor
        self.setup_ui()
        self.setup_timer()
    
    def setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Top 5 CPU-Intensive Processes")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['PID', 'Process', 'CPU %', 'Memory'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
    
    def setup_timer(self):
        """Setup update timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        interval = self.process_monitor.update_interval * 1000  # Convert to ms
        self.timer.start(int(interval))
    
    def update_data(self):
        """Update table with latest process data."""
        if not self.process_monitor.enabled:
            return
        
        processes = self.process_monitor.get_top_processes()
        self.table.setRowCount(len(processes))
        
        for row, proc in enumerate(processes):
            # PID
            self.table.setItem(row, 0, QTableWidgetItem(str(proc.pid)))
            
            # Process name (with tooltip showing full command)
            name_item = QTableWidgetItem(proc.name)
            name_item.setToolTip(proc.cmdline)
            self.table.setItem(row, 1, name_item)
            
            # CPU %
            cpu_item = QTableWidgetItem(f"{proc.cpu_percent:.1f}%")
            severity = self.process_monitor.get_severity(proc)
            cpu_item.setBackground(self._get_severity_color(severity))
            self.table.setItem(row, 2, cpu_item)
            
            # Memory
            mem_mb = proc.memory_rss / (1024 * 1024)
            mem_item = QTableWidgetItem(f"{mem_mb:.1f} MB")
            self.table.setItem(row, 3, mem_item)
    
    def _get_severity_color(self, severity: str) -> QColor:
        """Get color for severity level."""
        if severity == 'critical':
            return QColor(255, 200, 200)  # Light red
        elif severity == 'warning':
            return QColor(255, 230, 200)  # Light orange
        else:
            return QColor(255, 255, 255)  # White
```

**Integration into Overview Tab** (`src/ui/main_window.py`):

```python
# In OverviewTab.__init__()
if config.get('tier2', {}).get('process_monitoring', {}).get('enabled', False):
    self.process_widget = ProcessTableWidget(self.process_monitor)
    layout.addWidget(self.process_widget)
```

### 1.5 Data Logging

**Modification to** `src/storage/data_logger.py`:

```python
def log_process_data(self, processes: List[ProcessInfo], session_id: str):
    """
    Log process monitoring data to database.
    
    Args:
        processes: List of ProcessInfo objects
        session_id: Current monitoring session ID
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    for proc in processes:
        cursor.execute('''
            INSERT INTO process_data 
            (timestamp, session_id, pid, name, cpu_percent, memory_rss, 
             memory_vms, cmdline, status, num_threads, create_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            proc.timestamp,
            session_id,
            proc.pid,
            proc.name,
            proc.cpu_percent,
            proc.memory_rss,
            proc.memory_vms,
            proc.cmdline,
            proc.status,
            proc.num_threads,
            proc.create_time
        ))
    
    conn.commit()
    conn.close()
```

---

## Feature 2: System Log Collection

### 2.1 Configuration Schema

```yaml
log_collection:
  enabled: false  # Disabled by default for privacy
  sources:
    - /var/log/syslog
    - /var/log/kern.log
    - /var/log/dmesg
    - /var/log/messages
  keywords:
    - error
    - warning
    - critical
    - fail
    - oom
    - killed
    - segfault
    - gpu
    - thermal
    - throttle
  max_log_lines: 1000
  include_context_lines: 2
  anonymize:
    enabled: true
    patterns:
      - type: ip_address
        replacement: "xxx.xxx.xxx.xxx"
      - type: home_dir
        replacement: "/home/USER"
      - type: hostname
        replacement: "<hostname>"
```

### 2.2 Data Model

```sql
-- Table for log entries
CREATE TABLE IF NOT EXISTS log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    source_file TEXT NOT NULL,
    severity TEXT,
    facility TEXT,
    message TEXT NOT NULL,
    raw_line TEXT,
    process_context TEXT,  -- JSON array of related PIDs
    FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
);

CREATE INDEX IF NOT EXISTS idx_log_timestamp 
    ON log_entries(timestamp);
CREATE INDEX IF NOT EXISTS idx_log_session 
    ON log_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_log_severity 
    ON log_entries(severity);

-- Table for process-log correlations
CREATE TABLE IF NOT EXISTS process_log_correlation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    log_entry_id INTEGER NOT NULL,
    correlation_type TEXT,  -- 'mention', 'pid_match', 'name_match'
    confidence REAL,  -- 0.0 to 1.0
    FOREIGN KEY (process_id) REFERENCES process_data(id),
    FOREIGN KEY (log_entry_id) REFERENCES log_entries(id)
);
```

### 2.3 LogMonitor Class Design

**File**: `src/monitors/log_monitor.py`

```python
"""
System log monitoring and collection module.
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
    """Data class for log entry."""
    timestamp: datetime
    source_file: str
    severity: str
    facility: str
    message: str
    raw_line: str
    process_context: List[int]  # Related PIDs

class LogMonitor:
    """
    Monitor and collect system logs for a time period.
    
    Features:
    - Keyword-based filtering
    - Time-range extraction
    - Log rotation handling
    - Compression support (gzip)
    - Anonymization
    - Process correlation
    """
    
    # Log severity patterns
    SEVERITY_PATTERNS = {
        'critical': r'\b(critical|crit|fatal)\b',
        'error': r'\b(error|err|failed|failure)\b',
        'warning': r'\b(warning|warn)\b',
        'info': r'\b(info|information)\b',
        'debug': r'\b(debug)\b'
    }
    
    # PID extraction pattern
    PID_PATTERN = re.compile(r'\[(\d+)\]|pid[=:\s]+(\d+)|\((\d+)\)', re.IGNORECASE)
    
    def __init__(self, config: dict, mode: str = 'local',
                 ssh_client=None, adb_device=None):
        """Initialize LogMonitor."""
        self.enabled = config.get('enabled', False)
        self.sources = config.get('sources', [])
        self.keywords = [kw.lower() for kw in config.get('keywords', [])]
        self.max_lines = config.get('max_log_lines', 1000)
        self.context_lines = config.get('include_context_lines', 2)
        self.anonymize_enabled = config.get('anonymize', {}).get('enabled', True)
        self.anonymize_patterns = config.get('anonymize', {}).get('patterns', [])
        
        self.mode = mode
        self.ssh_client = ssh_client
        self.adb_device = adb_device
    
    def collect_logs(self, start_time: datetime, 
                    end_time: datetime) -> List[LogEntry]:
        """
        Collect logs for specified time period.
        
        Args:
            start_time: Start of monitoring period
            end_time: End of monitoring period
        
        Returns:
            List of LogEntry objects
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
    
    def _collect_local_logs(self, source: str, 
                           start_time: datetime,
                           end_time: datetime) -> List[LogEntry]:
        """Collect logs from local file system."""
        entries = []
        
        try:
            # Check if file exists
            if not Path(source).exists():
                return entries
            
            # Handle rotated logs
            log_files = self._find_rotated_logs(source)
            
            for log_file in log_files:
                entries.extend(
                    self._read_log_file(log_file, start_time, end_time)
                )
        
        except PermissionError:
            # Try with sudo
            try:
                entries = self._read_log_with_sudo(source, start_time, end_time)
            except Exception:
                pass  # Graceful degradation
        
        return entries
    
    def _find_rotated_logs(self, base_path: str) -> List[Path]:
        """Find rotated log files (e.g., syslog, syslog.1, syslog.2.gz)."""
        base = Path(base_path)
        if not base.exists():
            return []
        
        files = [base]
        
        # Look for numbered rotations
        for i in range(1, 10):
            rotated = Path(f"{base_path}.{i}")
            if rotated.exists():
                files.append(rotated)
            
            # Check for compressed versions
            compressed = Path(f"{base_path}.{i}.gz")
            if compressed.exists():
                files.append(compressed)
        
        return files
    
    def _read_log_file(self, file_path: Path,
                      start_time: datetime,
                      end_time: datetime) -> List[LogEntry]:
        """Read and parse a single log file."""
        entries = []
        
        # Determine if file is compressed
        if file_path.suffix == '.gz':
            opener = gzip.open
        else:
            opener = open
        
        try:
            with opener(file_path, 'rt', errors='ignore') as f:
                context_buffer = []
                
                for line in f:
                    # Parse timestamp
                    ts = self._parse_log_timestamp(line)
                    if not ts or ts < start_time or ts > end_time:
                        continue
                    
                    # Check keywords
                    if not self._matches_keywords(line):
                        context_buffer.append(line)
                        if len(context_buffer) > self.context_lines:
                            context_buffer.pop(0)
                        continue
                    
                    # Parse log entry
                    entry = self._parse_log_line(line, str(file_path))
                    
                    # Add context lines
                    if entry:
                        # Anonymize if enabled
                        if self.anonymize_enabled:
                            entry = self._anonymize_entry(entry)
                        
                        entries.append(entry)
                        context_buffer = []
                    
                    if len(entries) >= self.max_lines:
                        break
        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        
        return entries
    
    def _parse_log_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from log line."""
        # Support common log timestamp formats
        patterns = [
            # ISO 8601: 2025-11-21T14:23:45.123456
            (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)', 
             '%Y-%m-%dT%H:%M:%S'),
            
            # Syslog: Nov 21 14:23:45
            (r'([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',
             '%b %d %H:%M:%S'),
            
            # Timestamp with milliseconds: 2025-11-21 14:23:45.123
            (r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
             '%Y-%m-%d %H:%M:%S'),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    ts_str = match.group(1)
                    # Remove microseconds if present
                    if '.' in ts_str:
                        ts_str = ts_str[:ts_str.index('.')+4]
                    return datetime.strptime(ts_str, fmt)
                except ValueError:
                    continue
        
        return None
    
    def _matches_keywords(self, line: str) -> bool:
        """Check if line contains any of the configured keywords."""
        if not self.keywords:
            return True  # No filtering
        
        line_lower = line.lower()
        return any(kw in line_lower for kw in self.keywords)
    
    def _parse_log_line(self, line: str, source: str) -> Optional[LogEntry]:
        """Parse a log line into LogEntry."""
        timestamp = self._parse_log_timestamp(line)
        if not timestamp:
            return None
        
        # Detect severity
        severity = 'info'
        for sev, pattern in self.SEVERITY_PATTERNS.items():
            if re.search(pattern, line, re.IGNORECASE):
                severity = sev
                break
        
        # Extract PIDs
        pids = []
        for match in self.PID_PATTERN.finditer(line):
            for group in match.groups():
                if group:
                    try:
                        pids.append(int(group))
                    except ValueError:
                        pass
        
        return LogEntry(
            timestamp=timestamp,
            source_file=source,
            severity=severity,
            facility='system',  # Could be enhanced
            message=line.strip(),
            raw_line=line,
            process_context=pids
        )
    
    def _anonymize_entry(self, entry: LogEntry) -> LogEntry:
        """Anonymize sensitive data in log entry."""
        message = entry.message
        
        for pattern_config in self.anonymize_patterns:
            pattern_type = pattern_config.get('type')
            replacement = pattern_config.get('replacement')
            
            if pattern_type == 'ip_address':
                message = re.sub(
                    r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
                    replacement,
                    message
                )
            elif pattern_type == 'home_dir':
                message = re.sub(
                    r'/home/[\w-]+',
                    replacement,
                    message
                )
            elif pattern_type == 'hostname':
                message = re.sub(
                    r'\b[\w-]+\.[\w.-]+\b',
                    replacement,
                    message
                )
        
        entry.message = message
        return entry
    
    def _collect_ssh_logs(self, source: str,
                         start_time: datetime,
                         end_time: datetime) -> List[LogEntry]:
        """Collect logs from remote system via SSH."""
        # Use journalctl for systemd systems or cat for traditional logs
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Try journalctl first
        cmd = f'''
        if command -v journalctl >/dev/null 2>&1; then
            journalctl --since "{start_str}" --until "{end_str}" --no-pager
        else
            sudo cat {source} | awk '$0 >= "{start_str}" && $0 <= "{end_str}"'
        fi
        '''
        
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
        output = stdout.read().decode('utf-8', errors='ignore')
        
        entries = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            entry = self._parse_log_line(line, f"remote:{source}")
            if entry:
                entries.append(entry)
        
        return entries
    
    def _collect_adb_logs(self, start_time: datetime,
                         end_time: datetime) -> List[LogEntry]:
        """Collect logs from Android device via ADB."""
        # Use logcat with time filter
        start_str = start_time.strftime('%m-%d %H:%M:%S.000')
        
        cmd = f'logcat -t "{start_str}" -d'
        result = self.adb_device.shell(cmd)
        
        entries = []
        for line in result.split('\n'):
            if not line.strip():
                continue
            # Parse Android logcat format
            # Format: MM-DD HH:MM:SS.mmm PID TID LEVEL TAG: message
            entry = self._parse_android_logcat(line)
            if entry:
                entries.append(entry)
        
        return entries
    
    def _parse_android_logcat(self, line: str) -> Optional[LogEntry]:
        """Parse Android logcat line."""
        # Basic logcat parsing
        # Format: 11-21 14:23:45.123 1234 5678 E Tag: message
        pattern = r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+([\w-]+):\s+(.*)'
        match = re.match(pattern, line)
        
        if not match:
            return None
        
        ts_str, pid, tid, level, tag, message = match.groups()
        
        # Parse timestamp (add year)
        current_year = datetime.now().year
        timestamp = datetime.strptime(
            f"{current_year}-{ts_str}",
            '%Y-%m-%d %H:%M:%S.%f'
        )
        
        severity_map = {
            'V': 'debug', 'D': 'debug',
            'I': 'info',
            'W': 'warning',
            'E': 'error',
            'F': 'critical'
        }
        
        return LogEntry(
            timestamp=timestamp,
            source_file='logcat',
            severity=severity_map.get(level, 'info'),
            facility=tag,
            message=message,
            raw_line=line,
            process_context=[int(pid)]
        )
    
    def correlate_with_processes(self, 
                                 log_entries: List[LogEntry],
                                 process_data: List) -> Dict:
        """
        Correlate log entries with process data.
        
        Returns:
            Dictionary mapping PIDs to related log entries
        """
        correlations = {}
        
        for entry in log_entries:
            for pid in entry.process_context:
                if pid not in correlations:
                    correlations[pid] = []
                correlations[pid].append(entry)
        
        return correlations
```

### 2.4 Export Integration

**Modification to** `src/storage/data_exporter.py`:

```python
def export_html(self, session_id: str, output_path: str, 
                include_logs: bool = False):
    """
    Export monitoring data to HTML report.
    
    Args:
        session_id: Session ID to export
        output_path: Output HTML file path
        include_logs: Whether to include system logs
    """
    # Existing export logic...
    
    if include_logs:
        log_entries = self._get_log_entries(session_id)
        process_correlations = self._get_process_correlations(session_id)
        
        # Add log timeline to charts
        html_content += self._generate_log_timeline(log_entries)
        
        # Add detailed logs section
        html_content += self._generate_log_table(log_entries, process_correlations)
    
    # Write HTML file...

def _generate_log_timeline(self, log_entries: List) -> str:
    """Generate JavaScript for log event timeline overlay."""
    js_code = """
    <script>
    function addLogMarkers(chart, logData) {
        logData.forEach(function(log) {
            var color = getSeverityColor(log.severity);
            chart.addShape({
                type: 'line',
                x0: log.timestamp,
                x1: log.timestamp,
                y0: 0,
                y1: 1,
                yref: 'paper',
                line: {
                    color: color,
                    width: 2,
                    dash: 'dot'
                }
            });
        });
    }
    
    function getSeverityColor(severity) {
        var colors = {
            'critical': 'red',
            'error': 'orange',
            'warning': 'yellow',
            'info': 'blue',
            'debug': 'gray'
        };
        return colors[severity] || 'gray';
    }
    
    var logData = %s;
    addLogMarkers(cpuChart, logData);
    addLogMarkers(memoryChart, logData);
    </script>
    """ % json.dumps([{
        'timestamp': entry.timestamp.isoformat(),
        'severity': entry.severity,
        'message': entry.message[:100]
    } for entry in log_entries])
    
    return js_code

def _generate_log_table(self, log_entries: List, 
                       correlations: Dict) -> str:
    """Generate HTML table for detailed logs."""
    html = """
    <div class="log-section">
        <h2>System Events Log</h2>
        <input type="text" id="logSearch" placeholder="Search logs...">
        <select id="severityFilter">
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
        </select>
        <table id="logTable" class="log-table">
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Severity</th>
                    <th>Source</th>
                    <th>Message</th>
                    <th>Related Processes</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for entry in log_entries:
        severity_class = f"severity-{entry.severity}"
        related_procs = ", ".join(
            [str(pid) for pid in entry.process_context[:5]]
        )
        
        html += f"""
        <tr class="{severity_class}">
            <td>{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
            <td><span class="badge {severity_class}">{entry.severity}</span></td>
            <td>{entry.source_file}</td>
            <td>{entry.message[:200]}</td>
            <td>{related_procs}</td>
        </tr>
        """
    
    html += """
            </tbody>
        </table>
    </div>
    
    <script>
    // Filter functionality
    document.getElementById('logSearch').addEventListener('input', function(e) {
        filterLogs();
    });
    document.getElementById('severityFilter').addEventListener('change', function(e) {
        filterLogs();
    });
    
    function filterLogs() {
        var searchText = document.getElementById('logSearch').value.toLowerCase();
        var severity = document.getElementById('severityFilter').value;
        var rows = document.querySelectorAll('#logTable tbody tr');
        
        rows.forEach(function(row) {
            var message = row.cells[3].textContent.toLowerCase();
            var rowSeverity = row.classList[0].replace('severity-', '');
            
            var matchSearch = searchText === '' || message.includes(searchText);
            var matchSeverity = severity === '' || rowSeverity === severity;
            
            row.style.display = (matchSearch && matchSeverity) ? '' : 'none';
        });
    }
    </script>
    """
    
    return html
```

---

## Feature 3: AI-Powered Insights

### 3.1 Configuration Schema

```yaml
ai_insights:
  enabled: true
  provider: github_copilot  # Options: github_copilot, rule_based
  api_timeout: 30
  max_report_size: 5242880  # 5 MB
  
  # GitHub Copilot settings
  github_copilot:
    cli_command: gh copilot suggest  # or 'gh copilot explain'
    use_local_cli: true
  
  # Rule-based fallback thresholds
  thresholds:
    high_cpu: 80.0
    high_memory: 85.0
    high_disk_io: 100  # MB/s
    thermal_throttle_temp: 90  # Celsius
  
  # Insight sections to generate
  insight_sections:
    - performance_summary
    - bottleneck_analysis
    - recommendations
    - anomaly_detection
```

### 3.2 Module Architecture

```
src/ai/
├── __init__.py
├── report_analyzer.py      # Main analysis coordinator
├── insight_generator.py    # GitHub Copilot interface
└── rule_based_analyzer.py  # Fallback analyzer
```

### 3.3 ReportAnalyzer Class

**File**: `src/ai/report_analyzer.py`

```python
"""
Main coordinator for report analysis and insight generation.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class ReportSummary:
    """Summary of monitoring report for AI analysis."""
    hostname: str
    os_version: str
    duration_seconds: int
    start_time: datetime
    end_time: datetime
    
    # CPU metrics
    avg_cpu: float
    max_cpu: float
    cpu_cores: int
    
    # Memory metrics
    avg_memory: float
    max_memory: float
    total_memory_gb: float
    
    # GPU metrics (if available)
    gpu_present: bool
    gpu_model: str
    avg_gpu_usage: float
    max_gpu_usage: float
    
    # Network metrics
    total_upload_mb: float
    total_download_mb: float
    avg_upload_mbps: float
    avg_download_mbps: float
    
    # Disk metrics
    avg_read_mbps: float
    avg_write_mbps: float
    total_read_gb: float
    total_write_gb: float
    
    # Process data
    top_processes: List[Dict]
    
    # System events
    critical_events: int
    error_events: int
    warning_events: int
    event_samples: List[Dict]

class ReportAnalyzer:
    """
    Analyze monitoring reports and generate insights.
    """
    
    def __init__(self, config: dict):
        self.enabled = config.get('enabled', True)
        self.provider = config.get('provider', 'rule_based')
        self.timeout = config.get('api_timeout', 30)
        self.max_size = config.get('max_report_size', 5242880)
        self.sections = config.get('insight_sections', [])
        
        # Initialize providers
        from .insight_generator import InsightGenerator
        from .rule_based_analyzer import RuleBasedAnalyzer
        
        self.ai_generator = InsightGenerator(config.get('github_copilot', {}))
        self.rule_analyzer = RuleBasedAnalyzer(config.get('thresholds', {}))
    
    def analyze_report(self, session_id: str, 
                      db_path: str) -> Dict[str, str]:
        """
        Analyze a monitoring report and generate insights.
        
        Args:
            session_id: Session ID to analyze
            db_path: Path to SQLite database
        
        Returns:
            Dictionary with insight sections
        """
        # Extract report summary
        summary = self._extract_summary(session_id, db_path)
        
        # Generate insights based on provider
        if self.provider == 'github_copilot' and self.ai_generator.is_available():
            insights = self._generate_ai_insights(summary)
        else:
            insights = self._generate_rule_insights(summary)
        
        return insights
    
    def _extract_summary(self, session_id: str, 
                        db_path: str) -> ReportSummary:
        """Extract summary statistics from database."""
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get session time range
        cursor.execute('''
            SELECT MIN(timestamp), MAX(timestamp)
            FROM monitoring_data
            WHERE session_id = ?
        ''', (session_id,))
        start_time, end_time = cursor.fetchone()
        start_time = datetime.fromisoformat(start_time)
        end_time = datetime.fromisoformat(end_time)
        duration = (end_time - start_time).total_seconds()
        
        # CPU metrics
        cursor.execute('''
            SELECT AVG(cpu_usage), MAX(cpu_usage)
            FROM monitoring_data
            WHERE session_id = ?
        ''', (session_id,))
        avg_cpu, max_cpu = cursor.fetchone()
        
        # Memory metrics
        cursor.execute('''
            SELECT AVG(memory_percent), MAX(memory_percent), 
                   AVG(memory_total)
            FROM monitoring_data
            WHERE session_id = ?
        ''', (session_id,))
        avg_mem, max_mem, total_mem = cursor.fetchone()
        
        # GPU metrics (if available)
        cursor.execute('''
            SELECT AVG(gpu_usage), MAX(gpu_usage), gpu_name
            FROM monitoring_data
            WHERE session_id = ? AND gpu_usage IS NOT NULL
            LIMIT 1
        ''', (session_id,))
        gpu_row = cursor.fetchone()
        if gpu_row and gpu_row[0] is not None:
            avg_gpu, max_gpu, gpu_model = gpu_row
            gpu_present = True
        else:
            avg_gpu = max_gpu = 0
            gpu_model = 'N/A'
            gpu_present = False
        
        # Network metrics
        cursor.execute('''
            SELECT AVG(net_upload_speed), AVG(net_download_speed),
                   SUM(net_upload_speed), SUM(net_download_speed)
            FROM monitoring_data
            WHERE session_id = ?
        ''', (session_id,))
        avg_up, avg_down, total_up, total_down = cursor.fetchone()
        
        # Disk metrics
        cursor.execute('''
            SELECT AVG(disk_read_speed), AVG(disk_write_speed),
                   SUM(disk_read_speed), SUM(disk_write_speed)
            FROM monitoring_data
            WHERE session_id = ?
        ''', (session_id,))
        avg_read, avg_write, total_read, total_write = cursor.fetchone()
        
        # Top processes
        cursor.execute('''
            SELECT name, AVG(cpu_percent), AVG(memory_rss)
            FROM process_data
            WHERE session_id = ?
            GROUP BY name
            ORDER BY AVG(cpu_percent) DESC
            LIMIT 5
        ''', (session_id,))
        top_procs = [
            {'name': row[0], 'avg_cpu': row[1], 'avg_memory': row[2]}
            for row in cursor.fetchall()
        ]
        
        # System events
        cursor.execute('''
            SELECT severity, COUNT(*)
            FROM log_entries
            WHERE session_id = ?
            GROUP BY severity
        ''', (session_id,))
        event_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Sample events
        cursor.execute('''
            SELECT timestamp, severity, message
            FROM log_entries
            WHERE session_id = ? AND severity IN ('critical', 'error')
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (session_id,))
        event_samples = [
            {'time': row[0], 'severity': row[1], 'message': row[2][:100]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return ReportSummary(
            hostname='system',  # Could be extracted from metadata
            os_version='Linux',
            duration_seconds=int(duration),
            start_time=start_time,
            end_time=end_time,
            avg_cpu=avg_cpu,
            max_cpu=max_cpu,
            cpu_cores=4,  # Could be from system info
            avg_memory=avg_mem,
            max_memory=max_mem,
            total_memory_gb=total_mem / (1024**3) if total_mem else 0,
            gpu_present=gpu_present,
            gpu_model=gpu_model,
            avg_gpu_usage=avg_gpu or 0,
            max_gpu_usage=max_gpu or 0,
            total_upload_mb=(total_up or 0) / 1024 / 1024,
            total_download_mb=(total_down or 0) / 1024 / 1024,
            avg_upload_mbps=(avg_up or 0) / 1024 / 1024,
            avg_download_mbps=(avg_down or 0) / 1024 / 1024,
            avg_read_mbps=(avg_read or 0) / 1024 / 1024,
            avg_write_mbps=(avg_write or 0) / 1024 / 1024,
            total_read_gb=(total_read or 0) / 1024 / 1024 / 1024,
            total_write_gb=(total_write or 0) / 1024 / 1024 / 1024,
            top_processes=top_procs,
            critical_events=event_counts.get('critical', 0),
            error_events=event_counts.get('error', 0),
            warning_events=event_counts.get('warning', 0),
            event_samples=event_samples
        )
    
    def _generate_ai_insights(self, summary: ReportSummary) -> Dict[str, str]:
        """Generate insights using AI (GitHub Copilot)."""
        prompt = self._create_prompt(summary)
        
        try:
            response = self.ai_generator.generate(prompt, timeout=self.timeout)
            insights = self._parse_ai_response(response)
        except Exception as e:
            print(f"AI generation failed: {e}. Falling back to rules.")
            insights = self._generate_rule_insights(summary)
        
        return insights
    
    def _generate_rule_insights(self, summary: ReportSummary) -> Dict[str, str]:
        """Generate insights using rule-based analysis."""
        return self.rule_analyzer.analyze(summary)
    
    def _create_prompt(self, summary: ReportSummary) -> str:
        """Create prompt for AI model."""
        return f"""Analyze this system monitoring report and provide insights.

System Information:
- Hostname: {summary.hostname}
- OS: {summary.os_version}
- Monitoring Duration: {summary.duration_seconds // 3600}h {(summary.duration_seconds % 3600) // 60}m

Performance Metrics:
- CPU: Average {summary.avg_cpu:.1f}%, Peak {summary.max_cpu:.1f}% ({summary.cpu_cores} cores)
- Memory: Average {summary.avg_memory:.1f}%, Peak {summary.max_memory:.1f}% ({summary.total_memory_gb:.1f} GB total)
- GPU: {summary.gpu_model}, Average {summary.avg_gpu_usage:.1f}%, Peak {summary.max_gpu_usage:.1f}%

Network Activity:
- Upload: {summary.total_upload_mb:.1f} MB total, {summary.avg_upload_mbps:.2f} MB/s average
- Download: {summary.total_download_mb:.1f} MB total, {summary.avg_download_mbps:.2f} MB/s average

Disk I/O:
- Read: {summary.total_read_gb:.1f} GB total, {summary.avg_read_mbps:.2f} MB/s average
- Write: {summary.total_write_gb:.1f} GB total, {summary.avg_write_mbps:.2f} MB/s average

Top CPU Processes:
{self._format_processes(summary.top_processes)}

System Events:
- Critical: {summary.critical_events}
- Errors: {summary.error_events}
- Warnings: {summary.warning_events}

Recent Critical Events:
{self._format_events(summary.event_samples)}

Please provide:
1. Performance Summary (2-3 sentences highlighting key observations)
2. Identified Bottlenecks (specific areas of concern)
3. Actionable Recommendations (concrete steps to improve performance)
4. Detected Anomalies (unusual patterns or events)

Format your response in clear sections with headers."""
    
    def _format_processes(self, processes: List[Dict]) -> str:
        """Format process list for prompt."""
        if not processes:
            return "No process data available"
        
        lines = []
        for proc in processes:
            mem_mb = proc['avg_memory'] / (1024 * 1024)
            lines.append(
                f"- {proc['name']}: {proc['avg_cpu']:.1f}% CPU, "
                f"{mem_mb:.1f} MB RAM"
            )
        return "\n".join(lines)
    
    def _format_events(self, events: List[Dict]) -> str:
        """Format event list for prompt."""
        if not events:
            return "No critical events"
        
        lines = []
        for event in events[:5]:
            lines.append(f"- [{event['time']}] {event['severity']}: {event['message']}")
        return "\n".join(lines)
    
    def _parse_ai_response(self, response: str) -> Dict[str, str]:
        """Parse AI response into sections."""
        sections = {}
        current_section = None
        current_content = []
        
        for line in response.split('\n'):
            # Detect section headers
            if line.strip().startswith(('1.', '2.', '3.', '4.', '#', '##')):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Extract section name
                if 'Performance Summary' in line or 'Summary' in line:
                    current_section = 'performance_summary'
                elif 'Bottleneck' in line:
                    current_section = 'bottleneck_analysis'
                elif 'Recommendation' in line:
                    current_section = 'recommendations'
                elif 'Anomaly' in line or 'Anomalies' in line:
                    current_section = 'anomaly_detection'
                
                current_content = []
            else:
                current_content.append(line)
        
        # Add last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
```

### 3.4 GitHub Copilot Integration

**File**: `src/ai/insight_generator.py`

```python
"""
GitHub Copilot integration for AI insights.
"""

import subprocess
import shutil
from typing import Optional

class InsightGenerator:
    """Generate insights using GitHub Copilot CLI."""
    
    def __init__(self, config: dict):
        self.cli_command = config.get('cli_command', 'gh copilot suggest')
        self.use_local = config.get('use_local_cli', True)
    
    def is_available(self) -> bool:
        """Check if GitHub Copilot CLI is available."""
        if not self.use_local:
            return False
        
        # Check if 'gh' CLI is installed
        return shutil.which('gh') is not None
    
    def generate(self, prompt: str, timeout: int = 30) -> str:
        """
        Generate insights using GitHub Copilot.
        
        Args:
            prompt: Analysis prompt
            timeout: Timeout in seconds
        
        Returns:
            AI-generated insights as string
        """
        if not self.is_available():
            raise RuntimeError("GitHub Copilot CLI not available")
        
        try:
            # Use 'gh copilot suggest' with prompt
            cmd = ['gh', 'copilot', 'suggest', '-t', 'shell']
            
            result = subprocess.run(
                cmd,
                input=prompt.encode('utf-8'),
                capture_output=True,
                timeout=timeout,
                check=True
            )
            
            return result.stdout.decode('utf-8')
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"GitHub Copilot request timed out after {timeout}s")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"GitHub Copilot CLI failed: {e.stderr.decode()}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {str(e)}")
```

### 3.5 Rule-Based Fallback

**File**: `src/ai/rule_based_analyzer.py`

```python
"""
Rule-based analyzer as fallback when AI is unavailable.
"""

from typing import Dict, List
from .report_analyzer import ReportSummary

class RuleBasedAnalyzer:
    """Generate insights using rule-based analysis."""
    
    def __init__(self, thresholds: dict):
        self.high_cpu = thresholds.get('high_cpu', 80.0)
        self.high_memory = thresholds.get('high_memory', 85.0)
        self.high_disk_io = thresholds.get('high_disk_io', 100.0)
        self.thermal_throttle = thresholds.get('thermal_throttle_temp', 90.0)
    
    def analyze(self, summary: ReportSummary) -> Dict[str, str]:
        """
        Analyze report and generate rule-based insights.
        
        Returns:
            Dictionary with insight sections
        """
        insights = {}
        
        insights['performance_summary'] = self._generate_summary(summary)
        insights['bottleneck_analysis'] = self._identify_bottlenecks(summary)
        insights['recommendations'] = self._generate_recommendations(summary)
        insights['anomaly_detection'] = self._detect_anomalies(summary)
        
        return insights
    
    def _generate_summary(self, summary: ReportSummary) -> str:
        """Generate performance summary."""
        duration_str = f"{summary.duration_seconds // 3600}h {(summary.duration_seconds % 3600) // 60}m"
        
        summary_parts = [
            f"System monitored for {duration_str}."
        ]
        
        # CPU summary
        if summary.max_cpu > self.high_cpu:
            summary_parts.append(
                f"CPU usage peaked at {summary.max_cpu:.1f}%, "
                f"averaging {summary.avg_cpu:.1f}% (high load detected)."
            )
        else:
            summary_parts.append(
                f"CPU usage averaged {summary.avg_cpu:.1f}% "
                f"with peak at {summary.max_cpu:.1f}% (normal operation)."
            )
        
        # Memory summary
        if summary.max_memory > self.high_memory:
            summary_parts.append(
                f"Memory pressure observed with {summary.max_memory:.1f}% peak usage."
            )
        else:
            summary_parts.append(
                f"Memory usage stable at {summary.avg_memory:.1f}% average."
            )
        
        # GPU summary
        if summary.gpu_present:
            summary_parts.append(
                f"GPU ({summary.gpu_model}) averaged {summary.avg_gpu_usage:.1f}% utilization."
            )
        
        return " ".join(summary_parts)
    
    def _identify_bottlenecks(self, summary: ReportSummary) -> str:
        """Identify system bottlenecks."""
        bottlenecks = []
        
        # CPU bottleneck
        if summary.max_cpu > self.high_cpu:
            bottlenecks.append(
                f"**CPU Bottleneck**: Peak usage of {summary.max_cpu:.1f}% indicates "
                "CPU-bound workload. Top processes:\n" +
                "\n".join([
                    f"  - {p['name']}: {p['avg_cpu']:.1f}% CPU"
                    for p in summary.top_processes[:3]
                ])
            )
        
        # Memory bottleneck
        if summary.max_memory > self.high_memory:
            bottlenecks.append(
                f"**Memory Pressure**: System reached {summary.max_memory:.1f}% memory usage, "
                "potentially causing swap activity and performance degradation."
            )
        
        # Disk I/O bottleneck
        if summary.avg_write_mbps > self.high_disk_io:
            bottlenecks.append(
                f"**Disk I/O Bottleneck**: Write speed averaged {summary.avg_write_mbps:.1f} MB/s, "
                "which may indicate disk-intensive operations or slow storage."
            )
        
        # System events
        if summary.critical_events > 0 or summary.error_events > 5:
            bottlenecks.append(
                f"**System Stability**: Detected {summary.critical_events} critical events "
                f"and {summary.error_events} errors, indicating potential system issues."
            )
        
        if not bottlenecks:
            return "No significant bottlenecks detected. System operating within normal parameters."
        
        return "\n\n".join(bottlenecks)
    
    def _generate_recommendations(self, summary: ReportSummary) -> str:
        """Generate actionable recommendations."""
        recommendations = []
        
        # CPU recommendations
        if summary.max_cpu > self.high_cpu:
            recommendations.append(
                "**CPU Optimization**:\n"
                "- Identify and optimize CPU-intensive processes\n"
                "- Consider enabling CPU frequency scaling for better power/performance balance\n"
                "- Review multithreading efficiency in top processes"
            )
        
        # Memory recommendations
        if summary.max_memory > self.high_memory:
            recommendations.append(
                "**Memory Management**:\n"
                "- Close unnecessary applications to free RAM\n"
                "- Check for memory leaks in long-running processes\n"
                "- Consider adding more RAM if pressure is persistent"
            )
        
        # Disk recommendations
        if summary.avg_write_mbps > self.high_disk_io:
            recommendations.append(
                "**Storage Optimization**:\n"
                "- Review applications performing heavy disk writes\n"
                "- Consider upgrading to SSD if using HDD\n"
                "- Enable filesystem caching if not already active"
            )
        
        # GPU recommendations
        if summary.gpu_present and summary.avg_gpu_usage < 20:
            recommendations.append(
                "**GPU Utilization**:\n"
                "- GPU is underutilized; consider offloading more work to GPU\n"
                "- Verify GPU acceleration is enabled in applications"
            )
        
        if not recommendations:
            return "System is performing well. No immediate optimizations needed."
        
        return "\n\n".join(recommendations)
    
    def _detect_anomalies(self, summary: ReportSummary) -> str:
        """Detect anomalous patterns."""
        anomalies = []
        
        # Sudden CPU spikes
        if summary.max_cpu > 90 and summary.avg_cpu < 50:
            anomalies.append(
                "- CPU spike detected: Peak usage significantly higher than average, "
                "suggesting burst workload or transient process"
            )
        
        # Unusual network activity
        if summary.total_download_mb > 10000:  # >10GB
            anomalies.append(
                f"- High network download: {summary.total_download_mb/1024:.1f} GB transferred, "
                "which is unusually high"
            )
        
        # System events clustering
        if summary.critical_events > 0:
            anomalies.append(
                f"- Critical system events detected ({summary.critical_events}), "
                "review logs for details"
            )
        
        if not anomalies:
            return "No anomalies detected during monitoring period."
        
        return "\n".join(anomalies)
```

### 3.6 HTML Export Integration

**Add to HTML Report** (`src/storage/data_exporter.py`):

```html
<!-- AI Insights Section -->
<div class="insights-section">
    <h2>AI-Generated Insights 
        <button id="regenerateInsights" class="btn btn-primary">
            <i class="icon-refresh"></i> Regenerate
        </button>
        <button id="copyInsights" class="btn btn-secondary">
            <i class="icon-copy"></i> Copy
        </button>
    </h2>
    
    <div id="insightsContent">
        <div class="insight-section">
            <h3>Performance Summary</h3>
            <p>{{ insights.performance_summary }}</p>
        </div>
        
        <div class="insight-section">
            <h3>Identified Bottlenecks</h3>
            <div class="markdown-content">{{ insights.bottleneck_analysis }}</div>
        </div>
        
        <div class="insight-section">
            <h3>Recommendations</h3>
            <div class="markdown-content">{{ insights.recommendations }}</div>
        </div>
        
        <div class="insight-section">
            <h3>Anomaly Detection</h3>
            <p>{{ insights.anomaly_detection }}</p>
        </div>
    </div>
    
    <div class="insight-footer">
        <small>
            Generated using: <span id="insightProvider">{{ provider }}</span>
            <br>
            Timestamp: <span id="insightTimestamp">{{ timestamp }}</span>
        </small>
    </div>
</div>

<script>
// Copy insights to clipboard
document.getElementById('copyInsights').addEventListener('click', function() {
    var content = document.getElementById('insightsContent').innerText;
    navigator.clipboard.writeText(content);
    alert('Insights copied to clipboard!');
});

// Regenerate insights (would call Python backend)
document.getElementById('regenerateInsights').addEventListener('click', function() {
    alert('Regeneration requires backend integration');
    // In full implementation, would make AJAX call to regenerate
});
</script>
```

---

## Testing Strategy

### Unit Tests

```
tests/unit/
├── test_process_monitor.py
│   ├── test_local_process_collection
│   ├── test_ssh_process_collection
│   ├── test_adb_process_collection
│   ├── test_process_sorting
│   └── test_severity_detection
│
├── test_log_monitor.py
│   ├── test_log_parsing
│   ├── test_timestamp_extraction
│   ├── test_keyword_filtering
│   ├── test_log_anonymization
│   ├── test_compression_support
│   └── test_process_correlation
│
└── test_ai_insights.py
    ├── test_summary_extraction
    ├── test_rule_based_analysis
    ├── test_github_copilot_integration
    ├── test_prompt_generation
    └── test_insight_parsing
```

### Integration Tests

```
tests/integration/
├── test_process_ui_integration.py
├── test_log_export_integration.py
└── test_end_to_end_report.py
```

### Test Coverage Goals

- **Process Monitor**: >70%
- **Log Monitor**: >65%
- **AI Insights**: >60%
- **Overall**: Maintain >60% coverage

---

## Database Migrations

### Migration Script

**File**: `scripts/migrate_v1.0_to_v1.1.py`

```python
"""
Database migration from v1.0 to v1.1
"""

import sqlite3
from pathlib import Path

def migrate_database(db_path: str):
    """Apply migrations to upgrade database schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Add version tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check current version
    cursor.execute('SELECT version FROM schema_version ORDER BY version DESC LIMIT 1')
    current_version = cursor.fetchone()
    
    if current_version and current_version[0] >= '1.1':
        print("Database already at v1.1 or higher")
        conn.close()
        return
    
    print("Applying v1.1 migrations...")
    
    # Add process_data table
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
            create_time REAL,
            FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_process_timestamp ON process_data(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_process_session ON process_data(session_id)')
    
    # Add log_entries table
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
            process_context TEXT,
            FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log_entries(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_session ON log_entries(session_id)')
    
    # Add report_insights table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            provider TEXT,
            insights TEXT,
            prompt_used TEXT,
            FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
        )
    ''')
    
    # Record migration
    cursor.execute("INSERT INTO schema_version (version) VALUES ('1.1')")
    
    conn.commit()
    conn.close()
    
    print("Migration to v1.1 completed successfully")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        db_path = Path.home() / '.monitor-tool' / 'monitor_data.db'
    else:
        db_path = sys.argv[1]
    
    migrate_database(db_path)
```

---

## Deployment Plan

### Phase 1: Development (Week 1-2)
1. Implement ProcessMonitor class and UI widget
2. Add database schema and migrations
3. Unit tests for process monitoring
4. Integration with main window

### Phase 2: Log Collection (Week 3-4)
1. Implement LogMonitor class
2. Add log parsing and filtering
3. Implement anonymization
4. HTML export integration
5. Unit tests for log collection

### Phase 3: AI Insights (Week 5-6)
1. Implement ReportAnalyzer
2. Rule-based analyzer implementation
3. GitHub Copilot integration
4. HTML report integration
5. Unit tests for insights

### Phase 4: Testing & Polish (Week 7)
1. Integration testing
2. Performance optimization
3. Documentation updates
4. User acceptance testing

### Phase 5: Release (Week 8)
1. Final testing
2. Package building
3. Release notes
4. Version 1.1 release

---

## Performance Considerations

### Process Monitoring Overhead
- Target: <2% CPU overhead
- Use caching with configurable intervals
- Batch database writes
- Efficient psutil usage

### Log Collection Overhead
- Target: <10 seconds for typical exports
- Streaming file reads
- Keyword-based filtering early
- Limit to configured max lines

### Database Size Management
- Auto-cleanup of old data (>3 days)
- VACUUM after cleanup
- Index optimization
- Separate tables for features

### UI Responsiveness
- Background threads for all I/O
- Qt signals for UI updates
- No blocking on main thread
- Progress indicators for long operations

---

## Security Considerations

### Log Data Handling
- User consent required before collection
- Anonymization enabled by default
- Clear privacy warnings
- Optional review before export

### System Access
- Graceful degradation if permissions denied
- No hardcoded credentials
- Secure SSH/ADB handling
- Input validation for all user data

### API Usage
- Local-first approach
- No external API keys required for basic functionality
- Timeout handling
- Error sanitization (no credential leaking)

---

**Next Steps**: Proceed to `/speckit.tasks` for implementation task breakdown

