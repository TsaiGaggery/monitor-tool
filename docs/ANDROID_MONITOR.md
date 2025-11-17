# Android Monitor

Monitor Android device system performance and generate HTML reports using the same architecture as the desktop monitor-tool.

## Architecture

The Android monitor **reuses the desktop monitor's architecture**:

- **Data Collection**: Shell script reads `/proc/stat`, `/proc/meminfo`, `/sys/class/drm/` (similar to `CPUMonitor`, `MemoryMonitor`, `GPUMonitor`)
- **Database Logging**: SQLite on device with same schema as `DataLogger`
- **Report Generation**: Desktop PC uses existing `DataExporter` to generate HTML reports
- **Update Mechanism**: 1-second interval loop (like `QTimer` in GUI or `_background_logging_worker` in CLI)

## Requirements

### Android Device
- Android 5.0+ (API 21+)
- ADB debugging enabled
- SQLite3 (built-in on Android)

### Desktop PC
- ADB tools installed
- Python 3.7+ with monitor-tool dependencies
- Network connection to Android device (USB or WiFi)

## Quick Start

### 1. Connect to Android Device

```bash
# Via USB
adb devices

# Via WiFi (device IP: 192.168.1.100)
adb connect 192.168.1.100:5555
```

### 2. Push Monitor Script

```bash
./scripts/android_push.sh
```

This pushes `android_monitor.sh` to `/data/local/tmp/` on the device.

### 3. Start Monitoring

```bash
# Default: 1 second interval
./scripts/android_start.sh

# Custom interval (e.g., 0.5 seconds)
./scripts/android_start.sh 0.5
```

The monitor runs in the background and logs data to SQLite.

### 4. View Logs (Optional)

```bash
adb shell tail -f /data/local/tmp/monitor.log
```

### 5. Stop Monitoring

```bash
./scripts/android_stop.sh
```

### 6. Generate HTML Report

```bash
./scripts/android_pull.sh
```

This will:
1. Pull database from device (`/data/local/tmp/monitor.db`)
2. Save to `android_monitor_data.db` on PC
3. Generate HTML report using `DataExporter`
4. Save to `reports/YYYY-MM-DD/android_report_TIMESTAMP.html`

## Workflow Scripts

### `android_push.sh`
Push monitor script to device and set permissions.

### `android_start.sh [interval]`
Start monitoring on device.
- `interval`: Update interval in seconds (default: 1)

### `android_stop.sh`
Stop monitoring process on device.

### `android_pull.sh`
Pull database and generate HTML report.

## Database Schema

The Android monitor uses the **same schema as `DataLogger`**:

```sql
CREATE TABLE monitoring_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    cpu_usage REAL,
    cpu_freq_avg REAL,
    cpu_temp REAL,
    memory_total REAL,
    memory_used REAL,
    memory_percent REAL,
    gpu_usage REAL,
    gpu_freq REAL,
    gpu_temp REAL,
    data_json TEXT  -- Full JSON data for all metrics
);
```

## Supported Hardware

### CPU
- **x86/x64**: Intel, AMD (reads `/proc/cpuinfo`, `/sys/devices/system/cpu/`)
- **ARM**: Qualcomm, MediaTek, Samsung Exynos (reads `/proc/stat`)

### Memory
- **All platforms**: `/proc/meminfo`

### GPU
- **Intel GPU (x86)**: `/sys/class/drm/card0/gt_cur_freq_mhz`
- **Qualcomm Adreno**: `/sys/class/kgsl/kgsl-3d0/` (requires root)
- **ARM Mali**: `/sys/class/misc/mali0/` (device-dependent)

### Temperature
- **Thermal Zones**: `/sys/class/thermal/thermal_zone*/temp`
- **Hwmon**: `/sys/class/hwmon/hwmon*/temp*_input`

## Example Usage

### Development Testing (30 seconds)

