#!/bin/bash
# Remote Linux System Monitor - JSON Streaming + SQLite Storage
# Outputs monitoring data in JSON format, similar to Android monitor
# Also stores data in local SQLite database
# Usage: ssh user@host "bash -s" < linux_monitor.sh [interval]

INTERVAL=${1:-1}
DB_PATH="/tmp/monitor_tool_${USER}.db"

# Previous values for delta calculation (only for NPU, GPU calculation moved to host)
PREV_NPU_BUSY_US=0
PREV_TIMESTAMP_MS=0
FIRST_SAMPLE=true

# Initialize SQLite database
init_database() {
    sqlite3 "$DB_PATH" <<EOF
CREATE TABLE IF NOT EXISTS raw_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    timestamp_ms INTEGER,
    cpu_user INTEGER,
    cpu_nice INTEGER,
    cpu_sys INTEGER,
    cpu_idle INTEGER,
    cpu_iowait INTEGER,
    cpu_irq INTEGER,
    cpu_softirq INTEGER,
    cpu_steal INTEGER,
    per_core_raw TEXT,
    per_core_freq_khz TEXT,
    cpu_temp_millideg INTEGER,
    mem_total_kb INTEGER,
    mem_free_kb INTEGER,
    mem_available_kb INTEGER,
    gpu_driver TEXT,
    gpu_freq_mhz INTEGER,
    gpu_runtime_ms INTEGER,
    gpu_memory_used_bytes INTEGER,
    gpu_memory_total_bytes INTEGER,
    npu_info TEXT,
    net_rx_bytes INTEGER,
    net_tx_bytes INTEGER,
    disk_read_sectors INTEGER,
    disk_write_sectors INTEGER
);
CREATE INDEX IF NOT EXISTS idx_timestamp ON raw_samples(timestamp);
EOF
}

# Get raw CPU stats from /proc/stat
get_cpu_raw() {
    awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat
}

# Get raw per-core CPU stats
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
            freq=$(cat "$cpu_dir/cpufreq/scaling_cur_freq" 2>/dev/null || echo "0")
        else
            freq=0
        fi
        result="${result}${freq},"
    done
    echo "${result%,}"  # Remove trailing comma
}

# Get CPU temperature (millidegrees)
get_cpu_temp_raw() {
    # Try different thermal zones
    for zone in /sys/class/thermal/thermal_zone*/temp; do
        if [ -f "$zone" ]; then
            temp=$(cat "$zone" 2>/dev/null || echo "0")
            if [ "$temp" -gt 1000 ]; then
                echo "$temp"
                return
            fi
        fi
    done
    echo "0"
}

# Get raw memory info (kB)
get_memory_raw() {
    mem_total=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
    mem_free=$(awk '/MemFree:/ {print $2}' /proc/meminfo)
    mem_available=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
    
    # If MemAvailable not present, estimate it
    if [ -z "$mem_available" ] || [ "$mem_available" = "0" ]; then
        mem_buffers=$(awk '/Buffers:/ {print $2}' /proc/meminfo)
        mem_cached=$(awk '/^Cached:/ {print $2}' /proc/meminfo)
        mem_available=$((mem_free + mem_buffers + mem_cached))
    fi
    
    echo "$mem_total $mem_free $mem_available"
}

