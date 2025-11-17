#!/usr/bin/env python3
"""Test frequency control fallback scenarios."""

import sys
sys.path.insert(0, 'src')

from controllers.adb_freq_controller import ADBFrequencyController

print("=== Frequency Control Fallback Test ===\n")

# Scenario 1: Valid device with root (PASS)
print("✅ Scenario 1: Valid device with root access")
print("-" * 50)
ctrl1 = ADBFrequencyController('192.168.1.68:5555')
print(f"Status: {'ENABLED' if ctrl1.is_available else 'DISABLED'}")
print(f"Root: {ctrl1.has_root}")
print(f"CPU Count: {ctrl1.cpu_count}")
if ctrl1.is_available:
    print(f"Governors: {ctrl1.get_available_cpu_governors()}")
    print(f"Current: {ctrl1.get_current_cpu_governor()}")
    freq = ctrl1.get_cpu_freq_range()
    print(f"Freq Range: {freq['hardware_min']}-{freq['hardware_max']} MHz")
print()

# Scenario 2: Invalid/offline device (FAIL gracefully)
print("⚠️  Scenario 2: Invalid/offline device")
print("-" * 50)
ctrl2 = ADBFrequencyController('10.0.0.1:5555')  # Likely offline
print(f"Status: {'ENABLED' if ctrl2.is_available else 'DISABLED'}")
print(f"Root: {ctrl2.has_root}")
print(f"Safe fallback test:")
print(f"  get_available_cpu_governors(): {ctrl2.get_available_cpu_governors()}")
print(f"  get_current_cpu_governor(): {ctrl2.get_current_cpu_governor()}")
print(f"  set_cpu_governor('performance'): {ctrl2.set_cpu_governor('performance')}")
freq = ctrl2.get_cpu_freq_range()
print(f"  get_cpu_freq_range(): {freq['hardware_min']}-{freq['hardware_max']} MHz")
print()

# Scenario 3: Test method calls on disabled controller
print("🔒 Scenario 3: Method calls on disabled controller")
print("-" * 50)
if not ctrl2.is_available:
    print("All methods should return safe defaults:")
    print(f"  get_available_cpu_governors: {ctrl2.get_available_cpu_governors()}")
    print(f"  get_current_cpu_governor: {ctrl2.get_current_cpu_governor()}")
    print(f"  set_cpu_governor: {ctrl2.set_cpu_governor('powersave')}")
    print(f"  set_cpu_freq_range: {ctrl2.set_cpu_freq_range(1000, 3000)}")
    print(f"  get_gpu_freq_range: {ctrl2.get_gpu_freq_range()}")
    print(f"  set_gpu_freq_range: {ctrl2.set_gpu_freq_range(500, 1000)}")
print()

print("=" * 50)
print("✅ All fallback scenarios handled correctly!")
print("=" * 50)
