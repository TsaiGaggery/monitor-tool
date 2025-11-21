# System Monitor Tool v1.1 - Implementation Guide

## Document Information

**Version**: 1.0  
**Date**: 2025-11-21  
**Purpose**: Detailed implementation guidance with code examples

---

## Architecture Decisions

### Design Principles

1. **Modularity**: Each monitor is self-contained and independently testable
2. **Performance First**: Background threading, efficient polling, minimal overhead
3. **Graceful Degradation**: Features degrade gracefully when permissions/hardware unavailable
4. **Mode Abstraction**: Support local/SSH/ADB with unified interface
5. **Privacy by Default**: Anonymization enabled, explicit user consent for logs

### Technology Stack

- **Language**: Python 3.8+
- **UI Framework**: PyQt5
- **Database**: SQLite3
- **Testing**: pytest, pytest-mock, pytest-cov
- **Documentation**: Sphinx
- **CI/CD**: GitHub Actions

---

## Implementation Roadmap

### Phase 1: Foundation (TASK-001, TASK-002)

#### Step 1.1: Configuration Schema

**File**: `config/default.yaml`

```yaml
# Existing configuration (abbreviated)
monitoring:
  update_interval: 1000
  enable_cpu: true
  enable_gpu: true
  # ... existing config ...

# NEW: Tier 2 Configuration
tier2:
  process_monitoring:
    enabled: true
    update_interval: 1000  # ms, can differ from main monitor
    process_count: 5
    sort_by: cpu  # Options: cpu, memory, combined
    include_cmdline: true
    cmdline_max_length: 50
    thresholds:
      cpu_warning: 50.0
      cpu_critical: 80.0
      memory_warning: 1073741824  # 1 GB
      memory_critical: 2147483648  # 2 GB

# NEW: Log Collection Configuration
log_collection:
  enabled: false  # Disabled by default for privacy
  sources:
    - /var/log/syslog
    - /var/log/kern.log
    - /var/log/dmesg
    - /var/log/messages  # CentOS/RHEL
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

# NEW: AI Insights Configuration
ai_insights:
  enabled: true
  provider: rule_based  # Options: github_copilot, rule_based
  api_timeout: 30
  max_report_size: 5242880  # 5 MB
  
  github_copilot:
    cli_command: gh copilot suggest
    use_local_cli: true
  
  thresholds:
    high_cpu: 80.0
    high_memory: 85.0
    high_disk_io: 100
    thermal_throttle_temp: 90
  
  insight_sections:
    - performance_summary
    - bottleneck_analysis
    - recommendations
    - anomaly_detection
```

#### Step 1.2: Configuration Loader

