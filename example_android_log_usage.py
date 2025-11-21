#!/usr/bin/env python3
"""
Example: How to retrieve Android logs using LogMonitor

This demonstrates the complete flow of collecting logs from an Android device
via ADB, with time filtering, keyword matching, and severity mapping.
"""

from datetime import datetime, timedelta
from src.monitors.log_monitor import LogMonitor

def example_android_log_retrieval():
    """
    Example: Collect Android logs for the last 10 minutes.
    """
    print("=" * 70)
    print("Android Log Retrieval Example")
    print("=" * 70)
    
    # Configure LogMonitor for Android
    config = {
        'enabled': True,
        'keywords': ['error', 'crash', 'exception'],  # Filter for errors
        'max_lines': 500,
        'log_timezone': 'local'  # Android logs are usually in device local time
    }
    
    # Initialize with ADB mode
    monitor = LogMonitor(
        config=config,
        mode='adb',
        adb_device='emulator-5554'  # Or specific device ID
    )
    
    # Define time range (last 10 minutes)
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=10)
    
    print(f"\n📱 Collecting logs from: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"                    to: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔍 Keywords: {config['keywords']}")
    print(f"📊 Max lines: {config['max_lines']}")
    print("\n" + "-" * 70)
    
    # The actual ADB command executed behind the scenes:
    # adb logcat -d -v time -T '11-21 14:30:00.000' -e 'error|crash|exception'
    
    # Collect logs
    entries = monitor.collect_logs(start_time, end_time)
    
    print(f"\n✅ Collected {len(entries)} log entries\n")
    
    # Display results
    if entries:
        print("Sample entries:")
        print("-" * 70)
        for i, entry in enumerate(entries[:5], 1):  # Show first 5
            print(f"\n[{i}] {entry.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"    Severity: {entry.severity.upper()}")
            print(f"    Tag: {entry.facility}")
            print(f"    PID: {entry.process_context[0] if entry.process_context else 'N/A'}")
            print(f"    Message: {entry.message[:100]}...")
        
        if len(entries) > 5:
            print(f"\n... and {len(entries) - 5} more entries")
    else:
        print("No matching log entries found.")
    
    print("\n" + "=" * 70)
    return entries


def example_android_logcat_output():
    """
    Example: What the raw Android logcat output looks like
    and how it gets parsed.
    """
    print("\n" + "=" * 70)
    print("Android Logcat Format Parsing Example")
    print("=" * 70)
    
    raw_logcat_output = """
11-21 15:30:45.123  1234  5678 I ActivityManager: Starting activity: Intent { act=android.intent.action.MAIN }
11-21 15:30:46.456  1234  5679 E SQLiteDatabase: Error opening database: /data/data/com.app/databases/app.db
11-21 15:30:47.789  1235  5680 W NetworkController: No network connectivity
11-21 15:30:48.012  1236  5681 F AndroidRuntime: FATAL EXCEPTION: main
11-21 15:30:48.013  1236  5681 F AndroidRuntime:     at com.app.MainActivity.onCreate(MainActivity.java:42)
    """
    
    print("\n📋 Raw Logcat Output:")
    print("-" * 70)
    print(raw_logcat_output)
    
    print("\n🔍 Parsed Structure:")
    print("-" * 70)
    
    examples = [
        {
            'raw': '11-21 15:30:45.123  1234  5678 I ActivityManager: Starting activity',
            'parsed': {
                'timestamp': '2025-11-21 15:30:45.123',
                'pid': 1234,
                'tid': 5678,
                'level': 'I (Info)',
                'severity': 'info',
                'tag': 'ActivityManager',
                'message': 'Starting activity'
            }
        },
        {
            'raw': '11-21 15:30:46.456  1234  5679 E SQLiteDatabase: Error opening database',
            'parsed': {
                'timestamp': '2025-11-21 15:30:46.456',
                'pid': 1234,
                'tid': 5679,
                'level': 'E (Error)',
                'severity': 'error',
                'tag': 'SQLiteDatabase',
                'message': 'Error opening database'
            }
        },
        {
            'raw': '11-21 15:30:47.789  1235  5680 W NetworkController: No network',
            'parsed': {
                'timestamp': '2025-11-21 15:30:47.789',
                'pid': 1235,
                'tid': 5680,
                'level': 'W (Warning)',
                'severity': 'warning',
                'tag': 'NetworkController',
                'message': 'No network'
            }
        },
        {
            'raw': '11-21 15:30:48.012  1236  5681 F AndroidRuntime: FATAL EXCEPTION',
            'parsed': {
                'timestamp': '2025-11-21 15:30:48.012',
                'pid': 1236,
                'tid': 5681,
                'level': 'F (Fatal)',
                'severity': 'critical',
                'tag': 'AndroidRuntime',
                'message': 'FATAL EXCEPTION'
            }
        }
    ]
    
    for example in examples:
        print(f"\nRaw:  {example['raw']}")
        print(f"├─ Timestamp: {example['parsed']['timestamp']}")
        print(f"├─ PID/TID:   {example['parsed']['pid']}/{example['parsed']['tid']}")
        print(f"├─ Level:     {example['parsed']['level']} → severity='{example['parsed']['severity']}'")
        print(f"├─ Tag:       {example['parsed']['tag']}")
        print(f"└─ Message:   {example['parsed']['message']}")
    
    print("\n" + "=" * 70)


def example_adb_command_construction():
    """
    Example: Show how the ADB command is constructed based on parameters.
    """
    print("\n" + "=" * 70)
    print("ADB Command Construction")
    print("=" * 70)
    
    scenarios = [
        {
            'desc': 'Basic time-filtered collection',
            'start': '2025-11-21 13:23:24',
            'keywords': None,
            'max_lines': 1000,
            'command': "adb logcat -d -v time -T '11-21 13:23:24.000'"
        },
        {
            'desc': 'With keyword filtering',
            'start': '2025-11-21 13:23:24',
            'keywords': ['error', 'crash'],
            'max_lines': 1000,
            'command': "adb logcat -d -v time -T '11-21 13:23:24.000' -e 'error|crash'"
        },
        {
            'desc': 'Last hour of logs',
            'start': '2025-11-21 16:30:00',
            'keywords': ['exception', 'fatal'],
            'max_lines': 500,
            'command': "adb logcat -d -v time -T '11-21 16:30:00.000' -e 'exception|fatal'"
        }
    ]
    
    print("\n📋 Command Examples:")
    print("-" * 70)
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['desc']}")
        print(f"   Start time: {scenario['start']}")
        if scenario['keywords']:
            print(f"   Keywords:   {scenario['keywords']}")
        print(f"   Max lines:  {scenario['max_lines']}")
        print(f"\n   Command:")
        print(f"   $ {scenario['command']}")
    
    print("\n📝 Flag Meanings:")
    print("-" * 70)
    print("  -d              Dump logs and exit (non-blocking)")
    print("  -v time         Show timestamps in format 'MM-DD HH:MM:SS.mmm'")
    print("  -T <time>       Filter logs from specified time onwards")
    print("  -e <pattern>    Filter by regex pattern (case-insensitive)")
    
    print("\n" + "=" * 70)


def example_severity_mapping():
    """
    Example: Android log level to severity mapping.
    """
    print("\n" + "=" * 70)
    print("Android Log Level → Severity Mapping")
    print("=" * 70)
    
    mapping = [
        ('V', 'Verbose', 'debug', '💬', 'Detailed info for development'),
        ('D', 'Debug', 'debug', '🐛', 'Debugging information'),
        ('I', 'Info', 'info', 'ℹ️', 'General informational messages'),
        ('W', 'Warning', 'warning', '⚠️', 'Warning conditions'),
        ('E', 'Error', 'error', '❌', 'Error events'),
        ('F', 'Fatal', 'critical', '💀', 'Fatal errors, app crash')
    ]
    
    print("\n┌────────┬──────────┬───────────┬──────────────────────────────┐")
    print("│ Level  │ Name     │ Severity  │ Description                  │")
    print("├────────┼──────────┼───────────┼──────────────────────────────┤")
    
    for char, name, severity, emoji, desc in mapping:
        print(f"│ {emoji}  {char}   │ {name:8} │ {severity:9} │ {desc:28} │")
    
    print("└────────┴──────────┴───────────┴──────────────────────────────┘")
    print("\n" + "=" * 70)


if __name__ == '__main__':
    print("\n🤖 Android Log Collection Examples\n")
    
    # Show logcat format parsing
    example_android_logcat_output()
    
    # Show ADB command construction
    example_adb_command_construction()
    
    # Show severity mapping
    example_severity_mapping()
    
    # Uncomment to run live collection (requires connected Android device)
    # example_android_log_retrieval()
    
    print("\n✅ Examples complete!")
    print("\nTo run live collection:")
    print("  1. Connect Android device: adb devices")
    print("  2. Uncomment example_android_log_retrieval() above")
    print("  3. Run: python3 example_android_log_usage.py\n")
