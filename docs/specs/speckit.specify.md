# System Monitor Tool - Feature Enhancement Specification

## Project Context

**Project Name**: System Monitor Tool  
**Current Version**: 1.0  
**Target Version**: 1.1  
**Author**: TsaiGaggery  
**Date**: 2025-11-21

### Existing System Overview

The System Monitor Tool is a unified monitoring solution for Linux and Android devices with:
- Real-time CPU, GPU (Intel/NVIDIA/AMD), NPU, memory, network, and disk I/O monitoring
- Multiple modes: Local, Remote Linux (SSH), Android (ADB)
- PyQt5 GUI with real-time charts and CLI mode for headless environments
- Frequency control for CPU/GPU
- SQLite data logging with CSV/JSON/HTML export
- Comprehensive test suite (152 unit tests)

**Current Architecture**:
- Modular design with separate monitor modules (CPU, GPU, NPU, Memory, Network, Disk)
- PyQt5-based GUI with pyqtgraph for visualization
- SQLite backend for data persistence
- YAML configuration (`config/default.yaml`)
- Export system with HTML/CSV/JSON formats

## New Feature Requirements

### Feature 1: Top 5 Process Monitoring

**Priority**: High  
**Complexity**: Medium  
**Estimated Effort**: 3-5 days

#### User Story
```
As a system administrator
I want to see the top 5 processes consuming CPU resources in real-time
So that I can quickly identify resource-heavy applications
```

#### Acceptance Criteria
1. **Configuration Layer**
   - Add a new `tier2` section in `config/default.yaml`
   - Configuration includes:
     - `enabled: true/false` - toggle feature on/off
     - `update_interval: 1000` - refresh rate in milliseconds (can differ from main monitor)
     - `process_count: 5` - number of top processes to track (configurable)
     - `sort_by: cpu` - sorting metric (cpu, memory, both)

2. **Data Collection**
   - Create new `ProcessMonitor` class in `src/monitors/process_monitor.py`
   - Collect for each process:
     - Process ID (PID)
     - Process name
     - CPU usage percentage
     - Memory usage (RSS)
     - Command line arguments (truncated to 50 chars)
   - Update in real-time based on configured interval
   - Handle process lifecycle (started/terminated during monitoring)

3. **UI Integration**
   - Add new "Top Processes" section in Overview tab
   - Display format:
     ```
     Top 5 CPU-Intensive Processes
     ┌────────┬──────────────────┬──────────┬──────────┐
     │ PID    │ Process Name     │ CPU %    │ Memory   │
     ├────────┼──────────────────┼──────────┼──────────┤
     │ 12345  │ firefox          │ 45.2%    │ 2.3 GB   │
     │ 67890  │ chrome           │ 32.1%    │ 1.8 GB   │
     │ ...    │ ...              │ ...      │ ...      │
     └────────┴──────────────────┴──────────┴──────────┘
     ```
   - Color coding: >50% red, 30-50% orange, <30% green
   - Click on process to show command line in tooltip

4. **Data Persistence**
   - Store process data in SQLite database
   - New table: `process_data`
     - `id` (primary key)
     - `timestamp` (datetime)
     - `session_id` (foreign key to monitoring_data)
     - `pid` (integer)
     - `name` (text)
     - `cpu_percent` (real)
     - `memory_rss` (integer, bytes)
     - `cmdline` (text)
   - Index on `timestamp` and `session_id` for fast queries

5. **Mode Support**
   - **Local Mode**: Full support via psutil
   - **Remote Linux (SSH)**: Support via `ps` commands
   - **Android (ADB)**: Support via `top` command parsing

#### Non-Functional Requirements
- Process monitoring overhead < 2% CPU usage
- No UI freezing during process data collection (background thread)
- Handle edge cases: processes dying, permission denied, zombie processes

---

### Feature 2: System Log Collection in Reports

**Priority**: High  
**Complexity**: High  
**Estimated Effort**: 5-7 days

#### User Story
```
As a DevOps engineer
I want system logs captured during the monitoring period
So that I can correlate performance issues with system events
```

#### Acceptance Criteria

1. **Configuration Layer**
   - Add to `config/default.yaml` under new `log_collection` section:
     ```yaml
     log_collection:
       enabled: true
       sources:
         - /var/log/syslog
         - /var/log/kern.log
         - /var/log/dmesg
       keywords:
         - error
         - warning
         - critical
         - oom
         - segfault
         - gpu
         - thermal
       max_log_lines: 1000  # per file
       include_context_lines: 2  # lines before/after matched line
     ```

