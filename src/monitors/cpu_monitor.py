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
        # Track the monitor process itself
        self.monitor_process = psutil.Process()
        
        # Intel RAPL power monitoring
        self._prev_energy_uj = None
        self._prev_energy_time = None
        self._rapl_available = self._check_rapl_available()
    
    def _check_rapl_available(self) -> bool:
        """Check if Intel RAPL is available for power monitoring."""
        try:
            rapl_path = '/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj'
            with open(rapl_path, 'r') as f:
                f.read()
            return True
        except (FileNotFoundError, PermissionError):
            return False
        
    def get_usage(self) -> Dict:
        """Get CPU usage statistics."""
        return {
            'total': psutil.cpu_percent(interval=None),
            'per_core': psutil.cpu_percent(interval=None, percpu=True),
            'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        }
    
    def get_frequency(self) -> Dict:
        """Get current CPU frequency for all cores."""
        try:
            freq_info = psutil.cpu_freq(percpu=True)
            if freq_info:
                # Return per_core as number array (MHz) to match Android format
                return {
                    'per_core': [f.current for f in freq_info],
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
                    frequencies.append(freq_khz / 1000)  # Convert to MHz (number, not dict)
            except (FileNotFoundError, PermissionError):
                continue
        
        if frequencies:
            avg = sum(frequencies) / len(frequencies)
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
    
    def get_per_core_details(self) -> List[Dict]:
        """Get per-core detailed CPU times including IRQ and SoftIRQ.
        
        Returns:
            List of dictionaries with per-core CPU time details
        """
        per_core_details = []
        try:
            # psutil.cpu_times(percpu=True) gives us per-core times including irq and softirq
            per_core_times = psutil.cpu_times(percpu=True)
            
            for core_idx, times in enumerate(per_core_times):
                core_data = {
                    'core': core_idx,
                    'times': {
                        'user': getattr(times, 'user', 0),
                        'nice': getattr(times, 'nice', 0),
                        'system': getattr(times, 'system', 0),
                        'idle': getattr(times, 'idle', 0),
                        'iowait': getattr(times, 'iowait', 0),
                        'irq': getattr(times, 'irq', 0),
                        'softirq': getattr(times, 'softirq', 0),
                        'steal': getattr(times, 'steal', 0) if hasattr(times, 'steal') else 0
                    }
                }
                per_core_details.append(core_data)
        except Exception as e:
            print(f"Error getting per-core details: {e}")
        
        return per_core_details
    
    def get_power(self) -> Optional[float]:
        """Get CPU package power consumption in Watts using Intel RAPL.
        
        Returns:
            Power in Watts, or None if not available
        """
        if not self._rapl_available:
            return None
        
        try:
            import time
            rapl_path = '/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj'
            
            with open(rapl_path, 'r') as f:
                current_energy_uj = int(f.read().strip())
            
            current_time = time.time()
            
            # Need two samples to calculate power
            if self._prev_energy_uj is not None and self._prev_energy_time is not None:
                # Calculate energy delta (handle counter wrap-around)
                # RAPL counter is 32-bit and wraps around
                with open('/sys/class/powercap/intel-rapl/intel-rapl:0/max_energy_range_uj', 'r') as f:
                    max_range = int(f.read().strip())
                
                energy_delta_uj = current_energy_uj - self._prev_energy_uj
                if energy_delta_uj < 0:  # Counter wrapped
                    energy_delta_uj += max_range
                
                time_delta_sec = current_time - self._prev_energy_time
                
                if time_delta_sec > 0:
                    # Power (Watts) = Energy (Joules) / Time (seconds)
                    # Convert microjoules to joules: uj / 1,000,000
                    power_watts = (energy_delta_uj / 1_000_000) / time_delta_sec
                    
                    # Store current values for next calculation
                    self._prev_energy_uj = current_energy_uj
                    self._prev_energy_time = current_time
                    
                    return power_watts
            
            # First sample or time delta is 0
            self._prev_energy_uj = current_energy_uj
            self._prev_energy_time = current_time
            return None
            
        except Exception as e:
            print(f"Error reading CPU power: {e}")
            return None
    
    def get_all_info(self) -> Dict:
        """Get all CPU monitoring information."""
        # Get monitor process CPU usage (percentage across all cores)
        # psutil returns cumulative CPU across all cores, so divide by cpu_count for per-core average
        try:
            # First call initializes the measurement
            if not hasattr(self, '_monitor_cpu_initialized'):
                self.monitor_process.cpu_percent()
                self._monitor_cpu_initialized = True
                monitor_cpu_usage = 0.0
            else:
                # Subsequent calls return actual usage
                # Divide by cpu_count to get per-core percentage (same as system CPU usage display)
                raw_usage = self.monitor_process.cpu_percent()
                monitor_cpu_usage = raw_usage / self.cpu_count if self.cpu_count > 0 else raw_usage
        except Exception as e:
            monitor_cpu_usage = 0.0
        
        # Get CPU power consumption
        cpu_power = self.get_power()
        
        return {
            'usage': self.get_usage(),
            'frequency': self.get_frequency(),
            'temperature': self.get_temperature(),
            'stats': self.get_stats(),
            'per_core': self.get_per_core_details(),
            'cpu_count': self.cpu_count,
            'physical_count': self.physical_count,
            'monitor_cpu_usage': monitor_cpu_usage,
            'power_watts': cpu_power  # CPU package power in Watts (Intel RAPL)
        }


if __name__ == '__main__':
    # Test the monitor
    monitor = CPUMonitor()
    import json
    print(json.dumps(monitor.get_all_info(), indent=2))
