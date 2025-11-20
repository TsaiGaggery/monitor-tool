#!/usr/bin/env python3
"""Test interrupt data export format conversion."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test data in list format (as returned by data sources)
tier1_data = {
    'context_switches': 1000000,
    'load_avg': {'1min': 1.5, '5min': 1.2, '15min': 1.0},
    'process_counts': {'running': 2, 'blocked': 0},
    'interrupts': {
        'interrupts': [
            {'name': 'timer', 'irq': '0', 'total': 1000000, 'rate': 5000, 'cpu': 0, 'per_cpu': [500, 500]},
            {'name': 'i915', 'irq': '128', 'total': 50000, 'rate': 250, 'cpu': 1, 'per_cpu': [100, 150]},
        ]
    }
}

# Simulate the conversion logic
interrupts_data = tier1_data.get('interrupts', None)
if interrupts_data and isinstance(interrupts_data, dict):
    # Check if it's in list format: {'interrupts': [list]}
    if 'interrupts' in interrupts_data and isinstance(interrupts_data['interrupts'], list):
        # Convert list format to dict format for exporter
        interrupts_dict = {}
        for irq in interrupts_data['interrupts']:
            # Use 'name' field as key, fallback to 'irq' if no name
            key = irq.get('name', irq.get('irq', 'unknown'))
            interrupts_dict[key] = {
                'rate': irq.get('rate', irq.get('total', 0)),
                'total': irq.get('total', 0),
                'cpu': irq.get('cpu', -1),
                'per_cpu': irq.get('per_cpu', [])
            }
        
        print("✅ Conversion successful!")
        print("Original format (list):", interrupts_data)
        print("\nConverted format (dict):", interrupts_dict)
        
        # Test accessing the data as the exporter would
        for name in interrupts_dict.keys():
            irq_data = interrupts_dict[name]
            rate = irq_data.get('rate', 0)
            print(f"  {name}: rate={rate}")
    else:
        print("Already in dict format")
else:
    print("No interrupt data")
