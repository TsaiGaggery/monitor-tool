#!/usr/bin/env python3
"""CPU monitoring module for tracking usage, frequency, and temperature."""

import psutil
import os
import glob
from typing import Dict, List, Optional


class CPUMonitor:
    """Monitor CPU usage, frequency, temperature, and per-core statistics."""
    
    def __init__(self):
        self.cpu_count = psutil.cpu_count(logical=True)
        self.physical_count = psutil.cpu_count(logical=False)
        
    def get_usage(self) -> Dict:
        """Get CPU usage statistics."""
        return {
            'total': psutil.cpu_percent(interval=0.1),
            'per_core': psutil.cpu_percent(interval=0.1, percpu=True),
            'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        }
    
    def get_frequency(self) -> Dict:
        """Get current CPU frequency for all cores."""
        try:
            freq_info = psutil.cpu_freq(percpu=True)
            if freq_info:
                return {
                    'per_core': [
                        {
                            'current': f.current,
                            'min': f.min,
                            'max': f.max
                        } for f in freq_info
                    ],
                    'average': sum(f.current for f in freq_info) / len(freq_info)
                }
            else:
                # Fallback: read from sysfs
                return self._get_frequency_from_sysfs()
        except Exception as e:
            print(f"Error getting CPU frequency: {e}")
            return {'per_core': [], 'average': 0}
    
    def _get_frequency_from_sysfs(self) -> Dict:
        """Read CPU frequency directly from sysfs."""
        frequencies = []
        for cpu_id in range(self.cpu_count):
            freq_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_cur_freq'
            try:
                with open(freq_path, 'r') as f:
                    freq_khz = int(f.read().strip())
                    frequencies.append({
                        'current': freq_khz / 1000,  # Convert to MHz
                        'min': 0,
                        'max': 0
                    })
            except (FileNotFoundError, PermissionError):
                continue
        
        if frequencies:
            avg = sum(f['current'] for f in frequencies) / len(frequencies)
            return {'per_core': frequencies, 'average': avg}
        return {'per_core': [], 'average': 0}
    
    def get_temperature(self) -> Dict:
        """Get CPU temperature from sensors."""
        temps = {}
        try:
            # Try psutil sensors
            if hasattr(psutil, 'sensors_temperatures'):
                sensors = psutil.sensors_temperatures()
                if sensors:
                    # Look for common CPU temperature sensors
                    for name in ['coretemp', 'k10temp', 'cpu_thermal', 'soc_thermal']:
                        if name in sensors:
                            temps[name] = [
                                {'label': entry.label or f'Core {i}', 'current': entry.current}
                                for i, entry in enumerate(sensors[name])
                            ]
                            break
        except Exception as e:
            print(f"Error reading temperature: {e}")
        
        return temps
    
    def get_stats(self) -> Dict:
        """Get comprehensive CPU statistics."""
        stats = psutil.cpu_stats()
        return {
            'ctx_switches': stats.ctx_switches,
            'interrupts': stats.interrupts,
            'soft_interrupts': stats.soft_interrupts,
            'syscalls': stats.syscalls if hasattr(stats, 'syscalls') else 0
        }
    
    def get_all_info(self) -> Dict:
        """Get all CPU monitoring information."""
        return {
            'usage': self.get_usage(),
            'frequency': self.get_frequency(),
            'temperature': self.get_temperature(),
            'stats': self.get_stats(),
            'cpu_count': self.cpu_count,
            'physical_count': self.physical_count
        }


if __name__ == '__main__':
    # Test the monitor
    monitor = CPUMonitor()
    import json
    print(json.dumps(monitor.get_all_info(), indent=2))
