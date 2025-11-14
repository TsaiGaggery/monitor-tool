#!/usr/bin/env python3
"""Test GPU detection in UI context."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from monitors import GPUMonitor

print("=== GPU Detection Test ===")
gpu_monitor = GPUMonitor()

print(f"GPU Type: {gpu_monitor.gpu_type}")
print(f"Intel Available: {gpu_monitor.intel_available}")
print(f"NVIDIA Available: {gpu_monitor.nvidia_available}")
print(f"AMD Available: {gpu_monitor.amd_available}")

info = gpu_monitor.get_all_info()
print(f"\nGPU Info Available: {info.get('available')}")
print(f"Number of GPUs: {len(info.get('gpus', []))}")

if info.get('gpus'):
    for gpu in info['gpus']:
        print(f"\nGPU {gpu['id']} ({gpu['type']}):")
        print(f"  Name: {gpu['name']}")
        print(f"  Clock: {gpu['gpu_clock']} MHz")

# Check if GPU tab would be created
if gpu_monitor.gpu_type:
    print("\n✓ GPU tab WILL be created (gpu_type is truthy)")
else:
    print("\n✗ GPU tab will NOT be created (gpu_type is falsy)")
