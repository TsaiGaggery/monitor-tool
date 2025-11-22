# Log Storage Design for Monitor Tool

## Overview

This document defines the approach for storing system logs alongside monitoring data in session-specific databases for report generation.

## Architecture

### Session-Based Storage Model

Each monitoring session creates a **dedicated SQLite database** containing:
1. Monitoring metrics (CPU, Memory, GPU, NPU, Process data)
2. System logs (collected at report generation time)
3. Session metadata

### Directory Structure

```
reports/
├── session_20251121_143524/
│   ├── monitoring_data.db          # Session database (monitoring + logs)
│   ├── report.html                 # HTML report with charts and logs
│   ├── report.csv                  # Optional CSV export
│   └── report.json                 # Optional JSON export
│
├── session_20251121_150832/
│   ├── monitoring_data.db
│   ├── report.html
│   └── ...
│
└── latest -> session_20251121_150832/  # Symlink to most recent
```

## Database Schema

### Monitoring Data (Existing)

```sql
CREATE TABLE monitoring_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,           -- e.g., '20251121_143524'
    timestamp INTEGER NOT NULL,
    cpu_usage REAL,
    memory_percent REAL,
    gpu_usage REAL,
    -- ... existing columns ...
);

CREATE TABLE process_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    session_id TEXT NOT NULL,
    pid INTEGER NOT NULL,
    name TEXT NOT NULL,
    cpu_percent REAL NOT NULL,
    -- ... existing columns ...
);
```

### Log Data (New)

```sql
CREATE TABLE log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,        -- UTC normalized
    source TEXT NOT NULL,               -- 'local:/var/log/syslog', 'adb:logcat', 'ssh:server:/var/log/syslog'
    severity TEXT NOT NULL,             -- 'critical', 'error', 'warning', 'info', 'debug'
    facility TEXT,                      -- 'kernel', 'systemd', 'app', etc.
    message TEXT NOT NULL,              -- Anonymized message
    raw_line TEXT,                      -- Original line (for debugging)
    process_context TEXT,               -- JSON array of PIDs: "[1234, 5678]"
    FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
);

CREATE INDEX idx_log_timestamp ON log_entries(timestamp);
CREATE INDEX idx_log_session ON log_entries(session_id);
CREATE INDEX idx_log_severity ON log_entries(severity);

CREATE TABLE session_metadata (
    session_id TEXT PRIMARY KEY,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    source_type TEXT NOT NULL,          -- 'local', 'ssh', 'adb'
    source_name TEXT,                   -- 'localhost', '192.168.1.68:5555', 'server.com'
    log_collection_enabled BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Data Flow

### Phase 1: Monitoring (Real-time)

```
Remote Device (SSH/ADB)
├─ Monitoring script runs
├─ Stores metrics in remote DB: /tmp/monitor.db or /data/local/tmp/monitor.db
└─ Streams JSON to host for UI display

Host Machine
├─ Displays real-time metrics in GUI
└─ NO log collection yet (efficient)
```

### Phase 2: Report Generation

```
1. Query Remote DB (efficient)
   ├─ adb shell "sqlite3 -json /data/local/tmp/monitor.db 'SELECT * WHERE timestamp BETWEEN ...'"
   └─ ssh "sqlite3 -json /tmp/monitor.db 'SELECT * WHERE timestamp BETWEEN ...'"
   
2. Create Session Database
   ├─ reports/session_{timestamp}/monitoring_data.db
   └─ INSERT monitoring metrics from remote query results

3. Collect Logs (time-filtered)
   ├─ Get session time range: MIN(timestamp), MAX(timestamp) from monitoring_data
   ├─ LogMonitor.collect_logs(start_time, end_time)
   │   ├─ ADB: adb logcat -d -v time -T 'start_time'
   │   ├─ SSH: journalctl --since 'start_time' --until 'end_time'
   │   └─ Local: grep + tail with time filtering
   └─ Filter, parse, anonymize

4. Store Logs
   ├─ INSERT INTO log_entries (session_id, timestamp, source, severity, message, ...)
   └─ Batch insert for performance

5. Generate Report
   ├─ Read monitoring_data + log_entries
   ├─ Create charts with log event markers
   ├─ Create detailed log table with search/filter
   └─ Export to reports/session_{timestamp}/report.html
