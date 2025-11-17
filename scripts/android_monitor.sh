#!/system/bin/sh
# Android System Monitor - Shell Script Version
# 
# This script runs on Android device and logs system metrics to SQLite.
# Designed to mirror the architecture of monitor-tool's GUI/CLI monitors.
# 
# Usage:
#   ./android_monitor.sh [interval_seconds] [database_path]
#   Default: 1 second interval, /data/local/tmp/monitor.db

# Configuration
INTERVAL=${1:-1}  # Default 1 second
DB_PATH=${2:-/data/local/tmp/monitor.db}
LOG_TAG="AndroidMonitor"

# Initialize database
init_database() {
    log "Initializing database at $DB_PATH"
    
    # Create monitoring_data table (same schema as DataLogger)
    sqlite3 "$DB_PATH" <<'EOF'
CREATE TABLE IF NOT EXISTS monitoring_data (
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
    data_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON monitoring_data(timestamp);
EOF
    
    log "Database initialized"
}

# Logging helper
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Get CPU usage and per-core data (similar to CPUMonitor.get_all_info())
get_cpu_usage() {
    # Read /proc/stat for CPU usage calculation
    # First sample
    cpu_stats1=$(cat /proc/stat)
    sleep 0.1
    # Second sample
    cpu_stats2=$(cat /proc/stat)
    
    # Parse total CPU (first line)
    line1=$(echo "$cpu_stats1" | grep "^cpu " | head -1)
    line2=$(echo "$cpu_stats2" | grep "^cpu " | head -1)
    
    read cpu user1 nice1 system1 idle1 iowait1 irq1 softirq1 steal1 rest1 <<< "$line1"
    read cpu user2 nice2 system2 idle2 iowait2 irq2 softirq2 steal2 rest2 <<< "$line2"
    
    # Calculate total CPU usage
    total1=$((user1 + nice1 + system1 + idle1 + iowait1 + irq1 + softirq1 + steal1))
    total2=$((user2 + nice2 + system2 + idle2 + iowait2 + irq2 + softirq2 + steal2))
    active1=$((total1 - idle1))
    active2=$((total2 - idle2))
    
    total_diff=$((total2 - total1))
    active_diff=$((active2 - active1))
    
    if [ "$total_diff" -gt 0 ]; then
        cpu_percent=$((active_diff * 10000 / total_diff))
        cpu_usage="$((cpu_percent / 100)).$((cpu_percent % 100))"
    else
        cpu_usage="0.0"
    fi
    
    # Calculate per-core usage
    per_core_usage=""
    core_num=0
    
    # Get per-core stats
    cores1=$(echo "$cpu_stats1" | grep "^cpu[0-9]")
    cores2=$(echo "$cpu_stats2" | grep "^cpu[0-9]")
    
    # Process each core
    echo "$cores1" | while IFS= read -r line1; do
        core_num=$(echo "$line1" | awk '{print $1}' | sed 's/cpu//')
        line2=$(echo "$cores2" | grep "^cpu${core_num} ")
        
        read cpu user1 nice1 system1 idle1 iowait1 irq1 softirq1 steal1 rest1 <<< "$line1"
        read cpu user2 nice2 system2 idle2 iowait2 irq2 softirq2 steal2 rest2 <<< "$line2"
        
        total1=$((user1 + nice1 + system1 + idle1 + iowait1 + irq1 + softirq1 + steal1))
        total2=$((user2 + nice2 + system2 + idle2 + iowait2 + irq2 + softirq2 + steal2))
        active1=$((total1 - idle1))
        active2=$((total2 - idle2))
        
        total_diff=$((total2 - total1))
        active_diff=$((active2 - active1))
        
        if [ "$total_diff" -gt 0 ]; then
            core_percent=$((active_diff * 10000 / total_diff))
            core_usage="$((core_percent / 100)).$((core_percent % 100))"
        else
            core_usage="0.0"
        fi
        
        echo "$core_usage"
    done | tr '\n' ',' | sed 's/,$//' > /tmp/android_monitor_cores.tmp
    
    per_core_usage=$(cat /tmp/android_monitor_cores.tmp 2>/dev/null || echo "0.0")
    core_count=$(echo "$cores1" | wc -l)
    
    echo "$cpu_usage|$per_core_usage|$core_count"
}

# Get CPU frequency (similar to CPUMonitor.get_frequency())
get_cpu_freq() {
    # Get per-core frequencies and calculate average
    total_freq=0
    count=0
    per_core_freq=""
    
    # Try to read per-core frequencies
    for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
        if [ -f "$cpu_dir/cpufreq/scaling_cur_freq" ]; then
            freq=$(cat "$cpu_dir/cpufreq/scaling_cur_freq" 2>/dev/null || echo "0")
            freq_mhz=$((freq / 1000))
            total_freq=$((total_freq + freq_mhz))
            count=$((count + 1))
            per_core_freq="${per_core_freq}${freq_mhz},"
        fi
    done
    
    # Remove trailing comma
    per_core_freq=${per_core_freq%,}
    
    # Calculate average
    if [ "$count" -gt 0 ]; then
        avg_freq=$((total_freq / count))
    else
        # Fallback: read from cpuinfo
        freq=$(grep "cpu MHz" /proc/cpuinfo | head -1 | awk '{print $4}')
        if [ -n "$freq" ]; then
            avg_freq="${freq%.*}"
            per_core_freq="$avg_freq"
        else
            avg_freq="0"
            per_core_freq="0"
        fi
    fi
    
    echo "$avg_freq|$per_core_freq"
}

# Get CPU temperature (similar to CPUMonitor.get_temperature())
get_cpu_temp() {
    # Try different thermal zone paths and find the highest temperature
    max_temp=0
    temp_count=0
    
    # Method 1: thermal zones
    for zone in /sys/class/thermal/thermal_zone*/temp; do
        if [ -f "$zone" ]; then
            temp=$(cat "$zone" 2>/dev/null || echo "0")
            # Convert millicelsius to celsius
            temp=$((temp / 1000))
            if [ "$temp" -gt "$max_temp" ] && [ "$temp" -lt 200 ]; then
                max_temp=$temp
                temp_count=$((temp_count + 1))
            fi
        fi
    done
    
    # Method 2: hwmon (for x86 Android)
    if [ "$max_temp" -eq 0 ]; then
        for hwmon in /sys/class/hwmon/hwmon*/temp*_input; do
            if [ -f "$hwmon" ]; then
                temp=$(cat "$hwmon" 2>/dev/null || echo "0")
                temp=$((temp / 1000))
                if [ "$temp" -gt "$max_temp" ] && [ "$temp" -lt 200 ]; then
                    max_temp=$temp
                fi
            fi
        done
    fi
    
    # Method 3: Check /sys/devices/virtual/thermal/
    if [ "$max_temp" -eq 0 ]; then
        for zone in /sys/devices/virtual/thermal/thermal_zone*/temp; do
            if [ -f "$zone" ]; then
                temp=$(cat "$zone" 2>/dev/null || echo "0")
                temp=$((temp / 1000))
                if [ "$temp" -gt "$max_temp" ] && [ "$temp" -lt 200 ]; then
                    max_temp=$temp
                fi
            fi
        done
    fi
    
    echo "$max_temp"
}

# Get memory info (similar to MemoryMonitor.get_all_info())
get_memory_info() {
    # Parse /proc/meminfo
    mem_total=$(grep "MemTotal:" /proc/meminfo | awk '{print $2}')
    mem_free=$(grep "MemFree:" /proc/meminfo | awk '{print $2}')
    mem_available=$(grep "MemAvailable:" /proc/meminfo | awk '{print $2}')
    mem_buffers=$(grep "Buffers:" /proc/meminfo | awk '{print $2}')
    mem_cached=$(grep "^Cached:" /proc/meminfo | awk '{print $2}')
    
    # Default to 0 if values are empty
    mem_total=${mem_total:-0}
    mem_free=${mem_free:-0}
    mem_available=${mem_available:-0}
    mem_buffers=${mem_buffers:-0}
    mem_cached=${mem_cached:-0}
    
    # Calculate used memory (total - available)
    if [ "$mem_available" -gt 0 ]; then
        mem_used=$((mem_total - mem_available))
    else
        # Fallback for older kernels
        mem_used=$((mem_total - mem_free - mem_buffers - mem_cached))
    fi
    
    # Ensure non-negative
    if [ "$mem_used" -lt 0 ]; then
        mem_used=0
    fi
    
    # Convert KB to GB (with bc if available, otherwise integer division)
    if command -v bc >/dev/null 2>&1; then
        mem_total_gb=$(echo "scale=3; $mem_total / 1024 / 1024" | bc)
        mem_used_gb=$(echo "scale=3; $mem_used / 1024 / 1024" | bc)
    else
        # Fallback: integer division (less accurate)
        mem_total_gb=$((mem_total / 1024 / 1024))
        mem_used_gb=$((mem_used / 1024 / 1024))
    fi
    
    # Calculate percentage
    if [ "$mem_total" -gt 0 ]; then
        mem_percent=$((mem_used * 10000 / mem_total))
        mem_percent_dec="$((mem_percent / 100)).$((mem_percent % 100))"
    else
        mem_percent_dec="0.0"
    fi
    
    echo "$mem_total_gb $mem_used_gb $mem_percent_dec"
}

# Get GPU info (x86 Intel GPU - similar to GPUMonitor for Intel)
get_gpu_info() {
    gpu_usage=0
    gpu_freq=0
    gpu_temp=0
    
    # Intel GPU paths (for x86 Android with Intel GPU)
    # Check if Intel GPU is available
    if [ -d /sys/class/drm/card0 ]; then
        # Try to read GPU frequency from i915 debugfs
        if [ -f /sys/kernel/debug/dri/0/i915_frequency_info ]; then
            # This requires root, may not work
            freq_val=$(grep "CAGF:" /sys/kernel/debug/dri/0/i915_frequency_info 2>/dev/null | awk '{print $2}')
            if [ -n "$freq_val" ] && [ "$freq_val" != "" ]; then
                gpu_freq=$freq_val
            fi
        fi
        
        # Try sysfs for frequency
        if [ "$gpu_freq" = "0" ] && [ -f /sys/class/drm/card0/gt_cur_freq_mhz ]; then
            freq_val=$(cat /sys/class/drm/card0/gt_cur_freq_mhz 2>/dev/null || echo "0")
            if [ -n "$freq_val" ] && [ "$freq_val" != "" ]; then
                gpu_freq=$freq_val
            fi
        fi
    fi
    
    # For Qualcomm Adreno GPU (if this was ARM Android)
    # if [ -f /sys/class/kgsl/kgsl-3d0/gpubusy ]; then
    #     gpu_busy=$(cat /sys/class/kgsl/kgsl-3d0/gpubusy)
    #     # Parse "busy_time total_time" format
    #     busy=$(echo $gpu_busy | awk '{print $1}')
    #     total=$(echo $gpu_busy | awk '{print $2}')
    #     if [ "$total" -gt 0 ]; then
    #         gpu_usage=$((busy * 100 / total))
    #     fi
    #     gpu_freq=$(cat /sys/class/kgsl/kgsl-3d0/gpuclk 2>/dev/null || echo "0")
    #     gpu_freq=$((gpu_freq / 1000000))  # Hz to MHz
    # fi
    
    # Ensure we always return valid numbers
    echo "${gpu_usage:-0} ${gpu_freq:-0} ${gpu_temp:-0}"
}

# Get network I/O stats (similar to NetworkMonitor.get_io_stats())
get_network_info() {
    # Read /proc/net/dev for network statistics
    # Format: interface | rx_bytes rx_packets ... | tx_bytes tx_packets ...
    
    # First sample
    net_stats1=$(cat /proc/net/dev | grep -v "lo:" | grep ":")
    sleep 0.1
    # Second sample
    net_stats2=$(cat /proc/net/dev | grep -v "lo:" | grep ":")
    
    total_rx_bytes1=0
    total_tx_bytes1=0
    total_rx_bytes2=0
    total_tx_bytes2=0
    
    # Sum all interfaces (excluding loopback)
    while IFS=: read -r iface stats; do
        read rx_bytes rx_packets rest <<< "$stats"
        # tx_bytes is the 9th field
        tx_bytes=$(echo "$stats" | awk '{print $9}')
        total_rx_bytes1=$((total_rx_bytes1 + rx_bytes))
        total_tx_bytes1=$((total_tx_bytes1 + tx_bytes))
    done <<< "$net_stats1"
    
    while IFS=: read -r iface stats; do
        read rx_bytes rx_packets rest <<< "$stats"
        tx_bytes=$(echo "$stats" | awk '{print $9}')
        total_rx_bytes2=$((total_rx_bytes2 + rx_bytes))
        total_tx_bytes2=$((total_tx_bytes2 + tx_bytes))
    done <<< "$net_stats2"
    
    # Calculate speed (bytes per second, since we sleep 0.1s, multiply by 10)
    rx_speed=$(( (total_rx_bytes2 - total_rx_bytes1) * 10 ))
    tx_speed=$(( (total_tx_bytes2 - total_tx_bytes1) * 10 ))
    
    # Convert to MB/s (with bc if available)
    if command -v bc >/dev/null 2>&1; then
        rx_speed_mb=$(echo "scale=2; $rx_speed / 1024 / 1024" | bc)
        tx_speed_mb=$(echo "scale=2; $tx_speed / 1024 / 1024" | bc)
    else
        # Fallback: integer division
        rx_speed_mb=$((rx_speed / 1024 / 1024))
        tx_speed_mb=$((tx_speed / 1024 / 1024))
    fi
    
    echo "$rx_speed_mb $tx_speed_mb"
}

# Get disk I/O stats (similar to DiskMonitor.get_io_stats())
get_disk_info() {
    # Read /proc/diskstats for disk I/O
    # Format: major minor name reads ... sectors_read ... writes ... sectors_written ...
    
    # First sample
    disk_stats1=$(cat /proc/diskstats | grep -E "mmcblk0|sda|vda|nvme0n1" | head -1)
    sleep 0.1
    # Second sample
    disk_stats2=$(cat /proc/diskstats | grep -E "mmcblk0|sda|vda|nvme0n1" | head -1)
    
    if [ -z "$disk_stats1" ] || [ -z "$disk_stats2" ]; then
        # No disk found, return zeros
        echo "0.0 0.0"
        return
    fi
    
    # Parse diskstats (fields: 3=name, 6=sectors_read, 10=sectors_written)
    read maj min name reads1 rm1 sect_read1 ms_read1 writes1 wm1 sect_written1 rest1 <<< "$disk_stats1"
    read maj min name reads2 rm2 sect_read2 ms_read2 writes2 wm2 sect_written2 rest2 <<< "$disk_stats2"
    
    # Calculate sectors read/written (sector size is typically 512 bytes)
    sect_read_diff=$((sect_read2 - sect_read1))
    sect_written_diff=$((sect_written2 - sect_written1))
    
    # Convert to bytes (512 bytes per sector) and then to MB/s (0.1s interval, so * 10)
    read_bytes=$(( sect_read_diff * 512 * 10 ))
    write_bytes=$(( sect_written_diff * 512 * 10 ))
    
    # Convert to MB/s
    if command -v bc >/dev/null 2>&1; then
        read_speed_mb=$(echo "scale=2; $read_bytes / 1024 / 1024" | bc)
        write_speed_mb=$(echo "scale=2; $write_bytes / 1024 / 1024" | bc)
    else
        read_speed_mb=$((read_bytes / 1024 / 1024))
        write_speed_mb=$((write_bytes / 1024 / 1024))
    fi
    
    echo "$read_speed_mb $write_speed_mb"
}

# Build JSON data (similar to GUI's update_data())
build_json_data() {
    cpu_usage=$1
    per_core_usage=$2
    cpu_freq_avg=$3
    per_core_freq=$4
    cpu_temp=$5
    mem_total=$6
    mem_used=$7
    mem_percent=$8
    gpu_usage=$9
    gpu_freq=${10}
    gpu_temp=${11}
    net_rx_mb=${12}
    net_tx_mb=${13}
    disk_read_mb=${14}
    disk_write_mb=${15}
    
    # Build per-core arrays
    core_usage_json=$(echo "$per_core_usage" | sed 's/,/, /g')
    core_freq_json=$(echo "$per_core_freq" | sed 's/,/, /g')
    
    # Build JSON manually (no jq available on Android)
    cat <<EOF
{
  "cpu": {
    "usage": {
      "total": $cpu_usage,
      "per_core": [$core_usage_json]
    },
    "frequency": {
      "average": $cpu_freq_avg,
      "per_core": [$core_freq_json]
    },
    "temperature": $cpu_temp
  },
  "memory": {
    "memory": {
      "total": $mem_total,
      "used": $mem_used,
      "percent": $mem_percent
    }
  },
  "gpu": {
    "available": true,
    "gpus": [{
      "gpu_util": $gpu_usage,
      "gpu_clock": $gpu_freq,
      "temperature": $gpu_temp
    }]
  },
  "network": {
    "download_speed_mb": $net_rx_mb,
    "upload_speed_mb": $net_tx_mb
  },
  "disk": {
    "read_speed_mb": $disk_read_mb,
    "write_speed_mb": $disk_write_mb
  }
}
EOF
}

# Main monitoring loop (similar to CLI's _background_logging_worker())
main_loop() {
    log "Starting monitoring loop (interval: ${INTERVAL}s)"
    START_TIME=$(date +%s)
    
    trap 'log "Stopping monitor..."; exit 0' INT TERM
    
    while true; do
        LOOP_START=$(date +%s.%N 2>/dev/null || date +%s)
        
        # Collect data (like GUI's update_data())
        read cpu_usage per_core_usage cpu_count <<< $(get_cpu_usage | tr '|' ' ')
        read cpu_freq_avg per_core_freq <<< $(get_cpu_freq | tr '|' ' ')
        cpu_temp=$(get_cpu_temp)
        
        read mem_total mem_used mem_percent <<< $(get_memory_info)
        read gpu_usage gpu_freq gpu_temp <<< $(get_gpu_info)
        read net_rx_mb net_tx_mb <<< $(get_network_info)
        read disk_read_mb disk_write_mb <<< $(get_disk_info)
        
        # Build JSON
        json_data=$(build_json_data "$cpu_usage" "$per_core_usage" "$cpu_freq_avg" "$per_core_freq" "$cpu_temp" \
                                     "$mem_total" "$mem_used" "$mem_percent" \
                                     "$gpu_usage" "$gpu_freq" "$gpu_temp" \
                                     "$net_rx_mb" "$net_tx_mb" "$disk_read_mb" "$disk_write_mb")
        
        # Escape single quotes for SQL
        json_data_escaped=$(echo "$json_data" | sed "s/'/''/g")
        
        # Log to database (like DataLogger.log_data())
        sqlite3 "$DB_PATH" <<EOF
INSERT INTO monitoring_data (
    cpu_usage, cpu_freq_avg, cpu_temp,
    memory_total, memory_used, memory_percent,
    gpu_usage, gpu_freq, gpu_temp,
    data_json
) VALUES (
    $cpu_usage, $cpu_freq_avg, $cpu_temp,
    $mem_total, $mem_used, $mem_percent,
    $gpu_usage, $gpu_freq, $gpu_temp,
    '$json_data_escaped'
);
EOF
        
        # Print status (optional, for debugging)
        log "CPU: ${cpu_usage}% @ ${cpu_freq_avg}MHz (${cpu_temp}°C) | Mem: ${mem_used}/${mem_total}GB (${mem_percent}%) | GPU: ${gpu_usage}% @ ${gpu_freq}MHz | Net: ↓${net_rx_mb}/↑${net_tx_mb} MB/s | Disk: R${disk_read_mb}/W${disk_write_mb} MB/s"
        
        # Sleep until next interval (precise timing like CLI)
        LOOP_END=$(date +%s.%N 2>/dev/null || date +%s)
        if command -v bc >/dev/null 2>&1; then
            ELAPSED=$(echo "$LOOP_END - $LOOP_START" | bc)
            SLEEP_TIME=$(echo "$INTERVAL - $ELAPSED" | bc)
            if [ "$(echo "$SLEEP_TIME > 0" | bc)" -eq 1 ]; then
                sleep "$SLEEP_TIME"
            fi
        else
            # Fallback: simple integer sleep
            sleep "$INTERVAL"
        fi
    done
}

# Entry point
main() {
    log "========================================="
    log "Android System Monitor v1.0"
    log "Based on monitor-tool architecture"
    log "========================================="
    log "Database: $DB_PATH"
    log "Interval: ${INTERVAL}s"
    log "========================================="
    
    # Check dependencies
    if ! command -v sqlite3 >/dev/null 2>&1; then
        log "ERROR: sqlite3 not found"
        exit 1
    fi
    
    # Initialize database
    init_database
    
    # Start monitoring loop
    main_loop
}

# Run main function
main
