#!/usr/bin/env python3
"""Test comprehensive data export"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.data_exporter import DataExporter
from src.collectors.cpu_monitor import CPUMonitor
from src.collectors.gpu_monitor import GPUMonitor
from src.collectors.memory_monitor import MemoryMonitor

def main():
    print("Testing comprehensive data export...")
    
    # Create monitors
    cpu_monitor = CPUMonitor()
    gpu_monitor = GPUMonitor()
    memory_monitor = MemoryMonitor()
    
    # Create exporter
    exporter = DataExporter()
    
    # Collect 10 samples
    print("Collecting 10 samples...")
    for i in range(10):
        cpu_data = cpu_monitor.collect()
        gpu_data = gpu_monitor.collect()
        memory_data = memory_monitor.collect()
        
        sample = {
            'timestamp': datetime.now().isoformat(),
            'cpu': cpu_data,
            'gpu': gpu_data,
            'memory': memory_data
        }
        
        exporter.add_sample(sample)
        print(f"  Sample {i+1}/10 collected")
    
    # Export all formats
    print("\nExporting all formats...")
    csv_path = exporter.export_csv()
    json_path = exporter.export_json()
    html_path = exporter.export_html()
    
    print(f"\n✅ Export complete!")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")
    print(f"HTML: {html_path}")
    
    print(f"\n🌐 Open HTML in browser:")
    print(f"   file://{html_path}")

if __name__ == '__main__':
    main()
