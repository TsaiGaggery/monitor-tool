#!/bin/bash
# Start monitoring on Android device

set -e

DEVICE_PATH="/data/local/tmp/android_monitor.sh"
INTERVAL=${1:-1}  # Default 1 second

echo "========================================="
echo "Android Monitor - Start"
echo "========================================="

# Check ADB connection
if ! adb devices | grep -q "device$"; then
    echo "❌ No Android device connected"
    exit 1
fi

# Check if script exists
if ! adb shell "test -f $DEVICE_PATH && echo exists" | grep -q exists; then
    echo "❌ Monitor script not found on device"
    echo "   Run: ./scripts/android_push.sh"
    exit 1
fi

# Kill any existing monitor process
echo "🛑 Stopping any existing monitor..."
adb shell "pkill -f android_monitor.sh" 2>/dev/null || true

# Start monitor in background
echo "🚀 Starting monitor (interval: ${INTERVAL}s)..."
adb shell "nohup $DEVICE_PATH $INTERVAL > /data/local/tmp/monitor.log 2>&1 &"

# Wait a moment and check if it's running
sleep 1
if adb shell "pgrep -f android_monitor.sh" >/dev/null 2>&1; then
    PID=$(adb shell "pgrep -f android_monitor.sh" | tr -d '\r')
    echo "✅ Monitor started (PID: $PID)"
    echo ""
    echo "View logs: adb shell tail -f /data/local/tmp/monitor.log"
    echo "Stop monitoring: ./scripts/android_stop.sh"
else
    echo "❌ Failed to start monitor"
    echo "Check logs: adb shell cat /data/local/tmp/monitor.log"
    exit 1
fi