```bash
# Start monitoring
./scripts/android_start.sh

# Run your app/test on Android device
# ... wait 30 seconds ...

# Stop and generate report
./scripts/android_stop.sh
./scripts/android_pull.sh

# Open report
xdg-open reports/*/android_report_*.html
```

### Performance Benchmark (Custom Interval)

```bash
# High-frequency monitoring (0.1 second = 10 Hz)
./scripts/android_start.sh 0.1

# Run benchmark
# ...

# Stop and analyze
./scripts/android_stop.sh
./scripts/android_pull.sh
```

### Long-term Monitoring

```bash
# Start monitoring (1 second interval)
./scripts/android_start.sh

# Let it run for hours/days...
# Device can sleep, monitor continues in background

# Pull data anytime
./scripts/android_pull.sh
```

## Comparison with Desktop Monitor

| Feature | Desktop GUI | Desktop CLI | Android |
|---------|-------------|-------------|---------|
| Update Interval | QTimer (1s) | Background Thread (1s) | Shell Loop (1s) |
| Data Collection | Python Monitors | Python Monitors | Shell Script |
| Database | SQLite (DataLogger) | SQLite (DataLogger) | SQLite (Same Schema) |
| Export | DataExporter | DataExporter | DataExporter (on PC) |
| UI | PyQt5 Charts | Curses Text | None (headless) |
| Report | HTML/CSV/JSON | HTML/CSV/JSON | HTML (generated on PC) |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│ Android Device                                          │
│                                                         │
│  android_monitor.sh (Shell Script)                     │
│  ├── while loop (1s interval)                          │
│  ├── get_cpu_usage() → /proc/stat                      │
│  ├── get_memory_info() → /proc/meminfo                 │
│  ├── get_gpu_info() → /sys/class/drm/                  │
│  └── SQLite INSERT → /data/local/tmp/monitor.db        │
│                                                         │
└─────────────────────────────────────────────────────────┘
                        │
                        │ adb pull
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Desktop PC                                              │
│                                                         │
│  android_pull.sh (Python Script)                       │
│  ├── ADB pull database                                 │
│  ├── DataExporter.add_sample() (reuse!)                │
│  └── DataExporter.export_html() → HTML Report          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Troubleshooting

### No data collected
- Check if monitor is running: `adb shell pgrep -f android_monitor.sh`
- View logs: `adb shell cat /data/local/tmp/monitor.log`

### SQLite errors
- Ensure SQLite3 is available: `adb shell which sqlite3`
- Check database: `adb shell "sqlite3 /data/local/tmp/monitor.db 'SELECT COUNT(*) FROM monitoring_data;'"`

### GPU data not available
- Some devices require root for GPU metrics
- Check available paths: `adb shell ls -la /sys/class/kgsl/` or `adb shell ls -la /sys/class/drm/`

### ADB connection lost
- Reconnect: `adb connect <device_ip>:5555`
- Check network: `ping <device_ip>`

## Advanced Configuration

### Custom Database Location

```bash
# Start with custom DB path
adb shell "/data/local/tmp/android_monitor.sh 1 /sdcard/custom_monitor.db"
```

### Custom Metrics (Modify Script)

Edit `scripts/android_monitor.sh` to add new metrics:

```bash
# Add new function
get_custom_metric() {
    # Your custom metric collection
    echo "value"
}

# Add to main loop
custom_value=$(get_custom_metric)

# Add to SQL INSERT
INSERT INTO monitoring_data (..., custom_field) VALUES (..., $custom_value);
```

## Future Enhancements

- [ ] ARM-specific GPU support (Mali, Adreno with root)
- [ ] Network I/O monitoring (`/proc/net/dev`)
- [ ] Disk I/O monitoring (`/proc/diskstats`)
- [ ] Per-app CPU/Memory tracking
- [ ] Battery monitoring (`/sys/class/power_supply/`)
- [ ] Real-time streaming (WebSocket from device to PC)

## License

Same as monitor-tool (see main README).
