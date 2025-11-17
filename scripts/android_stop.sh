#!/bin/bash
# Stop monitoring on Android device

set -e

echo "========================================="
echo "Android Monitor - Stop"
echo "========================================="

# Check ADB connection
if ! adb devices | grep -q "device$"; then
    echo "❌ No Android device connected"
    exit 1
fi

# Kill monitor process
echo "🛑 Stopping monitor..."
if adb shell "pkill -f android_monitor.sh" 2>/dev/null; then
    echo "✅ Monitor stopped"
else
    echo "⚠️  No monitor process found"
fi

# Show summary
echo ""
echo "Database location: /data/local/tmp/monitor.db"
echo "Pull data: ./scripts/android_pull.sh"
