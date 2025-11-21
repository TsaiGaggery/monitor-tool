#!/usr/bin/env python3
"""
Live test script for LogMonitor with real log files.

This script demonstrates LogMonitor functionality by:
1. Reading system log files (if available)
2. Parsing timestamps, severity, and PIDs
3. Applying keyword filtering
4. Showing anonymization in action
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from monitors.log_monitor import LogMonitor, LogEntry


def test_system_logs():
    """Test reading actual system log files."""
    print("=" * 80)
    print("TEST 1: Reading System Logs")
    print("=" * 80)
    
    # Common log file locations
    possible_logs = [
        '/var/log/syslog',
        '/var/log/messages',
        '/var/log/auth.log',
        '/var/log/kern.log',
    ]
    
    # Find first available log
    log_file = None
    for path in possible_logs:
        if Path(path).exists():
            log_file = path
            print(f"✓ Found log file: {log_file}")
            break
    
    if not log_file:
        print("✗ No system logs found. Trying user logs...")
        # Try home directory logs
        home_logs = list(Path.home().glob('*.log'))
        if home_logs:
            log_file = str(home_logs[0])
            print(f"✓ Using: {log_file}")
        else:
            print("✗ No readable log files found")
            return False
    
    # Configure LogMonitor
    config = {
        'enabled': True,
        'sources': [log_file],
        'max_lines': 50,  # Limit output
        'anonymize': {
            'enabled': True,
            'patterns': ['ip_addresses', 'home_directories', 'hostnames']
        }
    }
    
    monitor = LogMonitor(config)
    
    # Get logs from last hour
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    print(f"\nReading logs from {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    
    try:
        entries = monitor.collect_logs(start_time, end_time)
        
        if not entries:
            print("No log entries found in the time range")
            return False
        
        print(f"\n✓ Found {len(entries)} log entries\n")
        
        # Show first 10 entries
        for i, entry in enumerate(entries[:10], 1):
            print(f"{i}. [{entry.timestamp}] {entry.severity.upper():8s} | {entry.message[:70]}")
            if entry.process_context:
                print(f"   PIDs: {entry.process_context}")
        
        if len(entries) > 10:
            print(f"\n... and {len(entries) - 10} more entries")
        
        # Statistics
        print("\n" + "-" * 80)
        print("STATISTICS:")
        severity_counts = {}
        pid_count = 0
        for entry in entries:
            severity_counts[entry.severity] = severity_counts.get(entry.severity, 0) + 1
            if entry.process_context:
                pid_count += 1
        
        print(f"  Total entries: {len(entries)}")
        print(f"  Entries with PIDs: {pid_count}")
        print(f"  Severity breakdown:")
        for sev, count in sorted(severity_counts.items()):
            print(f"    {sev:10s}: {count:3d}")
        
        return True
        
    except PermissionError:
        print(f"✗ Permission denied reading {log_file}")
        print("  Try running with: sudo python3 test_log_monitor_live.py")
        return False


def test_keyword_filtering():
    """Test keyword filtering."""
    print("\n" + "=" * 80)
    print("TEST 2: Keyword Filtering")
    print("=" * 80)
    
    # Create test log file
    test_log = Path('/tmp/test_monitor.log')
    test_content = f"""{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} INFO Application started
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} ERROR Connection failed to 192.168.1.100
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} WARNING Memory usage high
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} INFO User logged in
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} ERROR Database connection timeout
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} CRITICAL System crash detected
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} DEBUG [1234] Processing request
"""
    
    test_log.write_text(test_content)
    print(f"✓ Created test log: {test_log}")
    
    # Test with keywords
    config = {
        'enabled': True,
        'sources': [str(test_log)],
        'keywords': ['error', 'critical'],  # Only errors and critical
        'anonymize': {'enabled': True}
    }
    
    monitor = LogMonitor(config)
    
    end_time = datetime.now() + timedelta(minutes=1)
    start_time = datetime.now() - timedelta(minutes=1)
    
    entries = monitor.collect_logs(start_time, end_time)
    
    print(f"\n✓ Filtered to {len(entries)} entries with keywords ['error', 'critical']:\n")
    for entry in entries:
        print(f"  [{entry.severity.upper()}] {entry.message}")
        # Show anonymization
        if entry.raw_line != entry.message:
            print(f"    Original: {entry.raw_line}")
    
    # Cleanup
    test_log.unlink()
    return True


def test_gzip_logs():
    """Test reading gzipped logs."""
    print("\n" + "=" * 80)
    print("TEST 3: Gzip Compression Support")
    print("=" * 80)
    
    import gzip
    
    # Create gzipped test log
    test_log_gz = Path('/tmp/test_monitor.log.gz')
    test_content = f"""{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} INFO Message from compressed log [5678]
{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} ERROR Compressed error message
"""
    
    with gzip.open(test_log_gz, 'wt') as f:
        f.write(test_content)
    
    print(f"✓ Created gzipped test log: {test_log_gz}")
    
    config = {
        'enabled': True,
        'sources': [str(test_log_gz)],
        'anonymize': {'enabled': False}
    }
    
    monitor = LogMonitor(config)
    
    end_time = datetime.now() + timedelta(minutes=1)
    start_time = datetime.now() - timedelta(minutes=1)
    
    entries = monitor.collect_logs(start_time, end_time)
    
    print(f"\n✓ Read {len(entries)} entries from gzipped log:\n")
    for entry in entries:
        print(f"  [{entry.severity.upper()}] {entry.message}")
        if entry.process_context:
            print(f"    PIDs: {entry.process_context}")
    
    # Cleanup
    test_log_gz.unlink()
    return True


def test_log_rotation():
    """Test log rotation detection."""
    print("\n" + "=" * 80)
    print("TEST 4: Log Rotation Detection")
    print("=" * 80)
    
    import gzip
    
    # Create rotated log sequence
    base_log = Path('/tmp/app.log')
    log1 = Path('/tmp/app.log.1')
    log2_gz = Path('/tmp/app.log.2.gz')
    
    now = datetime.now()
    
    base_log.write_text(f"{now.strftime('%Y-%m-%dT%H:%M:%S')} INFO Current log\n")
    log1.write_text(f"{(now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S')} INFO Rotated log 1\n")
    
    with gzip.open(log2_gz, 'wt') as f:
        f.write(f"{(now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S')} INFO Rotated log 2\n")
    
    print(f"✓ Created log rotation sequence:")
    print(f"  - {base_log}")
    print(f"  - {log1}")
    print(f"  - {log2_gz}")
    
    config = {
        'enabled': True,
        'sources': [str(base_log)],  # Only specify base log
        'anonymize': {'enabled': False}
    }
    
    monitor = LogMonitor(config)
    
    # Get all rotated logs
    log_files = monitor._find_rotated_logs(str(base_log))
    print(f"\n✓ Found {len(log_files)} log files:")
    for lf in log_files:
        print(f"  - {lf}")
    
    # Read all
    end_time = datetime.now() + timedelta(minutes=1)
    start_time = datetime.now() - timedelta(hours=3)
    
    entries = monitor.collect_logs(start_time, end_time)
    
    print(f"\n✓ Read {len(entries)} total entries from all rotated logs:\n")
    for entry in sorted(entries, key=lambda e: e.timestamp):
        print(f"  {entry.timestamp} - {entry.message.strip()} (from {Path(entry.source_file).name})")
    
    # Cleanup
    base_log.unlink()
    log1.unlink()
    log2_gz.unlink()
    return True


def main():
    """Run all tests."""
    print("\n🔍 LogMonitor Live Testing\n")
    
    tests = [
        ("System Logs", test_system_logs),
        ("Keyword Filtering", test_keyword_filtering),
        ("Gzip Compression", test_gzip_logs),
        ("Log Rotation", test_log_rotation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {name}")
    
    passed = sum(1 for _, s in results if s)
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    return passed == len(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
