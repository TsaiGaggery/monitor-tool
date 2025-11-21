#!/usr/bin/env python3
"""Frequency controller for CPU/GPU/Memory."""

import os
import subprocess
from typing import List, Optional


class FrequencyController:
    """Control CPU, GPU, and memory frequencies (requires root/sudo)."""
    
    def __init__(self):
        self.has_root = os.geteuid() == 0
        self.cpu_count = len([f for f in os.listdir('/sys/devices/system/cpu/') 
                             if f.startswith('cpu') and f[3:].isdigit()])
    
    def _run_privileged_command(self, command: List[str]) -> bool:
        """Run a command with sudo if not root."""
        try:
            if not self.has_root:
                command = ['sudo'] + command
            
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running command {' '.join(command)}: {e}")
            return False
    
    def _write_sysfs(self, path: str, value: str) -> bool:
        """Write to a sysfs file with appropriate permissions."""
        try:
            if self.has_root:
                with open(path, 'w') as f:
                    f.write(value)
                return True
            else:
                # Use sudo to write
                cmd = ['sudo', 'sh', '-c', f'echo {value} > {path}']
                return self._run_privileged_command(cmd[1:])
        except Exception as e:
            print(f"Error writing to {path}: {e}")
            return False
    
    def get_available_cpu_governors(self) -> List[str]:
        """Get list of available CPU governors."""
        try:
            path = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors'
            with open(path, 'r') as f:
                return f.read().strip().split()
        except FileNotFoundError:
            return []
    
    def get_current_cpu_governor(self, cpu_id: int = 0) -> Optional[str]:
        """Get current CPU governor."""
        try:
            path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor'
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
    
    def set_cpu_governor(self, governor: str, cpu_id: Optional[int] = None) -> bool:
        """Set CPU governor for a specific CPU or all CPUs."""
        if cpu_id is not None:
            path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor'
            return self._write_sysfs(path, governor)
        else:
            # Set for all CPUs
            success = True
            for i in range(self.cpu_count):
                path = f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor'
                if not self._write_sysfs(path, governor):
                    success = False
            return success
    
    def get_cpu_freq_range(self, cpu_id: int = 0) -> dict:
        """Get min/max frequency range for a CPU."""
        try:
            base_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq'
            
            with open(f'{base_path}/cpuinfo_min_freq', 'r') as f:
                min_freq = int(f.read().strip()) / 1000  # kHz to MHz
            
            with open(f'{base_path}/cpuinfo_max_freq', 'r') as f:
                max_freq = int(f.read().strip()) / 1000
            
            with open(f'{base_path}/scaling_min_freq', 'r') as f:
                scaling_min = int(f.read().strip()) / 1000
            
            with open(f'{base_path}/scaling_max_freq', 'r') as f:
                scaling_max = int(f.read().strip()) / 1000
            
            return {
                'hardware_min': min_freq,
                'hardware_max': max_freq,
                'scaling_min': scaling_min,
                'scaling_max': scaling_max
            }
        except Exception as e:
            print(f"Error getting CPU frequency range: {e}")
            return {}
    
    def set_cpu_freq_range(self, min_freq: int, max_freq: int, 
                          cpu_id: Optional[int] = None) -> bool:
        """Set CPU frequency range in MHz."""
        min_khz = int(min_freq * 1000)
        max_khz = int(max_freq * 1000)
        
        if cpu_id is not None:
            base_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq'
            success = True
            success &= self._write_sysfs(f'{base_path}/scaling_min_freq', str(min_khz))
            success &= self._write_sysfs(f'{base_path}/scaling_max_freq', str(max_khz))
            return success
        else:
            # Set for all CPUs
            success = True
            for i in range(self.cpu_count):
                base_path = f'/sys/devices/system/cpu/cpu{i}/cpufreq'
                success &= self._write_sysfs(f'{base_path}/scaling_min_freq', str(min_khz))
                success &= self._write_sysfs(f'{base_path}/scaling_max_freq', str(max_khz))
            return success
    
    def set_cpu_performance_mode(self) -> bool:
        """Set CPU to performance mode (max frequency)."""
        return self.set_cpu_governor('performance')
    
    def set_cpu_powersave_mode(self) -> bool:
        """Set CPU to powersave mode."""
        return self.set_cpu_governor('powersave')
    
    def get_available_cpu_epp(self) -> List[str]:
        """Get list of available CPU EPP preferences."""
        try:
            path = '/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences'
            with open(path, 'r') as f:
                return f.read().strip().split()
        except FileNotFoundError:
            return []
    
    def get_current_cpu_epp(self, cpu_id: int = 0) -> Optional[str]:
        """Get current CPU EPP preference."""
        try:
            path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/energy_performance_preference'
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
    
    def set_cpu_epp(self, epp: str, cpu_id: Optional[int] = None) -> bool:
        """Set CPU EPP preference for a specific CPU or all CPUs."""
        if cpu_id is not None:
            path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/energy_performance_preference'
            return self._write_sysfs(path, epp)
        else:
            # Set for all CPUs
            success = True
            for i in range(self.cpu_count):
                path = f'/sys/devices/system/cpu/cpu{i}/cpufreq/energy_performance_preference'
                if not self._write_sysfs(path, epp):
                    success = False
            return success
    
    def get_gpu_freq_range(self) -> dict:
        """Get GPU frequency range information."""
        try:
            # Try to find Intel GPU on different card numbers
            for card_num in range(5):  # Check card0-4
                # Try Intel Xe driver first (newer GPUs)
                xe_base = f'/sys/class/drm/card{card_num}/device/tile0/gt0/freq0'
                if os.path.exists(xe_base):
                    with open(f'{xe_base}/min_freq', 'r') as f:
                        min_freq = int(f.read().strip())
                    with open(f'{xe_base}/max_freq', 'r') as f:
                        max_freq = int(f.read().strip())
                    with open(f'{xe_base}/rpn_freq', 'r') as f:
                        hw_min = int(f.read().strip())
                    with open(f'{xe_base}/rp0_freq', 'r') as f:
                        hw_max = int(f.read().strip())
                    with open(f'{xe_base}/act_freq', 'r') as f:
                        act_freq = int(f.read().strip())
                    
                    return {
                        'type': 'intel_xe',
                        'scaling_min': min_freq,
                        'scaling_max': max_freq,
                        'hardware_min': hw_min,
                        'hardware_max': hw_max,
                        'current': act_freq if act_freq > 0 else max_freq,
                        'card': f'card{card_num}'
                    }
                
                # Try Intel i915 driver (older GPUs)
                i915_base = f'/sys/class/drm/card{card_num}'
                if os.path.exists(f'{i915_base}/gt_min_freq_mhz'):
                    with open(f'{i915_base}/gt_min_freq_mhz', 'r') as f:
                        min_freq = int(f.read().strip())
                    with open(f'{i915_base}/gt_max_freq_mhz', 'r') as f:
                        max_freq = int(f.read().strip())
                    with open(f'{i915_base}/gt_cur_freq_mhz', 'r') as f:
                        cur_freq = int(f.read().strip())
                    
                    # Try to get hardware limits
                    hw_min = min_freq
                    hw_max = max_freq
                    if os.path.exists(f'{i915_base}/gt_RP1_freq_mhz'):
                        with open(f'{i915_base}/gt_RP1_freq_mhz', 'r') as f:
                            hw_min = int(f.read().strip())
                    if os.path.exists(f'{i915_base}/gt_RP0_freq_mhz'):
                        with open(f'{i915_base}/gt_RP0_freq_mhz', 'r') as f:
                            hw_max = int(f.read().strip())
                    
                    return {
                        'type': 'intel_i915',
                        'scaling_min': min_freq,
                        'scaling_max': max_freq,
                        'hardware_min': hw_min,
                        'hardware_max': hw_max,
                        'current': cur_freq,
                        'card': f'card{card_num}'
                    }
            
            return {}
        except Exception as e:
            print(f"Error getting GPU frequency range: {e}")
            return {}
    
    def set_gpu_freq_range(self, min_freq: int, max_freq: int) -> bool:
        """Set GPU frequency range in MHz."""
        try:
            # Try to find Intel GPU on different card numbers
            for card_num in range(5):  # Check card0-4
                # Try Intel Xe driver first
                xe_base = f'/sys/class/drm/card{card_num}/device/tile0/gt0/freq0'
                if os.path.exists(xe_base):
                    # Check hardware limits
                    with open(f'{xe_base}/rpn_freq', 'r') as f:
                        hw_min = int(f.read().strip())
                    with open(f'{xe_base}/rp0_freq', 'r') as f:
                        hw_max = int(f.read().strip())
                    
                    # Validate range
                    if min_freq < hw_min or max_freq > hw_max:
                        print(f"GPU frequency range must be within {hw_min}-{hw_max} MHz")
                        return False
                    
                    success = True
                    success &= self._write_sysfs(f'{xe_base}/min_freq', str(min_freq))
                    success &= self._write_sysfs(f'{xe_base}/max_freq', str(max_freq))
                    return success
                
                # Try Intel i915 driver
                i915_base = f'/sys/class/drm/card{card_num}'
                if os.path.exists(f'{i915_base}/gt_min_freq_mhz'):
                    success = True
                    success &= self._write_sysfs(f'{i915_base}/gt_min_freq_mhz', str(min_freq))
                    success &= self._write_sysfs(f'{i915_base}/gt_max_freq_mhz', str(max_freq))
                    return success
            
            print("GPU frequency control not available")
            return False
        except Exception as e:
            print(f"Error setting GPU frequency: {e}")
            return False
    
    def set_gpu_freq(self, freq_mhz: int) -> bool:
        """Set GPU frequency (platform-specific)."""
        # Set both min and max to the same value to lock frequency
        return self.set_gpu_freq_range(freq_mhz, freq_mhz)
    
    def get_all_info(self) -> dict:
        """Get all frequency controller information."""
        return {
            'has_root': self.has_root,
            'cpu_count': self.cpu_count,
            'available_governors': self.get_available_cpu_governors(),
            'current_governor': self.get_current_cpu_governor(),
            'cpu_freq_range': self.get_cpu_freq_range(),
            'gpu_freq_range': self.get_gpu_freq_range()
        }


if __name__ == '__main__':
    # Test the controller
    controller = FrequencyController()
    import json
    print(json.dumps(controller.get_all_info(), indent=2))
