#!/usr/bin/env python3
"""Test monitoring modules without GUI - for headless/SSH environments."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from monitors import CPUMonitor, GPUMonitor, MemoryMonitor, NPUMonitor
from controllers import FrequencyController
import json
import time


def print_section(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def test_cpu():
    """Test CPU monitoring."""
    print_section("CPU Monitoring")
    monitor = CPUMonitor()
    
    info = monitor.get_all_info()
    print(f"CPU Cores: {info['cpu_count']} (Physical: {info['physical_count']})")
    print(f"CPU Usage: {info['usage']['total']:.1f}%")
    print(f"Average Frequency: {info['frequency']['average']:.0f} MHz")
    
    temps = info['temperature']
    if temps:
        for sensor_name, readings in temps.items():
            print(f"Temperature ({sensor_name}):")
            for reading in readings[:3]:  # Show first 3
                print(f"  {reading['label']}: {reading['current']:.1f}°C")
    
    print("\nPer-core usage:")
    for i, usage in enumerate(info['usage']['per_core'][:8]):  # Show first 8 cores
        print(f"  Core {i}: {usage:.1f}%")


def test_memory():
    """Test memory monitoring."""
    print_section("Memory Monitoring")
    monitor = MemoryMonitor()
    
    info = monitor.get_all_info()
    mem = info['memory']
    swap = info['swap']
    
    print(f"RAM: {mem['used']:.2f} / {mem['total']:.2f} GB ({mem['percent']:.1f}%)")
    print(f"Available: {mem['available']:.2f} GB")
    print(f"Swap: {swap['used']:.2f} / {swap['total']:.2f} GB ({swap['percent']:.1f}%)")


def test_gpu():
    """Test GPU monitoring."""
    print_section("GPU Monitoring")
    monitor = GPUMonitor()
    
    info = monitor.get_all_info()
    print(f"GPU Type: {info['gpu_type']}")
    print(f"Available: {info['available']}")
    
    if info['available']:
        for gpu in info['gpus']:
            print(f"\nGPU {gpu['id']} ({gpu['type']}):")
            print(f"  Name: {gpu.get('name', 'N/A')}")
            print(f"  Usage: {gpu.get('gpu_util', 0)}%")
            print(f"  Temperature: {gpu.get('temperature', 0)}°C")
            print(f"  Memory: {gpu.get('memory_used', 0):.0f} / {gpu.get('memory_total', 0):.0f} MB")
            print(f"  GPU Clock: {gpu.get('gpu_clock', 0)} MHz")
    else:
        print("No GPU detected")


def test_npu():
    """Test NPU monitoring."""
    print_section("NPU Monitoring")
    monitor = NPUMonitor()
    
    info = monitor.get_all_info()
    print(f"Available: {info.get('available', False)}")
    
    if info.get('available'):
        print(f"Platform: {info.get('platform', 'Unknown')}")
        print(f"Utilization: {info.get('utilization', 0)}%")
        print(f"Frequency: {info.get('frequency', 0)} MHz")
        print(f"Power: {info.get('power', 0)} W")
    else:
        print(f"Message: {info.get('message', 'No NPU detected')}")


def test_frequency_controller():
    """Test frequency controller."""
    print_section("Frequency Controller")
    controller = FrequencyController()
    
    print(f"Has Root: {controller.has_root}")
    print(f"CPU Count: {controller.cpu_count}")
    
    governors = controller.get_available_cpu_governors()
    if governors:
        print(f"Available Governors: {', '.join(governors)}")
        current = controller.get_current_cpu_governor()
        print(f"Current Governor: {current}")
    
    freq_range = controller.get_cpu_freq_range()
    if freq_range:
        print(f"Frequency Range:")
        print(f"  Hardware: {freq_range['hardware_min']:.0f} - {freq_range['hardware_max']:.0f} MHz")
        print(f"  Scaling: {freq_range['scaling_min']:.0f} - {freq_range['scaling_max']:.0f} MHz")


def main():
    """Main test function."""
    print("\n" + "="*60)
    print("  System Monitor Tool - Headless Test")
    print("="*60)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        test_cpu()
        test_memory()
        test_gpu()
        test_npu()
        test_frequency_controller()
        
        print_section("Test Complete")
        print("All monitoring modules working correctly!")
        print("\nTo run the GUI dashboard:")
        print("  1. Ensure you're in a graphical session")
        print("  2. Run: ./monitor-tool")
        print("\nIf using SSH:")
        print("  ssh -X user@hostname")
        print("  ./monitor-tool")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
