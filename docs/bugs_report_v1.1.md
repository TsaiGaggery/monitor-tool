# Bug Report & Fixes - Monitor Tool v1.1

## 1. Android Log Collection Failures

### Issue
Users reported "No log entries collected" despite logs being present on the device.

### Root Causes
1.  **Timezone Mismatch**: 
    *   Host queries were in UTC (e.g., `02:25 UTC`).
    *   Android `logcat` expects Local Time (e.g., `18:25 PST`).
    *   Result: `logcat -T` looked for logs in the future relative to the device clock.
2.  **Regex Parsing Failure**:
    *   Original Regex: `r'([^\s(]+)\s*'` (Assumed tags have no spaces).
    *   Actual Tags: `Audio Flinger`, `System Server` (Contain spaces).
    *   Result: Valid log lines were rejected by the parser.

### Fixes
*   **Timezone Awareness**: `LogMonitor` now detects device timezone offset via `adb shell date +%z` and adjusts the query start time to Device Local Time.
*   **Robust Parsing**: Updated regex to `r'(.*?)\s*'` (Non-greedy match) to correctly capture tags with spaces.

## 2. Android SQLite Data Persistence

### Issue
"No data found" in the report for Android sessions, and the on-device database was empty.

### Root Causes
1.  **Database Disabled**: The Python controller (`adb_monitor_raw.py`) was explicitly passing `0` (disable) to the device script for the database flag.
2.  **Script Syntax Errors**: 
    *   `android_monitor_raw.sh` used `read <<<` which is fragile with empty inputs.
    *   `$npu_info` was undefined (hardcoded to "none" only in comments/logic but not variable), causing SQL syntax errors (missing value).
    *   `$net_rx` / `$net_tx` could be empty, causing SQL errors.
3.  **Data Loss on Restart**: The script was `rm`ing the database on startup.

### Fixes
*   **Enable Database**: Updated `adb_monitor_raw.py` to pass `1` (enable) for the DB flag.
*   **Robust Scripting**: 
    *   Updated `android_monitor_raw.sh` to use `set --` for variable assignment.
    *   Added default values (`:-0`) for all metrics.
    *   Implemented `get_npu_info` for proper NPU detection.
*   **Data Safety**: Changed `rm` to `mv ... .bak` to preserve previous session data.

## 3. NPU Detection

### Issue
NPU information was hardcoded to "none" or missing.

### Fixes
*   Added `get_npu_info` function in `android_monitor_raw.sh` to detect:
    *   Intel NPU (`/dev/accel/accel0`)
    *   Intel VPU (`/sys/class/intel_vpu`)
    *   Generic NPU (`/dev/gnpu`)

## 4. Visualization

### Issue
Log markers were not visible on the timeline.

### Fixes
*   Implemented Chart.js annotations plugin in `report.html` to render log entries as vertical lines on the performance charts.