# Get GPU runtime (raw idle/rc6 residency for host-side calculation)
# Returns: driver freq_mhz runtime_ms mem_used_bytes mem_total_bytes
# For Xe: runtime_ms is idle_residency_ms (host will calculate util = 100 - idle%)
# For i915: runtime_ms is rc6_residency_ms (host will calculate util = 100 - rc6%)
get_gpu_info() {
    
    # Try NVIDIA first (not implemented yet, would need raw counter)
    # TODO: NVIDIA support for raw counters
    
    # Check for Intel GPU (i915 or Xe)
    for card in /sys/class/drm/card[0-9]; do
        if [ ! -d "$card" ]; then
            continue
        fi
        
        vendor_file="$card/device/vendor"
        if [ -f "$vendor_file" ]; then
            vendor=$(cat "$vendor_file" 2>/dev/null)
            # Check if Intel GPU (0x8086)
            if [ "$vendor" = "0x8086" ]; then
                # Detect GPU type and get info
                card_num=$(echo "$card" | grep -o 'card[0-9]' | grep -o '[0-9]')
                
                # Get GPU name
                device_file="$card/device/device"
                gpu_name="Intel GPU"
                if [ -f "$device_file" ]; then
                    device_id=$(cat "$device_file" 2>/dev/null)
                    gpu_name="Intel GPU ($device_id)"
                fi
                
                # Check for Xe driver (has tile0/gt0 structure)
                xe_idle_path="/sys/class/drm/card${card_num}/device/tile0/gt0/gtidle/idle_residency_ms"
                
                if [ -f "$xe_idle_path" ]; then
                    # Intel Xe GPU - return RAW idle_residency_ms
                    xe_idle=$(cat "$xe_idle_path" 2>/dev/null || echo "0")
                    
                    # Read frequency from all GT units and use maximum
                    xe_freq=0
                    for gt_freq in /sys/class/drm/card${card_num}/device/tile0/gt*/freq0/act_freq; do
                        if [ -f "$gt_freq" ]; then
                            freq=$(cat "$gt_freq" 2>/dev/null || echo "0")
                            if [ "$freq" -gt "$xe_freq" ]; then
                                xe_freq=$freq
                            fi
                        fi
                    done
                    
                    # Get GPU memory usage
                    # Note: For integrated GPUs, accurate memory tracking is not available
                    # Per-process fdinfo values are VIRTUAL addresses and summing them
                    # leads to massive over-counting due to shared buffers
                    # System-wide metrics are not exposed by Xe driver
                    # Best we can do: report 0 (memory is shared with system RAM)
                    mem_used_bytes=0
                    
                    # Get total system memory (integrated GPU uses system RAM)
                    mem_total_kb=$(grep "^MemTotal:" /proc/meminfo 2>/dev/null | awk '{print $2}')
                    mem_total_bytes=$((mem_total_kb * 1024))
                    
                    # Return: driver freq_mhz runtime_ms mem_used_bytes mem_total_bytes
                    echo "xe ${xe_freq} ${xe_idle} ${mem_used_bytes} ${mem_total_bytes}"
                    return
                fi
                
                # Check for i915 driver
                i915_rc6_path="/sys/class/drm/card${card_num}/gt/gt0/rc6_residency_ms"
                i915_freq_path="/sys/class/drm/card${card_num}/gt_cur_freq_mhz"
                
                if [ -f "$i915_rc6_path" ]; then
                    # Intel i915 GPU - return RAW rc6_residency_ms
                    i915_rc6=$(cat "$i915_rc6_path" 2>/dev/null || echo "0")
                    i915_freq=$(cat "$i915_freq_path" 2>/dev/null || echo "0")
                    
                    # Get GPU memory usage
                    # Note: For integrated GPUs, accurate memory tracking is not available
                    # Per-process fdinfo values are VIRTUAL addresses and summing them
                    # leads to massive over-counting due to shared buffers
                    # System-wide metrics are not exposed by i915 driver for integrated GPUs
                    # Best we can do: report 0 (memory is shared with system RAM)
                    mem_used_bytes=0
                    
                    # Get total system memory (integrated GPU uses system RAM)
                    mem_total_kb=$(grep "^MemTotal:" /proc/meminfo 2>/dev/null | awk '{print $2}')
                    mem_total_bytes=$((mem_total_kb * 1024))
                    
                    # Return: driver freq_mhz runtime_ms mem_used_bytes mem_total_bytes
                    echo "i915 ${i915_freq} ${i915_rc6} ${mem_used_bytes} ${mem_total_bytes}"
                    return
                fi
            fi
        fi
    done
    
    # No GPU found
    echo "none 0 0 0 0"
}

