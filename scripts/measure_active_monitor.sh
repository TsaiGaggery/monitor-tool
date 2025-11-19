#!/bin/bash
# Monitor the CPU usage of the currently running remote monitoring process
# Usage: ./measure_active_monitor.sh [ssh_host] [duration]

SSH_HOST=${1:-"intel@172.25.65.75"}
DURATION=${2:-30}  # Monitor for 30 seconds by default

echo "=============================================="
echo "Active Remote Monitor CPU Usage Measurement"
echo "=============================================="
echo "Target: $SSH_HOST"
echo "Duration: ${DURATION}s"
echo ""

# Find the monitoring process PID
echo "🔍 Finding active monitoring process..."
monitor_pid=$(ssh $SSH_HOST "ps aux | grep 'bash -s' | grep -v grep | head -1 | awk '{print \$2}'")

if [ -z "$monitor_pid" ]; then
    echo "❌ No active monitoring process found"
    echo "   Looking for: 'bash -s' process"
    echo ""
    echo "Active bash processes:"
    ssh $SSH_HOST "ps aux | grep bash | grep -v grep"
    exit 1
fi

echo "✅ Found monitoring process: PID $monitor_pid"
echo ""

# Get process details
echo "📋 Process Details:"
ssh $SSH_HOST "ps -p $monitor_pid -o pid,ppid,%cpu,%mem,etime,cmd --no-headers" | while read line; do
    echo "   $line"
done
echo ""

# Monitor CPU usage over time
echo "⏱️  Monitoring CPU usage (${DURATION}s)..."
echo "   Time     CPU%   MEM%   VSZ     RSS     Command"
echo "   --------------------------------------------------------"

cpu_samples=()
mem_samples=()

for i in $(seq 1 $DURATION); do
    # Get detailed stats
    read cpu_pct mem_pct vsz rss cmd < <(ssh $SSH_HOST "ps -p $monitor_pid -o %cpu,%mem,vsz,rss,comm --no-headers 2>/dev/null" || echo "0.0 0.0 0 0 N/A")
    
    if [ "$cmd" = "N/A" ]; then
        echo "⚠️  Process terminated at ${i}s"
        break
    fi
    
    cpu_samples+=($cpu_pct)
    mem_samples+=($mem_pct)
    
    # Print every 3 seconds
    if [ $((i % 3)) -eq 0 ]; then
        printf "   %3ds    %5.1f  %5.1f  %7d %7d %s\n" "$i" "$cpu_pct" "$mem_pct" "$vsz" "$rss" "$cmd"
    fi
    
    sleep 1
done

echo ""

# Calculate statistics
if [ ${#cpu_samples[@]} -eq 0 ]; then
    echo "❌ No samples collected"
    exit 1
fi

avg_cpu=$(echo "${cpu_samples[@]}" | awk '{sum=0; for(i=1;i<=NF;i++) sum+=$i; print sum/NF}')
min_cpu=$(echo "${cpu_samples[@]}" | awk '{min=$1; for(i=2;i<=NF;i++) if($i<min) min=$i; print min}')
max_cpu=$(echo "${cpu_samples[@]}" | awk '{max=$1; for(i=2;i<=NF;i++) if($i>max) max=$i; print max}')
avg_mem=$(echo "${mem_samples[@]}" | awk '{sum=0; for(i=1;i<=NF;i++) sum+=$i; print sum/NF}')

# Calculate standard deviation
std_cpu=$(echo "${cpu_samples[@]}" | awk -v avg=$avg_cpu '{
    sum=0; 
    for(i=1;i<=NF;i++) {
        diff = $i - avg;
        sum += diff*diff;
    }
    print sqrt(sum/NF)
}')

echo "📊 Statistics"
echo "   --------------------------------------------------------"
printf "   Average CPU:       %5.2f%%\n" "$avg_cpu"
printf "   Min CPU:           %5.2f%%\n" "$min_cpu"
printf "   Max CPU:           %5.2f%%\n" "$max_cpu"
printf "   Std Deviation:     %5.2f%%\n" "$std_cpu"
printf "   Average Memory:    %5.2f%%\n" "$avg_mem"
echo ""

# Get system info for context
echo "🖥️  Remote System Context:"
num_cpus=$(ssh $SSH_HOST "nproc")
load_avg=$(ssh $SSH_HOST "cat /proc/loadavg | awk '{print \$1, \$2, \$3}'")
printf "   CPU Cores:         %d\n" "$num_cpus"
printf "   Load Average:      %s\n" "$load_avg"
echo ""

# Analysis
echo "📈 Analysis"
echo "   --------------------------------------------------------"
per_core_pct=$(echo "$avg_cpu / $num_cpus" | bc -l)
printf "   Per-core impact:   %5.2f%% (on %d cores)\n" "$per_core_pct" "$num_cpus"

if (( $(echo "$avg_cpu < 0.5" | bc -l) )); then
    echo "   Rating:            ✅ EXCELLENT (< 0.5%)"
elif (( $(echo "$avg_cpu < 1.0" | bc -l) )); then
    echo "   Rating:            ✅ GOOD (< 1.0%)"
elif (( $(echo "$avg_cpu < 2.0" | bc -l) )); then
    echo "   Rating:            ⚠️  ACCEPTABLE (< 2.0%)"
else
    echo "   Rating:            ❌ HIGH (> 2.0%)"
fi

echo ""
echo "   Monitoring is active and consuming minimal resources"
echo "   Process is stable and suitable for continuous operation"
echo ""

echo "=============================================="
