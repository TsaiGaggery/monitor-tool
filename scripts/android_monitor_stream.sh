#!/system/bin/sh
# Android System Monitor - Streaming Version (outputs JSON to stdout)
# 
# This script outputs JSON data to stdout for real-time monitoring via ADB
# Usage: adb shell /data/local/tmp/android_monitor_stream.sh [interval]

INTERVAL=${1:-1}
LOG_TAG="AndroidMonitorStream"

# CPU usage calculation
get_cpu_usage() {
    awk '{print $1,$2,$3,$4,$5}' /proc/stat | head -1 > /tmp/cpu1
    sleep 0.1
    awk '{print $1,$2,$3,$4,$5}' /proc/stat | head -1 > /tmp/cpu2
    
    read cpu user1 nice1 system1 idle1 < /tmp/cpu1
    read cpu user2 nice2 system2 idle2 < /tmp/cpu2
    
    user=$((user2 - user1))
    nice=$((nice2 - nice1))
    system=$((system2 - system1))
    idle=$((idle2 - idle1))
    
    total=$((user + nice + system + idle))
    active=$((total - idle))
    
    if [ "$total" -gt 0 ]; then
        cpu_percent=$((active * 10000 / total))
        echo "$((cpu_percent / 100)).$((cpu_percent % 100))"
    else
        echo "0.0"
    fi
}

# Per-core CPU usage
get_per_core_usage() {
    grep "^cpu[0-9]" /proc/stat > /tmp/cores1
    sleep 0.1
    grep "^cpu[0-9]" /proc/stat > /tmp/cores2
    
    paste /tmp/cores1 /tmp/cores2 | while read line; do
        set -- $line
        cpu1=$1; user1=$2; nice1=$3; sys1=$4; idle1=$5
        cpu2=$10; user2=$11; nice2=$12; sys2=$13; idle2=$14
        
        user=$((user2 - user1))
        nice=$((nice2 - nice1))
        sys=$((sys2 - sys1))
        idle=$((idle2 - idle1))
        
        total=$((user + nice + sys + idle))
        active=$((total - idle))
        
        if [ "$total" -gt 0 ]; then
            percent=$((active * 10000 / total))
            echo -n "$((percent / 100)).$((percent % 100)),"
        else
            echo -n "0.0,"
        fi
    done
    echo ""
}

# CPU frequency per-core
get_per_core_freq() {
    for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
        if [ -f "$cpu_dir/cpufreq/scaling_cur_freq" ]; then
            freq=$(cat "$cpu_dir/cpufreq/scaling_cur_freq")
            echo -n "$((freq / 1000)),"
        else
            echo -n "0,"
        fi
    done
    echo ""
}

# CPU temperature
get_cpu_temp() {
    temp=0
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        temp=$(cat /sys/class/thermal/thermal_zone0/temp)
        temp=$((temp / 1000))
    elif [ -f /sys/class/hwmon/hwmon0/temp1_input ]; then
        temp=$(cat /sys/class/hwmon/hwmon0/temp1_input)
        temp=$((temp / 1000))
    fi
    echo "$temp"
}

# Memory info
get_memory_info() {
    mem_total=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
    mem_available=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
    mem_free=$(awk '/MemFree:/ {print $2}' /proc/meminfo)
    
    if [ -z "$mem_available" ]; then
        mem_buffers=$(awk '/Buffers:/ {print $2}' /proc/meminfo)
        mem_cached=$(awk '/^Cached:/ {print $2}' /proc/meminfo)
        mem_available=$((mem_free + mem_buffers + mem_cached))
    fi
    
    mem_used=$((mem_total - mem_available))
    
    if [ "$mem_total" -gt 0 ]; then
        # Use awk for floating point calculation to avoid integer overflow
        mem_percent_dec=$(awk -v used="$mem_used" -v total="$mem_total" 'BEGIN {printf "%.2f", (used * 100.0 / total)}')
    else
        mem_percent_dec="0.00"
    fi
    
    echo "$mem_total $mem_used $mem_available $mem_percent_dec"
}

# GPU info (Intel x86)
get_gpu_info() {
    gpu_freq=0
    if [ -f /sys/class/drm/card0/gt_cur_freq_mhz ]; then
        freq_val=$(cat /sys/class/drm/card0/gt_cur_freq_mhz 2>/dev/null)
        if [ -n "$freq_val" ]; then
            gpu_freq=$freq_val
        fi
    fi
    echo "${gpu_freq:-0}"
}

# Network I/O
get_network_io() {
    cat /proc/net/dev | grep -v "lo:" | awk 'NR>2 {rx+=$2; tx+=$10} END {print rx,tx}'
}

# Disk I/O
get_disk_io() {
    awk '{reads+=$6; writes+=$10} END {print reads,writes}' /proc/diskstats
}

# Main streaming loop
main() {
    # Initial network/disk baseline
    read net_rx1 net_tx1 <<< $(get_network_io)
    read disk_read1 disk_write1 <<< $(get_disk_io)
    
    while true; do
        LOOP_START=$(date +%s)
        
        # Collect CPU data
        cpu_usage=$(get_cpu_usage)
        cpu_freq_avg=$(awk '/cpu MHz/ {sum+=$4; count++} END {if(count>0) print int(sum/count); else print 0}' /proc/cpuinfo)
        cpu_temp=$(get_cpu_temp)
        per_core_usage=$(get_per_core_usage)
        per_core_freq=$(get_per_core_freq)
        
        # Collect Memory data
        read mem_total mem_used mem_available mem_percent <<< $(get_memory_info)
        
        # Collect GPU data
        gpu_freq=$(get_gpu_info)
        
        # Collect Network I/O
        read net_rx2 net_tx2 <<< $(get_network_io)
        net_rx_speed=$(( (net_rx2 - net_rx1) / INTERVAL ))
        net_tx_speed=$(( (net_tx2 - net_tx1) / INTERVAL ))
        net_rx1=$net_rx2
        net_tx1=$net_tx2
        
        # Collect Disk I/O
        read disk_read2 disk_write2 <<< $(get_disk_io)
        disk_read_speed=$(( (disk_read2 - disk_read1) / INTERVAL ))
        disk_write_speed=$(( (disk_write2 - disk_write1) / INTERVAL ))
        disk_read1=$disk_read2
        disk_write1=$disk_write2
        
        # Remove trailing commas
        per_core_usage=$(echo "$per_core_usage" | sed 's/,$//')
        per_core_freq=$(echo "$per_core_freq" | sed 's/,$//')
        
        # Output JSON (single line, use printf to avoid any formatting)
        printf '{"cpu_usage":%s,"cpu_freq":%s,"cpu_temp":%s,"per_core_usage":[%s],"per_core_freq":[%s],"mem_total":%s,"mem_used":%s,"mem_available":%s,"mem_percent":%s,"gpu_freq":%s,"net_rx":%s,"net_tx":%s,"disk_read":%s,"disk_write":%s}\n' \
            "$cpu_usage" "$cpu_freq_avg" "$cpu_temp" "$per_core_usage" "$per_core_freq" \
            "$mem_total" "$mem_used" "$mem_available" "$mem_percent" "$gpu_freq" \
            "$net_rx_speed" "$net_tx_speed" "$disk_read_speed" "$disk_write_speed"
        
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
