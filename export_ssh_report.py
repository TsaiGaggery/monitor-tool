#!/usr/bin/env python3
"""
Quick script to export HTML report from remote SSH database
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from storage.data_exporter import DataExporter
from datetime import datetime

# Create a minimal mock data source
class MockSSHDataSource:
    def __init__(self):
        self.ssh_host = '172.25.65.75'
        self.username = 'intel'
        self.port = 22
        self.key_path = None
        self.session_start_time = datetime(2020, 1, 1)  # Get all data
    
    def get_source_name(self):
        return f"RemoteLinux({self.ssh_host})"

# Create exporter with mock data source
exporter = DataExporter()
exporter.data_source = MockSSHDataSource()

print('🔄 Generating HTML report from remote database...')
try:
    output_path = exporter.export_html(use_ssh_db=True)
    print(f'✅ Report saved to: {output_path}')
    
    # Debug: Check if interrupt data was processed
    if hasattr(exporter, 'session_data') and exporter.session_data:
        sample_with_tier1 = next((s for s in exporter.session_data if 'tier1' in s and 'interrupts' in s['tier1']), None)
        if sample_with_tier1:
            print(f'✅ Found tier1 interrupt data in session_data')
            print(f'   Sample interrupt count: {len(sample_with_tier1["tier1"]["interrupts"])}')
        else:
            print(f'⚠️  No tier1 interrupt data found in {len(exporter.session_data)} samples')
            # Check first few samples
            for i, sample in enumerate(exporter.session_data[:3]):
                print(f'   Sample {i}: has tier1={("tier1" in sample)}, keys={list(sample.keys())[:5]}...')
    
    print(f'\nOpen the report with:')
    print(f'  xdg-open {output_path}')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
