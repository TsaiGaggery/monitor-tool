#!/usr/bin/env python3
"""Debug Android interrupt data collection."""

import sys
import time
sys.path.insert(0, 'src')

# Test with actual Android connection
device_ip = sys.argv[1] if len(sys.argv) > 1 else None

if not device_ip:
    print("Usage: python3 test_android_debug.py <device_ip>")
    print("Example: python3 test_android_debug.py 192.168.1.68")
    sys.exit(1)

from data_source import AndroidDataSource

print(f"\n🤖 Connecting to Android device at {device_ip}:5555...")
ds = AndroidDataSource(device_ip, 5555, enable_tier1=True)

if not ds.connect():
    print("❌ Failed to connect")
    sys.exit(1)

print("✅ Connected successfully!")

# Wait a bit for data to start flowing
print("\n⏳ Waiting 3 seconds for data collection to start...")
time.sleep(3)

# Get raw data directly from monitor
print("\n" + "="*70)
print("RAW DATA from adb_monitor.get_latest_data():")
print("="*70)
raw_data = ds.adb_monitor.get_latest_data()

print(f"\nKeys in raw_data: {list(raw_data.keys())}")
print(f"\nHas 'interrupt_data' key: {'interrupt_data' in raw_data}")

if 'interrupt_data' in raw_data:
    irq_data = raw_data['interrupt_data']
    print(f"\ninterrupt_data type: {type(irq_data)}")
    print(f"interrupt_data keys: {irq_data.keys() if isinstance(irq_data, dict) else 'N/A'}")
    
    if isinstance(irq_data, dict) and 'interrupts' in irq_data:
        irqs = irq_data['interrupts']
        print(f"\nNumber of interrupts: {len(irqs)}")
        print(f"\nFirst 3 interrupts:")
        for i, irq in enumerate(irqs[:3]):
            print(f"  {i+1}. {irq}")
    else:
        print(f"\ninterrupt_data content: {irq_data}")
else:
    print("\n❌ No interrupt_data in raw_data!")

# Now test tier1_info
print("\n" + "="*70)
print("TIER1 DATA from get_tier1_info():")
print("="*70)

tier1 = ds.get_tier1_info()
print(f"\nKeys in tier1: {list(tier1.keys())}")
print(f"\nHas 'interrupts' key: {'interrupts' in tier1}")

if 'interrupts' in tier1:
    irq_data = tier1['interrupts']
    print(f"\ninterrupts type: {type(irq_data)}")
    print(f"interrupts keys: {irq_data.keys() if isinstance(irq_data, dict) else 'N/A'}")
    
    if isinstance(irq_data, dict) and 'interrupts' in irq_data:
        irqs = irq_data['interrupts']
        print(f"\nNumber of interrupts: {len(irqs)}")
        print(f"\nTop 5 interrupts with rates:")
        for i, irq in enumerate(irqs[:5]):
            name = irq.get('name', 'Unknown')[:30]
            total = irq.get('total', 0)
            rate = irq.get('rate', 0)
            print(f"  {i+1}. {name:30s} total={total:>12,} rate={rate:>8,}/s")
    else:
        print(f"\ninterrupts content: {irq_data}")
else:
    print("\n❌ No interrupts in tier1 data!")

print("\n" + "="*70)

# Wait and check again
print("\n⏳ Waiting 2 more seconds and checking again...")
time.sleep(2)

tier1_2 = ds.get_tier1_info()
if 'interrupts' in tier1_2 and isinstance(tier1_2['interrupts'], dict):
    irqs = tier1_2['interrupts'].get('interrupts', [])
    print(f"\nSecond sample - Top 5 interrupts with rates:")
    for i, irq in enumerate(irqs[:5]):
        name = irq.get('name', 'Unknown')[:30]
        total = irq.get('total', 0)
        rate = irq.get('rate', 0)
        print(f"  {i+1}. {name:30s} total={total:>12,} rate={rate:>8,}/s")

ds.disconnect()
print("\n✅ Test complete")
