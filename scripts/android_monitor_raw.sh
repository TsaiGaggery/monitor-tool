#!/system/bin/sh
# Android System Monitor - Raw Data Streaming + SQLite Storage
# Outputs RAW data only - all calculations done on host side
# Also stores data in local SQLite database for accurate export
# Usage: adb shell /data/local/tmp/android_monitor_stream.sh [interval] [enable_tier1]

INTERVAL=${1:-1}
ENABLE_TIER1=${2:-0}  # 0=disabled, 1=enabled (Tier 1 metrics: ctxt, load, procs, irq%)
ENABLE_DB=${3:-1}     # 0=disabled, 1=enabled (SQLite logging)
DB_PATH="/data/local/tmp/monitor.db"

# Initialize database (recreate to ensure schema is up to date)
init_database() {
    if [ "$ENABLE_DB" -ne 1 ]; then
        return
    fi
    
    # Backup old database if it exists (preserve data in case of crash/disconnect)
    if [ -f "$DB_PATH" ]; then
        mv "$DB_PATH" "${DB_PATH}.bak"
    fi
    
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
        "    monitor_cpu_stime INTEGER," \
        "    cpu_power_uj BIGINT" \
        ");" \
        "CREATE TABLE IF NOT EXISTS process_data (" \
        "    id INTEGER PRIMARY KEY AUTOINCREMENT," \
        "    timestamp INTEGER NOT NULL," \
        "    pid INTEGER," \
        "    name TEXT," \
        "    cpu_percent REAL," \
        "    memory_rss INTEGER," \
        "    cmdline TEXT," \
        "    status TEXT," \
        "    num_threads INTEGER" \
        ");" \
        "CREATE INDEX IF NOT EXISTS idx_timestamp ON raw_samples(timestamp);" \
        "CREATE INDEX IF NOT EXISTS idx_proc_timestamp ON process_data(timestamp);" \
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
    # 1. Search for specific CPU thermal zones by type
    for zone in /sys/class/thermal/thermal_zone*; do
        if [ -f "$zone/type" ]; then
            type=$(cat "$zone/type" 2>/dev/null)
            
            # Check for Intel package temp
            if [ "$type" = "x86_pkg_temp" ]; then
                temp=$(cat "$zone/temp" 2>/dev/null)
                if [ "$temp" -gt 1000 ]; then
                    echo "$temp"
                    return
                fi
            fi
        fi
    done
    
    # 2. Search for generic CPU thermal zones
    for zone in /sys/class/thermal/thermal_zone*; do
        if [ -f "$zone/type" ]; then
            type=$(cat "$zone/type" 2>/dev/null)
            
            # Check for common CPU thermal names
            case "$type" in
                *cpu*|*CPU*|*tsens_tz_sensor*|*mtktscpu*|*exynos-therm*)
                    if [ -f "$zone/temp" ]; then
                        temp=$(cat "$zone/temp" 2>/dev/null)
                        if [ "$temp" -gt 1000 ]; then
                            echo "$temp"
                            return
                        fi
                    fi
                    ;;
            esac
        fi
    done

    # 3. Fallback to zone0
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        temp=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        if [ "$temp" -gt 1000 ]; then
            echo "$temp"
            return
        fi
    fi

    # 4. Fallback to hwmon
    if [ -f /sys/class/hwmon/hwmon0/temp1_input ]; then
        cat /sys/class/hwmon/hwmon0/temp1_input
        return
    fi

    echo "0"
}

