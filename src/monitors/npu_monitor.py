#!/usr/bin/env python3
"""NPU monitoring module - supports various NPU platforms including Intel."""

import os
import subprocess
from typing import Dict, Optional


class NPUMonitor:
    """Monitor NPU usage and performance (platform-specific)."""
    
    def __init__(self):
        self.platform = self._detect_platform()
        self.available = self.platform is not None
    
    def _detect_platform(self) -> Optional[str]:
        """Detect NPU platform."""
        # Check for Intel NPU (Meteor Lake, Arrow Lake, Lunar Lake)
        if self._check_intel_npu():
            return 'intel'
        
        # Check for RockChip NPU
        if os.path.exists('/dev/rknpu'):
            return 'rockchip'
        
        # Check for Qualcomm NPU
        if os.path.exists('/dev/qcom_npu'):
            return 'qualcomm'
        
        # Check for MediaTek APU
        if os.path.exists('/dev/mdla'):
            return 'mediatek'
        
        # Check for Amlogic NPU
        if os.path.exists('/sys/class/npu'):
            return 'amlogic'
        
        # Check for generic NPU entries
        if os.path.exists('/sys/devices/platform/npu'):
            return 'generic'
        
        return None
    
    def _check_intel_npu(self) -> bool:
        """Check for Intel NPU (VPU) on Meteor Lake and newer platforms."""
        try:
            # Check for Intel VPU device in sysfs
            intel_vpu_paths = [
                '/sys/class/accel/accel0',  # Intel NPU acceleration device
                '/sys/bus/pci/drivers/intel_vpu',
                '/dev/accel/accel0',
            ]
            
            for path in intel_vpu_paths:
                if os.path.exists(path):
                    return True
            
            # Check PCI devices for Intel VPU
            try:
                result = subprocess.run(['lspci'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Intel VPU device ID check
                    if 'VPU' in result.stdout or '7d1d' in result.stdout.lower():
                        return True
            except:
                pass
                
        except Exception as e:
            print(f"Error checking Intel NPU: {e}")
        
        return False
    
    def get_intel_info(self) -> Dict:
        """Get Intel NPU (VPU) information."""
        info = {
            'platform': 'Intel NPU',
            'utilization': 0,
            'frequency': 0,
            'power': 0,
            'memory_used': 0,
            'max_frequency': 0,
            'available': True
        }
        
        try:
            # Try to read from PCI device sysfs (Intel VPU driver)
            device_path = '/sys/class/accel/accel0/device'
            if os.path.exists(device_path):
                # Read current frequency
                freq_file = f'{device_path}/npu_current_frequency_mhz'
                if os.path.exists(freq_file):
                    try:
                        with open(freq_file, 'r') as f:
                            info['frequency'] = int(f.read().strip())
                    except:
                        pass
                
                # Read max frequency
                max_freq_file = f'{device_path}/npu_max_frequency_mhz'
                if os.path.exists(max_freq_file):
                    try:
                        with open(max_freq_file, 'r') as f:
                            info['max_frequency'] = int(f.read().strip())
                    except:
                        pass
                
                # Read memory utilization (in bytes)
                mem_file = f'{device_path}/npu_memory_utilization'
                if os.path.exists(mem_file):
                    try:
                        with open(mem_file, 'r') as f:
                            mem_bytes = int(f.read().strip())
                            info['memory_used'] = mem_bytes / (1024 * 1024)  # Convert to MB
                    except:
                        pass
                
                # Calculate utilization from busy time
                # Read busy time in microseconds
                busy_file = f'{device_path}/npu_busy_time_us'
                if os.path.exists(busy_file):
                    try:
                        with open(busy_file, 'r') as f:
                            busy_us = int(f.read().strip())
                            
                        # Store busy time for delta calculation
                        if not hasattr(self, '_last_busy_us'):
                            self._last_busy_us = busy_us
                            self._last_time = __import__('time').time()
                        else:
                            import time
                            current_time = time.time()
                            time_delta = current_time - self._last_time
                            busy_delta = busy_us - self._last_busy_us
                            
                            if time_delta > 0:
                                # Calculate utilization percentage
                                utilization = (busy_delta / (time_delta * 1000000)) * 100
                                info['utilization'] = min(100, max(0, utilization))
                            
                            self._last_busy_us = busy_us
                            self._last_time = current_time
                    except:
                        pass
                
                # Check for power information
                power_file = f'{device_path}/power'
                if os.path.exists(power_file):
                    try:
                        with open(power_file, 'r') as f:
                            power = int(f.read().strip())
                            info['power'] = power / 1000000  # uW to W
                    except:
                        pass
            
            # Fallback: Try old paths
            accel_path = '/sys/class/accel/accel0'
            if os.path.exists(accel_path):
                device_path_old = f'{accel_path}/device'
                
                # Check for frequency information (old path)
                freq_file_old = f'{device_path_old}/freq'
                if os.path.exists(freq_file_old) and info['frequency'] == 0:
                    try:
                        with open(freq_file_old, 'r') as f:
                            freq = int(f.read().strip())
                            info['frequency'] = freq / 1000000  # Hz to MHz
                    except:
                        pass
            
            # Try to get utilization from debugfs (requires root)
            debugfs_path = '/sys/kernel/debug/dri/0/i915_vpu_usage'
            if os.path.exists(debugfs_path) and info['utilization'] == 0:
                try:
                    with open(debugfs_path, 'r') as f:
                        content = f.read()
                        # Parse utilization percentage
                        import re
                        match = re.search(r'utilization:\s*(\d+)', content)
                        if match:
                            info['utilization'] = int(match.group(1))
                except PermissionError:
                    # debugfs requires root access
                    pass
                except:
                    pass
                    
        except Exception as e:
            print(f"Error reading Intel NPU info: {e}")
        
        return info
    
    def get_rockchip_info(self) -> Dict:
        """Get RockChip NPU information."""
        info = {
            'platform': 'RockChip',
            'utilization': 0,
            'frequency': 0
        }
        
        try:
            # Try to read NPU frequency
            freq_path = '/sys/class/devfreq/fde40000.npu/cur_freq'
            if os.path.exists(freq_path):
                with open(freq_path, 'r') as f:
                    freq = int(f.read().strip())
                    info['frequency'] = freq / 1000000  # Hz to MHz
            
            # Try to read NPU load
            load_path = '/sys/class/devfreq/fde40000.npu/load'
            if os.path.exists(load_path):
                with open(load_path, 'r') as f:
                    load = int(f.read().strip())
                    info['utilization'] = load
        except Exception as e:
            print(f"Error reading RockChip NPU info: {e}")
        
        return info
    
    def get_generic_info(self) -> Dict:
        """Get generic NPU information from sysfs."""
        info = {
            'platform': self.platform or 'Unknown',
            'utilization': 0,
            'frequency': 0,
            'available': False
        }
        
        # Try common sysfs paths
        sysfs_paths = [
            '/sys/class/npu',
            '/sys/devices/platform/npu',
            '/sys/kernel/debug/npu'
        ]
        
        for base_path in sysfs_paths:
            if not os.path.exists(base_path):
                continue
            
            info['available'] = True
            
            # Look for frequency files
            for freq_file in ['freq', 'cur_freq', 'frequency']:
                freq_path = os.path.join(base_path, freq_file)
                if os.path.exists(freq_path):
                    try:
                        with open(freq_path, 'r') as f:
                            freq = int(f.read().strip())
                            info['frequency'] = freq / 1000000  # Assume Hz
                            break
                    except:
                        pass
            
            # Look for utilization files
            for util_file in ['load', 'utilization', 'usage']:
                util_path = os.path.join(base_path, util_file)
                if os.path.exists(util_path):
                    try:
                        with open(util_path, 'r') as f:
                            util = int(f.read().strip())
                            info['utilization'] = util
                            break
                    except:
                        pass
        
        return info
    
    def get_all_info(self) -> Dict:
        """Get NPU information based on detected platform."""
        if not self.available:
            return {
                'available': False,
                'platform': None,
                'message': 'No NPU detected'
            }
        
        if self.platform == 'intel':
            return self.get_intel_info()
        elif self.platform == 'rockchip':
            return self.get_rockchip_info()
        else:
            return self.get_generic_info()


if __name__ == '__main__':
    # Test the monitor
    monitor = NPUMonitor()
    import json
    print(json.dumps(monitor.get_all_info(), indent=2))
