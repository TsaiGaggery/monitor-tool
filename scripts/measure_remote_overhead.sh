#!/bin/bash
# Measure CPU overhead of remote monitoring on intel@172.25.65.75
# This script connects via SSH and measures the actual CPU usage

SSH_HOST=${1:-"intel@172.25.65.75"}
DURATION=${2:-60}  # Measure for 60 seconds
TIER1_ENABLED=${3:-0}  # 0=disabled, 1=enabled

echo "=============================================="
echo "Remote Monitoring CPU Overhead Measurement"
echo "=============================================="
echo "Target: $SSH_HOST"
echo "Duration: ${DURATION}s"
echo "Tier 1 Metrics: $([ "$TIER1_ENABLED" = "1" ] && echo "ENABLED" || echo "DISABLED")"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Get baseline CPU usage (no monitoring)
echo "📊 Step 1: Measuring baseline CPU usage (10s)..."
baseline_cpu=$(ssh $SSH_HOST "top -b -n 10 -d 1 | grep '^%Cpu' | awk '{sum+=\$2} END {print sum/NR}'")
echo "   Baseline CPU: ${baseline_cpu}%"
echo ""

# Step 2: Start monitoring in background
echo "🚀 Step 2: Starting monitoring script..."
monitor_script_path="/tmp/linux_monitor_remote_$$.sh"

# Copy monitoring script to remote
scp -q scripts/linux_monitor_remote.sh ${SSH_HOST}:${monitor_script_path}

# Start monitoring in background and get PID
ssh $SSH_HOST "bash ${monitor_script_path} 1 ${TIER1_ENABLED} > /dev/null 2>&1 & echo \$!" > /tmp/monitor_pid_$$.txt
monitor_pid=$(cat /tmp/monitor_pid_$$.txt)

if [ -z "$monitor_pid" ]; then
    echo "❌ Failed to start monitoring script"
    exit 1
fi

echo "   Monitor PID: $monitor_pid"
echo ""

# Step 3: Measure CPU usage of monitoring process
echo "⏱️  Step 3: Measuring monitoring CPU overhead (${DURATION}s)..."
echo "   Timestamp          CPU%    MEM%    Command"
echo "   -----------------------------------------------"

# Collect samples every second
cpu_samples=()
mem_samples=()

for i in $(seq 1 $DURATION); do
    # Get CPU and memory usage of the monitoring process
    read cpu_pct mem_pct cmd < <(ssh $SSH_HOST "ps -p $monitor_pid -o %cpu,%mem,comm --no-headers 2>/dev/null" || echo "0.0 0.0 N/A")
    
    if [ "$cmd" = "N/A" ]; then
        echo "⚠️  Monitoring process died at ${i}s"
        break
    fi
    
    cpu_samples+=($cpu_pct)
    mem_samples+=($mem_pct)
    
    # Print every 5 seconds
    if [ $((i % 5)) -eq 0 ]; then
        timestamp=$(date '+%H:%M:%S')
        printf "   ${timestamp}        %5.2f   %5.2f   %s\n" "$cpu_pct" "$mem_pct" "$cmd"
    fi
    
    sleep 1
done

echo ""

# Step 4: Stop monitoring
echo "🛑 Step 4: Stopping monitoring..."
ssh $SSH_HOST "kill $monitor_pid 2>/dev/null; rm -f ${monitor_script_path} /tmp/monitor_tool_*.db"
echo ""

# Step 5: Calculate statistics
echo "📈 Step 5: Statistics"
echo "   -----------------------------------------------"

# Calculate average, min, max CPU usage
if [ ${#cpu_samples[@]} -eq 0 ]; then
    echo "❌ No samples collected"
    exit 1
fi

avg_cpu=$(echo "${cpu_samples[@]}" | awk '{sum=0; for(i=1;i<=NF;i++) sum+=$i; print sum/NF}')
min_cpu=$(echo "${cpu_samples[@]}" | awk '{min=$1; for(i=2;i<=NF;i++) if($i<min) min=$i; print min}')
max_cpu=$(echo "${cpu_samples[@]}" | awk '{max=$1; for(i=2;i<=NF;i++) if($i>max) max=$i; print max}')

avg_mem=$(echo "${mem_samples[@]}" | awk '{sum=0; for(i=1;i<=NF;i++) sum+=$i; print sum/NF}')

# Determine color based on CPU usage
if (( $(echo "$avg_cpu < 0.5" | bc -l) )); then
    color=$GREEN
    rating="✅ EXCELLENT"
elif (( $(echo "$avg_cpu < 1.0" | bc -l) )); then
    color=$YELLOW
    rating="⚠️  ACCEPTABLE"
else
    color=$RED
    rating="❌ HIGH"
fi

printf "   Baseline CPU:      %5.2f%%\n" "$baseline_cpu"
printf "   ${color}Average CPU:       %5.2f%% ${rating}${NC}\n" "$avg_cpu"
printf "   Min CPU:           %5.2f%%\n" "$min_cpu"
printf "   Max CPU:           %5.2f%%\n" "$max_cpu"
printf "   Average Memory:    %5.2f%%\n" "$avg_mem"
echo ""

# Step 6: Analysis
echo "📊 Analysis"
echo "   -----------------------------------------------"
overhead=$(echo "$avg_cpu - $baseline_cpu" | bc -l)
printf "   Monitoring Overhead: %+.2f%% CPU\n" "$overhead"
echo ""

# Per-sample overhead estimate
collection_interval=1  # 1 second
per_sample_ms=$(echo "$avg_cpu * 10" | bc -l)  # Rough estimate: CPU% * 10ms
printf "   Est. per-sample cost: ~%.1f ms (at 1Hz)\n" "$per_sample_ms"
echo ""

# Comparison with benchmark
echo "   Benchmark Comparison:"
echo "   - Benchmark estimated: ~51ms per collection (with Tier 1)"
echo "   - Benchmark estimated: ~38ms per collection (baseline)"
printf "   - Actual measured: ~%.1f ms average\n" "$per_sample_ms"
echo ""

if (( $(echo "$avg_cpu < 1.0" | bc -l) )); then
    echo "✅ VERDICT: Monitoring overhead is acceptable (< 1% CPU)"
    echo "   Safe to run continuously in production"
else
    echo "⚠️  VERDICT: Monitoring overhead is significant (> 1% CPU)"
    echo "   Consider increasing collection interval or disabling Tier 1"
fi
echo ""

# Cleanup
rm -f /tmp/monitor_pid_$$.txt

echo "=============================================="
echo "Measurement Complete"
echo "=============================================="
