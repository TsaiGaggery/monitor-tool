#!/usr/bin/env python3
"""Test background threading implementation."""

import sys
import time
import threading

# Add src to path
sys.path.insert(0, 'src')

from cli_monitor import CLIMonitor

def test_background_logging():
    """Test that background logging continues during sleep."""
    print("Testing background logging...")
    
    monitor = CLIMonitor(update_interval=1.0)
    
    # Pre-populate data
    monitor.latest_data = monitor._get_all_data()
    print(f"Initial data: CPU cores={len(monitor.latest_data['cpu']['per_core_usage'])}")
    
    # Start background thread
    monitor.running = True
    monitor.logging_thread = threading.Thread(
        target=monitor._background_logging_worker,
        daemon=True
    )
    monitor.logging_thread.start()
    print("Background thread started")
    
    # Let it run for 5 seconds
    for i in range(5):
        time.sleep(1)
        with monitor.logging_lock:
            data = monitor.latest_data
        print(f"  [{i+1}s] CPU: {data['cpu']['overall_usage']:.1f}%, "
              f"Memory: {data['memory']['percent']:.1f}%")
    
    # Stop thread
    monitor.running = False
    monitor.logging_thread.join(timeout=2.0)
    print("Background thread stopped")
    
    # Check database
    from datetime import datetime, timezone
    utc_now = datetime.now(timezone.utc)
    session_start = utc_now.strftime('%Y-%m-%d %H:%M:%S')
    
    # Query data count from last 10 seconds
    query = "SELECT COUNT(*) FROM monitoring_data WHERE timestamp > datetime('now', '-10 seconds')"
    cursor = monitor.logger.conn.execute(query)
    count = cursor.fetchone()[0]
    print(f"\nData points logged in last 10s: {count}")
    print(f"Expected: ~5 (at 1s interval)")
    
    if count >= 4:  # Allow some tolerance
        print("✅ Background logging works!")
        return True
    else:
        print("❌ Background logging failed - too few data points")
        return False

if __name__ == '__main__':
    success = test_background_logging()
    sys.exit(0 if success else 1)
