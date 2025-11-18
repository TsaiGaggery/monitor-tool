# Remote Linux SSH Monitoring

Monitor remote Linux systems via SSH with streaming JSON data architecture.

## Architecture

Similar to Android ADB monitoring, the remote Linux implementation uses:

1. **Remote Script** (`linux_monitor_remote.sh`): Runs on the remote Linux host, collects raw system data and streams JSON output
2. **SSH Transport** (`SSHMonitorRaw`): Establishes SSH connection and receives JSON stream
3. **Data Source** (`RemoteLinuxDataSource`): Parses JSON and provides unified interface

```
┌─────────────────┐       SSH        ┌──────────────────────┐
│   Local GUI/CLI │ ←─────────────→  │  Remote Linux Host   │
│  (data_source)  │   JSON Stream    │  (monitor script)    │
└─────────────────┘                  └──────────────────────┘
         ↓                                      ↓
    Parse JSON                          Collect raw data:
    Calculate metrics                   - /proc/stat (CPU)
    Display charts                      - /proc/meminfo (RAM)
                                       - nvidia-smi (GPU)
                                       - /proc/net/dev (NET)
                                       - /proc/diskstats (Disk)
                                       - Store in SQLite DB
```

## Features

- ✅ Real-time CPU monitoring (total + per-core usage, frequency, temperature)
- ✅ Memory monitoring (RAM usage)
- ✅ GPU monitoring (NVIDIA via nvidia-smi)
- ✅ Network monitoring (upload/download speeds)
- ✅ Disk I/O monitoring (read/write speeds)
- ✅ Remote database storage (`/tmp/monitor_tool_${USER}.db`)
- ✅ SSH password or key-based authentication
- ✅ Configurable monitoring interval
- ✅ Unified GUI/CLI interface

## Requirements

### Local System

- Python 3.6+
- paramiko library (`pip install paramiko`)
- monitor-tool installed

### Remote Linux System

**Required packages:**
- `bash` - Bourne Again Shell
- `awk` - Text processing (gawk or mawk)
- `grep` - Pattern matching
- `cat` - File concatenation utilities
- `date` - Date/time utilities
- `sqlite3` - SQLite database (for data storage)

**Optional:**
- `nvidia-smi` - For NVIDIA GPU monitoring

