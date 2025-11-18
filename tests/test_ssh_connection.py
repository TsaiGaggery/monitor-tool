#!/usr/bin/env python3
"""Test SSH connection and monitoring capabilities."""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_source import RemoteLinuxDataSource


def test_ssh_connection():
    """Test SSH connection to remote Linux system."""
    
    # Get connection details from user
    host = input("Remote host (IP or hostname): ")
    username = input("Username: ")
    port_str = input("Port (default 22): ")
    port = int(port_str) if port_str else 22
    
    use_key = input("Use SSH key? (y/n): ").lower() == 'y'
    
    if use_key:
        key_path = input("Path to SSH private key: ")
        data_source = RemoteLinuxDataSource(
            host=host,
            username=username,
            port=port,
            key_path=key_path
        )
    else:
        # Password will be prompted during connection
        data_source = RemoteLinuxDataSource(
            host=host,
            username=username,
            port=port
        )
    
    print(f"\n📡 Connecting to {username}@{host}:{port}...")
    
    if data_source.connect():
        print(f"\n✅ Connection successful!")
        print(f"   Data source: {data_source.get_source_name()}")
        
        # Test getting data multiple times to verify delta calculations
        print(f"\n📊 Testing data collection (3 samples, 2 seconds apart)...")
        
        for i in range(3):
            if i > 0:
                time.sleep(2)
            
            print(f"\n--- Sample {i+1} ---")
            
            # CPU
            cpu_info = data_source.get_cpu_info()
            print(f"CPU:")
            print(f"  Cores: {cpu_info.get('cpu_count', 0)}")
            print(f"  Usage: {cpu_info.get('usage', {}).get('total', 0):.1f}%")
            print(f"  Frequency: {cpu_info.get('frequency', {}).get('average', 0):.0f} MHz")
            
            temps = cpu_info.get('temperature', {})
            if temps:
                for sensor, readings in temps.items():
                    if readings:
                        print(f"  Temperature: {readings[0].get('current', 0):.1f}°C")
            
            # Memory
            memory_info = data_source.get_memory_info()
            mem = memory_info.get('memory', {})
            print(f"\nMemory:")
            print(f"  Total: {mem.get('total', 0):.1f} GB")
            print(f"  Used: {mem.get('used', 0):.1f} GB ({mem.get('percent', 0):.1f}%)")
            print(f"  Available: {mem.get('available', 0):.1f} GB")
            
            swap = memory_info.get('swap', {})
            if swap.get('total', 0) > 0:
                print(f"  Swap: {swap.get('used', 0):.1f} / {swap.get('total', 0):.1f} GB")
            
            # GPU
            gpu_info = data_source.get_gpu_info()
            if gpu_info.get('available', False):
                print(f"\nGPU:")
                for gpu in gpu_info.get('gpus', []):
                    print(f"  Name: {gpu.get('name', 'Unknown')}")
                    print(f"  Usage: {gpu.get('gpu_util', 0):.1f}%")
                    if gpu.get('memory_total', 0) > 0:
                        print(f"  Memory: {gpu.get('memory_used', 0):.0f} / {gpu.get('memory_total', 0):.0f} MB")
                    if gpu.get('temperature', 0) > 0:
                        print(f"  Temperature: {gpu.get('temperature', 0):.0f}°C")
            else:
                print(f"\nGPU: Not available")
            
            # Network
            network_info = data_source.get_network_info()
            print(f"\nNetwork:")
            upload_mb = network_info.get('upload_speed', 0) / (1024 * 1024)
            download_mb = network_info.get('download_speed', 0) / (1024 * 1024)
            print(f"  Upload: {upload_mb:.2f} MB/s")
            print(f"  Download: {download_mb:.2f} MB/s")
            
            # Disk
            disk_info = data_source.get_disk_info()
            print(f"\nDisk:")
            print(f"  Read: {disk_info.get('read_speed_mb', 0):.2f} MB/s")
            print(f"  Write: {disk_info.get('write_speed_mb', 0):.2f} MB/s")
            
            partitions = disk_info.get('partition_usage', [])
            if partitions:
                print(f"  Partitions:")
                for part in partitions[:3]:  # Show first 3
                    print(f"    {part['mountpoint']}: {part['used']:.1f} / {part['total']:.1f} GB ({part['percent']:.1f}%)")
        
        # Disconnect
        data_source.disconnect()
        print(f"\n✅ Test completed successfully!")
        
    else:
        print(f"\n❌ Connection failed!")
        sys.exit(1)


if __name__ == '__main__':
    test_ssh_connection()
