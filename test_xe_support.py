#!/usr/bin/env python3
"""Test Xe GPU monitoring support."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from monitors.gpu_monitor import GPUMonitor
from controllers.freq_controller import FrequencyController
import json

def main():
    print("=" * 60)
    print("Testing Intel Xe GPU Support")
    print("=" * 60)
    print()
    
    # Test GPU Monitor
    print("1. GPU Monitoring Test:")
    print("-" * 60)
    monitor = GPUMonitor()
    print(f"GPU Type Detected: {monitor.gpu_type}")
    print(f"Intel Available: {monitor.intel_available}")
    print()
    
    if monitor.intel_available:
        print("Getting Intel GPU Info...")
        info = monitor.get_intel_info()
        print(json.dumps(info, indent=2))
        print()
        
        # Test utilization specifically
        print("Testing Xe GPU Utilization...")
        for card_num in range(3):
            xe_path = f'/sys/class/drm/card{card_num}/device/tile0/gt0/gtidle/idle_residency_ms'
            if os.path.exists(xe_path):
                print(f"  Found Xe GPU on card{card_num}")
                util = monitor._get_xe_gpu_utilization(card_num)
                print(f"  Utilization: {util}%")
                
                mem = monitor._get_xe_gpu_memory(card_num)
                if mem:
                    used_mb = mem[0] / (1024 * 1024)
                    total_mb = mem[1] / (1024 * 1024)
                    print(f"  Memory: {used_mb:.0f} MB / {total_mb:.0f} MB")
                break
        print()
    
    # Test Frequency Controller
    print("2. Frequency Control Test:")
    print("-" * 60)
    controller = FrequencyController()
    
    print("GPU Frequency Range:")
    freq_info = controller.get_gpu_freq_range()
    print(json.dumps(freq_info, indent=2))
    print()
    
    if freq_info:
        print("GPU Type:", freq_info.get('type'))
        if freq_info.get('type') == 'intel_xe':
            print("✅ Xe GPU detected and supported!")
            print(f"  Card: {freq_info.get('card')}")
            print(f"  Current: {freq_info.get('current')} MHz")
            print(f"  Range: {freq_info.get('scaling_min')}-{freq_info.get('scaling_max')} MHz")
            print(f"  Hardware: {freq_info.get('hardware_min')}-{freq_info.get('hardware_max')} MHz")
        elif freq_info.get('type') == 'intel_i915':
            print("✅ i915 GPU detected and supported!")
            print(f"  Card: {freq_info.get('card')}")
            print(f"  Current: {freq_info.get('current')} MHz")
            print(f"  Range: {freq_info.get('scaling_min')}-{freq_info.get('scaling_max')} MHz")
    
    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == '__main__':
    main()