# Get CPU power consumption (Intel RAPL on x86 Android)
get_cpu_power_uj() {
    # Try Intel RAPL energy counter
    if [ -f /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj ]; then
        cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj 2>/dev/null || echo "0"
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

# Get NPU information
get_npu_info() {
    # Check for standard Linux AI accelerator interface (Intel NPU uses this)
    if [ -c "/dev/accel/accel0" ]; then
        echo "Intel NPU"
        return
    fi
    
    # Check for legacy Intel VPU
    if [ -d "/sys/class/intel_vpu" ]; then
        echo "Intel VPU"
        return
    fi
    
    # Check for other common NPU devices
    if [ -c "/dev/gnpu" ]; then
        echo "Generic NPU"
        return
    fi
    
    echo "none"
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

# Collect and store top processes
collect_top_processes() {
    local ts=$1
    
    # Use top command for accurate CPU% (not ps which causes high CPU usage)
    # -b: batch mode, -n 1: one iteration, -m 10: max 10 processes  
    # Parse top output using simpler awk (Android awk doesn't support 3-arg match)
    top -b -n 1 -m 10 | awk '
    BEGIN { header_found=0; count=0; }
    # Find header line containing PID
    /^[ ]*PID/ { header_found=1; next; }
    # Process data lines after header (starts with number)
    header_found && /^[ ]*[0-9]+/ && count < 5 {
        # Format: PID USER PR NI VIRT RES SHR S[%CPU] %MEM TIME+ ARGS...
        # Example: 7633 u10_system 20 0 14G 171M 121M S 3.8 1.0 1:21.28 com.android.desktop.network.debugtool
        pid = $1;
        res_str = $6;  # RES like "4.7M", "171M", "10G"
        state = substr($8, 1, 1);  # First char of S or S[%CPU] column
        
        # Parse CPU% - column 9 is %MEM, need to find CPU which might be in col 8 or 9
        # If col 9 is a plain number (e.g., "3.8"), it might be CPU or %MEM
        # Android top format: S[%CPU] is col 8, but shown as just "S" or "R" with CPU next
        # Actually: col 8 is "S", col 9 is likely the CPU% (after the [ part is dropped)
        # Let me check if $9 looks like CPU (small number with decimal)
        cpu_pct = 0;
        if ($9 ~ /^[0-9]+\.[0-9]+$/ && $9 < 100) {
            cpu_pct = $9;
        } else if ($8 ~/[0-9]/) {
            # Extract number from S[7.6] format
            tmp = $8;
            gsub(/[^0-9.]/, "", tmp);
            if (tmp != "") cpu_pct = tmp;
        }
        
        # Parse RES (memory) - extract number and unit
        mem_kb = 0;
        tmp_res = res_str;
        if (tmp_res ~ /G$/) {
            gsub(/[^0-9.]/, "", tmp_res);
            mem_kb = tmp_res * 1024 * 1024;
        } else if (tmp_res ~ /M$/) {
            gsub(/[^0-9.]/, "", tmp_res);
            mem_kb = tmp_res * 1024;
        } else if (tmp_res ~ /K$/) {
            gsub(/[^0-9.]/, "", tmp_res);
            mem_kb = tmp_res;
        }
        
        # ARGS is everything from column 12 onwards (after TIME+ which is col 11)
        name = "";
        for (i=12; i<=NF; i++) {
            name = name $i " ";
        }
        # Trim whitespace
        gsub(/^[ \t]+|[ \t]+$/, "", name);
        
        # Skip if no name extracted
        if (name == "") next;
        
        # Extract short name from full command
        short_name = name;
        # Kernel threads: [kworker/u25:1] -> kworker
        if (name ~ /^\[/) {
            short_name = name;
            sub(/\[/, "", short_name);
            sub(/\/.*/, "", short_name);
            sub(/].*/, "", short_name);
        }
        # Paths: /system/bin/surfaceflinger args -> surfaceflinger
        else if (name ~ /^\//) {
            short_name = name;
            sub(/.*\//, "", short_name);  # Remove path
            sub(/ .*/, "", short_name);   # Remove args
        }
        # Android apps: com.android.settings:something -> settings
        else if (name ~ /\./) {
            short_name = name;
            sub(/.*\./, "", short_name);  # Get last component
            sub(/:.*/, "", short_name);   # Remove :suffix
            sub(/ .*/, "", short_name);   # Remove args
        }
        
        # Escape special characters for JSON
        gsub(/\\/, "\\\\", short_name);  # Backslashes first
        gsub(/"/, "\\\"", short_name);   # Then quotes
        gsub(/\\/, "\\\\", name);        # Backslashes first
        gsub(/"/, "\\\"", name);         # Then quotes
        
        # Output JSON  
        printf "{\"type\":\"process\",\"pid\":%d,\"name\":\"%s\",\"cpu\":%.1f,\"mem\":%d,\"cmd\":\"%s\"}\n", 
            pid, short_name, cpu_pct, int(mem_kb * 1024), name;
        
        count++;
    }
    '
}

# Main monitoring loop
main() {
    echo "Starting raw data stream (interval: ${INTERVAL}s)" >&2
    
    # Initialize database
    init_database
    
    # Detect GPU driver type once at startup
    GPU_DRIVER=$(get_gpu_driver_type)
    
    # Counter for process collection throttling
    LOOP_COUNT=0
    PROCESS_INTERVAL=5  # Collect processes every 5 iterations to save CPU
    
    while true; do
        # Use millisecond precision for accurate timing
        LOOP_START_MS=$(date +%s%3N)
        
        # CPU data
        set -- $(get_cpu_raw)
        cpu_user=${1:-0}; cpu_nice=${2:-0}; cpu_sys=${3:-0}; cpu_idle=${4:-0}
        cpu_iowait=${5:-0}; cpu_irq=${6:-0}; cpu_softirq=${7:-0}; cpu_steal=${8:-0}
        
        per_core_stats=$(get_per_core_raw)
        per_core_freq=$(get_per_core_freq)
        cpu_temp=$(get_cpu_temp_raw)
        cpu_power_uj=$(get_cpu_power_uj)
        
        # Memory data  
        set -- $(get_memory_raw)
        mem_total=${1:-0}; mem_free=${2:-0}; mem_available=${3:-0}
        
        # Tier 1 metrics (conditional)
        set -- $(get_tier1_metrics)
        ctxt=${1:-0}; load_1m=${2:-0}; load_5m=${3:-0}; load_15m=${4:-0}
        procs_running=${5:-0}; procs_blocked=${6:-0}
        per_core_irq_pct=${7:-0}; per_core_softirq_pct=${8:-0}
        
        # Interrupt distribution (conditional, part of Tier 1)
        interrupt_data=$(get_interrupt_data)
        
        # Monitor CPU usage
        # Use tr to replace comma with space for splitting
        set -- $(get_monitor_cpu_usage | tr ',' ' ')
        monitor_utime=${1:-0}; monitor_stime=${2:-0}
        
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
        # Use set -- for robust splitting
        set -- $(get_gpu_memory_raw)
        gpu_mem_used=${1:-0}
        gpu_mem_total=${2:-0}
        
        # NPU info
        npu_info=$(get_npu_info)
        
        # Network I/O (cumulative bytes - host will calculate delta)
        set -- $(get_network_raw)
        net_rx=${1:-0}
        net_tx=${2:-0}
        
        # Disk I/O (cumulative sectors - host will calculate delta)
        set -- $(get_disk_raw)
        disk_read=${1:-0}
        disk_write=${2:-0}
        
        # Get current timestamp (seconds since epoch)
        TIMESTAMP=$(date +%s)
        # Get millisecond timestamp for accurate GPU utilization calculation
        TIMESTAMP_MS=$(date +%s%3N)
        
        # Insert into SQLite database (with proper escaping for JSON arrays)
        # Log every write attempt so we can trace timestamps
        # echo "[$(date '+%F %T')] INSERT timestamp=$TIMESTAMP runtime_ms=$gpu_runtime mem_used=$gpu_mem_used" >> /data/local/tmp/monitor_db_writes.log
        
        if [ "$ENABLE_DB" -eq 1 ]; then
            sqlite3 "$DB_PATH" "INSERT INTO raw_samples (timestamp, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle, cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz, cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb, gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes, npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors, ctxt, load_avg_1m, load_avg_5m, load_avg_15m, procs_running, procs_blocked, per_core_irq_pct, per_core_softirq_pct, interrupt_data, monitor_cpu_utime, monitor_cpu_stime, cpu_power_uj) VALUES ($TIMESTAMP, $TIMESTAMP_MS, $cpu_user, $cpu_nice, $cpu_sys, $cpu_idle, $cpu_iowait, $cpu_irq, $cpu_softirq, $cpu_steal, '$per_core_stats', '$per_core_freq', $cpu_temp, $mem_total, $mem_free, $mem_available, '$gpu_driver', $gpu_freq_mhz, $gpu_runtime, $gpu_mem_used, $gpu_mem_total, '$npu_info', $net_rx, $net_tx, $disk_read, $disk_write, $ctxt, $load_1m, $load_5m, $load_15m, $procs_running, $procs_blocked, '$per_core_irq_pct', '$per_core_softirq_pct', '$interrupt_data', $monitor_utime, $monitor_stime, $cpu_power_uj);"
        fi
        
        # Collect and store top processes (throttled)
        if [ $((LOOP_COUNT % PROCESS_INTERVAL)) -eq 0 ]; then
            collect_top_processes "$TIMESTAMP"
        fi
        LOOP_COUNT=$((LOOP_COUNT + 1))
        
        # Output JSON to stdout (for ADB streaming to host)
        # Send RAW gpu_runtime_ms AND timestamp_ms for accurate host-side calculation
        # gpu_driver: "i915" (runtime=active time) or "xe" (runtime=idle time, util=100-idle%)
        # npu_info: "none" for Android (NPU support typically not available on Android x86)
        # disk_read_sectors/disk_write_sectors: CUMULATIVE values (host calculates delta)
        # net_rx_bytes/net_tx_bytes: CUMULATIVE values (host calculates delta)
        # Tier 1 fields included conditionally (null values if disabled)
        printf '{"timestamp_ms":%s,"cpu_raw":{"user":%d,"nice":%d,"sys":%d,"idle":%d,"iowait":%d,"irq":%d,"softirq":%d,"steal":%d},"per_core_raw":[%s],"per_core_freq_khz":[%s],"cpu_temp_millideg":%d,"cpu_power_uj":%d,"mem_total_kb":%d,"mem_free_kb":%d,"mem_available_kb":%d,"gpu_driver":"%s","gpu_freq_mhz":%d,"gpu_runtime_ms":%d,"gpu_memory_used_bytes":%d,"gpu_memory_total_bytes":%d,"npu_info":"%s","net_rx_bytes":%d,"net_tx_bytes":%d,"disk_read_sectors":%d,"disk_write_sectors":%d,"ctxt":%s,"load_avg_1m":%s,"load_avg_5m":%s,"load_avg_15m":%s,"procs_running":%s,"procs_blocked":%s,"per_core_irq_pct":%s,"per_core_softirq_pct":%s,"interrupt_data":%s,"monitor_cpu_utime":%d,"monitor_cpu_stime":%d}\n' \
            "$TIMESTAMP_MS" \
            "$cpu_user" "$cpu_nice" "$cpu_sys" "$cpu_idle" "$cpu_iowait" "$cpu_irq" "$cpu_softirq" "$cpu_steal" \
            "$per_core_stats" "$per_core_freq" "$cpu_temp" "$cpu_power_uj" \
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
        
        # Sleep until next interval (millisecond precision)
        LOOP_END_MS=$(date +%s%3N)
        ELAPSED_MS=$((LOOP_END_MS - LOOP_START_MS))
        SLEEP_MS=$((INTERVAL * 1000 - ELAPSED_MS))
        
        if [ "$SLEEP_MS" -gt 0 ]; then
            # Convert to seconds with decimal (e.g., 0.750 for 750ms)
            SLEEP_SEC=$(awk "BEGIN {printf \"%.3f\", $SLEEP_MS/1000}")
            sleep "$SLEEP_SEC"
        fi
    done
}

main