**File**: `src/config/config_loader.py` (if doesn't exist)

```python
"""
Configuration loader with validation.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """Load and validate configuration from YAML file."""
    
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / 'config' / 'default.yaml'
    
    @staticmethod
    def load(config_path: str = None) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to config file (optional)
        
        Returns:
            Configuration dictionary
        """
        if config_path is None:
            config_path = ConfigLoader.DEFAULT_CONFIG_PATH
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate and set defaults
        config = ConfigLoader._apply_defaults(config)
        ConfigLoader._validate(config)
        
        return config
    
    @staticmethod
    def _apply_defaults(config: Dict) -> Dict:
        """Apply default values for missing keys."""
        # Tier2 defaults
        if 'tier2' not in config:
            config['tier2'] = {}
        
        if 'process_monitoring' not in config['tier2']:
            config['tier2']['process_monitoring'] = {
                'enabled': True,
                'update_interval': 1000,
                'process_count': 5,
                'sort_by': 'cpu'
            }
        
        # Log collection defaults
        if 'log_collection' not in config:
            config['log_collection'] = {
                'enabled': False,
                'sources': [],
                'keywords': [],
                'max_log_lines': 1000
            }
        
        # AI insights defaults
        if 'ai_insights' not in config:
            config['ai_insights'] = {
                'enabled': True,
                'provider': 'rule_based'
            }
        
        return config
    
    @staticmethod
    def _validate(config: Dict):
        """Validate configuration values."""
        # Validate tier2 settings
        proc_config = config['tier2']['process_monitoring']
        
        if proc_config['process_count'] < 1 or proc_config['process_count'] > 20:
            raise ValueError("process_count must be between 1 and 20")
        
        if proc_config['sort_by'] not in ['cpu', 'memory', 'combined']:
            raise ValueError("sort_by must be one of: cpu, memory, combined")
        
        # Validate log collection
        log_config = config['log_collection']
        
        if log_config['max_log_lines'] < 100 or log_config['max_log_lines'] > 10000:
            raise ValueError("max_log_lines must be between 100 and 10000")
```

#### Step 1.3: Database Migration

**File**: `scripts/migrate_v1.0_to_v1.1.py`

```python
#!/usr/bin/env python3
"""
Database migration script for v1.0 to v1.1
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

class DatabaseMigrator:
    """Handle database schema migrations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def get_current_version(self) -> str:
        """Get current schema version."""
        try:
            self.cursor.execute(
                'SELECT version FROM schema_version '
                'ORDER BY applied_at DESC LIMIT 1'
            )
            result = self.cursor.fetchone()
            return result[0] if result else '1.0'
        except sqlite3.OperationalError:
            # Table doesn't exist, assume v1.0
            return '1.0'
    
    def migrate_to_v1_1(self):
        """Apply v1.1 migrations."""
        print("Starting migration to v1.1...")
        
        # Create version tracking table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        ''')
        
        # Check if already migrated
        current_version = self.get_current_version()
        if current_version >= '1.1':
            print(f"Database already at version {current_version}")
            return
        
        # Create process_data table
        print("Creating process_data table...")
        self.cursor.execute('''
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
                FOREIGN KEY (session_id) 
                    REFERENCES monitoring_data(session_id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for process_data
        print("Creating indexes for process_data...")
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_process_timestamp '
            'ON process_data(timestamp)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_process_session '
            'ON process_data(session_id)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_process_cpu '
            'ON process_data(cpu_percent DESC)'
        )
        
        # Create log_entries table
        print("Creating log_entries table...")
        self.cursor.execute('''
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
                FOREIGN KEY (session_id) 
                    REFERENCES monitoring_data(session_id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for log_entries
        print("Creating indexes for log_entries...")
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_log_timestamp '
            'ON log_entries(timestamp)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_log_session '
            'ON log_entries(session_id)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_log_severity '
            'ON log_entries(severity)'
        )
        
        # Create process_log_correlation table
        print("Creating process_log_correlation table...")
        self.cursor.execute('''
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
        print("Creating report_insights table...")
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                provider TEXT,
                insights TEXT,
                prompt_used TEXT,
                FOREIGN KEY (session_id) 
                    REFERENCES monitoring_data(session_id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Record migration
        print("Recording migration...")
        self.cursor.execute('''
            INSERT INTO schema_version (version, description)
            VALUES (?, ?)
        ''', ('1.1', 'Added process monitoring, log collection, and AI insights'))
        
        # Commit all changes
        self.conn.commit()
        
        print("Migration to v1.1 completed successfully!")
    
    def verify_migration(self):
        """Verify migration was successful."""
        print("\nVerifying migration...")
        
        tables = [
            'process_data',
            'log_entries',
            'process_log_correlation',
            'report_insights'
        ]
        
        for table in tables:
            self.cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            if self.cursor.fetchone():
                print(f"✓ Table {table} exists")
            else:
                print(f"✗ Table {table} missing!")
                return False
        
        print("\nMigration verification passed!")
        return True

def main():
    """Main migration entry point."""
    if len(sys.argv) < 2:
        db_path = Path.home() / '.monitor-tool' / 'monitor_data.db'
    else:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    print(f"Migrating database: {db_path}")
    
    migrator = DatabaseMigrator(str(db_path))
    
    try:
        migrator.connect()
        migrator.migrate_to_v1_1()
        migrator.verify_migration()
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)
    finally:
        migrator.close()

if __name__ == '__main__':
    main()
```

---

### Phase 2: Process Monitor (TASK-003 to TASK-008)

#### Step 2.1: ProcessMonitor Core Implementation

**File**: `src/monitors/process_monitor.py`

```python
"""
Process monitoring module for tracking top CPU/memory consuming processes.

This module provides cross-platform process monitoring with support for:
- Local monitoring via psutil
- Remote Linux monitoring via SSH
- Android monitoring via ADB

Author: TsaiGaggery
Date: 2025-11-21
"""

import psutil
import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from threading import Lock

logger = logging.getLogger(__name__)

@dataclass
class ProcessInfo:
    """
    Data class representing process information.
    
    Attributes:
        pid: Process ID
        name: Process name
        cpu_percent: CPU usage percentage (0-100)
        memory_rss: Resident Set Size (bytes)
        memory_vms: Virtual Memory Size (bytes)
        cmdline: Command line (truncated)
        status: Process status (running, sleeping, etc.)
        num_threads: Number of threads
        create_time: Process creation time (Unix timestamp)
        timestamp: When this data was collected
    """
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
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class ProcessMonitor:
    """
    Monitor top processes by CPU and memory usage.
    
    This class provides a unified interface for monitoring processes across
    different platforms (local, SSH, ADB) with configurable sorting and
    filtering options.
    
    Thread Safety:
        This class is thread-safe. Multiple threads can call get_top_processes()
        concurrently.
    
    Example:
        >>> config = {
        ...     'enabled': True,
        ...     'process_count': 5,
        ...     'sort_by': 'cpu'
        ... }
        >>> monitor = ProcessMonitor(config, mode='local')
        >>> processes = monitor.get_top_processes()
        >>> for proc in processes:
        ...     print(f"{proc.name}: {proc.cpu_percent}%")
    """
    
    def __init__(self, config: dict, mode: str = 'local',
                 ssh_client=None, adb_device=None):
        """
        Initialize ProcessMonitor.
        
        Args:
            config: Configuration dictionary with keys:
                - enabled (bool): Enable/disable monitoring
                - update_interval (int): Update interval in milliseconds
                - process_count (int): Number of top processes to track
                - sort_by (str): Sort metric ('cpu', 'memory', 'combined')
                - cmdline_max_length (int): Maximum command line length
                - thresholds (dict): CPU/memory thresholds for severity
            mode: Operation mode ('local', 'ssh', 'adb')
            ssh_client: paramiko.SSHClient for remote monitoring
            adb_device: ADB device object for Android monitoring
        
        Raises:
            ValueError: If mode is invalid or required client is missing
        """
        self.enabled = config.get('enabled', True)
        self.update_interval = config.get('update_interval', 1000) / 1000.0
        self.process_count = config.get('process_count', 5)
        self.sort_by = config.get('sort_by', 'cpu')
        self.cmdline_max_length = config.get('cmdline_max_length', 50)
        self.thresholds = config.get('thresholds', {})
        
        # Validate mode and clients
        self.mode = mode
        if mode not in ['local', 'ssh', 'adb']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'local', 'ssh', or 'adb'")
        
        if mode == 'ssh' and ssh_client is None:
            raise ValueError("SSH client required for SSH mode")
        if mode == 'adb' and adb_device is None:
            raise ValueError("ADB device required for ADB mode")
        
        self.ssh_client = ssh_client
        self.adb_device = adb_device
        
        # Cache and timing
        self._last_update = 0
        self._process_cache: List[ProcessInfo] = []
        self._cache_lock = Lock()
        
        logger.info(f"ProcessMonitor initialized in {mode} mode")
    
    def get_top_processes(self, force_update: bool = False) -> List[ProcessInfo]:
        """
        Get top processes sorted by configured metric.
        
        This method uses caching to avoid excessive system calls. The cache
        is refreshed based on the configured update_interval.
        
        Args:
            force_update: Force cache refresh regardless of interval
        
        Returns:
            List of ProcessInfo objects for top processes
        
        Raises:
            RuntimeError: If process collection fails
        """
        if not self.enabled:
            return []
        
        current_time = time.time()
        
        # Check if cache is still valid
        with self._cache_lock:
            if not force_update and (current_time - self._last_update) < self.update_interval:
                return self._process_cache.copy()
        
        # Collect processes based on mode
        try:
            if self.mode == 'local':
                processes = self._get_local_processes()
            elif self.mode == 'ssh':
                processes = self._get_ssh_processes()
            elif self.mode == 'adb':
                processes = self._get_adb_processes()
            else:
                raise RuntimeError(f"Unsupported mode: {self.mode}")
        except Exception as e:
            logger.error(f"Failed to collect processes: {e}")
            return self._process_cache.copy()  # Return cached data
        
        # Sort and filter
        processes = self._sort_processes(processes)[:self.process_count]
        
        # Update cache
        with self._cache_lock:
            self._process_cache = processes
            self._last_update = current_time
        
        return processes.copy()
    
    def _get_local_processes(self) -> List[ProcessInfo]:
        """
        Get processes from local system using psutil.
        
        Returns:
            List of ProcessInfo objects
        """
        processes = []
        now = datetime.now()
        
        # First pass: trigger CPU percent calculation
        for proc in psutil.process_iter(['pid']):
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Wait a bit for CPU calculation
        time.sleep(0.1)
        
        # Second pass: collect data
        for proc in psutil.process_iter([
            'pid', 'name', 'cpu_percent', 'memory_info',
            'cmdline', 'status', 'num_threads', 'create_time'
        ]):
            try:
                info = proc.info
                
                # Get CPU percent
                cpu_percent = info['cpu_percent']
                if cpu_percent is None:
                    cpu_percent = 0.0
                
                # Build command line
                cmdline_list = info['cmdline'] or []
                cmdline = ' '.join(cmdline_list)
                if len(cmdline) > self.cmdline_max_length:
                    cmdline = cmdline[:self.cmdline_max_length] + '...'
                
                # Get memory info
                mem_info = info['memory_info']
                
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    cpu_percent=cpu_percent,
                    memory_rss=mem_info.rss,
                    memory_vms=mem_info.vms,
                    cmdline=cmdline,
                    status=info['status'],
                    num_threads=info['num_threads'] or 0,
                    create_time=info['create_time'] or 0.0,
                    timestamp=now
                ))
            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process disappeared or no access
                continue
            except Exception as e:
                logger.warning(f"Error reading process info: {e}")
                continue
        
        return processes
    
    def _get_ssh_processes(self) -> List[ProcessInfo]:
        """
        Get processes from remote Linux system via SSH.
        
        Uses 'ps aux' command to retrieve process information.
        
        Returns:
            List of ProcessInfo objects
        """
        # Command to get process info
        # Format: PID|NAME|CPU%|MEM_KB|COMMAND
        cmd = """ps aux --sort=-%cpu | head -n 50 | awk 'NR>1 {
            printf "%s|%s|%s|%s|", $2, $11, $3, $6;
            for(i=11;i<=NF;i++) printf "%s ", $i;
            printf "\\n"
        }'"""
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=5)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if error:
                logger.warning(f"SSH command stderr: {error}")
        
        except Exception as e:
            logger.error(f"SSH command failed: {e}")
            return []
        
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
                cmdline = parts[4].strip() if len(parts) > 4 else name
                
                # Truncate command line
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
                    num_threads=0,  # Not available via ps
                    create_time=0.0,
                    timestamp=now
                ))
            
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse line: {line}, error: {e}")
                continue
        
        return processes
    
    def _get_adb_processes(self) -> List[ProcessInfo]:
        """
        Get processes from Android device via ADB.
        
        Uses 'top -n 1 -b' for batch mode output.
        
        Returns:
            List of ProcessInfo objects
        """
        try:
            # Run top in batch mode
            result = self.adb_device.shell("top -n 1 -b | head -n 30")
        except Exception as e:
            logger.error(f"ADB command failed: {e}")
            return []
        
        processes = []
        now = datetime.now()
        
        # Parse Android top output
        # Format varies by Android version
        # Common format: PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ COMMAND
        lines = result.split('\n')
        
        # Skip header lines
        data_start = False
        for line in lines:
            if 'PID' in line and 'CPU' in line:
                data_start = True
                continue
            
            if not data_start or not line.strip():
                continue
            
            parts = line.split()
            if len(parts) < 9:
                continue
            
            try:
                pid = int(parts[0])
                # CPU might be column 8 or 9 depending on format
                cpu_col = 8 if len(parts) > 10 else 2
                cpu_str = parts[cpu_col].rstrip('%')
                cpu_percent = float(cpu_str) if cpu_str else 0.0
                
                # Memory in KB
                mem_col = 5
                mem_str = parts[mem_col].rstrip('KkMmGg')
                memory_kb = int(float(mem_str)) if mem_str else 0
                
                # Process name is last column
                name = parts[-1]
                
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
            
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse top line: {line}, error: {e}")
                continue
        
        return processes
    
    def _sort_processes(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """
        Sort processes by configured metric.
        
        Args:
            processes: List of ProcessInfo objects
        
        Returns:
            Sorted list of ProcessInfo objects
        """
        if not processes:
            return []
        
        if self.sort_by == 'cpu':
            return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)
        
        elif self.sort_by == 'memory':
            return sorted(processes, key=lambda p: p.memory_rss, reverse=True)
        
        elif self.sort_by == 'combined':
            # Normalize and combine both metrics
            max_cpu = max((p.cpu_percent for p in processes), default=1.0)
            max_mem = max((p.memory_rss for p in processes), default=1.0)
            
            if max_cpu == 0:
                max_cpu = 1.0
            if max_mem == 0:
                max_mem = 1.0
            
            return sorted(
                processes,
                key=lambda p: (p.cpu_percent / max_cpu + p.memory_rss / max_mem),
                reverse=True
            )
        
        else:
            logger.warning(f"Unknown sort mode: {self.sort_by}, using 'cpu'")
            return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)
    
    def get_severity(self, process: ProcessInfo) -> str:
        """
        Determine severity level based on thresholds.
        
        Args:
            process: ProcessInfo object
        
        Returns:
            Severity level: 'critical', 'warning', or 'normal'
        """
        cpu_warning = self.thresholds.get('cpu_warning', 50.0)
        cpu_critical = self.thresholds.get('cpu_critical', 80.0)
        mem_warning = self.thresholds.get('memory_warning', 1073741824)  # 1GB
        mem_critical = self.thresholds.get('memory_critical', 2147483648)  # 2GB
        
        if (process.cpu_percent >= cpu_critical or 
            process.memory_rss >= mem_critical):
            return 'critical'
        
        elif (process.cpu_percent >= cpu_warning or 
              process.memory_rss >= mem_warning):
            return 'warning'
        
        else:
            return 'normal'
```

**Key Implementation Notes**:

1. **Thread Safety**: Uses Lock for cache access
2. **Error Handling**: Graceful degradation on errors
3. **Caching**: Reduces system calls with configurable interval
4. **Extensibility**: Easy to add new sorting modes
5. **Documentation**: Comprehensive docstrings for all methods

#### Step 2.2: UI Widget

**File**: `src/ui/widgets/process_table_widget.py`

```python
"""
Widget for displaying top processes in a table.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
import logging

logger = logging.getLogger(__name__)

class ProcessTableWidget(QWidget):
    """
    Table widget showing top CPU/memory consuming processes.
    
    Features:
    - Real-time updates
    - Color-coded severity
    - Tooltips with full command lines
    - Automatic refresh
    
    Signals:
        processClicked: Emitted when a process row is clicked
    """
    
    processClicked = pyqtSignal(int)  # Emits PID
    
    def __init__(self, process_monitor, parent=None):
        """
        Initialize ProcessTableWidget.
        
        Args:
            process_monitor: ProcessMonitor instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.process_monitor = process_monitor
        self.setup_ui()
        self.setup_timer()
    
    def setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("Top 5 CPU-Intensive Processes")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['PID', 'Process', 'CPU %', 'Memory'])
        
        # Configure table
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        
        # Connect signals
        self.table.cellClicked.connect(self._on_cell_clicked)
        
        layout.addWidget(self.table)
    
    def setup_timer(self):
        """Setup update timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        
        # Convert interval from seconds to milliseconds
        interval = int(self.process_monitor.update_interval * 1000)
        self.timer.start(interval)
        
        # Initial update
        self.update_data()
    
    def update_data(self):
        """Update table with latest process data."""
        if not self.process_monitor.enabled:
            return
        
        try:
            processes = self.process_monitor.get_top_processes()
        except Exception as e:
            logger.error(f"Failed to get processes: {e}")
            return
        
        # Update table
        self.table.setRowCount(len(processes))
        
        for row, proc in enumerate(processes):
            # PID
            pid_item = QTableWidgetItem(str(proc.pid))
            pid_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, pid_item)
            
            # Process name (with tooltip showing full command)
            name_item = QTableWidgetItem(proc.name)
            name_item.setToolTip(f"Command: {proc.cmdline}\nStatus: {proc.status}")
            self.table.setItem(row, 1, name_item)
            
            # CPU %
            cpu_item = QTableWidgetItem(f"{proc.cpu_percent:.1f}%")
            cpu_item.setTextAlignment(Qt.AlignCenter)
            
            # Apply color based on severity
            severity = self.process_monitor.get_severity(proc)
            color = self._get_severity_color(severity)
            cpu_item.setBackground(color)
            
            self.table.setItem(row, 2, cpu_item)
            
            # Memory
            mem_mb = proc.memory_rss / (1024 * 1024)
            mem_str = f"{mem_mb:.1f} MB" if mem_mb < 1024 else f"{mem_mb/1024:.2f} GB"
            mem_item = QTableWidgetItem(mem_str)
            mem_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, mem_item)
    
    def _get_severity_color(self, severity: str) -> QColor:
        """
        Get color for severity level.
        
        Args:
            severity: 'critical', 'warning', or 'normal'
        
        Returns:
            QColor object
        """
        if severity == 'critical':
            return QColor(255, 200, 200)  # Light red
        elif severity == 'warning':
            return QColor(255, 230, 200)  # Light orange
        else:
            return QColor(255, 255, 255)  # White
    
    def _on_cell_clicked(self, row: int, column: int):
        """Handle cell click event."""
        pid_item = self.table.item(row, 0)
        if pid_item:
            pid = int(pid_item.text())
            self.processClicked.emit(pid)
    
    def stop(self):
        """Stop the update timer."""
        if hasattr(self, 'timer'):
            self.timer.stop()
```

---

### Implementation Best Practices

#### Error Handling Pattern

```python
def some_monitor_method(self):
    """Monitor method with proper error handling."""
    try:
        # Attempt operation
        data = self._collect_data()
        return data
    
    except PermissionError:
        logger.warning("Permission denied, returning cached data")
        return self._cached_data
    
    except TimeoutError:
        logger.error("Operation timed out")
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return None
```

#### Testing Pattern

```python
def test_process_monitor_local():
    """Test ProcessMonitor in local mode."""
    config = {
        'enabled': True,
        'process_count': 5,
        'sort_by': 'cpu',
        'update_interval': 1000
    }
    
    monitor = ProcessMonitor(config, mode='local')
    processes = monitor.get_top_processes()
    
    assert len(processes) <= 5
    assert all(isinstance(p, ProcessInfo) for p in processes)
    assert processes[0].cpu_percent >= processes[-1].cpu_percent
```

---

## Additional Notes

Due to length constraints, I've provided the core implementation guidance for the first phase. The remaining implementations follow similar patterns:

- **Log Monitor**: Similar structure to ProcessMonitor, with file I/O and parsing
- **AI Insights**: Uses subprocess for GitHub CLI, rule-based fallback
- **Export Enhancements**: Extends existing exporter with new sections

Would you like me to continue with specific implementations for Phase 3 (Log Collection) or Phase 4 (AI Insights)?

---

## Quick Start for Developers

1. **Setup Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run Migration**:
   ```bash
   python scripts/migrate_v1.0_to_v1.1.py
   ```

3. **Run Tests**:
   ```bash
   pytest tests/unit/ -v
   ```

4. **Start Development**:
   ```bash
   python src/main.py
   ```

---

**For questions or clarifications, refer to the specification documents or contact the project maintainer.**
