import sys
import os
from pathlib import Path
import yaml
import time

# Add src to path
sys.path.insert(0, os.path.abspath('src'))

from data_source import LocalDataSource
from storage.data_logger import DataLogger

def main():
    # Load config
    config_path = Path('config/default.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print("Initializing LocalDataSource...")
    ds = LocalDataSource(enable_tier1=True, config=config)
    
    print("Initializing DataLogger...")
    logger = DataLogger()
    
    print("Fetching process info...")
    processes = ds.get_process_info()
    
    print(f"Found {len(processes)} processes:")
    print(f"{'PID':<8} {'Name':<20} {'CPU%':<8} {'Memory':<10} {'Severity'}")
    print("-" * 60)
    
    for p in processes:
        severity = ds.process_monitor.get_severity(p)
        mem_mb = p.memory_rss / (1024 * 1024)
        print(f"{p.pid:<8} {p.name[:20]:<20} {p.cpu_percent:<8.1f} {mem_mb:<10.1f} {severity}")
        
    print("\nLogging to database...")
    logger.log_process_data(processes)
    print("Done.")

if __name__ == '__main__':
    main()
