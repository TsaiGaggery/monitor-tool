#!/bin/bash
# Remote Linux System Monitor - JSON Streaming + SQLite Storage
# Outputs monitoring data in JSON format, similar to Android monitor
# Also stores data in local SQLite database
# Usage: ssh user@host "bash -s" < linux_monitor.sh [interval]

INTERVAL=${1:-1}
DB_PATH="/tmp/monitor_tool_${USER}.db"

# Previous values for delta calculation (host-side)
PREV_XE_IDLE_MS=0
PREV_I915_RC6_MS=0
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
    gpu_info TEXT,
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

# Get GPU info (NVIDIA or Intel)
get_gpu_info() {
    local current_ts_ms=$1  # Pass current timestamp for delta calculation
    
    # Try NVIDIA first
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia_info=$(nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.gr --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ -n "$nvidia_info" ]; then
            # NVIDIA reports utilization directly
            echo "nvidia:$nvidia_info"
            return
        fi
    fi
    
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
                xe_freq_path="/sys/class/drm/card${card_num}/device/tile0/gt0/freq0/act_freq"
                xe_freq_cur_path="/sys/class/drm/card${card_num}/device/tile0/gt0/freq0/cur_freq"
                
                if [ -f "$xe_idle_path" ]; then
                    # Intel Xe GPU
                    xe_idle=$(cat "$xe_idle_path" 2>/dev/null || echo "0")
                    # Only use act_freq (actual frequency), not cur_freq
                    xe_freq=$(cat "$xe_freq_path" 2>/dev/null || echo "0")
                    # Note: If act_freq returns 0, it means driver doesn't support it
                    # We intentionally show 0 instead of falling back to cur_freq

                    
                    # Get memory from fdinfo (approximate) - DISABLED: too slow
                    # Scanning all /proc/*/fdinfo/* takes too long (thousands of files)
                    mem_used=0
                    # for fd in /proc/*/fdinfo/*; do
                    #     if [ -f "$fd" ] && grep -q "drm-memory-vram" "$fd" 2>/dev/null; then
                    #         mem=$(grep "drm-memory-vram" "$fd" | awk '{print $2}')
                    #         mem_used=$((mem_used + mem))
                    #     fi
                    # done
                    mem_used_mb=$((mem_used / 1024))  # KB to MB
                    
                    # Calculate utilization on host
                    gpu_util=0
                    if [ "$FIRST_SAMPLE" = false ] && [ "$PREV_TIMESTAMP_MS" -gt 0 ]; then
                        time_delta=$((current_ts_ms - PREV_TIMESTAMP_MS))
                        idle_delta=$((xe_idle - PREV_XE_IDLE_MS))
                        
                        if [ "$time_delta" -gt 0 ]; then
                            # Clamp idle_delta to time_delta
                            if [ "$idle_delta" -gt "$time_delta" ]; then
                                idle_delta=$time_delta
                            fi
                            
                            # Utilization = 100 - (idle_percentage) using awk for float math
                            gpu_util=$(awk "BEGIN {printf \"%.0f\", 100 - ($idle_delta * 100.0 / $time_delta)}")
                            
                            # Clamp to 0-100
                            if [ "$gpu_util" -lt 0 ]; then gpu_util=0; fi
                            if [ "$gpu_util" -gt 100 ]; then gpu_util=100; fi
                        fi
                    fi
                    
                    PREV_XE_IDLE_MS=$xe_idle
                    
                    # Output format: type:card_num:name:util:freq_mhz:mem_used_mb
                    echo "intel-xe:${card_num}:${gpu_name}:${gpu_util}:${xe_freq}:${mem_used_mb}"
                    return
                fi
                
                # Check for i915 driver
                i915_rc6_path="/sys/class/drm/card${card_num}/gt/gt0/rc6_residency_ms"
                i915_freq_path="/sys/class/drm/card${card_num}/gt_cur_freq_mhz"
                
                if [ -f "$i915_rc6_path" ]; then
                    # Intel i915 GPU
                    i915_rc6=$(cat "$i915_rc6_path" 2>/dev/null || echo "0")
                    i915_freq=$(cat "$i915_freq_path" 2>/dev/null || echo "0")
                    
                    # Get memory from i915_gem_objects (if accessible)
                    mem_used_mb=0
                    gem_path="/sys/kernel/debug/dri/${card_num}/i915_gem_objects"
                    if [ -f "$gem_path" ]; then
                        mem_bytes=$(grep "Total" "$gem_path" 2>/dev/null | grep -o '[0-9]* bytes' | grep -o '[0-9]*' | head -1)
                        if [ -n "$mem_bytes" ]; then
                            mem_used_mb=$((mem_bytes / 1024 / 1024))
                        fi
                    fi
                    
                    # Calculate utilization on host
                    gpu_util=0
                    if [ "$FIRST_SAMPLE" = false ] && [ "$PREV_TIMESTAMP_MS" -gt 0 ]; then
                        time_delta=$((current_ts_ms - PREV_TIMESTAMP_MS))
                        rc6_delta=$((i915_rc6 - PREV_I915_RC6_MS))
                        
                        if [ "$time_delta" -gt 0 ]; then
                            # Clamp rc6_delta to time_delta
                            if [ "$rc6_delta" -gt "$time_delta" ]; then
                                rc6_delta=$time_delta
                            fi
                            
                            # Utilization = 100 - (rc6_percentage) using awk for float math
                            gpu_util=$(awk "BEGIN {printf \"%.0f\", 100 - ($rc6_delta * 100.0 / $time_delta)}")
                            
                            # Clamp to 0-100
                            if [ "$gpu_util" -lt 0 ]; then gpu_util=0; fi
                            if [ "$gpu_util" -gt 100 ]; then gpu_util=100; fi
                        fi
                    fi
                    
                    PREV_I915_RC6_MS=$i915_rc6
                    
                    # Output format: type:card_num:name:util:freq_mhz:mem_used_mb
                    echo "intel-i915:${card_num}:${gpu_name}:${gpu_util}:${i915_freq}:${mem_used_mb}"
                    return
                fi
            fi
        fi
    done
    
    echo "none"
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
        LOOP_START=$(date +%s)
        
        # Collect all raw data
        # Get timestamps FIRST for accurate delta calculations
        TIMESTAMP=$(date +%s)
        TIMESTAMP_MS=$(date +%s%3N)
        
        read cpu_user cpu_nice cpu_sys cpu_idle cpu_iowait cpu_irq cpu_softirq cpu_steal <<< $(get_cpu_raw)
        per_core_stats=$(get_per_core_raw)
        per_core_freq=$(get_per_core_freq)
        cpu_temp=$(get_cpu_temp_raw)
        
        read mem_total mem_free mem_available <<< $(get_memory_raw)
        
        # GPU/NPU info - must call directly (not in subshell) to update PREV_* globals
        gpu_info=$(get_gpu_info "$TIMESTAMP_MS")
        npu_info=$(get_npu_info "$TIMESTAMP_MS")
        
        # Update global PREV_* variables after getting GPU/NPU info
        # Extract current values and save for next iteration
        if [[ "$gpu_info" == intel-xe:* ]]; then
            # Parse: intel-xe:card:name:util:freq:mem
            # Save current idle value for next delta calculation
            xe_idle=$(cat /sys/class/drm/card1/device/tile0/gt0/gtidle/idle_residency_ms 2>/dev/null || echo "0")
            PREV_XE_IDLE_MS=$xe_idle
        elif [[ "$gpu_info" == intel-i915:* ]]; then
            i915_rc6=$(cat /sys/class/drm/card0/gt/gt0/rc6_residency_ms 2>/dev/null || echo "0")
            PREV_I915_RC6_MS=$i915_rc6
        fi
        
        if [[ "$npu_info" == intel-npu:* ]]; then
            npu_busy=$(cat /sys/class/accel/accel0/device/npu_busy_time_us 2>/dev/null || echo "0")
            PREV_NPU_BUSY_US=$npu_busy
        fi
        
        read net_rx net_tx <<< $(get_network_stats)
        read disk_read disk_write <<< $(get_disk_stats)
        
        # Update previous timestamp and mark first sample complete
        PREV_TIMESTAMP_MS=$TIMESTAMP_MS
        FIRST_SAMPLE=false
        
        # Insert into SQLite database on target device (redirect to stderr to avoid mixing with JSON stdout)
        sqlite3 "$DB_PATH" "INSERT INTO raw_samples (timestamp, timestamp_ms, cpu_user, cpu_nice, cpu_sys, cpu_idle, cpu_iowait, cpu_irq, cpu_softirq, cpu_steal, per_core_raw, per_core_freq_khz, cpu_temp_millideg, mem_total_kb, mem_free_kb, mem_available_kb, gpu_info, npu_info, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors) VALUES ($TIMESTAMP, $TIMESTAMP_MS, $cpu_user, $cpu_nice, $cpu_sys, $cpu_idle, $cpu_iowait, $cpu_irq, $cpu_softirq, $cpu_steal, '$per_core_stats', '$per_core_freq', $cpu_temp, $mem_total, $mem_free, $mem_available, '$gpu_info', '$npu_info', $net_rx, $net_tx, $disk_read, $disk_write);" 2>&2
        
        # Output JSON to stdout (for SSH streaming to host)
        printf '{"timestamp_ms":%s,"cpu_raw":{"user":%d,"nice":%d,"sys":%d,"idle":%d,"iowait":%d,"irq":%d,"softirq":%d,"steal":%d},"per_core_raw":[%s],"per_core_freq_khz":[%s],"cpu_temp_millideg":%d,"mem_total_kb":%d,"mem_free_kb":%d,"mem_available_kb":%d,"gpu_info":"%s","npu_info":"%s","net_rx_bytes":%d,"net_tx_bytes":%d,"disk_read_sectors":%d,"disk_write_sectors":%d}\n' \
            "$TIMESTAMP_MS" \
            "$cpu_user" "$cpu_nice" "$cpu_sys" "$cpu_idle" "$cpu_iowait" "$cpu_irq" "$cpu_softirq" "$cpu_steal" \
            "$per_core_stats" "$per_core_freq" "$cpu_temp" \
            "$mem_total" "$mem_free" "$mem_available" \
            "$gpu_info" "$npu_info" \
            "$net_rx" "$net_tx" \
            "$disk_read" "$disk_write"
        
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
