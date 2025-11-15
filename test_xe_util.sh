#!/bin/bash
# Test Xe GPU utilization methods

echo "=== Xe GPU Utilization Test ==="
echo ""

echo "1. Frequency Info:"
echo "Current: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq) MHz"
echo "Actual: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq) MHz"
echo "Min: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/min_freq) MHz"
echo "Max: $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/max_freq) MHz"
echo "RP0 (max): $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/rp0_freq) MHz"
echo "RPn (min): $(cat /sys/class/drm/card0/device/tile0/gt0/freq0/rpn_freq) MHz"
echo ""

echo "2. GT Idle Info:"
if [ -d /sys/class/drm/card0/device/tile0/gt0/gtidle ]; then
    ls -la /sys/class/drm/card0/device/tile0/gt0/gtidle/
    echo "Idle files:"
    find /sys/class/drm/card0/device/tile0/gt0/gtidle/ -type f 2>/dev/null | while read f; do
        echo "$f: $(cat $f 2>/dev/null | head -1)"
    done
fi
echo ""

echo "3. Checking for fdinfo (process GPU usage):"
for pid in $(pgrep -x chrome || pgrep -x Xorg); do
    echo "Process $pid:"
    for fd in /proc/$pid/fdinfo/*; do
        if grep -q "drm-" "$fd" 2>/dev/null; then
            echo "  FD: $fd"
            grep "drm-" "$fd" 2>/dev/null | head -10
        fi
    done
done
echo ""

echo "4. Perf events:"
if [ -f /sys/devices/xe_0000_00_02.0/type ]; then
    echo "PMU type: $(cat /sys/devices/xe_0000_00_02.0/type)"
fi
ls -la /sys/devices/xe_0000_00_02.0/events/ 2>/dev/null
echo ""

echo "5. Trying intel_gpu_top:"
timeout 2 intel_gpu_top -J 2>/dev/null | head -50 || echo "intel_gpu_top not available or timed out"
echo ""

echo "6. Memory info from debugfs:"
if [ -f /sys/kernel/debug/dri/0/gtt_mm ]; then
    sudo head -20 /sys/kernel/debug/dri/0/gtt_mm
fi
