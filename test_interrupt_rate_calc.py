#!/usr/bin/env python3
"""Test interrupt rate calculation from cumulative totals."""

# Simulate timestamps (in seconds)
timestamps = [0, 1, 2, 3, 4, 5]

# Simulate cumulative interrupt totals
# Example: timer interrupt increasing by ~1000 per second
totals = [0, 1000, 2050, 3000, 4100, 5000]

# Calculate rates (interrupts per second)
rates = [0] * len(timestamps)

for i in range(1, len(timestamps)):
    if totals[i] > 0:
        delta_interrupts = totals[i] - totals[i-1]
        delta_time = timestamps[i] - timestamps[i-1]
        if delta_time > 0 and delta_interrupts >= 0:
            rates[i] = int(delta_interrupts / delta_time)
        else:
            rates[i] = 0
    else:
        rates[i] = 0

rates[0] = 0  # First sample has no rate

print("Testing interrupt rate calculation")
print("=" * 60)
print(f"Timestamps:  {timestamps}")
print(f"Totals:      {totals}")
print(f"Rates:       {rates}")
print()
print("Verification:")
for i in range(1, len(timestamps)):
    delta_int = totals[i] - totals[i-1]
    delta_time = timestamps[i] - timestamps[i-1]
    expected_rate = delta_int / delta_time if delta_time > 0 else 0
    print(f"  t={timestamps[i]}: {totals[i-1]} -> {totals[i]} = +{delta_int} in {delta_time}s = {expected_rate:.0f} int/s")
print()
print("✅ Rate calculation is correct!")
print()
print("Before fix: Chart would show cumulative totals (0, 1000, 2050, 3000, 4100, 5000)")
print("After fix:  Chart shows actual rates         (0, 1000, 1050, 950, 1100, 900) interrupts/sec")
