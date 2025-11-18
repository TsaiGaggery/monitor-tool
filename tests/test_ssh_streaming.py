#!/usr/bin/env python3
"""
Test Remote Linux SSH Monitoring
Simpler approach - streaming JSON from remote script
"""

import sys
import time
import getpass

# Add src to path
sys.path.insert(0, '/home/gaggery/monitor-tool/src')

from data_source import RemoteLinuxDataSource


def test_ssh_monitoring():
    """Test SSH monitoring with streaming approach"""
    
    print("=" * 60)
    print("Remote Linux SSH Monitoring Test")
    print("=" * 60)
    
    # Get connection details
    host = input("\n📡 Remote host (IP or hostname): ").strip()
    if not host:
        print("❌ Host is required")
        return
    
    user = input(f"👤 SSH username [{getpass.getuser()}]: ").strip()
    if not user:
        user = getpass.getuser()
    
    ssh_port = input("🔌 SSH port [22]: ").strip()
    ssh_port = int(ssh_port) if ssh_port else 22
    
    # Authentication method
    print("\n🔐 Authentication method:")
    print("  1. Password")
    print("  2. SSH key")
    auth_method = input("Choice [1]: ").strip()
    
    password = None
    key_path = None
    
    if auth_method == "2":
        key_path = input("🔑 SSH private key path: ").strip()
        if not key_path:
            print("❌ Key path is required")
            return
    else:
        password = getpass.getpass(f"🔒 SSH password for {user}@{host}: ")
    
    interval = input("\n⏱️  Monitoring interval (seconds) [1]: ").strip()
    interval = int(interval) if interval else 1
    
    # Create data source
    print(f"\n📡 Connecting to {user}@{host}:{ssh_port}...")
    data_source = RemoteLinuxDataSource(
        host=host,
        username=user,
        password=password,
        key_path=key_path,
        port=ssh_port,
        interval=interval
    )
    
    # Connect
    if not data_source.connect():
        print("❌ Connection failed")
        return
    
    print("✅ Connected successfully!")
    print(f"📊 Source: {data_source.get_source_name()}")
    
    # Monitor for a few samples
    num_samples = 3
    print(f"\n📈 Collecting {num_samples} samples (interval: {interval}s)...\n")
    
    try:
        for i in range(num_samples):
            print(f"--- Sample {i+1}/{num_samples} ---")
            
            # CPU
            cpu_info = data_source.get_cpu_info()
            print(f"💻 CPU: {cpu_info['usage']['total']:.1f}% "
                  f"({cpu_info['cpu_count']} cores)")
            if cpu_info['frequency']['average'] > 0:
                print(f"   Freq: {cpu_info['frequency']['average']:.0f} MHz")
            if cpu_info['temperature']:
                for sensor, temp in cpu_info['temperature'].items():
                    if temp:
                        print(f"   Temp: {temp:.1f}°C")
            
            # Memory
            mem_info = data_source.get_memory_info()
            mem_gb = mem_info['memory']['total'] / (1024**3)
            mem_pct = mem_info['memory']['percent']
            print(f"🧠 Memory: {mem_pct:.1f}% ({mem_gb:.1f} GB total)")
            
            # GPU
            gpu_info = data_source.get_gpu_info()
            if gpu_info['gpus']:
                for gpu in gpu_info['gpus']:
                    print(f"🎮 GPU: {gpu['name']} - {gpu['utilization']:.1f}%")
                    print(f"   Memory: {gpu['memory_used']:.0f}/{gpu['memory_total']:.0f} MB")
                    print(f"   Temp: {gpu['temperature']:.1f}°C, Clock: {gpu['clock_speed']:.0f} MHz")
            else:
                print("🎮 GPU: Not detected")
            
            # Network
            net_info = data_source.get_network_info()
            down_mb = net_info['download_speed'] / (1024 * 1024)
            up_mb = net_info['upload_speed'] / (1024 * 1024)
            print(f"🌐 Network: ↓ {down_mb:.2f} MB/s, ↑ {up_mb:.2f} MB/s")
            
            # Disk
            disk_info = data_source.get_disk_info()
            print(f"💾 Disk: Read {disk_info['read_speed_mb']:.2f} MB/s, "
                  f"Write {disk_info['write_speed_mb']:.2f} MB/s")
            
            if i < num_samples - 1:
                print(f"\n⏳ Waiting {interval} seconds...\n")
                time.sleep(interval)
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    
    finally:
        # Cleanup
        print("\n🔌 Disconnecting...")
        data_source.disconnect()
        print("👋 Done!")


if __name__ == "__main__":
    test_ssh_monitoring()