```

## Implementation

### DataLogger Enhancement (TASK-015)

```python
class DataLogger:
    def __init__(self, session_id: str = None, db_path: str = None):
        """
        Initialize with session-specific database.
        
        Args:
            session_id: Session identifier (e.g., '20251121_143524')
            db_path: Explicit path, or auto-create in reports/session_{id}/
        """
        if db_path is None:
            if session_id is None:
                session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            session_dir = Path('reports') / f'session_{session_id}'
            session_dir.mkdir(parents=True, exist_ok=True)
            db_path = session_dir / 'monitoring_data.db'
        
        self.session_id = session_id
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create schema including log_entries table."""
        # ... existing monitoring_data schema ...
        
        # Add log_entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                source TEXT NOT NULL,
                severity TEXT NOT NULL,
                facility TEXT,
                message TEXT NOT NULL,
                raw_line TEXT,
                process_context TEXT,
                FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
            )
        ''')
        
        # Add indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log_entries(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_session ON log_entries(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_severity ON log_entries(severity)')
        
        # Add session metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_metadata (
                session_id TEXT PRIMARY KEY,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT,
                log_collection_enabled BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def log_entries(self, log_entries: List[LogEntry], 
                   batch_size: int = 100) -> int:
        """
        Store log entries in batch for performance.
        
        Args:
            log_entries: List of LogEntry objects
            batch_size: Number of entries per batch insert
        
        Returns:
            Number of entries inserted
        """
        if not log_entries:
            return 0
        
        with self.db_lock:
            cursor = self.conn.cursor()
            inserted = 0
            
            # Batch insert for performance
            for i in range(0, len(log_entries), batch_size):
                batch = log_entries[i:i+batch_size]
                
                values = []
                for entry in batch:
                    # Convert process PIDs to JSON array
                    pids_json = json.dumps(entry.process_context) if entry.process_context else '[]'
                    
                    values.append((
                        self.session_id,
                        entry.timestamp.isoformat(),
                        entry.source_file,
                        entry.severity,
                        entry.facility,
                        entry.message,
                        entry.raw_line,
                        pids_json
                    ))
                
                cursor.executemany('''
                    INSERT INTO log_entries 
                    (session_id, timestamp, source, severity, facility, 
                     message, raw_line, process_context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
                
                inserted += len(values)
            
            self.conn.commit()
            
        return inserted
```

### Report Generation Workflow

```python
class DataExporter:
    def export_html(self, session_id: str = None, include_logs: bool = True) -> str:
        """
        Generate HTML report with monitoring data and logs.
        
        Args:
            session_id: Session to export, or use current
            include_logs: Whether to collect and include system logs
        
        Returns:
            Path to generated HTML report
        """
        # 1. Get monitoring data from remote/local DB
        monitoring_data = self._pull_monitoring_data(session_id)
        
        # 2. Determine time range
        start_time = min(sample['timestamp'] for sample in monitoring_data)
        end_time = max(sample['timestamp'] for sample in monitoring_data)
        
        # 3. Create session database and store monitoring data
        session_db = self._create_session_db(session_id)
        session_db.insert_monitoring_data(monitoring_data)
        
        # 4. Collect logs if enabled
        if include_logs:
            print(f"📋 Collecting logs from {start_time} to {end_time}...")
            
            config = self._get_log_config()
            log_monitor = LogMonitor(
                config, 
                mode=self._get_log_mode(),
                ssh_client=self._get_ssh_client(),
                adb_device=self._get_adb_device()
            )
            
            log_entries = log_monitor.collect_logs(start_time, end_time)
            print(f"✓ Collected {len(log_entries)} log entries")
            
            # Store in session database
            session_db.log_entries(log_entries)
        
        # 5. Generate HTML report with logs
        report_path = self._generate_html_with_logs(session_db, session_id)
        
        return report_path
```

## Benefits

### 1. **Self-Contained Reports**
- Each session has its own database
- No dependency on remote systems after generation
- Easy to archive, share, or analyze later

### 2. **Efficient Storage**
- Logs only stored when needed (report generation)
- Time-filtered: only logs from monitoring period
- Compressed in SQLite (better than text files)

### 3. **Easy Management**
- One directory per session
- Simple cleanup: `rm -rf reports/session_20251121_*`
- Clear organization: DB + HTML + CSV/JSON together

### 4. **Flexible Export**
- Generate multiple reports from same data
- Re-export with different filters
- Query database directly with SQL

### 5. **Correlation Ready**
- Monitoring data + logs in same DB
- Foreign key relationships
- Efficient JOIN queries for correlation

## Size Estimates

Typical session (1 hour, 1-second intervals):

```
monitoring_data:  3,600 rows × ~200 bytes  = ~720 KB
process_data:    36,000 rows × ~100 bytes  = ~3.6 MB
log_entries:      ~500 rows × ~200 bytes  = ~100 KB

Total database size: ~5 MB per hour
HTML report: ~500 KB (with embedded charts)

Per session total: ~6 MB
```

## Configuration

```yaml
# config/default.yaml

reports:
  output_dir: 'reports'           # Base directory for all reports
  session_db_enabled: true        # Use session-specific databases
  keep_sessions: 10               # Keep last N sessions, delete older
  auto_cleanup_days: 30           # Delete sessions older than N days

log_collection:
  enabled: true
  on_report_generation: true      # Collect logs when generating report
  sources:
    - /var/log/syslog
    - /var/log/kern.log
  keywords:
    - error
    - warning
    - critical
  max_log_lines: 1000
  anonymize_enabled: true
  log_timezone: 'local'           # 'local', 'utc', or timezone name
```

## Migration Path

1. **TASK-015**: Implement session database schema and log storage
2. **TASK-016**: Add log timeline visualization to HTML reports
3. **TASK-017**: Add detailed log table with search/filter
4. **TASK-018**: Implement process-log correlation

Current code is already 90% compatible - just needs session DB integration!
