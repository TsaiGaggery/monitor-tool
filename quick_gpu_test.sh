#!/bin/bash
# Quick GPU load test

echo "=== Quick GPU Load Test ==="
echo ""

# Method 1: Simple glxgears test
echo "Test 1: Single glxgears (run for 10 seconds)"
echo "Starting glxgears..."
timeout 10 glxgears &
GEARS_PID=$!

# Monitor GPU frequency while glxgears is running
echo ""
echo "Monitoring GPU frequency every second:"
for i in {1..10}; do
    sleep 1
    ACT_FREQ=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq 2>/dev/null || echo "0")
    CUR_FREQ=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq 2>/dev/null || echo "0")
    echo "[$i] act_freq: ${ACT_FREQ} MHz, cur_freq: ${CUR_FREQ} MHz"
done

wait $GEARS_PID 2>/dev/null

echo ""
echo "Test complete. Check monitor-tool dashboard for GPU usage!"
echo ""
echo "If GPU still shows 0%:"
echo "1. Make sure glxgears window is visible (not minimized)"
echo "2. Try installing glmark2: sudo apt install glmark2"
echo "3. Run: glmark2 (this will stress GPU heavily)"