**Auto-Detection:**
The tool **automatically checks** for required packages when connecting. If any are missing, it will:
1. Display which packages are missing
2. Show installation commands for your distro
3. Stop the connection (won't run with missing dependencies)

Example output when missing packages:
```
✅ SSH connected to user@remote-host:22
🔍 Checking remote dependencies...
   Found:
     bash         ✓
     awk          ✓
     grep         ✓
     cat          ✓
     date         ✓

❌ Missing required packages on remote host remote-host:
     sqlite3      - SQLite database (REQUIRED for data storage)

📦 Install missing packages:
   Ubuntu/Debian:
     sudo apt-get install bash gawk grep coreutils sqlite3
   RHEL/CentOS:
     sudo yum install bash gawk grep coreutils sqlite
   Arch Linux:
     sudo pacman -S bash gawk grep coreutils sqlite
```

### Installation on Remote Host

**Ubuntu/Debian:**
```bash
sudo apt-get install bash gawk grep coreutils sqlite3
```

**RHEL/CentOS/Fedora:**
```bash
sudo yum install bash gawk grep coreutils sqlite
```

**Arch Linux:**
```bash
sudo pacman -S bash gawk grep coreutils sqlite
```

## Usage

### GUI Mode

```bash
# With password authentication
monitor-tool --ssh --host <remote_host> --user <username>

# With SSH key
monitor-tool --ssh --host <remote_host> --user <username> --key ~/.ssh/id_rsa

# Custom SSH port
monitor-tool --ssh --host <remote_host> --user <username> --ssh-port 2222
```

### CLI Mode

```bash
# With password authentication
monitor-tool-cli --ssh --host <remote_host> --user <username>

# With SSH key
monitor-tool-cli --ssh --host <remote_host> --user <username> --key ~/.ssh/id_rsa

# Custom interval (for monitoring script)
# Note: interval is set in RemoteLinuxDataSource constructor, default is 1 second
```

## How It Works

### 1. SSH Connection

When you start monitoring:

1. `SSHMonitorRaw` establishes SSH connection using paramiko
2. Reads local `linux_monitor_remote.sh` script
3. Executes script on remote host via SSH stdin: `bash -s <interval>`

### 2. Remote Monitoring Script

The `linux_monitor_remote.sh` script:

1. Creates SQLite database at `/tmp/monitor_tool_${USER}.db`
2. Enters monitoring loop:
   - Collects raw data from /proc filesystem
   - Parses CPU, memory, GPU, network, disk metrics
   - Inserts data into SQLite database
   - Outputs JSON to stdout
   - Sleeps until next interval

### 3. JSON Streaming

JSON output format:
```json
{
  "timestamp_ms": 1699999999999,
  "cpu_raw": {"user": 123, "nice": 0, "sys": 45, "idle": 890, ...},
  "per_core_raw": [{"user": 30, "nice": 0, ...}, ...],
  "per_core_freq_khz": [2400000, 2400000, ...],
  "cpu_temp_millideg": 45000,
  "mem_total_kb": 16000000,
  "mem_free_kb": 8000000,
  "mem_available_kb": 10000000,
  "gpu_info": "0, NVIDIA GeForce RTX 3080, 45, 2048, 10240, 65, 1800",
  "net_rx_bytes": 12345678,
  "net_tx_bytes": 87654321,
  "disk_read_sectors": 123456,
  "disk_write_sectors": 654321
}
```

### 4. Local Processing

`RemoteLinuxDataSource`:

1. Receives JSON line from SSH stdout
2. Parses raw data
3. Calculates deltas (CPU usage, network speeds, disk speeds)
4. Converts to standardized format
5. Returns to GUI/CLI for display

## Database Storage

Similar to Android monitoring, data is stored on the remote system:

- Location: `/tmp/monitor_tool_${USER}.db`
- Table: `raw_samples`
- Columns: timestamp, CPU raw values, memory, GPU, network, disk
- Index: timestamp for efficient queries
- Purpose: Enable data export and historical analysis

## Testing

### Quick Test

```bash
cd /home/gaggery/monitor-tool
python3 tests/test_ssh_streaming.py
```

This will:
1. Prompt for connection details (host, user, authentication)
2. Connect to remote system
3. Collect 3 samples with specified interval
4. Display CPU, memory, GPU, network, disk metrics
5. Disconnect cleanly

### Manual Testing

You can also test the remote script directly:

```bash
# On remote system
bash /path/to/linux_monitor_remote.sh 1

# You should see JSON output every second
```

## Troubleshooting

### Connection Issues

**SSH connection fails:**
- Check host/port/username are correct
- Verify firewall allows SSH (port 22 or custom)
- Test with: `ssh username@hostname`

**Permission denied:**
- Check SSH password is correct
- Or verify SSH key is authorized: `~/.ssh/authorized_keys`

### Monitoring Issues

**No CPU temperature:**
- Some systems don't expose thermal sensors
- Check: `cat /sys/class/thermal/thermal_zone*/temp`

**No GPU detected:**
- Install nvidia-smi: `sudo apt install nvidia-utils`
- Or script falls back to "none"

**Network/Disk speeds are 0:**
- First sample has no previous data for delta calculation
- Wait for second sample to see actual speeds

### Script Issues

**Script doesn't start:**
- Check remote has bash: `which bash`
- Check sqlite3 installed: `which sqlite3`

**Script output garbled:**
- Disable colored prompts that interfere with JSON
- Script outputs status to stderr, JSON to stdout

## Comparison with Other Methods

| Feature | SSH Streaming | psutil over SSH | Direct psutil |
|---------|--------------|-----------------|---------------|
| Installation on remote | None (uses /proc) | Requires Python + psutil | N/A |
| Data format | JSON (structured) | Python objects | Python objects |
| Database | Remote SQLite | Not available | Local SQLite |
| Transport overhead | Low (1 JSON/interval) | Medium (Python RPC) | None |
| Code reuse | High (like Android) | Low (new implementation) | Full |
| Dependencies | bash, sqlite3, /proc | Python, psutil, SSH | Python, psutil |

## Architecture Benefits

1. **Minimal Remote Requirements**: Only bash and standard Linux /proc
2. **Consistent with Android**: Same streaming JSON approach
3. **Remote Database**: Data stored on monitored system
4. **Low Overhead**: Single JSON message per interval
5. **Easy Testing**: Script can run standalone for debugging

## Future Enhancements

- [ ] Sudo support for privileged operations
- [ ] Intel GPU support (intel_gpu_top)
- [ ] AMD GPU support (radeontop)
- [ ] NPU monitoring
- [ ] Partition disk usage (df command)
- [ ] Export functionality from remote database
- [ ] Connection retry logic
- [ ] Multiple remote hosts simultaneously
