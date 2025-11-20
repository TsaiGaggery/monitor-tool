#!/bin/bash
# Push android_monitor.sh to Android device and setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/android_monitor_raw.sh"
DEVICE_PATH="/data/local/tmp/android_monitor.sh"

echo "========================================="
echo "Android Monitor - Push Script"
echo "========================================="

# Check ADB connection
if ! adb devices | grep -q "device$"; then
    echo "❌ No Android device connected"
    echo "   Run: adb connect <device_ip>:5555"
    exit 1
fi

echo "✓ Android device connected"

# Push monitor script
echo "📤 Pushing monitor script to device..."
adb push "$MONITOR_SCRIPT" "$DEVICE_PATH"

# Make it executable
echo "🔧 Setting executable permissions..."
adb shell "chmod +x $DEVICE_PATH"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start monitoring: ./scripts/android_start.sh"
echo "  2. Stop monitoring: ./scripts/android_stop.sh"
echo "  3. Get data: ./scripts/android_pull.sh"
echo ""
