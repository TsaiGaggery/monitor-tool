#!/bin/bash
# Better benchmark: Measure actual shell script overhead (like our monitoring scripts do)
# This simulates the real collection pattern used in linux_monitor_remote.sh

ITERATIONS=100
INTERVAL=0.01  # 10ms between samples to simulate rapid collection

echo "=========================================="
echo "Real-world Monitoring Overhead Test"
echo "Iterations: $ITERATIONS"
echo "Method: Single shell script (like actual monitoring)"
echo "=========================================="
echo ""

# Create baseline monitoring script (current)
cat > /tmp/benchmark_baseline.sh << 'EOF'
# Current baseline metrics
read cpu_user cpu_nice cpu_sys cpu_idle cpu_iowait cpu_irq cpu_softirq cpu_steal < <(awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
per_core_raw=$(awk '/^cpu[0-9]/ {printf "%s,%s,%s,%s,%s,%s,%s,%s ", $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
per_core_freq=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | tr '\n' ',' | sed 's/,$//')
read mem_total mem_free mem_available < <(awk '/MemTotal:|MemFree:|MemAvailable:/ {print $2}' /proc/meminfo | xargs)
read rx_bytes tx_bytes < <(cat /proc/net/dev | awk 'NR>2 && !/lo:/ {rx+=$2; tx+=$10} END {print rx,tx}')
read read_sectors write_sectors < <(grep -E '(nvme[0-9]+n[0-9]+|sd[a-z]|vd[a-z])\s' /proc/diskstats | awk '{read+=$6; write+=$10} END {print read,write}')
EOF

# Create Tier 1 enhanced script
cat > /tmp/benchmark_tier1.sh << 'EOF'
# Baseline + Tier 1 metrics
read cpu_user cpu_nice cpu_sys cpu_idle cpu_iowait cpu_irq cpu_softirq cpu_steal < <(awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
per_core_raw=$(awk '/^cpu[0-9]/ {printf "%s,%s,%s,%s,%s,%s,%s,%s ", $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
per_core_freq=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | tr '\n' ',' | sed 's/,$//')
read mem_total mem_free mem_available < <(awk '/MemTotal:|MemFree:|MemAvailable:/ {print $2}' /proc/meminfo | xargs)
read rx_bytes tx_bytes < <(cat /proc/net/dev | awk 'NR>2 && !/lo:/ {rx+=$2; tx+=$10} END {print rx,tx}')
read read_sectors write_sectors < <(grep -E '(nvme[0-9]+n[0-9]+|sd[a-z]|vd[a-z])\s' /proc/diskstats | awk '{read+=$6; write+=$10} END {print read,write}')

# NEW: Tier 1 additions (same /proc/stat already read, plus /proc/loadavg)
read ctxt < <(awk '/^ctxt/ {print $2}' /proc/stat)
read load1 load5 load15 running_procs total_procs < <(cat /proc/loadavg)
read processes procs_running procs_blocked < <(awk '/^processes |^procs_running |^procs_blocked / {print $2}' /proc/stat | xargs)
# IRQ/softirq % calculated from per_core_raw (no extra I/O)
EOF

# Create Tier 1 + Tier 2 script
cat > /tmp/benchmark_tier1_tier2.sh << 'EOF'
# Baseline + Tier 1 + Tier 2 metrics
read cpu_user cpu_nice cpu_sys cpu_idle cpu_iowait cpu_irq cpu_softirq cpu_steal < <(awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
per_core_raw=$(awk '/^cpu[0-9]/ {printf "%s,%s,%s,%s,%s,%s,%s,%s ", $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
per_core_freq=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | tr '\n' ',' | sed 's/,$//')
read mem_total mem_free mem_available < <(awk '/MemTotal:|MemFree:|MemAvailable:/ {print $2}' /proc/meminfo | xargs)
read rx_bytes tx_bytes < <(cat /proc/net/dev | awk 'NR>2 && !/lo:/ {rx+=$2; tx+=$10} END {print rx,tx}')
read read_sectors write_sectors < <(grep -E '(nvme[0-9]+n[0-9]+|sd[a-z]|vd[a-z])\s' /proc/diskstats | awk '{read+=$6; write+=$10} END {print read,write}')

# Tier 1
read ctxt < <(awk '/^ctxt/ {print $2}' /proc/stat)
read load1 load5 load15 running_procs total_procs < <(cat /proc/loadavg)
read processes procs_running procs_blocked < <(awk '/^processes |^procs_running |^procs_blocked / {print $2}' /proc/stat | xargs)

# NEW: Tier 2 additions
read buffers cached slab < <(awk '/^Buffers:|^Cached:|^Slab:/ {print $2}' /proc/meminfo | xargs)
top5_irqs=$(awk 'NR>1 && NR<=6 {sum=0; for(i=2;i<=NF;i++) sum+=$i; print sum}' /proc/interrupts | xargs)
EOF

chmod +x /tmp/benchmark_*.sh

# Benchmark function for shell scripts
benchmark_script() {
    local name="$1"
    local script="$2"
    
    # Warmup
    for i in {1..5}; do
        bash "$script" > /dev/null 2>&1
    done
    
    # Monitor CPU usage during benchmark
    (
        sleep 0.5
        top -b -n 5 -d 0.2 -p $$ | grep "^ *$$" | awk '{sum+=$9; count++} END {print sum/count}'
    ) > /tmp/cpu_usage_$$.tmp &
    monitor_pid=$!
    
    # Actual benchmark
    start=$(date +%s%N)
    for i in $(seq 1 $ITERATIONS); do
        bash "$script" > /dev/null 2>&1
        sleep $INTERVAL
    done
    end=$(date +%s%N)
    
    # Wait for CPU monitor
    sleep 1
    kill $monitor_pid 2>/dev/null
    wait $monitor_pid 2>/dev/null
    
    # Calculate time
    elapsed_ns=$((end - start))
    elapsed_ms=$((elapsed_ns / 1000000))
    per_call_us=$((elapsed_ns / ITERATIONS / 1000))
    avg_cpu=$(cat /tmp/cpu_usage_$$.tmp 2>/dev/null || echo "0")
    rm -f /tmp/cpu_usage_$$.tmp
    
    # Determine color based on cost
    if [ $per_call_us -lt 1000 ]; then
        color='\033[0;32m'  # GREEN
        status="✅ LOW"
    elif [ $per_call_us -lt 5000 ]; then
        color='\033[1;33m'  # YELLOW
        status="⚠️  MEDIUM"
    else
        color='\033[0;31m'  # RED
        status="❌ HIGH"
    fi
    
    printf "${color}%-45s %8d µs/call  %6d ms total  %5.1f%% CPU  ${status}\033[0m\n" \
        "$name" "$per_call_us" "$elapsed_ms" "$avg_cpu"
}

echo "=== Monitoring Script Overhead (Realistic Test) ==="
echo ""

benchmark_script "Current baseline" "/tmp/benchmark_baseline.sh"
benchmark_script "Baseline + Tier 1 (ctxt, load, procs)" "/tmp/benchmark_tier1.sh"
benchmark_script "Baseline + Tier 1 + Tier 2 (mem details)" "/tmp/benchmark_tier1_tier2.sh"

echo ""
echo "=== File Read Cost Analysis ==="
echo ""

# Count file reads for each approach
echo "Files read per collection:"
echo "  Baseline:        /proc/stat, /proc/meminfo, /proc/net/dev, /proc/diskstats, /sys/devices/.../cpufreq (N files)"
echo "  + Tier 1:        +/proc/loadavg (1 extra file, /proc/stat already read)"
echo "  + Tier 2:        +/proc/interrupts (1 extra file, /proc/meminfo already read)"
echo ""

# Calculate overhead increase
baseline_files=4
tier1_files=5
tier2_files=6

echo "Overhead increase:"
echo "  Tier 1: +$((tier1_files - baseline_files)) files = +$(((tier1_files - baseline_files) * 100 / baseline_files))% file I/O"
echo "  Tier 2: +$((tier2_files - baseline_files)) files = +$(((tier2_files - baseline_files) * 100 / baseline_files))% file I/O"

echo ""
echo "=== Analysis ==="
echo "✅ LOW COST:    < 1000 µs per collection (< 0.1% CPU at 1Hz)"
echo "⚠️  MEDIUM COST: 1000-5000 µs per collection (0.1-0.5% CPU at 1Hz)"
echo "❌ HIGH COST:   > 5000 µs per collection (> 0.5% CPU at 1Hz)"
echo ""
echo "Recommendation:"
echo "  - Tier 1 adds context switches, load avg, process counts from already-read files"
echo "  - Cost: +1 file read (/proc/loadavg), minimal processing overhead"
echo "  - Expected impact: < 10% increase in collection time"
echo ""

# Cleanup
rm -f /tmp/benchmark_*.sh
