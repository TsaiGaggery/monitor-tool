#!/usr/bin/env python3
"""
Live demonstration: Create a real report with logs that you can inspect.
This creates a report in ./reports/ that persists after the test.
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from storage.data_exporter import DataExporter


def demonstrate_log_storage():
    """Create a real report with logs for manual inspection."""
    print("=" * 80)
    print("LIVE DEMO: Creating Report with Log Storage")
    print("=" * 80)
    
    # Use actual reports directory
    reports_dir = 'reports'
    
    print("\n📊 Step 1: Creating monitoring session...")
    start_time = datetime.now() - timedelta(minutes=10)
    exporter = DataExporter(output_dir=reports_dir, session_start_time=start_time)
    
    # Add realistic monitoring samples
    for i in range(30):
        timestamp = start_time + timedelta(seconds=i * 20)
        sample = {
            'timestamp': int(timestamp.timestamp()),
            'cpu_usage': 30.0 + (i % 15) * 3,
            'memory_percent': 55.0 + (i % 10) * 2,
            'gpu_usage': 20.0 + (i % 8) * 5,
            'net_rx_bytes': 1024 * i * 50,
            'net_tx_bytes': 512 * i * 30
        }
        exporter.add_sample(sample)
    
    print(f"✓ Created {len(exporter.session_data)} monitoring samples")
    print(f"   Time range: {start_time.strftime('%H:%M:%S')} to {(start_time + timedelta(seconds=29*20)).strftime('%H:%M:%S')}")
    
    print("\n📋 Step 2: Generating report with log collection...")
    print("   (This will collect actual system logs from /var/log/syslog)")
    
    # Use real config to collect actual system logs
    config = {
        'log_collection': {
            'enabled': True,
            'sources': ['/var/log/syslog'],  # Real system log
            'keywords': ['error', 'warning', 'kernel', 'systemd'],
            'max_log_lines': 500,
            'anonymize': {
                'enabled': True
            },
            'log_timezone': 'local'
        }
    }
    
    try:
        report_path = exporter.export_html(
            collect_logs=True,
            config=config,
            use_android_db=False,
            use_ssh_db=False
        )
        
        session_dir = Path(report_path).parent
        db_path = session_dir / 'monitoring_data.db'
        
        print(f"\n✅ Report created successfully!")
        print(f"\n📁 Session Directory: {session_dir}")
        print(f"   ├── {db_path.name}")
        print(f"   └── {Path(report_path).name}")
        
        # Inspect the database
        print(f"\n🔍 Database Contents:")
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get counts
        cursor.execute("SELECT COUNT(*) FROM monitoring_data")
        data_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM log_entries")
        log_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM session_metadata")
        meta_count = cursor.fetchone()[0]
        
        print(f"   ✓ Monitoring data records: {data_count}")
        print(f"   ✓ Log entries: {log_count}")
        print(f"   ✓ Session metadata: {meta_count}")
        
        if log_count > 0:
            # Show severity breakdown
            cursor.execute("""
                SELECT severity, COUNT(*) 
                FROM log_entries 
                GROUP BY severity 
                ORDER BY COUNT(*) DESC
            """)
            print(f"\n   Log Severity Breakdown:")
            for severity, count in cursor.fetchall():
                print(f"   ✓ {severity:10} {count:4} entries")
            
            # Show latest 3 logs
            print(f"\n   Latest 3 Log Entries:")
            cursor.execute("""
                SELECT timestamp, severity, message 
                FROM log_entries 
                ORDER BY timestamp DESC 
                LIMIT 3
            """)
            for ts, sev, msg in cursor.fetchall():
                msg_short = msg[:70] + '...' if len(msg) > 70 else msg
                print(f"   [{sev:8}] {msg_short}")
        
        conn.close()
        
        # Provide inspection commands
        print("\n" + "=" * 80)
        print("📖 How to Inspect the Results:")
        print("=" * 80)
        
        print(f"\n1️⃣  Open the HTML report:")
        print(f"   firefox {report_path}")
        print(f"   # or")
        print(f"   xdg-open {report_path}")
        
        print(f"\n2️⃣  Query the database directly:")
        print(f"   sqlite3 {db_path}")
        print(f"   sqlite> SELECT COUNT(*) FROM log_entries;")
        print(f"   sqlite> SELECT * FROM log_entries LIMIT 5;")
        print(f"   sqlite> SELECT * FROM session_metadata;")
        print(f"   sqlite> .exit")
        
        print(f"\n3️⃣  Python inspection:")
        print(f"""   python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('{db_path}')
cursor = conn.cursor()

# Get all logs
cursor.execute('SELECT * FROM log_entries')
for row in cursor.fetchall():
    print(row)

# Get session info
cursor.execute('SELECT * FROM session_metadata')
print(cursor.fetchone())
EOF""")
        
        print(f"\n4️⃣  Quick stats:")
        print(f"   sqlite3 {db_path} \"SELECT severity, COUNT(*) FROM log_entries GROUP BY severity\"")
        
        print("\n" + "=" * 80)
        print(f"✅ SUCCESS! Report with {log_count} log entries created at:")
        print(f"   {session_dir}")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = demonstrate_log_storage()
    sys.exit(0 if success else 1)