2. **Log Collection Module**
   - Create `src/monitors/log_monitor.py`
   - Functions:
     - `collect_logs(start_time, end_time)` - collects logs for time range
     - `parse_log_entry(line)` - extracts timestamp, severity, message
     - `filter_by_keywords(logs, keywords)` - filters relevant entries
     - `anonymize_sensitive_data(log)` - removes IPs, paths, usernames
   - Handle:
     - Log rotation (detect .1, .2.gz files)
     - Compressed logs (gzip support)
     - Permission denied (graceful degradation)
     - Large log files (streaming read, memory efficient)

3. **Report Integration**
   - Modify `src/storage/data_exporter.py`
   - Add new section in HTML report: "System Events Timeline"
   - Visualization:
     - Timeline chart with log events as vertical markers
     - Color-coded by severity (red=error, yellow=warning, blue=info)
     - Hoverable tooltips showing full log message
     - Overlay on existing CPU/Memory/GPU charts
   - Add new tab in HTML report: "Detailed Logs"
     - Filterable table with timestamp, source, severity, message
     - Searchable interface
     - Export filtered logs to text file

4. **Process-Log Correlation**
   - Cross-reference process data with log events
   - Identify processes mentioned in logs
   - Create correlation section:
     ```
     Process-Event Correlations
     ├─ firefox (PID 12345) 
     │  └─ 14:23:45 kernel: Out of memory: Kill process 12345 (firefox)
     ├─ Xorg (PID 1234)
     │  └─ 14:25:12 kernel: GPU hang detected
     ```

5. **Data Storage**
   - New table: `log_entries`
     ```sql
     CREATE TABLE log_entries (
       id INTEGER PRIMARY KEY,
       session_id INTEGER,
       timestamp DATETIME,
       source TEXT,
       severity TEXT,
       message TEXT,
       process_context TEXT,  -- related PIDs if found
       FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
     );
     ```
   - Index on `timestamp` and `session_id`

6. **Security & Privacy**
   - Require explicit user consent before collecting logs
   - Add checkbox in export dialog: "Include system logs (may contain sensitive info)"
   - Implement basic anonymization:
     - Replace `/home/<username>` with `/home/USER`
     - Replace IP addresses with `xxx.xxx.xxx.xxx`
     - Replace hostnames with `<hostname>`
   - Option to review logs before export

7. **Mode-Specific Implementation**
   - **Local Mode**: Direct file access with fallback to sudo
   - **Remote Linux (SSH)**: SSH commands with `sudo cat` for protected logs
   - **Android (ADB)**: Use `logcat -t <time>` for log retrieval

#### Non-Functional Requirements
- Log collection completes within 10 seconds for typical reports
- Handles log files up to 500MB efficiently
- No blocking of main monitoring during log collection (background thread)
- Graceful degradation if log access is denied

---

### Feature 3: AI-Powered Report Insights (GitHub Copilot Integration)

**Priority**: Medium  
**Complexity**: Medium-High  
**Estimated Effort**: 3-4 days

#### User Story
```
As a performance analyst
I want AI-generated insights from my monitoring reports
So that I can quickly understand system behavior without manual analysis
```

#### Acceptance Criteria

1. **Configuration Layer**
   - Add to `config/default.yaml`:
     ```yaml
     ai_insights:
       enabled: true
       provider: github_copilot  # future: claude, openai
       api_timeout: 30  # seconds
       max_report_size: 5  # MB for API submission
       insight_sections:
         - performance_summary
         - bottleneck_analysis
         - recommendations
         - anomaly_detection
     ```

2. **HTML Report Enhancement**
   - Add "AI Insights" button in HTML report header
   - Button opens modal/section with:
     - Loading spinner while processing
     - "Generate Insights" button
     - Display area for AI-generated content
   - Insights displayed as markdown-rendered text

3. **Data Preparation**
   - Create `src/ai/report_analyzer.py`
   - Extract report summary:
     ```json
     {
       "duration": "2 hours",
       "avg_cpu": 45.2,
       "max_cpu": 89.3,
       "avg_memory": 62.1,
       "max_memory": 87.4,
       "gpu_usage": {...},
       "top_processes": [...],
       "system_events": [
         {"time": "14:23:45", "event": "OOM killer activated"}
       ],
       "network_stats": {...},
       "disk_stats": {...}
     }
     ```

