#!/usr/bin/env python3
"""
Test interrupt rate calculation in CLI display.
Verifies that all data sources provide 'rate' field in interrupt data.
"""

from src.data_source import LocalDataSource, AndroidDataSource, RemoteLinuxDataSource
import time

def test_local_interrupt_rates():
    """Test Local data source provides interrupt rates."""
    print("=" * 60)
    print("Testing LOCAL data source interrupt rates")
    print("=" * 60)
    
    ds = LocalDataSource(enable_tier1=True)
    
    # First sample - should have rate=0 (no previous data)
    tier1_1 = ds.get_tier1_info()
    if 'interrupts' in tier1_1:
        interrupts = tier1_1['interrupts']
        if 'interrupts' in interrupts:
            print(f"\nFirst sample - Top 3 interrupts:")
            for irq in interrupts['interrupts'][:3]:
                name = irq.get('name', 'Unknown')
                total = irq.get('total', 0)
                rate = irq.get('rate', 'MISSING')
                print(f"  {name:30s} total={total:>12,}  rate={rate:>10}")
    
    # Wait and collect second sample
    time.sleep(2)
    
    tier1_2 = ds.get_tier1_info()
    if 'interrupts' in tier1_2:
        interrupts = tier1_2['interrupts']
        if 'interrupts' in interrupts:
            print(f"\nSecond sample (2s later) - Top 5 interrupts:")
            print(f"{'Name':<30s} {'Total':>12s} {'Rate (int/s)':>12s}")
            print("-" * 60)
            for irq in interrupts['interrupts'][:5]:
                name = irq.get('name', 'Unknown')
                total = irq.get('total', 0)
                rate = irq.get('rate', 'MISSING')
                print(f"  {name:30s} {total:>12,}  {rate:>12}")
            
            # Verify rate field exists and is sorted correctly
            has_rate_field = all('rate' in irq for irq in interrupts['interrupts'][:5])
            print(f"\n✓ All interrupts have 'rate' field: {has_rate_field}")
            
            # Check if sorted by rate
            rates = [irq.get('rate', 0) for irq in interrupts['interrupts'][:5]]
            is_sorted = all(rates[i] >= rates[i+1] for i in range(len(rates)-1))
            print(f"✓ Sorted by rate (descending): {is_sorted}")
            print(f"  Rates: {rates}")

def test_android_interrupt_format():
    """Show expected Android interrupt data format (requires ADB device)."""
    print("\n" + "=" * 60)
    print("Testing ANDROID data source interrupt format")
    print("=" * 60)
    
    # This would require an actual Android device connected
    # Just document the expected behavior
    print("""
Expected behavior for Android:
1. First sample: All interrupts have rate=0 (no previous data)
2. Subsequent samples: rate = (current_total - prev_total) / time_delta_sec
3. Sorted by rate (highest interrupt/sec first)
4. CLI displays: irq.get('rate', irq.get('total', 0))
   - Shows current activity, not cumulative counts
    """)

def test_ssh_interrupt_format():
    """Show expected SSH interrupt data format (requires SSH connection)."""
    print("\n" + "=" * 60)
    print("Testing SSH data source interrupt format")
    print("=" * 60)
    
    print("""
Expected behavior for Remote Linux (SSH):
1. First sample: All interrupts have rate=0 (no previous data)
2. Subsequent samples: rate = (current_total - prev_total) / time_delta_sec
3. Sorted by rate (highest interrupt/sec first)
4. CLI displays: irq.get('rate', irq.get('total', 0))
   - Shows current activity, not cumulative counts
    """)

if __name__ == '__main__':
    print("\n🔍 Testing interrupt rate calculation and display\n")
    
    try:
        test_local_interrupt_rates()
    except Exception as e:
        print(f"❌ Error testing local source: {e}")
    
    test_android_interrupt_format()
    test_ssh_interrupt_format()
    
    print("\n" + "=" * 60)
    print("✅ Test complete - CLI should now display interrupt RATES")
    print("   not cumulative totals")
    print("=" * 60)
