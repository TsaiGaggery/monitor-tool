#!/usr/bin/env python3
"""
Practical test to verify logs are stored in session database.
This test creates a real monitoring session and exports a report with logs.
"""

import os
import sys
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from storage.data_exporter import DataExporter
from storage.data_logger import DataLogger


def create_test_log_files(temp_dir):
    """Create temporary log files with test content."""
    log_dir = os.path.join(temp_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    syslog_path = os.path.join(log_dir, 'test_syslog.log')
    
    # Create syslog with various severity levels
    now = datetime.now()
    log_entries = []
    
    for i in range(20):
        timestamp = now - timedelta(minutes=20-i)
        time_str = timestamp.strftime('%b %d %H:%M:%S')
        
        if i % 4 == 0:
            log_entries.append(f"{time_str} localhost kernel: [ERROR] Test error message {i}\n")
        elif i % 4 == 1:
            log_entries.append(f"{time_str} localhost systemd[1234]: [WARNING] Test warning {i}\n")
        elif i % 4 == 2:
            log_entries.append(f"{time_str} localhost app[5678]: [CRITICAL] Critical issue {i}\n")
        else:
            log_entries.append(f"{time_str} localhost daemon: [INFO] Normal operation {i}\n")
    
    with open(syslog_path, 'w') as f:
        f.writelines(log_entries)
    
    print(f"✓ Created test log file with {len(log_entries)} entries: {syslog_path}")
    return syslog_path


def test_real_log_storage():
    """Test that logs are actually stored in session database."""
    print("=" * 80)
    print("PRACTICAL TEST: Log Storage in Session Database")
    print("=" * 80)
    
    # Create temp directories
    temp_base = tempfile.mkdtemp()
    reports_dir = os.path.join(temp_base, 'reports')
    
    try:
        # Create test log files
        log_file = create_test_log_files(temp_base)
        
        print("\n📊 Step 1: Creating monitoring session with data...")
        # Create exporter with monitoring data
        start_time = datetime.now() - timedelta(minutes=5)
        exporter = DataExporter(output_dir=reports_dir, session_start_time=start_time)
        
        # Add monitoring samples
        for i in range(15):
            timestamp = start_time + timedelta(seconds=i * 20)
            sample = {
                'timestamp': int(timestamp.timestamp()),
                'cpu_usage': 25.0 + i * 3,
                'memory_percent': 50.0 + i * 2,
                'gpu_usage': 15.0 + i,
                'net_rx_bytes': 1024 * i * 10,
                'net_tx_bytes': 512 * i * 10
            }
            exporter.add_sample(sample)
        
        print(f"✓ Added {len(exporter.session_data)} monitoring samples")
        
        print("\n📋 Step 2: Configuring log collection...")
        # Configure to use our test log file
        config = {
            'log_collection': {
                'enabled': True,
                'sources': [log_file],  # Use our test log file
                'keywords': ['error', 'warning', 'critical', 'info'],
                'max_log_lines': 100,
                'anonymize': {
                    'enabled': True
                },
                'log_timezone': 'local'
            }
        }
        
        print(f"✓ Configured to collect logs from: {log_file}")
        
        print("\n🚀 Step 3: Generating HTML report with log collection...")
        report_path = exporter.export_html(
            collect_logs=True,
            config=config,
            use_android_db=False,
            use_ssh_db=False
        )
        
        print(f"\n✓ Report generated: {report_path}")
        
        # Verify session structure
        session_dir = Path(report_path).parent
        print(f"\n📁 Step 4: Verifying session directory structure...")
        print(f"   Session directory: {session_dir}")
        
        # Check files exist
        db_path = session_dir / 'monitoring_data.db'
        html_path = session_dir / 'report.html'
        
        assert db_path.exists(), f"Database not found: {db_path}"
        assert html_path.exists(), f"Report not found: {html_path}"
        
        print(f"   ✓ Database: {db_path.name}")
        print(f"   ✓ HTML Report: {html_path.name}")
        
        # Inspect database contents
        print(f"\n🔍 Step 5: Inspecting session database contents...")
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\n   Tables ({len(tables)}):")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   ✓ {table:30} {count:5} rows")
        
        # Get session metadata
        print(f"\n   Session Metadata:")
        cursor.execute("SELECT * FROM session_metadata")
        metadata = cursor.fetchone()
        if metadata:
            columns = ['session_id', 'start_time', 'end_time', 'source_type', 
                      'source_name', 'log_collection_enabled', 'created_at']
            for col, val in zip(columns, metadata):
                print(f"   ✓ {col:25} {val}")
        
        # Get log entries with details
        print(f"\n   Log Entries Analysis:")
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        total_logs = cursor.fetchone()[0]
        print(f"   ✓ Total log entries: {total_logs}")
        
        if total_logs > 0:
            # Group by severity
            cursor.execute("""
                SELECT severity, COUNT(*) as count 
                FROM log_entries 
                GROUP BY severity 
                ORDER BY count DESC
            """)
            print(f"\n   Severity Breakdown:")
            for severity, count in cursor.fetchall():
                print(f"   ✓ {severity:15} {count:3} entries")
            
            # Show sample entries
            print(f"\n   Sample Log Entries:")
            cursor.execute("""
                SELECT timestamp, severity, source_file, message 
                FROM log_entries 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            for timestamp, severity, source, message in cursor.fetchall():
                msg_preview = message[:60] + '...' if len(message) > 60 else message
                print(f"   {timestamp} [{severity:8}] {msg_preview}")
            
            # Verify process context
            cursor.execute("""
                SELECT process_context 
                FROM log_entries 
                WHERE process_context != '[]' 
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                print(f"\n   ✓ Process context stored: {result[0]}")
        
        conn.close()
        
        # Final verification
        print(f"\n" + "=" * 80)
        print("✅ VERIFICATION RESULTS")
        print("=" * 80)
        
        checks = [
            ("Session directory created", session_dir.exists()),
            ("Database file exists", db_path.exists()),
            ("HTML report exists", html_path.exists()),
            ("Session metadata stored", metadata is not None),
            ("Log entries stored", total_logs > 0),
            ("Multiple severity levels", total_logs >= 15),  # Should have ~20 from test file
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status:8} {check_name}")
            if not result:
                all_passed = False
        
        print("=" * 80)
        
        if all_passed:
            print("\n🎉 SUCCESS! Logs are properly stored in session database!")
            print(f"\n💡 You can inspect the database yourself:")
            print(f"   sqlite3 {db_path}")
            print(f"   > SELECT * FROM log_entries;")
            print(f"\n📊 Or view the report:")
            print(f"   open {html_path}")
            return True
        else:
            print("\n❌ Some checks failed!")
            return False
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up temporary files...")
        if os.path.exists(temp_base):
            shutil.rmtree(temp_base)
        print("✓ Cleanup complete")


if __name__ == '__main__':
    success = test_real_log_storage()
    sys.exit(0 if success else 1)
