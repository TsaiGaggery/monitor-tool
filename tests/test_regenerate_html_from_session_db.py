#!/usr/bin/env python3
"""
Test re-generating HTML report from an existing session database.
This simulates the workflow of loading old session data and creating a new report.
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from storage.data_exporter import DataExporter

def regenerate_html_from_session_db(session_db_path: str, output_dir: str = None):
    """
    Re-generate HTML report from an existing session database.
    
    Args:
        session_db_path: Path to the session database file
        output_dir: Output directory for the new report (defaults to same directory as DB)
    
    Returns:
        Path to the generated HTML file
    """
    session_db_path = Path(session_db_path)
    
    if not session_db_path.exists():
        raise FileNotFoundError(f"Session database not found: {session_db_path}")
    
    print(f"📂 Loading data from: {session_db_path}")
    
    # Read data from session database
    conn = sqlite3.connect(str(session_db_path))
    cursor = conn.cursor()
    
    # Get all monitoring data with correct column names
    cursor.execute("""
        SELECT timestamp, timestamp_ms, cpu_usage, memory_percent, gpu_usage, gpu_temp, gpu_memory,
               npu_usage, net_rx_bytes, net_tx_bytes, disk_read_sectors, disk_write_sectors,
               gpu_freq_mhz, cpu_temp_millideg, mem_total_kb, mem_available_kb
        FROM monitoring_data
        ORDER BY timestamp
    """)
    
    rows = cursor.fetchall()
    print(f"📊 Found {len(rows)} data samples")
    
    if not rows:
        conn.close()
        raise ValueError("No monitoring data found in database")
    
    # Convert flat database format to nested format for HTML generation
    # (This is the same processing that _process_ssh_raw_data does)
    processed_samples = []
    
    for row in rows:
        sample = {
            'timestamp': row[0],
            'timestamp_ms': row[1],
            'cpu_usage': row[2],
            'memory_percent': row[3],
            'gpu_usage': row[4],
            'gpu_temp': row[5],
            'gpu_memory': row[6],
            'npu_usage': row[7],
            'net_rx_bytes': row[8],
            'net_tx_bytes': row[9],
            'disk_read_sectors': row[10],
            'disk_write_sectors': row[11],
            'gpu_freq_mhz': row[12],
            'cpu_temp_millideg': row[13],
            'mem_total_kb': row[14],
            'mem_available_kb': row[15]
        }
        processed_samples.append(sample)
    
    conn.close()
    
    # Create exporter
    if output_dir is None:
        output_dir = session_db_path.parent.parent
    
    exporter = DataExporter(output_dir=str(output_dir))
    
    # Set the processed data as session data
    # The HTML generator will use the flat format support we added
    exporter.session_data = processed_samples
    
    print(f"🎨 Generating HTML report...")
    
    # Generate HTML (without re-collecting logs or pulling from other DBs)
    html_path = exporter.export_html(
        collect_logs=False,
        use_android_db=False,
        use_ssh_db=False
    )
    
    print(f"✅ HTML report generated: {html_path}")
    return html_path


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_regenerate_html_from_session_db.py <session_db_path>")
        print("\nExample:")
        print("  python test_regenerate_html_from_session_db.py reports/session_Local_System_20251121_163724/monitoring_data.db")
        sys.exit(1)
    
    session_db_path = sys.argv[1]
    
    try:
        html_path = regenerate_html_from_session_db(session_db_path)
        
        # Verify HTML contains data
        with open(html_path, 'r') as f:
            content = f.read()
        
        # Check for chartData presence
        if 'chartData' in content and 'cpu' in content:
            print("\n✅ Verification: HTML contains chart data")
            
            # Try to find some actual data values
            import re
            cpu_match = re.search(r'"cpu":\s*\{"usage_total":\s*\[([\d., ]+)\]', content)
            if cpu_match:
                values = cpu_match.group(1).split(',')[:3]
                print(f"   CPU values (first 3): {', '.join(v.strip() for v in values)}")
        else:
            print("\n⚠️  Warning: HTML might not contain chart data")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
