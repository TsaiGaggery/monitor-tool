# Tier 1 Metrics - Advanced Debugging Plugin

## Overview

Tier 1 metrics are **optional advanced monitoring metrics** designed for debugging system performance issues with minimal overhead. They can be enabled/disabled via configuration to control collection cost.

## Design Principles

- **Plugin Architecture**: Completely optional, disabled by default
- **Minimal Overhead**: +33% collection time (~12ms extra per 1Hz sample)
- **High Value**: Essential for debugging scheduler issues, IRQ storms, load spikes
- **Graceful Degradation**: All code handles missing Tier 1 data (NULL values in database)

## Metrics Included

### 1. Context Switches (ctxt)
- **Type**: INTEGER (cumulative counter)
- **Source**: `/proc/stat` → `ctxt` field
- **Cost**: No extra I/O (already reading /proc/stat)
- **Export**: Delta between samples (context_switches per interval)
- **Use Case**: Detect excessive context switching (scheduler thrashing)

### 2. Load Average (load_avg_1m, load_avg_5m, load_avg_15m)
- **Type**: REAL (floating point)
- **Source**: `/proc/loadavg` → first 3 fields
- **Cost**: +1 file read (~100 bytes, ~50-200µs)
- **Export**: Absolute values (1min, 5min, 15min averages)
- **Use Case**: System load trends, capacity planning

### 3. Process Counts (procs_running, procs_blocked)
- **Type**: INTEGER
- **Source**: `/proc/stat` → `procs_running`, `procs_blocked` fields
- **Cost**: No extra I/O (already reading /proc/stat)
- **Export**: Absolute values (count of running/blocked processes)
- **Use Case**: Detect process storms, D-state hangs

### 4. Per-Core IRQ/Softirq Percentages (per_core_irq_pct, per_core_softirq_pct)
- **Type**: TEXT (comma-separated floats: "0.15,0.23,0.18,...")
- **Source**: Calculated from existing `per_core_raw` data
- **Cost**: No extra I/O, minimal CPU for percentage calculation
- **Export**: Array of floats, one per CPU core
- **Use Case**: Identify IRQ imbalance, softirq bottlenecks, network/disk interrupt overhead

## Performance Impact

Based on benchmark results (see `scripts/benchmark_cpu_time.sh`):

| Metric | Collection Time | CPU @ 1Hz | I/O Cost |
|--------|----------------|-----------|----------|
| **Baseline (current)** | ~38ms | 0.38% | 4 files |
| **Tier 1 additions** | +12ms | +0.12% | +1 file (/proc/loadavg) |
| **Total with Tier 1** | ~51ms | 0.51% | 5 files |

**Conclusion**: +33% collection time, but still < 0.6% CPU at 1Hz monitoring.

## Configuration

Enable in `config/default.yaml`:

```yaml
monitoring:
  tier1_metrics:
    enabled: true  # Default: false
```

## Implementation Details

### Database Schema

Both `linux_monitor_remote.sh` and `android_monitor_raw.sh` use unified schema:

```sql
CREATE TABLE raw_samples (
    ...existing columns...
    -- Tier 1 metrics (optional, NULL if disabled)
    ctxt INTEGER,
    load_avg_1m REAL,
    load_avg_5m REAL,
    load_avg_15m REAL,
    procs_running INTEGER,
    procs_blocked INTEGER,
    per_core_irq_pct TEXT,
    per_core_softirq_pct TEXT
);
```

### Collection Scripts

Both monitoring scripts accept `ENABLE_TIER1` parameter:

**Linux:**
```bash
ssh user@host "bash -s" < linux_monitor_remote.sh 1 1  # interval=1s, tier1=enabled
```

**Android:**
```bash
adb shell /data/local/tmp/android_monitor_raw.sh 1 1  # interval=1s, tier1=enabled
```

### JSON Streaming Format

When Tier 1 is enabled, JSON output includes additional fields:

```json
{
  "timestamp_ms": 1234567890123,
  ...existing fields...
  "ctxt": 123456789,
  "load_avg_1m": 1.25,
  "load_avg_5m": 1.10,
  "load_avg_15m": 0.95,
  "procs_running": 3,
  "procs_blocked": 0,
  "per_core_irq_pct": [0.15, 0.23, 0.18, 0.20],
  "per_core_softirq_pct": [2.50, 3.10, 2.80, 2.90]
}
```

When disabled, these fields are `NULL` or omitted.

### Export Format

**CSV/JSON exports** include Tier 1 fields when available:

```csv
timestamp,cpu_usage_total,tier1_context_switches,tier1_load_avg_1min,...
2025-11-18 10:30:00,45.2,15234,1.25,...
```

**HTML reports** include additional charts:
1. Context Switches (line chart)
2. Load Average (3 lines: 1m, 5m, 15m)
3. Running/Blocked Processes (stacked area)
4. Per-Core IRQ% (stacked area chart)

### Data Processing

`data_exporter.py` processes Tier 1 metrics in both `_process_ssh_raw_data()` and `_process_android_raw_data()`:

```python
# Tier 1 metrics (optional, may be NULL/None if disabled)
if 'ctxt' in raw_data and raw_data['ctxt'] is not None:
    sample['tier1'] = {
        'context_switches': delta_ctxt,  # Delta from previous sample
        'load_average': {'1min': load_1m, '5min': load_5m, '15min': load_15m},
        'processes': {'running': procs_running, 'blocked': procs_blocked},
        'per_core_irq_pct': [0.15, 0.23, ...],  # Parsed from CSV string
        'per_core_softirq_pct': [2.50, 3.10, ...]
    }
```

## Usage Examples

### Enable Tier 1 for Debugging

When investigating performance issues:

1. Edit `config/default.yaml`:
   ```yaml
   tier1_metrics:
     enabled: true
   ```

2. Restart monitoring

3. Export data includes Tier 1 metrics:
   ```bash
   python src/cli_monitor.py --export-html report.html
   ```

### Interpreting Tier 1 Data

**High Context Switches:**
- \> 50k/sec: Possible scheduler thrashing
- Check: Many short-lived processes or excessive threading

**High Load Average:**
- load_1m > CPU count: System overloaded
- load_1m >> load_15m: Recent spike (investigate current processes)
- load_1m << load_15m: Load decreasing (past issue)

**Blocked Processes:**
- procs_blocked > 0: I/O bottleneck or D-state hang
- Check: Disk health, NFS mounts, unresponsive devices

**IRQ Imbalance:**
- One core with >> 5% IRQ: Interrupt affinity issue
- All cores with high softirq: Network/disk saturation

## Future Enhancements (Tier 2)

**Deferred due to higher overhead:**
- Memory breakdown (Buffers, Cached, Slab)
- Top IRQ sources (/proc/interrupts)
- Softirq types (/proc/softirqs)

Can be added later if needed with similar plugin architecture.

## Testing

Benchmark scripts available:
- `scripts/benchmark_metrics.sh` - Individual metric costs
- `scripts/benchmark_realistic.sh` - Realistic workload simulation
- `scripts/benchmark_cpu_time.sh` - Pure CPU time measurement

Run tests:
```bash
./scripts/benchmark_cpu_time.sh
```

## References

- Benchmark results: `scripts/benchmark_*.sh`
- Configuration: `config/default.yaml`
- Schema: `scripts/linux_monitor_remote.sh:18` and `scripts/android_monitor_raw.sh:13`
- Processing: `src/storage/data_exporter.py:_process_*_raw_data()`