# Get NPU info (Intel NPU/VPU)
get_npu_info() {
    local current_ts_ms=$1  # Pass current timestamp for delta calculation
    
    # Check for Intel NPU (VPU) - Meteor Lake and newer
    npu_device="/sys/class/accel/accel0/device"
    
    if [ -d "$npu_device" ]; then
        # Intel NPU detected
        npu_freq=0
        npu_max_freq=0
        npu_mem_mb=0
        npu_busy_us=0
        
        # Read current frequency
        if [ -f "$npu_device/npu_current_frequency_mhz" ]; then
            npu_freq=$(cat "$npu_device/npu_current_frequency_mhz" 2>/dev/null || echo "0")
        fi
        
        # Read max frequency
        if [ -f "$npu_device/npu_max_frequency_mhz" ]; then
            npu_max_freq=$(cat "$npu_device/npu_max_frequency_mhz" 2>/dev/null || echo "0")
        fi
        
        # Read memory utilization
        if [ -f "$npu_device/npu_memory_utilization" ]; then
            mem_bytes=$(cat "$npu_device/npu_memory_utilization" 2>/dev/null || echo "0")
            npu_mem_mb=$((mem_bytes / 1024 / 1024))
        fi
        
        # Read busy time (for utilization calculation)
        if [ -f "$npu_device/npu_busy_time_us" ]; then
            npu_busy_us=$(cat "$npu_device/npu_busy_time_us" 2>/dev/null || echo "0")
        fi
        
        # Calculate utilization on host
        npu_util=0
        if [ "$FIRST_SAMPLE" = false ] && [ "$PREV_TIMESTAMP_MS" -gt 0 ] && [ "$PREV_NPU_BUSY_US" -gt 0 ]; then
            time_delta_ms=$((current_ts_ms - PREV_TIMESTAMP_MS))
            time_delta_us=$((time_delta_ms * 1000))
            busy_delta=$((npu_busy_us - PREV_NPU_BUSY_US))
            
            if [ "$time_delta_us" -gt 0 ]; then
                # Clamp busy_delta to time_delta
                if [ "$busy_delta" -gt "$time_delta_us" ]; then
                    busy_delta=$time_delta_us
                fi
                
                # Utilization = busy_time / total_time * 100 using awk for float math
                npu_util=$(awk "BEGIN {printf \"%.0f\", $busy_delta * 100.0 / $time_delta_us}")
                
                # Clamp to 0-100
                if [ "$npu_util" -lt 0 ]; then npu_util=0; fi
                if [ "$npu_util" -gt 100 ]; then npu_util=100; fi
            fi
        fi
        
        PREV_NPU_BUSY_US=$npu_busy_us
        
        # Output format: intel-npu:freq_mhz:max_freq_mhz:mem_mb:util
        echo "intel-npu:${npu_freq}:${npu_max_freq}:${npu_mem_mb}:${npu_util}"
        return
    fi
    
    echo "none"
}

# Get network stats (cumulative bytes)
get_network_stats() {
    rx_bytes=0
    tx_bytes=0
    
    while IFS= read -r line; do
        # Skip header and loopback
        if [[ ! "$line" =~ : ]] || [[ "$line" =~ lo: ]]; then
            continue
        fi
        
        # Parse interface stats
        iface_stats=$(echo "$line" | awk -F: '{print $2}')
        rx=$(echo "$iface_stats" | awk '{print $1}')
        tx=$(echo "$iface_stats" | awk '{print $9}')
        
        rx_bytes=$((rx_bytes + rx))
        tx_bytes=$((tx_bytes + tx))
    done < /proc/net/dev
    
    echo "$rx_bytes $tx_bytes"
}

# Get disk stats (cumulative sectors)
get_disk_stats() {
    read_sectors=0
    write_sectors=0
    
    while IFS= read -r line; do
        # Only get main disks (sda, nvme0n1, etc), skip partitions
        if echo "$line" | grep -qE '(sd[a-z]|nvme[0-9]+n[0-9]+|vd[a-z])\s'; then
            parts=($line)
            read_sectors=$((read_sectors + ${parts[5]}))
            write_sectors=$((write_sectors + ${parts[9]}))
        fi
    done < /proc/diskstats
    
    echo "$read_sectors $write_sectors"
}