4. **GitHub Copilot Integration**
   - **Approach**: Use local GitHub Copilot CLI if available
   - Fallback: Provide instructions for using Copilot Chat manually
   - Workflow:
     1. Generate analysis prompt from report data
     2. Call `gh copilot suggest` or `gh copilot explain` (if installed)
     3. Parse and format response
     4. Display in HTML report
   
   - Prompt template:
     ```
     Analyze this system monitoring report and provide insights:
     
     System: {hostname}, {os_version}
     Duration: {duration}
     
     Performance Metrics:
     - Average CPU: {avg_cpu}%
     - Peak CPU: {max_cpu}%
     - Average Memory: {avg_memory}%
     - GPU Usage: {gpu_summary}
     
     Top Processes:
     {process_list}
     
     System Events:
     {event_list}
     
     Please provide:
     1. Performance summary (2-3 sentences)
     2. Identified bottlenecks
     3. Specific recommendations
     4. Any detected anomalies
     ```

5. **Alternative Implementation (If GitHub Copilot Unavailable)**
   - Implement local rule-based insights:
     - High CPU usage detection (>80% sustained)
     - Memory pressure indicators
     - Frequent process churn
     - Thermal throttling events
     - I/O bottlenecks
   - Template-based recommendations:
     ```python
     if avg_cpu > 80:
         insights.append("High CPU usage detected. Consider:")
         insights.append("- Identifying CPU-intensive processes")
         insights.append("- Checking for infinite loops or runaway processes")
     ```

6. **Export Integration**
   - Add insights to exported HTML report
   - Option to regenerate insights with different parameters
   - Cache insights in SQLite for quick retrieval
   - New table: `report_insights`
     ```sql
     CREATE TABLE report_insights (
       id INTEGER PRIMARY KEY,
       session_id INTEGER,
       generated_at DATETIME,
       provider TEXT,
       insights TEXT,
       prompt_used TEXT,
       FOREIGN KEY (session_id) REFERENCES monitoring_data(session_id)
     );
     ```

7. **User Experience**
   - Clear indication when using local rule-based vs AI insights
   - "Copy to clipboard" button for insights
   - "Regenerate" button to try again
   - Error handling with user-friendly messages:
     - "GitHub Copilot not available. Showing rule-based insights."
     - "API timeout. Please try again."

#### Non-Functional Requirements
- Insight generation completes within 30 seconds
- Works offline with rule-based fallback
- No external API keys required for basic functionality
- Privacy: User data not sent to external services without consent

---

## Technical Constraints

1. **Compatibility**
   - Must maintain backward compatibility with existing databases
   - Support Python 3.8+
   - Work on Ubuntu 18.04+

2. **Performance**
   - New features add < 5% overhead to monitoring
   - UI remains responsive (60 FPS)
   - Database queries optimized with proper indexing

3. **Security**
   - No hardcoded credentials
   - Secure handling of log data
   - User consent for log collection
   - Optional anonymization

4. **Testing**
   - Unit test coverage > 60% for new code
   - Integration tests for each feature
   - Manual testing checklist

## Success Criteria

1. **Feature 1 Success Metrics**
   - Top 5 processes displayed in < 1 second
   - Process data correctly captured for all modes
   - No performance degradation

2. **Feature 2 Success Metrics**
   - Logs correctly correlated with monitoring data
   - HTML reports include timeline visualization
   - Log collection completes in < 10 seconds

3. **Feature 3 Success Metrics**
   - Insights generated successfully (AI or rule-based)
   - Insights are actionable and relevant
   - Users can understand system behavior faster

## Out of Scope (Future Enhancements)

- Real-time alerting based on thresholds
- Machine learning anomaly detection
- Multi-user collaboration features
- Cloud sync for monitoring data
- Mobile app interface

## Dependencies

- **Existing**: psutil, PyQt5, pyqtgraph, sqlite3, pyyaml
- **New for Feature 1**: (none, uses existing psutil)
- **New for Feature 2**: (none, uses standard library)
- **New for Feature 3**: (optional) GitHub CLI, markdown renderer

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Log files too large | High | Medium | Streaming read, size limits, filtering |
| Permission denied for logs | Medium | High | Graceful degradation, user guidance |
| GitHub Copilot unavailable | Low | High | Rule-based fallback built-in |
| Process monitoring overhead | High | Low | Efficient psutil usage, configurable intervals |
| SQLite database size growth | Medium | Medium | Auto-cleanup, configurable retention |

## Approval & Sign-off

- [ ] Technical review completed
- [ ] Security review completed  
- [ ] UX/UI mockups approved
- [ ] Resource allocation confirmed
- [ ] Timeline approved

---

**Next Steps**: Proceed to `/speckit.plan` for technical design
