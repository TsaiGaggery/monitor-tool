#!/usr/bin/env python3
"""End-to-end test for report generation with log collection."""

import os
import sys
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from storage.data_exporter import DataExporter
from storage.data_logger import DataLogger


def test_local_report_with_logs():
    """Test generating a report with log collection for local data."""
    print("=" * 70)
    print("Testing Local Report Generation with Log Collection")
    print("=" * 70)
    
    # Create temporary directory for output
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, 'reports')
    
    try:
        # Create exporter
        start_time = datetime.now() - timedelta(minutes=5)
        exporter = DataExporter(output_dir=output_dir, session_start_time=start_time)
        
        # Add some sample data
        for i in range(10):
            timestamp = start_time + timedelta(seconds=i * 30)
            sample = {
                'timestamp': int(timestamp.timestamp()),
                'cpu_usage': 30.0 + i * 2,
                'memory_percent': 40.0 + i,
                'gpu_usage': 20.0 + i * 3,
                'net_rx_bytes': 1000 * i,
                'net_tx_bytes': 500 * i
            }
            exporter.add_sample(sample)
        
        print(f"✓ Added {len(exporter.session_data)} monitoring samples")
        
        # Create config for log collection
        config = {
            'log_collection': {
                'enabled': True,
                'sources': ['/var/log/syslog'],
                'keywords': ['error', 'warning'],
                'max_log_lines': 100,
                'anonymize': {'enabled': True}
            }
        }
        
        # Export HTML with logs
        print("\n📊 Generating HTML report with log collection...")
        report_path = exporter.export_html(collect_logs=True, config=config)
        
        print(f"\n✓ Report generated: {report_path}")
        
        # Verify report file exists
        assert os.path.exists(report_path), f"Report file not found: {report_path}"
        print("✓ Report file exists")
        
        # Verify session directory structure
        session_dir = Path(report_path).parent
        assert session_dir.name.startswith('session_'), f"Invalid session directory: {session_dir}"
        print(f"✓ Session directory: {session_dir.name}")
        
        # Verify database exists
        db_path = session_dir / 'monitoring_data.db'
        assert db_path.exists(), f"Database not found: {db_path}"
        print(f"✓ Session database exists: {db_path}")
        
        # Verify database contents
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check monitoring data
        cursor.execute("SELECT COUNT(*) FROM monitoring_data")
        data_count = cursor.fetchone()[0]
        print(f"✓ Monitoring data records: {data_count}")
        
        # Check session metadata
        cursor.execute("SELECT * FROM session_metadata")
        metadata = cursor.fetchone()
        if metadata:
            print(f"✓ Session metadata:")
            print(f"  - Session ID: {metadata[0]}")
            print(f"  - Start time: {metadata[1]}")
            print(f"  - End time: {metadata[2]}")
            print(f"  - Source type: {metadata[3]}")
            print(f"  - Log collection: {bool(metadata[5])}")
        
        # Check log entries
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        log_count = cursor.fetchone()[0]
        print(f"✓ Log entries: {log_count}")
        
        if log_count > 0:
            cursor.execute("SELECT severity, COUNT(*) FROM log_entries GROUP BY severity")
            for severity, count in cursor.fetchall():
                print(f"  - {severity}: {count}")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_session_database_schema():
    """Test that session database has all required tables."""
    print("\n" + "=" * 70)
    print("Testing Session Database Schema")
    print("=" * 70)
    
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_schema.db')
    
    try:
        # Create logger
        logger = DataLogger(db_path=db_path, auto_cleanup_days=0)
        
        # Check tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        print("\n📋 Tables in session database:")
        for table in tables:
            print(f"  ✓ {table}")
        
        required_tables = [
            'monitoring_data',
            'process_data',
            'log_entries',
            'session_metadata',
            'process_log_correlation',
            'report_insights'
        ]
        
        for table in required_tables:
            assert table in tables, f"Missing table: {table}"
        
        print(f"\n✓ All {len(required_tables)} required tables present")
        
        # Check indexes
        cursor.execute("""
            SELECT name, tbl_name FROM sqlite_master 
            WHERE type='index' 
            ORDER BY tbl_name, name
        """)
        indexes = cursor.fetchall()
        
        print(f"\n📇 Indexes ({len(indexes)}):")
        for idx_name, tbl_name in indexes:
            if not idx_name.startswith('sqlite_'):
                print(f"  ✓ {idx_name} on {tbl_name}")
        
        conn.close()
        logger.close()
        
        print("\n" + "=" * 70)
        print("✓ SCHEMA TEST PASSED")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)


def test_log_storage_performance():
    """Test batch insert performance with large log dataset."""
    print("\n" + "=" * 70)
    print("Testing Log Storage Performance")
    print("=" * 70)
    
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_perf.db')
    
    try:
        from monitors.log_monitor import LogEntry
        
        logger = DataLogger(db_path=db_path, auto_cleanup_days=0)
        
        # Create 1000 log entries
        log_entries = []
        base_time = datetime.now()
        
        print("\n📝 Creating 1000 test log entries...")
        for i in range(1000):
            entry = LogEntry(
                timestamp=base_time + timedelta(seconds=i),
                source_file='/var/log/syslog',
                severity=['info', 'warning', 'error'][i % 3],
                facility='kernel',
                message=f'Test log message {i}',
                raw_line=f'Nov 21 14:30:{i%60:02d} kernel: Test log message {i}',
                process_context=[i, i+1, i+2]
            )
            log_entries.append(entry)
        
        print("✓ Created 1000 log entries")
        
        # Insert with batch processing
        print("\n💾 Inserting with batch processing...")
        import time
        start = time.time()
        count = logger.log_entries(log_entries, batch_size=100)
        elapsed = time.time() - start
        
        print(f"✓ Inserted {count} entries in {elapsed:.3f}s")
        print(f"✓ Rate: {count/elapsed:.0f} entries/second")
        
        # Verify count
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        db_count = cursor.fetchone()[0]
        
        assert db_count == 1000, f"Expected 1000, got {db_count}"
        print(f"✓ Verified {db_count} entries in database")
        
        # Test query performance
        print("\n🔍 Testing query performance...")
        start = time.time()
        cursor.execute("""
            SELECT * FROM log_entries 
            WHERE severity = 'error' 
            ORDER BY timestamp DESC 
            LIMIT 100
        """)
        results = cursor.fetchall()
        elapsed = time.time() - start
        
        print(f"✓ Query returned {len(results)} results in {elapsed:.3f}s")
        
        conn.close()
        logger.close()
        
        print("\n" + "=" * 70)
        print("✓ PERFORMANCE TEST PASSED")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)


if __name__ == '__main__':
    print("\n🧪 Running End-to-End Tests for Log Storage\n")
    
    results = []
    
    # Run schema test
    results.append(("Schema Test", test_session_database_schema()))
    
    # Run performance test
    results.append(("Performance Test", test_log_storage_performance()))
    
    # Run full integration test
    results.append(("Integration Test", test_local_report_with_logs()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print("=" * 70)
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 70)
    
    sys.exit(0 if passed == total else 1)
