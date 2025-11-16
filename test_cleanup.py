#!/usr/bin/env python3
"""Test database auto cleanup functionality."""

import sys
import os

# Add src to path
sys.path.insert(0, 'src')

from storage.data_logger import DataLogger

def test_auto_cleanup():
    """Test that auto cleanup runs on initialization."""
    print("Testing auto cleanup on initialization...")
    
    # Create logger with 3-day auto cleanup
    logger = DataLogger(auto_cleanup_days=3)
    
    # Check database stats
    stats = logger.get_statistics(hours=24*7)  # Last 7 days
    print(f"\nDatabase stats:")
    print(f"  Total samples: {stats.get('sample_count', 0):,}")
    print(f"  Database path: {logger.db_path}")
    
    # Check database file size
    if os.path.exists(logger.db_path):
        size_mb = os.path.getsize(logger.db_path) / (1024 * 1024)
        print(f"  Database size: {size_mb:.2f} MB")
    
    logger.close()
    print("\n✅ Auto cleanup test completed")

if __name__ == '__main__':
    test_auto_cleanup()