# Main monitoring loop
main() {
    echo "Starting remote Linux monitor..." >&2
    
    # Initialize database on remote device (redirect errors to stderr to avoid mixing with JSON stdout)
    init_database 2>&2
    
    while true; do
        LOOP_START=$(date +%s%3N)
        
        # Collect all raw data
        # Get timestamps FIRST for accurate delta calculations
        TIMESTAMP=$(date +%s)
        TIMESTAMP_MS=$(date +%s%3N)
        
        read cpu_user cpu_nice cpu_sys cpu_idle cpu_iowait cpu_irq cpu_softirq cpu_steal <<< $(get_cpu_raw)
        per_core_stats=$(get_per_core_raw)
        per_core_freq=$(get_per_core_freq)
        cpu_temp=$(get_cpu_temp_raw)
        
        read mem_total mem_free mem_available <<< $(get_memory_raw)
        
        # GPU/NPU info
        read gpu_driver gpu_freq gpu_runtime gpu_mem_used gpu_mem_total <<< $(get_gpu_info)
        npu_info=$(get_npu_info "$TIMESTAMP_MS")
        
        # Only update PREV_NPU_BUSY_US as NPU still calculates on remote
        if [[ "$npu_info" == intel-npu:* ]]; then
            npu_busy=$(cat /sys/class/accel/accel0/device/npu_busy_time_us 2>/dev/null || echo "0")
            PREV_NPU_BUSY_US=$npu_busy
        fi
        
        read net_rx net_tx <<< $(get_network_stats)
        read disk_read disk_write <<< $(get_disk_stats)
        
        # Update previous timestamp and mark first sample complete
        PREV_TIMESTAMP_MS=$TIMESTAMP_MS
        FIRST_SAMPLE=false
        
        # Insert into SQLite database on target device
        # Log every write attempt so we can trace timestamps
        echo "[$(date '+%F %T')] INSERT timestamp=$TIMESTAMP runtime_ms=$gpu_runtime mem_used=$gpu_mem_used" >> /tmp/monitor_db_writes.log
        # Check for errors and log to file for debugging
        if ! sqlite3 "$DB_PATH" "INSERT INTO raw_samples (timestamp, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle, cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz, cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb, gpu_driver, gpu_freq_mhz, gpu_runtime_ms, gpu_memory_used_bytes, gpu_memory_total_bytes, npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors) VALUES ($TIMESTAMP, $TIMESTAMP_MS, $cpu_user, $cpu_nice, $cpu_sys, $cpu_idle, $cpu_iowait, $cpu_irq, $cpu_softirq, $cpu_steal, '$per_core_stats', '$per_core_freq', $cpu_temp, $mem_total, $mem_free, $mem_available, '$gpu_driver', $gpu_freq, $gpu_runtime, $gpu_mem_used, $gpu_mem_total, '$npu_info', $net_rx, $net_tx, $disk_read, $disk_write);" 2>>/tmp/monitor_db_errors.log; then
            echo "[$(date)] DB INSERT failed at timestamp $TIMESTAMP" >> /tmp/monitor_db_errors.log
        fi
        
        # Output JSON to stdout (for SSH streaming to host)
        # Send RAW gpu_runtime_ms AND timestamp_ms for accurate host-side calculation
        printf '{"timestamp_ms":%s,"cpu_raw":{"user":%d,"nice":%d,"sys":%d,"idle":%d,"iowait":%d,"irq":%d,"softirq":%d,"steal":%d},"per_core_raw":[%s],"per_core_freq_khz":[%s],"cpu_temp_millideg":%d,"mem_total_kb":%d,"mem_free_kb":%d,"mem_available_kb":%d,"gpu_driver":"%s","gpu_freq_mhz":%d,"gpu_runtime_ms":%d,"gpu_memory_used_bytes":%d,"gpu_memory_total_bytes":%d,"npu_info":"%s","net_rx_bytes":%d,"net_tx_bytes":%d,"disk_read_sectors":%d,"disk_write_sectors":%d}\n' \
            "$TIMESTAMP_MS" \
            "$cpu_user" "$cpu_nice" "$cpu_sys" "$cpu_idle" "$cpu_iowait" "$cpu_irq" "$cpu_softirq" "$cpu_steal" \
            "$per_core_stats" "$per_core_freq" "$cpu_temp" \
            "$mem_total" "$mem_free" "$mem_available" \
            "$gpu_driver" "$gpu_freq" "$gpu_runtime" "$gpu_mem_used" "$gpu_mem_total" \
            "$npu_info" \
            "$net_rx" "$net_tx" \
            "$disk_read" "$disk_write"
        
        # Sleep until next interval
        LOOP_END=$(date +%s%3N)
        ELAPSED=$((LOOP_END - LOOP_START))
        SLEEP_TIME=$((INTERVAL * 1000 - ELAPSED))
        if [ "$SLEEP_TIME" -gt 0 ]; then
            sleep $(awk "BEGIN {print $SLEEP_TIME/1000}")
        fi
    done
}

main
