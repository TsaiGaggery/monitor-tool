#!/system/bin/sh
# Android System Monitor - Raw Data Streaming + SQLite Storage
# Outputs RAW data only - all calculations done on host side
# Also stores data in local SQLite database for accurate export
# Usage: adb shell /data/local/tmp/android_monitor_stream.sh [interval] [enable_tier1]

INTERVAL=${1:-1}
ENABLE_TIER1=${2:-0}  # 0=disabled, 1=enabled (Tier 1 metrics: ctxt, load, procs, irq%)
DB_PATH="/data/local/tmp/monitor.db"

# Initialize database (recreate to ensure schema is up to date)
init_database() {
    # Remove old database if it exists to avoid schema mismatch
    rm -f "$DB_PATH"
    
    # Use printf instead of heredoc since script is piped through ADB
    printf "%s\n" \
        "CREATE TABLE IF NOT EXISTS raw_samples (" \
        "    id INTEGER PRIMARY KEY AUTOINCREMENT," \
        "    timestamp INTEGER NOT NULL," \
        "    timestamp_ms INTEGER," \
        "    cpu_user INTEGER," \
        "    cpu_nice INTEGER," \
        "    cpu_sys INTEGER," \
        "    cpu_idle INTEGER," \
        "    cpu_iowait INTEGER," \
        "    cpu_irq INTEGER," \
        "    cpu_softirq INTEGER," \
        "    cpu_steal INTEGER," \
        "    per_core_raw TEXT," \
        "    per_core_freq_khz TEXT," \
        "    cpu_temp_millideg INTEGER," \
        "    mem_total_kb INTEGER," \
        "    mem_free_kb INTEGER," \
        "    mem_available_kb INTEGER," \
        "    gpu_driver TEXT," \
        "    gpu_freq_mhz INTEGER," \
        "    gpu_runtime_ms INTEGER," \
        "    gpu_memory_used_bytes INTEGER," \
        "    gpu_memory_total_bytes INTEGER," \
        "    npu_info TEXT," \
        "    net_rx_bytes INTEGER," \
        "    net_tx_bytes INTEGER," \
        "    disk_read_sectors INTEGER," \
        "    disk_write_sectors INTEGER," \
        "    ctxt INTEGER," \
        "    load_avg_1m REAL," \
        "    load_avg_5m REAL," \
        "    load_avg_15m REAL," \
        "    procs_running INTEGER," \
        "    procs_blocked INTEGER," \
        "    per_core_irq_pct TEXT," \
        "    per_core_softirq_pct TEXT," \
        "    interrupt_data TEXT," \
        "    monitor_cpu_utime INTEGER," \
        "    monitor_cpu_stime INTEGER" \
        ");" \
        "CREATE INDEX IF NOT EXISTS idx_timestamp ON raw_samples(timestamp);" \
        | sqlite3 "$DB_PATH"
}

# Get raw CPU stats from /proc/stat
# Returns: user nice system idle iowait irq softirq steal
get_cpu_raw() {
    awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat
}

# Get raw per-core CPU stats
# Returns JSON array of objects: [{"user":x,"nice":y,...}, ...]
get_per_core_raw() {
    awk '/^cpu[0-9]/ {
        printf "{\"user\":%s,\"nice\":%s,\"sys\":%s,\"idle\":%s,\"iowait\":%s,\"irq\":%s,\"softirq\":%s,\"steal\":%s},", $2,$3,$4,$5,$6,$7,$8,$9
    }' /proc/stat | sed 's/,$//'
}

# Get CPU frequency per-core (kHz)
get_per_core_freq() {
    result=""
    for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
        if [ -f "$cpu_dir/cpufreq/scaling_cur_freq" ]; then
            freq=$(cat "$cpu_dir/cpufreq/scaling_cur_freq")
        else
            freq=0
        fi
        result="${result}${freq},"
    done
    echo "${result%,}"  # Remove trailing comma
}

