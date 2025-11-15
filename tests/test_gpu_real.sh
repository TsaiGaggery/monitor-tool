#!/bin/bash
# Real GPU workload test for NoMachine

echo "=== Intel GPU Real Workload Test (NoMachine compatible) ==="
echo ""

# Install glmark2 if not present
if ! command -v glmark2 &> /dev/null; then
    echo "Installing glmark2..."
    sudo apt update
    sudo apt install -y glmark2
fi

echo "Before GPU load:"
echo "  act_freq: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq) MHz"
echo "  cur_freq: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq) MHz"
echo ""

echo "Starting GPU workload with glmark2..."
echo "This will run for about 10 seconds"
echo ""

# Run glmark2 in benchmark mode (single test)
timeout 10 glmark2 --benchmark build &
BENCH_PID=$!

# Monitor GPU while benchmark runs
echo "Monitoring GPU frequency:"
for i in {1..10}; do
    sleep 1
    ACT=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq 2>/dev/null)
    CUR=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq 2>/dev/null)
    MIN=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/min_freq 2>/dev/null)
    MAX=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/max_freq 2>/dev/null)
    
    # Calculate usage based on actual frequency
    if [ "$ACT" -gt 0 ] && [ "$MAX" -gt "$MIN" ]; then
        USAGE=$(( (ACT - MIN) * 100 / (MAX - MIN) ))
    else
        USAGE=0
    fi
    
    echo "[$i] act: ${ACT} MHz, cur: ${CUR} MHz, usage: ${USAGE}%"
done

wait $BENCH_PID 2>/dev/null

echo ""
echo "After GPU load:"
echo "  act_freq: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq) MHz"
echo ""
echo "✓ Check your monitor-tool dashboard now!"
