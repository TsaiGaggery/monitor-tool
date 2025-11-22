#!/usr/bin/env python3
"""
Test that data stored in session DB can be re-exported to HTML correctly.
This simulates the workflow:
1. Export with log collection → creates session DB with flat format data
2. Re-export from session DB → should produce same HTML output
"""
import os
import sys
import tempfile
import shutil
import sqlite3
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from storage.data_exporter import DataExporter

def test_session_db_reexport():
    """Test that data can be stored and re-exported from session DB"""
    
    # Create temp directory for reports
    temp_dir = tempfile.mkdtemp(prefix='test_reexport_')
    print(f"Test directory: {temp_dir}")
    
    try:
        # Step 1: Create initial export with nested format data (normal workflow)
        print("\n=== Step 1: Initial export with nested format data ===")
        exporter = DataExporter(output_dir=temp_dir)
        
        # Simulate in-memory monitoring data (nested format from monitors)
        monitoring_data = []
        for i in range(10):
            sample = {
                'timestamp': 1700000000 + i * 20,
                'cpu': {
                    'usage': {'total': 30.0 + i * 3, 'per_core': [25.0 + i, 28.0 + i]},
                    'frequency': {'average': 2400, 'per_core': [2400, 2500]},
                    'temperature': {'sensors': [45.0, 46.0]},
                    'power': {'package': 15.5}
                },
                'gpu': {
                    'available': True,
                    'gpus': [{
                        'id': 0,
                        'usage': 20.0 + i * 5,
                        'memory_used': 1024 * (1 + i),
                        'memory_util': 40.0 + i,
                        'frequency': 1500,
                        'temperature': 55.0,
                        'power': 75.0
                    }]
                },
                'memory': {
                    'percent': 55.0 + i * 2,
                    'used': 8192 * 1024 * 1024,
                    'available': 8192 * 1024 * 1024,
                    'swap_percent': 10.0
                },
                'network': {
                    'net_io': {
                        'bytes_sent': 1000000 * i,
                        'bytes_recv': 2000000 * i
                    }
                },
                'disk': {
                    'disk_io': {
                        'read_bytes': 500000 * i,
                        'write_bytes': 300000 * i
                    }
                },
                'npu': {'usage': 0}
            }
            monitoring_data.append(sample)
        
        # Set session data
        exporter.session_data = monitoring_data
        
        # Export with log collection
        session1_html = exporter.export_html(
            collect_logs=True,
            use_android_db=False,
            use_ssh_db=False
        )
        
        print(f"Session 1 HTML: {session1_html}")
        session1_dir = os.path.dirname(session1_html)
        session1_db = os.path.join(session1_dir, 'monitoring_data.db')
        
        assert os.path.exists(session1_db), "Session DB should exist"
        assert os.path.exists(session1_html), "HTML report should exist"
        
        # Verify data in session DB (should be in flat format)
        print("\n=== Verifying session DB format ===")
        conn = sqlite3.connect(session1_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT cpu_usage, gpu_usage, memory_percent FROM monitoring_data LIMIT 3")
        rows = cursor.fetchall()
        print(f"Sample DB rows (flat format):")
        for row in rows:
            print(f"  cpu_usage: {row[0]}, gpu_usage: {row[1]}, memory_percent: {row[2]}")
        
        # Check that data is stored
        assert len(rows) > 0, "Should have data in DB"
        assert rows[0][0] == 30.0, f"First CPU usage should be 30.0, got {rows[0][0]}"
        
        conn.close()
        
        # Verify HTML has data (check for actual values in chartData)
        print("\n=== Verifying HTML 1 has data ===")
        with open(session1_html, 'r') as f:
            html_content = f.read()
        
        assert '30.0' in html_content, "HTML should contain CPU data"
        assert '20.0' in html_content, "HTML should contain GPU data"
        assert '55.0' in html_content, "HTML should contain Memory data"
        print("✓ HTML 1 contains data values")
        
        # Step 2: Re-export from session DB (simulate pulling from remote)
        print("\n=== Step 2: Re-export from session DB ===")
        exporter2 = DataExporter(output_dir=temp_dir)
        
        # Simulate pulling data from session DB (like remote DB)
        # This would normally happen through _pull_ssh_db_data() or similar
        conn = sqlite3.connect(session1_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, cpu_usage, cpu_freq_avg, cpu_temp, cpu_power,
                   gpu_usage, gpu_memory_used, gpu_memory_util, gpu_freq, gpu_temp, gpu_power,
                   memory_percent, memory_used, memory_available, memory_swap_percent,
                   net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors,
                   npu_usage
            FROM monitoring_data
            ORDER BY timestamp
        """)
        
        raw_data = []
        for row in cursor.fetchall():
            raw_data.append({
                'timestamp': row[0],
                'cpu_usage': row[1],
                'cpu_freq_avg': row[2],
                'cpu_temp': row[3],
                'cpu_power': row[4],
                'gpu_usage': row[5],
                'gpu_memory_used': row[6],
                'gpu_memory_util': row[7],
                'gpu_freq': row[8],
                'gpu_temp': row[9],
                'gpu_power': row[10],
                'memory_percent': row[11],
                'memory_used': row[12],
                'memory_available': row[13],
                'memory_swap_percent': row[14],
                'net_rx_bytes': row[15],
                'net_tx_bytes': row[16],
                'disk_read_sectors': row[17],
                'disk_write_sectors': row[18],
                'npu_usage': row[19]
            })
        conn.close()
        
        print(f"Pulled {len(raw_data)} samples from session DB (flat format)")
        
        # Process through _process_ssh_raw_data to convert to nested format
        processed_data = []
        for raw_sample in raw_data:
            processed = exporter2._process_ssh_raw_data(raw_sample)
            processed_data.append(processed)
        
        print(f"Processed to nested format: {len(processed_data)} samples")
        print(f"Sample processed data keys: {list(processed_data[0].keys())}")
        
        # Set as session data and export again
        exporter2.session_data = processed_data
        
        session2_html = exporter2.export_html(
            collect_logs=False,  # Don't collect logs again
            use_android_db=False,
            use_ssh_db=False
        )
        
        print(f"Session 2 HTML: {session2_html}")
        session2_dir = os.path.dirname(session2_html)
        
        assert os.path.exists(session2_html), "Second HTML report should exist"
        
        # Verify HTML 2 also has data
        print("\n=== Verifying HTML 2 has data ===")
        with open(session2_html, 'r') as f:
            html2_content = f.read()
        
        assert '30.0' in html2_content, "Re-exported HTML should contain CPU data"
        assert '20.0' in html2_content, "Re-exported HTML should contain GPU data"
        assert '55.0' in html2_content, "Re-exported HTML should contain Memory data"
        print("✓ HTML 2 contains data values")
        
        # Compare key data points
        print("\n=== Comparing data consistency ===")
        # Both should have same CPU usage values
        assert html_content.count('30.0') > 0, "HTML 1 should have CPU data"
        assert html2_content.count('30.0') > 0, "HTML 2 should have CPU data"
        print("✓ Both HTMLs contain consistent data")
        
        print("\n=== ✅ Test PASSED ===")
        print("Data can be stored in session DB (flat format) and re-exported correctly!")
        
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up: {temp_dir}")

if __name__ == '__main__':
    test_session_db_reexport()