# Get CPU temperature (millidegrees)
get_cpu_temp_raw() {
    # Try TCPU (actual CPU temp) first
    if [ -f /sys/class/thermal/thermal_zone5/temp ]; then
        cat /sys/class/thermal/thermal_zone5/temp
    # Try x86_pkg_temp (package temp)
    elif [ -f /sys/class/thermal/thermal_zone7/temp ]; then
        cat /sys/class/thermal/thermal_zone7/temp
    # Fallback to zone0 (generic)
    elif [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        cat /sys/class/thermal/thermal_zone0/temp
    elif [ -f /sys/class/hwmon/hwmon0/temp1_input ]; then
        cat /sys/class/hwmon/hwmon0/temp1_input
    else
        echo "0"
    fi
}

# Get monitor CPU usage (utime and stime for this script and its children)
get_monitor_cpu_usage() {
    monitor_pid=$$
    total_utime=0
    total_stime=0
    
    # Get CPU ticks for this process and all children
    for pid in $(ps -o pid= --ppid $monitor_pid 2>/dev/null; echo $monitor_pid); do
        if [ -f "/proc/$pid/stat" ]; then
            read -r _ _ _ _ _ _ _ _ _ _ _ _ _ utime stime _ < /proc/$pid/stat 2>/dev/null
            total_utime=$((total_utime + utime))
            total_stime=$((total_stime + stime))
        fi
    done
    
    echo "$total_utime,$total_stime"
}

# Get Tier 1 metrics (context switches, load average, process counts)
get_tier1_metrics() {
    if [ "$ENABLE_TIER1" != "1" ]; then
        # Return null for JSON compatibility (lowercase, not NULL)
        echo "null null null null null null \"\" \"\""
        return
    fi
    
    # Context switches (total system-wide)
    ctxt=$(awk '/^ctxt / {print $2}' /proc/stat)
    
    # Load average (1m, 5m, 15m) - Android shell compatible
    loadavg_line=$(cat /proc/loadavg)
    load_1m=$(echo "$loadavg_line" | awk '{print $1}')
    load_5m=$(echo "$loadavg_line" | awk '{print $2}')
    load_15m=$(echo "$loadavg_line" | awk '{print $3}')
    procs_running_slash_total=$(echo "$loadavg_line" | awk '{print $4}')
    procs_total=$(echo "$procs_running_slash_total" | cut -d'/' -f2)
    
    # Process counts (currently running, blocked)
    procs_running=$(awk '/^procs_running / {print $2}' /proc/stat)
    procs_blocked=$(awk '/^procs_blocked / {print $2}' /proc/stat)
    
    # Calculate per-core IRQ and softirq percentages
    per_core_irq_pct=$(awk '/^cpu[0-9]/ {
        total = $2 + $3 + $4 + $5 + $6 + $7 + $8 + $9
        if (total > 0) {
            irq_pct = ($7 * 100.0) / total
            printf "%.2f,", irq_pct
        } else {
            printf "0.00,"
        }
    }' /proc/stat | sed 's/,$//')
    
    per_core_softirq_pct=$(awk '/^cpu[0-9]/ {
        total = $2 + $3 + $4 + $5 + $6 + $7 + $8 + $9
        if (total > 0) {
            softirq_pct = ($8 * 100.0) / total
            printf "%.2f,", softirq_pct
        } else {
            printf "0.00,"
        }
    }' /proc/stat | sed 's/,$//')
    
    echo "$ctxt $load_1m $load_5m $load_15m $procs_running $procs_blocked $per_core_irq_pct $per_core_softirq_pct"
}

# Get interrupt distribution data
# Returns JSON with top device interrupts and per-CPU totals
get_interrupt_data() {
    if [ "$ENABLE_TIER1" != "1" ]; then
        echo "null"
        return
    fi
    
    # Parse /proc/interrupts to get top device interrupts
    # Format: IRQ: CPU0 CPU1 ... CPU15 type name
    # We want to track device interrupts (MSI/MSIX/IO-APIC), not system ones (LOC/CAL/TLB/RES)
    
    local top_interrupts=$(cat /proc/interrupts | awk '
    BEGIN { 
        num_cpus = 0
    }
    NR == 1 {
        # Count CPUs from header
        for (i = 1; i <= NF; i++) {
            if ($i ~ /CPU[0-9]+/) num_cpus++
        }
        next
    }
    $1 ~ /^[0-9]+:$/ {
        # Device interrupt line (numbered IRQ)
        irq = $1
        gsub(/:/, "", irq)
        
        # Sum total interrupts across all CPUs
        total = 0
        cpu_counts = ""
        primary_cpu = -1
        max_count = 0
        
        for (i = 2; i <= num_cpus + 1; i++) {
            count = $i + 0  # Convert to number
            total += count
            if (count > max_count) {
                max_count = count
                primary_cpu = i - 2
            }
            if (i > 2) cpu_counts = cpu_counts ","
            cpu_counts = cpu_counts count
        }
        
        # Get interrupt name (everything after CPU columns and type)
        name = ""
        for (i = num_cpus + 3; i <= NF; i++) {
            if (name != "") name = name " "
            name = name $i
        }
        
        # Escape special characters in name for JSON
        # Replace backslash, quotes, and control characters
        gsub(/\\/, "\\\\", name)
        gsub(/"/, "\\\"", name)
        gsub(/\t/, " ", name)
        gsub(/\r/, "", name)
        gsub(/\n/, "", name)
        
        # Only track interrupts with significant activity (>1000 total)
        if (total > 1000) {
            # Format: total|irq|primary_cpu|name|cpu_counts (total first for sorting)
            printf "%020d|%s|%s|%s|%s\n", total, irq, primary_cpu, name, cpu_counts
        }
    }
    ' | sort -rn | head -10 | awk -F'|' '
    BEGIN {
        printf "{\"interrupts\":["
        first = 1
    }
    {
        if (!first) printf ","
        first = 0
        # $1=total, $2=irq, $3=primary_cpu, $4=name, $5=cpu_counts
        # Convert $1 to number to remove leading zeros
        printf "{\"irq\":%s,\"name\":\"%s\",\"total\":%d,\"cpu\":%s,\"per_cpu\":[%s]}", 
               $2, $4, $1, $3, $5
    }
    END {
        printf "]}\n"
    }
    ' 2>/dev/null)
    
    echo "$top_interrupts"
}

# Get raw memory info (kB)
get_memory_raw() {
    mem_total=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
    mem_free=$(awk '/MemFree:/ {print $2}' /proc/meminfo)
    mem_available=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
    mem_buffers=$(awk '/Buffers:/ {print $2}' /proc/meminfo)
    mem_cached=$(awk '/^Cached:/ {print $2}' /proc/meminfo)
    
    # If MemAvailable not present, estimate it
    if [ -z "$mem_available" ] || [ "$mem_available" = "0" ]; then
        mem_available=$((mem_free + mem_buffers + mem_cached))
    fi
    
    echo "$mem_total $mem_free $mem_available"
}

# Get GPU frequency (MHz for Intel, or Hz for others)
get_gpu_freq_raw() {
    # Try Intel GPU first (common on x86 Android)
    if [ -f /sys/class/drm/card0/gt_cur_freq_mhz ]; then
        cat /sys/class/drm/card0/gt_cur_freq_mhz
    elif [ -f /sys/kernel/debug/dri/0/i915_frequency_info ]; then
        awk '/Current freq:/ {print $3}' /sys/kernel/debug/dri/0/i915_frequency_info
    else
        echo "0"
    fi
}

# Get Intel GPU runtime/idle data (supports both i915 and Xe drivers)
# For i915: returns runtime in ms from i915_engine_info
# For Xe: returns idle_residency_ms (host will calculate util = 100 - idle%)
# Returns the raw value (milliseconds)
get_gpu_runtime_raw() {
    # Try i915 driver first (debugfs path)
    for variant in 0000:00:02.0 0 128; do
        engine_info="/sys/kernel/debug/dri/$variant/i915_engine_info"
        if [ -f "$engine_info" ]; then
            # Parse "Runtime: 555809ms" from rcs0 section
            # Use awk to find rcs0 section, then extract Runtime value
            runtime=$(awk '
                /^rcs0/ { in_rcs0=1 }
                in_rcs0 && /Runtime:/ {
                    gsub(/ms/, "", $2)
                    print $2
                    exit
                }
            ' "$engine_info" 2>/dev/null)
            
            if [ -n "$runtime" ] && [ "$runtime" != "0" ]; then
                echo "$runtime"
                return
            fi
        fi
    done
    
    # Try Xe driver (idle_residency_ms)
    for card in 0 1 2 3 4; do
        idle_path="/sys/class/drm/card${card}/device/tile0/gt0/gtidle/idle_residency_ms"
        if [ -f "$idle_path" ]; then
            idle_ms=$(cat "$idle_path" 2>/dev/null)
            if [ -n "$idle_ms" ]; then
                echo "$idle_ms"
                return
            fi
        fi
    done
    
    # No runtime/idle found
    echo "0"
}

# Detect GPU driver type (i915 or xe)
# Returns "i915", "xe", or "unknown"
get_gpu_driver_type() {
    # Check for i915
    for variant in 0000:00:02.0 0 128; do
        if [ -f "/sys/kernel/debug/dri/$variant/i915_engine_info" ]; then
            echo "i915"
            return
        fi
    done
    
    # Check for Xe
    for card in 0 1 2 3 4; do
        if [ -f "/sys/class/drm/card${card}/device/tile0/gt0/gtidle/idle_residency_ms" ]; then
            echo "xe"
            return
        fi
    done
    
    echo "unknown"
}

# Get Intel GPU memory usage (supports both i915 and Xe drivers)
# Returns "used_bytes total_bytes" or "0 0"
get_gpu_memory_raw() {
    # Try i915 driver first (debugfs path)
    for variant in 0000:00:02.0 0 128; do
        gem_objects="/sys/kernel/debug/dri/$variant/i915_gem_objects"
        if [ -f "$gem_objects" ]; then
            # First line: "726 shrinkable [5 free] objects, 753983488 bytes"
            # Extract the bytes value (last number before "bytes")
            used_bytes=$(head -1 "$gem_objects" | awk '{print $(NF-1)}')
            
            # System memory line: "system: total:0x00000003de1de000 bytes"
            # Convert hex to decimal (use head -1 to avoid matching "stolen-system: total:")
            total_hex=$(grep "system: total:" "$gem_objects" | head -1 | awk '{print $2}' | cut -d: -f2)
            
            if [ -n "$total_hex" ]; then
                # Convert hex to decimal using printf
                total_bytes=$(printf "%d" "$total_hex" 2>/dev/null || echo "0")
                
                if [ -n "$used_bytes" ] && [ "$used_bytes" != "0" ]; then
                    echo "$used_bytes $total_bytes"
                    return
                fi
            fi
        fi
    done
    
    # Try Xe driver (scan /proc/*/fdinfo for drm-total-gtt or drm-total-system)
    # This aggregates memory usage across all GPU clients
    total_used=0
    for pid in /proc/[0-9]*; do
        [ -d "$pid/fdinfo" ] || continue
        for fd in "$pid/fdinfo"/*; do
            [ -f "$fd" ] || continue
            # Check if this is a Xe GPU fd
            if grep -q "drm-driver:.*xe" "$fd" 2>/dev/null; then
                # Parse drm-total-gtt or drm-total-system (in KiB)
                mem_kb=$(awk '/^drm-total-(gtt|system):/ {print $2}' "$fd" 2>/dev/null)
                if [ -n "$mem_kb" ]; then
                    total_used=$((total_used + mem_kb * 1024))
                fi
            fi
        done
    done
    
    if [ "$total_used" -gt 0 ]; then
        # Get total system memory (Xe uses system RAM)
        total_bytes=$(awk '/MemTotal:/ {print $2 * 1024}' /proc/meminfo)
        echo "$total_used $total_bytes"
        return
    fi
    
    # No memory info found
    echo "0 0"
}

# Get raw network I/O (bytes)
get_network_raw() {
    rx_bytes=0
    tx_bytes=0
    
    for iface in /sys/class/net/*; do
        if [ -f "$iface/statistics/rx_bytes" ]; then
            rx=$(cat "$iface/statistics/rx_bytes")
            tx=$(cat "$iface/statistics/tx_bytes")
            rx_bytes=$((rx_bytes + rx))
            tx_bytes=$((tx_bytes + tx))
        fi
    done
    
    echo "$rx_bytes $tx_bytes"
}

# Get raw disk I/O (sectors)
get_disk_raw() {
    # Read sectors from /proc/diskstats
    # Format: major minor name reads reads_merged sectors_read time_reading writes writes_merged sectors_written time_writing
    # Include physical disks only (nvme0n1, sda, vda, mmcblk0), exclude partitions (nvme0n1p1, sda1, mmcblk0p1)
    
    # Use grep to pre-filter, then awk to sum
    grep -E '^[[:space:]]*[0-9]+[[:space:]]+[0-9]+[[:space:]]+(nvme[0-9]+n[0-9]+|sd[a-z]|vd[a-z]|mmcblk[0-9]+)[[:space:]]' /proc/diskstats | \
    awk '{read_sectors += $6; write_sectors += $10} END {printf "%d %d", read_sectors, write_sectors}'
}

# Main streaming loop
main() {
    echo "Starting raw data stream (interval: ${INTERVAL}s)" >&2
    
    # Initialize database
    init_database
    
    # Detect GPU driver type once at startup
    GPU_DRIVER=$(get_gpu_driver_type)
    
    while true; do
        LOOP_START=$(date +%s)
        
        # CPU data
        read cpu_user cpu_nice cpu_sys cpu_idle cpu_iowait cpu_irq cpu_softirq cpu_steal <<< $(get_cpu_raw)
        per_core_stats=$(get_per_core_raw)
        per_core_freq=$(get_per_core_freq)
        cpu_temp=$(get_cpu_temp_raw)
        
        # Memory data  
        read mem_total mem_free mem_available <<< $(get_memory_raw)
        
        # Tier 1 metrics (conditional)
        read ctxt load_1m load_5m load_15m procs_running procs_blocked per_core_irq_pct per_core_softirq_pct <<< $(get_tier1_metrics)
        
        # Interrupt distribution (conditional, part of Tier 1)
        interrupt_data=$(get_interrupt_data)
        
        # Monitor CPU usage
        read monitor_utime monitor_stime <<< $(get_monitor_cpu_usage | tr ',' ' ')
        
        # Format per_core arrays for JSON (add brackets if not empty, otherwise use empty array)
        if [ -n "$per_core_irq_pct" ]; then
            tier1_irq_json="[$per_core_irq_pct]"
        else
            tier1_irq_json="[]"
        fi
        
        if [ -n "$per_core_softirq_pct" ]; then
            tier1_softirq_json="[$per_core_softirq_pct]"
        else
            tier1_softirq_json="[]"
        fi
        
        # GPU data (raw values only, host will calculate utilization)
        gpu_freq=$(get_gpu_freq_raw)
        gpu_runtime=$(get_gpu_runtime_raw)
        read gpu_mem_used gpu_mem_total <<< $(get_gpu_memory_raw)
        
        # Network I/O (cumulative bytes - host will calculate delta)
        read net_rx net_tx <<< $(get_network_raw)
        
        # Disk I/O (cumulative sectors - host will calculate delta)
        read disk_read disk_write <<< $(get_disk_raw)
        
        # Get current timestamp (seconds since epoch)
        TIMESTAMP=$(date +%s)
        # Get millisecond timestamp for accurate GPU utilization calculation
        TIMESTAMP_MS=$(date +%s%3N)
        
        # Insert into SQLite database (with proper escaping for JSON arrays)
        sqlite3 "$DB_PATH" "INSERT INTO raw_samples (timestamp, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle, cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz, cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb, gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes, npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors, ctxt, load_avg_1m, load_avg_5m, load_avg_15m, procs_running, procs_blocked, per_core_irq_pct, per_core_softirq_pct, interrupt_data, monitor_cpu_utime, monitor_cpu_stime) VALUES ($TIMESTAMP, $TIMESTAMP_MS, $cpu_user, $cpu_nice, $cpu_sys, $cpu_idle, $cpu_iowait, $cpu_irq, $cpu_softirq, $cpu_steal, '$per_core_stats', '$per_core_freq', $cpu_temp, $mem_total, $mem_free, $mem_available, '$GPU_DRIVER', $gpu_freq, $gpu_runtime, $gpu_mem_used, $gpu_mem_total, 'none', $net_rx, $net_tx, $disk_read, $disk_write, $ctxt, $load_1m, $load_5m, $load_15m, $procs_running, $procs_blocked, '$per_core_irq_pct', '$per_core_softirq_pct', '$interrupt_data', $monitor_utime, $monitor_stime);"
        
        # Output JSON - single line with printf (no line wrapping issues)
        # Send RAW gpu_runtime_ms AND timestamp_ms for accurate host-side calculation
        # gpu_driver: "i915" (runtime=active time) or "xe" (runtime=idle time, util=100-idle%)
        # npu_info: "none" for Android (NPU support typically not available on Android x86)
        # disk_read_sectors/disk_write_sectors: CUMULATIVE values (host calculates delta)
        # net_rx_bytes/net_tx_bytes: CUMULATIVE values (host calculates delta)
        # Tier 1 fields included conditionally (null values if disabled)
        printf '{"timestamp_ms":%s,"cpu_raw":{"user":%d,"nice":%d,"sys":%d,"idle":%d,"iowait":%d,"irq":%d,"softirq":%d,"steal":%d},"per_core_raw":[%s],"per_core_freq_khz":[%s],"cpu_temp_millideg":%d,"mem_total_kb":%d,"mem_free_kb":%d,"mem_available_kb":%d,"gpu_driver":"%s","gpu_freq_mhz":%d,"gpu_runtime_ms":%d,"gpu_memory_used_bytes":%d,"gpu_memory_total_bytes":%d,"npu_info":"%s","net_rx_bytes":%d,"net_tx_bytes":%d,"disk_read_sectors":%d,"disk_write_sectors":%d,"ctxt":%s,"load_avg_1m":%s,"load_avg_5m":%s,"load_avg_15m":%s,"procs_running":%s,"procs_blocked":%s,"per_core_irq_pct":%s,"per_core_softirq_pct":%s,"interrupt_data":%s,"monitor_cpu_utime":%d,"monitor_cpu_stime":%d}\n' \
            "$TIMESTAMP_MS" \
            "$cpu_user" "$cpu_nice" "$cpu_sys" "$cpu_idle" "$cpu_iowait" "$cpu_irq" "$cpu_softirq" "$cpu_steal" \
            "$per_core_stats" "$per_core_freq" "$cpu_temp" \
            "$mem_total" "$mem_free" "$mem_available" \
            "$GPU_DRIVER" \
            "$gpu_freq" "$gpu_runtime" "$gpu_mem_used" "$gpu_mem_total" \
            "none" \
            "$net_rx" "$net_tx" \
            "$disk_read" "$disk_write" \
            "$ctxt" "$load_1m" "$load_5m" "$load_15m" "$procs_running" "$procs_blocked" \
            "$tier1_irq_json" "$tier1_softirq_json" \
            "$interrupt_data" \
            "$monitor_utime" "$monitor_stime"
        
        # Sleep until next interval
        LOOP_END=$(date +%s)
        ELAPSED=$((LOOP_END - LOOP_START))
        SLEEP_TIME=$((INTERVAL - ELAPSED))
        if [ "$SLEEP_TIME" -gt 0 ]; then
            sleep "$SLEEP_TIME"
        fi
    done
}

main
