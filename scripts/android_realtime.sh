#!/bin/bash
# Real-time Android monitoring viewer
# Displays live Android monitoring data on Desktop terminal

set -e

echo "========================================="
echo "Android Monitor - Real-Time Viewer"
echo "========================================="

# Check ADB connection
if ! adb devices | grep -q "device$"; then
    echo "❌ No Android device connected"
    exit 1
fi

# Check if monitor is running
if ! adb shell "pgrep -f android_monitor.sh" >/dev/null 2>&1; then
    echo "❌ Android monitor not running"
    echo "   Start it with: ./scripts/android_start.sh"
    exit 1
fi

echo "✓ Connected to Android device"
echo "✓ Monitor is running"
echo ""
echo "Press Ctrl+C to stop viewing"
echo "========================================="
echo ""

# Follow the log file in real-time
adb shell "tail -f /data/local/tmp/monitor.log 2>/dev/null" | while IFS= read -r line; do
    # Color-code the output
    if echo "$line" | grep -q "CPU:"; then
        # Extract values and format nicely
        echo -e "\033[1;36m$(date '+%H:%M:%S')\033[0m $line"
    else
        echo "$line"
    fi
done
