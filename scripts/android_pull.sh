#!/bin/bash
# Pull monitoring data from Android device and generate HTML report

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEVICE_DB="/data/local/tmp/monitor.db"
LOCAL_DB="$PROJECT_ROOT/android_monitor_data.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_HTML="android_report_${TIMESTAMP}.html"

echo "========================================="
echo "Android Monitor - Pull Data & Report"
echo "========================================="

# Check ADB connection
if ! adb devices | grep -q "device$"; then
    echo "❌ No Android device connected"
    exit 1
fi

# Check if database exists on device
if ! adb shell "test -f $DEVICE_DB && echo exists" | grep -q exists; then
    echo "❌ No monitoring data found on device"
    echo "   Start monitoring first: ./scripts/android_start.sh"
    exit 1
fi

# Pull database
echo "📥 Pulling database from device..."
adb pull "$DEVICE_DB" "$LOCAL_DB"

# Check record count
RECORD_COUNT=$(sqlite3 "$LOCAL_DB" "SELECT COUNT(*) FROM monitoring_data;")
echo "✓ Found $RECORD_COUNT data points"

if [ "$RECORD_COUNT" -eq 0 ]; then
    echo "⚠️  No data recorded yet"
    exit 0
fi

# Get time range
TIME_RANGE=$(sqlite3 "$LOCAL_DB" "SELECT MIN(timestamp), MAX(timestamp) FROM monitoring_data;")
echo "✓ Time range: $TIME_RANGE"

# Generate HTML report using Python CLI monitor
echo ""
echo "📊 Generating HTML report..."
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Use CLI monitor to export HTML (it can read from any database)
python3 - <<PYTHON_SCRIPT
import sys
import os
sys.path.insert(0, 'src')

from storage.data_exporter import DataExporter
import sqlite3
import json
from datetime import datetime

# Load data from Android database
db_path = "$LOCAL_DB"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT * FROM monitoring_data ORDER BY timestamp")
rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]
conn.close()

print(f"Processing {len(rows)} samples...")

# Create exporter and add samples
exporter = DataExporter()
first_timestamp = None

for i, row in enumerate(rows):
    data = dict(zip(columns, row))
    
    # Parse JSON data
    try:
        full_data = json.loads(data.get('data_json', '{}'))
    except:
        full_data = {}
    
    # Calculate time offset
    timestamp_str = data.get('timestamp', '')
    if first_timestamp is None and timestamp_str:
        first_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    
    if first_timestamp and timestamp_str:
        current_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        time_seconds = (current_time - first_timestamp).total_seconds()
    else:
        time_seconds = i
    
    # Build sample in GUI format
    sample = {
        'timestamp': timestamp_str,
        'time_seconds': time_seconds,
        'cpu': full_data.get('cpu', {}),
        'memory': full_data.get('memory', {}),
        'gpu': full_data.get('gpu', {}),
        'npu': {'available': False},  # No NPU on this device
    }
    exporter.add_sample(sample)

# Export to HTML
filepath = exporter.export_html("$OUTPUT_HTML")
print(f"✅ HTML report: {filepath}")
PYTHON_SCRIPT

echo ""
echo "========================================="
echo "✅ Complete!"
echo "========================================="
echo "Database: $LOCAL_DB"
echo "Report: $OUTPUT_HTML"
echo ""
echo "Open report: xdg-open $OUTPUT_HTML"
echo ""
