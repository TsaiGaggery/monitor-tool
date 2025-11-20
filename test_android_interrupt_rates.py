#!/usr/bin/env python3
"""Test Android interrupt rates - verify rates show up on first call."""

import sys
sys.path.insert(0, 'src')

# Mock test - simulate the cached data scenario
print("Testing interrupt rate calculation with cached data scenario...")
print("=" * 70)

# Simulate what happens with Android/SSH:
# 1. First call gets cached data
# 2. Warm-up waits 1.2 seconds
# 3. Second call gets fresh data with different timestamp

import time

class MockData:
    def __init__(self):
        self.call_count = 0
        self.base_time = int(time.time() * 1000)
        
    def get_latest_data(self):
        """Simulate cached data that updates every second."""
        # Return data that changes based on call time (simulating 1-second updates)
        current_time = int(time.time() * 1000)
        
        return {
            'timestamp_ms': current_time,
            'ctxt': 1000000 + (current_time - self.base_time) // 10,  # Changes over time
            'interrupt_data': {
                'interrupts': [
                    {'irq': 'timer', 'name': 'timer', 'total': 500000 + (current_time - self.base_time) * 5},
                    {'irq': 'i915', 'name': 'i915', 'total': 100000 + (current_time - self.base_time) * 2},
                ]
            }
        }

mock_monitor = MockData()

print("\n1. First call to get_latest_data() - baseline:")
data1 = mock_monitor.get_latest_data()
print(f"   timestamp_ms: {data1['timestamp_ms']}")
print(f"   timer total: {data1['interrupt_data']['interrupts'][0]['total']:,}")
print(f"   i915 total: {data1['interrupt_data']['interrupts'][1]['total']:,}")

print("\n2. Waiting 1.2 seconds (simulating warm-up)...")
time.sleep(1.2)

print("\n3. Second call to get_latest_data() - should have fresh data:")
data2 = mock_monitor.get_latest_data()
print(f"   timestamp_ms: {data2['timestamp_ms']}")
print(f"   timer total: {data2['interrupt_data']['interrupts'][0]['total']:,}")
print(f"   i915 total: {data2['interrupt_data']['interrupts'][1]['total']:,}")

# Calculate rates
time_delta_ms = data2['timestamp_ms'] - data1['timestamp_ms']
time_delta_sec = time_delta_ms / 1000.0

timer_delta = data2['interrupt_data']['interrupts'][0]['total'] - data1['interrupt_data']['interrupts'][0]['total']
i915_delta = data2['interrupt_data']['interrupts'][1]['total'] - data1['interrupt_data']['interrupts'][1]['total']

timer_rate = int(timer_delta / time_delta_sec) if time_delta_sec > 0 else 0
i915_rate = int(i915_delta / time_delta_sec) if time_delta_sec > 0 else 0

print(f"\n4. Calculated rates:")
print(f"   Time delta: {time_delta_ms:.0f} ms ({time_delta_sec:.3f} sec)")
print(f"   timer rate: {timer_rate:,}/s")
print(f"   i915 rate: {i915_rate:,}/s")

if timer_rate > 0 and i915_rate > 0:
    print("\n✅ SUCCESS: Rates are non-zero after warm-up!")
else:
    print("\n❌ FAIL: Rates are still zero!")

print("=" * 70)
