#!/usr/bin/env python3
"""Test Android database export functionality."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_source import AndroidDataSource
from storage import DataExporter
import time

def test_android_export():
    """Test exporting data from Android SQLite database."""
    print("🔍 Testing Android database export...")
    
    # Connect to Android device
    device_ip = "192.168.1.68"
    print(f"\n📱 Connecting to {device_ip}...")
    
    data_source = AndroidDataSource(device_ip)
    
    # Create exporter with data source
    exporter = DataExporter(data_source=data_source)
    
    print("\n⏳ Collecting 10 samples for streaming data (for comparison)...")
    for i in range(10):
        data = {
            'timestamp': time.time(),
            'cpu': data_source.get_cpu_info(),
            'memory': data_source.get_memory_info(),
            'gpu': data_source.get_gpu_info(),
            'network': data_source.get_network_info(),
            'disk': data_source.get_disk_info()
        }
        exporter.add_sample(data)
        print(f"  Sample {i+1}/10")
        time.sleep(1)
    
    print(f"\n✅ Collected {len(exporter.session_data)} streaming samples")
    
    # Test HTML export (should pull from Android DB)
    print("\n📊 Testing HTML export (should pull from Android DB)...")
    try:
        html_path = exporter.export_html()
        print(f"✅ HTML export successful: {html_path}")
    except Exception as e:
        print(f"❌ HTML export failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test CSV export
    print("\n📊 Testing CSV export...")
    try:
        csv_path = exporter.export_csv()
        print(f"✅ CSV export successful: {csv_path}")
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test JSON export
    print("\n📊 Testing JSON export...")
    try:
        json_path = exporter.export_json()
        print(f"✅ JSON export successful: {json_path}")
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ All export tests completed!")

if __name__ == '__main__':
    test_android_export()
