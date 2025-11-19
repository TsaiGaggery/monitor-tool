#!/bin/bash
# Benchmark script to measure CPU cost of collecting monitoring metrics
# Tests individual metric collection overhead

ITERATIONS=1000

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Monitoring Metrics Collection Benchmark"
echo "Iterations: $ITERATIONS"
echo "=========================================="
echo ""

# Benchmark function
benchmark() {
    local name="$1"
    local cmd="$2"
    
    # Warmup
    for i in {1..10}; do
        eval "$cmd" > /dev/null 2>&1
    done
    
    # Actual benchmark
    start=$(date +%s%N)
    for i in $(seq 1 $ITERATIONS); do
        eval "$cmd" > /dev/null 2>&1
    done
    end=$(date +%s%N)
    
    # Calculate time
    elapsed_ns=$((end - start))
    elapsed_ms=$((elapsed_ns / 1000000))
    per_call_us=$((elapsed_ns / ITERATIONS / 1000))
    
    # Determine color based on cost
    if [ $per_call_us -lt 100 ]; then
        color=$GREEN
        status="✅ LOW"
    elif [ $per_call_us -lt 500 ]; then
        color=$YELLOW
        status="⚠️  MEDIUM"
    else
        color=$RED
        status="❌ HIGH"
    fi
    
    printf "${color}%-40s %8d µs/call  %6d ms total  ${status}${NC}\n" \
        "$name" "$per_call_us" "$elapsed_ms"
}

echo "=== Current Metrics (Baseline) ==="
benchmark "CPU raw data (/proc/stat)" \
    "awk '/^cpu / {print \$2,\$3,\$4,\$5,\$6,\$7,\$8,\$9}' /proc/stat"

benchmark "Per-core raw data" \
    "awk '/^cpu[0-9]/ {printf \"%s,%s,%s,%s,%s,%s,%s,%s \", \$2,\$3,\$4,\$5,\$6,\$7,\$8,\$9}' /proc/stat"

benchmark "Per-core frequency" \
    "cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | tr '\n' ','"

benchmark "CPU temperature" \
    "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -1"

benchmark "Memory info (3 fields)" \
    "awk '/MemTotal:|MemFree:|MemAvailable:/ {print \$2}' /proc/meminfo"

benchmark "Network stats" \
    "cat /proc/net/dev | awk 'NR>2 && !/lo:/ {rx+=\$2; tx+=\$10} END {print rx,tx}'"

benchmark "Disk stats" \
    "grep -E '(nvme[0-9]+n[0-9]+|sd[a-z]|vd[a-z])\s' /proc/diskstats | awk '{read+=\$6; write+=\$10} END {print read,write}'"

echo ""
echo "=== Tier 1 - Proposed New Metrics ==="

benchmark "Context switches (1 field)" \
    "awk '/^ctxt/ {print \$2}' /proc/stat"

benchmark "Load average (5 fields)" \
    "cat /proc/loadavg"

benchmark "Process counts (3 fields)" \
    "awk '/^processes|^procs_running|^procs_blocked/ {print \$2}' /proc/stat"

benchmark "Per-core IRQ/softirq % (from existing)" \
    "awk '/^cpu[0-9]/ {total=\$2+\$3+\$4+\$5+\$6+\$7+\$8+\$9; irq_pct=\$7*100/total; softirq_pct=\$8*100/total; printf \"%.2f,%.2f \", irq_pct, softirq_pct}' /proc/stat"

echo ""
echo "=== Tier 2 - Nice to Have Metrics ==="

benchmark "Memory breakdown (8 fields)" \
    "awk '/Buffers:|Cached:|Slab:|SReclaimable:|SUnreclaim:|PageTables:|KernelStack:|Mapped:/ {print \$2}' /proc/meminfo"

benchmark "Top 5 IRQ sources" \
    "awk 'NR>1 && NR<=6 {print \$1,\$2,\$3,\$4,\$5}' /proc/interrupts"

benchmark "Softirq breakdown (per type)" \
    "cat /proc/softirqs"

echo ""
echo "=== Combined Collection Cost ==="

# Current baseline
benchmark "Current baseline (all existing)" \
    "cat /proc/stat /proc/meminfo /proc/net/dev /proc/diskstats > /dev/null 2>&1; cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq /sys/class/thermal/thermal_zone*/temp > /dev/null 2>&1"

# With Tier 1 additions
benchmark "Baseline + Tier 1 additions" \
    "cat /proc/stat /proc/meminfo /proc/net/dev /proc/diskstats /proc/loadavg > /dev/null 2>&1; cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq /sys/class/thermal/thermal_zone*/temp > /dev/null 2>&1"

# With Tier 1 + Tier 2
benchmark "Baseline + Tier 1 + Tier 2" \
    "cat /proc/stat /proc/meminfo /proc/net/dev /proc/diskstats /proc/loadavg /proc/interrupts /proc/softirqs > /dev/null 2>&1; cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq /sys/class/thermal/thermal_zone*/temp > /dev/null 2>&1"

echo ""
echo "=== Analysis ==="
echo "✅ LOW COST:    < 100 µs per call (negligible overhead)"
echo "⚠️  MEDIUM COST: 100-500 µs per call (acceptable for 1Hz monitoring)"
echo "❌ HIGH COST:   > 500 µs per call (may impact system at high frequency)"
echo ""
echo "At 1Hz monitoring (default interval):"
echo "  - LOW cost metrics use < 0.01% CPU"
echo "  - MEDIUM cost metrics use 0.01-0.05% CPU"
echo "  - HIGH cost metrics use > 0.05% CPU"
echo ""
echo "Recommendation: Add only GREEN (✅) and YELLOW (⚠️) metrics"
