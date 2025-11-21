#!/usr/bin/env python3
"""GPU monitoring module supporting NVIDIA, AMD, and Intel GPUs."""

import subprocess
import re
import os
import json
from typing import Dict, List, Optional


class GPUMonitor:
    """Monitor GPU usage, frequency, temperature, and memory."""
    
    def __init__(self):
        self.gpu_type = self._detect_gpu_type()
        self.nvidia_available = self.gpu_type == 'nvidia'
        self.amd_available = self.gpu_type == 'amd'
        self.intel_available = self.gpu_type == 'intel'
        
        # Previous sample for delta calculation (Intel i915 GPU)
        self._prev_intel_runtime_ms = None
        self._prev_intel_timestamp = None
        
        # Previous sample for delta calculation (Intel Xe GPU)
        self._prev_xe_idle_ms = None
        self._prev_xe_timestamp = None
        
        if self.nvidia_available:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=FutureWarning)
                    import pynvml
                self.pynvml = pynvml
                self.pynvml.nvmlInit()
                self.device_count = self.pynvml.nvmlDeviceGetCount()
            except Exception as e:
                print(f"NVIDIA GPU detected but pynvml failed: {e}")
                self.nvidia_available = False
    
    def _detect_gpu_type(self) -> Optional[str]:
        """Detect GPU type (NVIDIA, AMD, or Intel) via sysfs first."""
        try:
            # Check sysfs for GPU vendor ID (most reliable)
            gpu_info = self._detect_gpu_via_sysfs()
            if gpu_info:
                return gpu_info
            
            # Fallback to command-line tools
            # Check for NVIDIA
            result = subprocess.run(['which', 'nvidia-smi'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return 'nvidia'
            
            # Check for AMD
            result = subprocess.run(['which', 'rocm-smi'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return 'amd'
            
            # Check for Mali/other ARM GPUs
            if self._check_mali_gpu():
                return 'mali'
                
        except Exception as e:
            print(f"Error detecting GPU: {e}")
        
        return None
    
    def _detect_gpu_via_sysfs(self) -> Optional[str]:
        """Detect GPU type by reading sysfs vendor IDs."""
        try:
            # Check all DRM cards
            for card_num in range(10):
                vendor_path = f'/sys/class/drm/card{card_num}/device/vendor'
                if os.path.exists(vendor_path):
                    with open(vendor_path, 'r') as f:
                        vendor_id = f.read().strip()
                        # Intel: 0x8086, NVIDIA: 0x10de, AMD: 0x1002
                        if vendor_id in ['0x8086', '8086']:
                            return 'intel'
                        elif vendor_id in ['0x10de', '10de']:
                            return 'nvidia'
                        elif vendor_id in ['0x1002', '1002']:
                            return 'amd'
        except Exception:
            pass
        return None
    
    def _check_intel_gpu(self) -> bool:
        """Check if Intel GPU is present."""
        try:
            # Check for Intel GPU via sysfs
            intel_gpu_paths = [
                '/sys/class/drm/card0/device/vendor',
                '/sys/class/drm/card1/device/vendor',
            ]
            
            for path in intel_gpu_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        vendor_id = f.read().strip()
                        # Intel vendor ID is 0x8086
                        if vendor_id in ['0x8086', '8086']:
                            return True
            
            # Check for intel_gpu_top command
            result = subprocess.run(['which', 'intel_gpu_top'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return True
                
        except Exception:
            pass
        
        return False
    
    def _check_mali_gpu(self) -> bool:
        """Check if Mali GPU is present."""
        try:
            with open('/proc/device-tree/compatible', 'r') as f:
                content = f.read()
                if 'mali' in content.lower():
                    return True
        except:
            pass
        return False
    
    def _get_intel_gpu_utilization_from_debugfs(self) -> Optional[float]:
        """Calculate Intel GPU utilization from i915_engine_info Runtime.
        
        This reads /sys/kernel/debug/dri/*/i915_engine_info once per sample,
        and calculates utilization based on the delta from the previous sample.
        Requires sudo access to /sys/kernel/debug.
        
        Returns:
            GPU utilization percentage (0-100) or None if unavailable
        """
        import time
        
        def parse_engine_runtime(content: str) -> Optional[int]:
            """Parse runtime from i915_engine_info for rcs0 (Render/3D engine).
            
            Looking for line like: "        Runtime: 56749864ms"
            """
            for line in content.split('\n'):
                # Look for rcs0 section first
                if line.strip() == 'rcs0':
                    # Found rcs0, now look for Runtime in following lines
                    lines = content.split('\n')
                    rcs0_idx = lines.index(line)
                    # Check next ~20 lines for Runtime
                    for i in range(rcs0_idx, min(rcs0_idx + 20, len(lines))):
                        if 'Runtime:' in lines[i]:
                            # Extract runtime value (e.g., "        Runtime: 56749864ms")
                            parts = lines[i].split('Runtime:')
                            if len(parts) == 2:
                                runtime_str = parts[1].strip().replace('ms', '')
                                try:
                                    return int(runtime_str)
                                except ValueError:
                                    return None
            return None
        
        try:
            # Find i915_engine_info file by trying to read it with sudo
            engine_info_path = None
            for variant in ['0000:00:02.0', '1', '128', '0']:
                path = f'/sys/kernel/debug/dri/{variant}/i915_engine_info'
                test_result = subprocess.run(['sudo', '-n', 'cat', path],
                                           capture_output=True, text=True, timeout=1)
                if test_result.returncode == 0:
                    engine_info_path = path
                    break
            
            if not engine_info_path:
                return None
            
            # Read current sample
            result = subprocess.run(['sudo', '-n', 'cat', engine_info_path],
                                   capture_output=True, text=True, timeout=1)
            if result.returncode != 0:
                return None
            
            current_time = time.time()
            current_runtime = parse_engine_runtime(result.stdout)
            
            if current_runtime is None:
                return None
            
            # Need previous sample to calculate delta
            if self._prev_intel_runtime_ms is None or self._prev_intel_timestamp is None:
                # First sample - save and return 0
                self._prev_intel_runtime_ms = current_runtime
                self._prev_intel_timestamp = current_time
                return 0.0
            
            # Calculate utilization from delta
            time_delta = (current_time - self._prev_intel_timestamp) * 1000  # Convert to ms
            runtime_delta = current_runtime - self._prev_intel_runtime_ms  # Already in ms
            
            # Save current values for next calculation
            self._prev_intel_runtime_ms = current_runtime
            self._prev_intel_timestamp = current_time
            
            if time_delta <= 0:
                return None
            
            utilization = (runtime_delta / time_delta) * 100.0
            
            # Clamp to 0-100%
            return max(0.0, min(100.0, utilization))
            
        except Exception as e:
            return None
    
    def _get_intel_gpu_memory_from_debugfs(self) -> Optional[tuple]:
        """Get Intel GPU memory usage from i915_gem_objects.
        
        Returns:
            Tuple of (used_bytes, total_bytes) or None if unavailable
        """
        try:
            # Find i915_gem_objects file
            gem_objects_path = None
            for variant in ['0000:00:02.0', '1', '128', '0']:
                path = f'/sys/kernel/debug/dri/{variant}/i915_gem_objects'
                test_result = subprocess.run(['sudo', '-n', 'cat', path],
                                           capture_output=True, text=True, timeout=1)
                if test_result.returncode == 0:
                    gem_objects_path = path
                    content = test_result.stdout
                    break
            
            if not gem_objects_path or not content:
                return None
            
            # Parse first line: "3787 shrinkable [0 free] objects, 4150968320 bytes"
            first_line = content.split('\n')[0]
            if 'bytes' in first_line:
                parts = first_line.split(',')
                if len(parts) >= 2:
                    bytes_part = parts[-1].strip()  # "4150968320 bytes"
                    used_bytes = int(bytes_part.split()[0])
                    
                    # Parse system memory line: "system: total:0x0000000f9effa000 bytes"
                    for line in content.split('\n'):
                        if 'system: total:' in line:
                            # Extract hex value
                            hex_part = line.split('total:')[1].split()[0]
                            total_bytes = int(hex_part, 16)
                            return (used_bytes, total_bytes)
                    
                    # If no system total found, return used with 0 total
                    return (used_bytes, 0)
            
            return None
            
        except Exception as e:
            return None
    
    def _get_xe_gpu_utilization(self, card_num: int = 0) -> Optional[float]:
        """Calculate Xe GPU utilization using idle residency (delta-based).
        
        For Xe driver, we calculate utilization from gt-c6 idle time delta:
        utilization = 100 - (idle_time_delta / total_time_delta * 100)
        
        This method uses delta calculation between samples, similar to i915 approach.
        No sleep() calls - uses actual time between samples.
        
        Args:
            card_num: DRM card number (e.g., 0 for card0)
            
        Returns:
            GPU utilization percentage (0-100) or None if unavailable
        """
        import time
        
        try:
            idle_path = f'/sys/class/drm/card{card_num}/device/tile0/gt0/gtidle/idle_residency_ms'
            
            if not os.path.exists(idle_path):
                return None
            
            # Read current idle time
            with open(idle_path, 'r') as f:
                current_idle_ms = int(f.read().strip())
            current_time = time.time()
            
            # Need previous sample to calculate delta
            if self._prev_xe_idle_ms is None or self._prev_xe_timestamp is None:
                # First sample - save and return 0
                self._prev_xe_idle_ms = current_idle_ms
                self._prev_xe_timestamp = current_time
                return 0.0
            
            # Calculate deltas
            time_delta = (current_time - self._prev_xe_timestamp) * 1000  # Convert to ms
            idle_delta = current_idle_ms - self._prev_xe_idle_ms  # Already in ms
            
            # Save current values for next calculation
            self._prev_xe_idle_ms = current_idle_ms
            self._prev_xe_timestamp = current_time
            
            if time_delta <= 0:
                return None
            
            # Utilization = 100 - (idle_percentage)
            idle_percentage = (idle_delta / time_delta) * 100
            utilization = max(0.0, min(100.0, 100 - idle_percentage))
            
            return utilization
            
        except Exception as e:
            return None
    
    def _get_xe_gpu_memory(self, card_num: int = 0) -> Optional[tuple]:
        """Get Xe GPU memory usage from fdinfo.
        
        This aggregates memory usage across all GPU clients.
        
        Args:
            card_num: DRM card number
            
        Returns:
            Tuple of (used_bytes, total_bytes) or None
        """
        try:
            # Read all process fdinfo for drm memory usage
            total_used = 0
            
            # Scan /proc for all processes
            for pid_dir in os.listdir('/proc'):
                if not pid_dir.isdigit():
                    continue
                
                fdinfo_dir = f'/proc/{pid_dir}/fdinfo'
                if not os.path.exists(fdinfo_dir):
                    continue
                
                try:
                    for fd_file in os.listdir(fdinfo_dir):
                        fd_path = os.path.join(fdinfo_dir, fd_file)
                        try:
                            with open(fd_path, 'r') as f:
                                content = f.read()
                                if 'drm-driver:' in content and 'xe' in content:
                                    # Parse memory fields
                                    # Xe GPU uses GTT (Graphics Translation Table) memory
                                    for line in content.split('\n'):
                                        if line.startswith('drm-total-gtt:') or line.startswith('drm-total-system:'):
                                            # Format can be:
                                            # "drm-total-gtt:     25984 KiB"
                                            # "drm-total-system:  50060 KiB"
                                            # "drm-total-stolen:  0"
                                            try:
                                                parts = line.split(':')[1].strip().split()
                                                if len(parts) >= 1:
                                                    mem_kb = int(parts[0])
                                                    # If unit is specified, verify it's KiB
                                                    # Otherwise assume bytes and convert
                                                    if len(parts) >= 2:
                                                        if parts[1] == 'KiB':
                                                            total_used += mem_kb * 1024
                                                        else:
                                                            # Unknown unit, skip
                                                            pass
                                                    else:
                                                        # No unit specified, assume already in bytes
                                                        total_used += mem_kb
                                            except (ValueError, IndexError):
                                                pass
                        except (PermissionError, FileNotFoundError, ValueError):
                            continue
                except (PermissionError, FileNotFoundError):
                    continue
            
            # Get total system memory as GPU memory (integrated GPU uses system RAM)
            try:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            total_kb = int(line.split()[1])
                            total_bytes = total_kb * 1024
                            return (total_used, total_bytes)
            except Exception:
                pass
            
            return (total_used, 0) if total_used > 0 else None
            
        except Exception as e:
            return None
    
    def get_intel_info(self) -> Dict:
        """Get Intel GPU information using sysfs (supports i915 and Xe drivers)."""
        info = {
            'name': 'Intel GPU',
            'gpu_util': 0,
            'memory_util': 0,
            'memory_used': 0,
            'memory_total': 0,
            'temperature': 0,
            'power': 0,
            'gpu_clock': 0,
            'memory_clock': 0
        }
        
        try:
            # Detect GPU name from lspci
            for card_num in range(5):
                vendor_path = f'/sys/class/drm/card{card_num}/device/vendor'
                if os.path.exists(vendor_path):
                    with open(vendor_path, 'r') as f:
                        if f.read().strip() in ['0x8086', '8086']:
                            # Found Intel GPU, get name from lspci
                            uevent_path = f'/sys/class/drm/card{card_num}/device/uevent'
                            if os.path.exists(uevent_path):
                                with open(uevent_path, 'r') as ue:
                                    for line in ue:
                                        if line.startswith('PCI_SLOT_NAME='):
                                            pci_addr = line.split('=')[1].strip()
                                            result = subprocess.run(['lspci', '-s', pci_addr],
                                                                  capture_output=True, text=True)
                                            if result.returncode == 0:
                                                # Extract GPU name
                                                match = re.search(r'VGA.*?:\s+Intel.*?Device\s+(\w+)', result.stdout)
                                                if match:
                                                    device_id = match.group(1)
                                                    info['name'] = f'Intel GPU (Device {device_id})'
                                                else:
                                                    info['name'] = 'Intel GPU'
                            
                            # Try Xe driver frequency (newer Intel GPUs)
                            xe_freq_path = f'/sys/class/drm/card{card_num}/device/tile0/gt0/freq0/act_freq'
                            if os.path.exists(xe_freq_path):
                                # Always use actual frequency (act_freq)
                                # This is the real running frequency, 0 when idle
                                with open(xe_freq_path, 'r') as f:
                                    act_freq = int(f.read().strip())
                                info['gpu_clock'] = act_freq
                                
                                # NOTE: Intel GPU sysfs does not provide actual utilization
                                # act_freq indicates GPU activity (0 = idle, >0 = active)
                                # but frequency does NOT equal utilization percentage
                                # Leave gpu_util as 0 (use intel_gpu_top for real data)
                                
                            # Try i915 driver frequency (older Intel GPUs)
                            elif os.path.exists(f'/sys/class/drm/card{card_num}/gt_cur_freq_mhz'):
                                # Always use actual frequency (gt_act_freq_mhz) for i915
                                # This is the real running frequency
                                act_freq_path = f'/sys/class/drm/card{card_num}/gt_act_freq_mhz'
                                
                                if os.path.exists(act_freq_path):
                                    with open(act_freq_path, 'r') as f:
                                        act_freq = int(f.read().strip())
                                    info['gpu_clock'] = act_freq
                                else:
                                    # If act_freq not available, fallback to cur_freq
                                    cur_freq_path = f'/sys/class/drm/card{card_num}/gt_cur_freq_mhz'
                                    with open(cur_freq_path, 'r') as f:
                                        info['gpu_clock'] = int(f.read().strip())
                                
                                # NOTE: Intel GPU sysfs does not provide actual utilization
                                # Frequency != Utilization, so we leave gpu_util as 0
                                # Use intel_gpu_top for real utilization (requires sudo)
                            
                            # Found Intel GPU, exit loop
                            break
            
            # Try to get real GPU utilization from debugfs (fast, direct)
            # First try i915 driver (older Intel GPUs)
            util = self._get_intel_gpu_utilization_from_debugfs()
            if util is not None:
                info['gpu_util'] = int(util)
            else:
                # Try Xe driver (newer Intel GPUs like Arc, Meteor Lake, etc.)
                for card_num in range(5):
                    xe_idle_path = f'/sys/class/drm/card{card_num}/device/tile0/gt0/gtidle/idle_residency_ms'
                    if os.path.exists(xe_idle_path):
                        util = self._get_xe_gpu_utilization(card_num)
                        if util is not None:
                            info['gpu_util'] = int(util)
                            break
            
            # Try to get GPU memory usage from debugfs
            # First try i915
            mem_info = self._get_intel_gpu_memory_from_debugfs()
            if mem_info is not None:
                used_bytes, total_bytes = mem_info
                info['memory_used'] = used_bytes // (1024 * 1024)  # Convert to MB
                info['memory_total'] = total_bytes // (1024 * 1024)  # Convert to MB
                if total_bytes > 0:
                    info['memory_util'] = int((used_bytes / total_bytes) * 100)
            else:
                # Try Xe driver memory
                for card_num in range(5):
                    xe_idle_path = f'/sys/class/drm/card{card_num}/device/tile0/gt0/gtidle/idle_residency_ms'
                    if os.path.exists(xe_idle_path):
                        mem_info = self._get_xe_gpu_memory(card_num)
                        if mem_info is not None:
                            used_bytes, total_bytes = mem_info
                            info['memory_used'] = used_bytes // (1024 * 1024)  # Convert to MB
                            info['memory_total'] = total_bytes // (1024 * 1024)  # Convert to MB
                            if total_bytes > 0:
                                info['memory_util'] = int((used_bytes / total_bytes) * 100)
                            break
            
            # Legacy code kept for reference (commented out)
            # Try intel_gpu_top for utilization (if available)
            result = subprocess.run(['which', 'intel_gpu_top'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # intel_gpu_top requires sudo and continuous monitoring
                # We'll try to parse /sys/kernel/debug/dri/0/i915_gem_objects instead
                gem_path = '/sys/kernel/debug/dri/0/i915_gem_objects'
                if os.path.exists(gem_path):
                    try:
                        with open(gem_path, 'r') as f:
                            content = f.read()
                            # Parse memory usage from gem objects
                            match = re.search(r'Total (\d+) objects, (\d+) bytes', content)
                            if match:
                                info['memory_used'] = int(match.group(2)) / (1024**2)  # Convert to MB
                    except PermissionError:
                        pass
            
            # Try to read from i915 PMU counters
            i915_path = '/sys/class/drm/card0/device/drm/card0'
            if os.path.exists(i915_path):
                # Look for engine utilization
                engine_path = f'{i915_path}/engine'
                if os.path.exists(engine_path):
                    # This would require parsing PMU events which is complex
                    # For now, we'll set a placeholder
                    pass
            
        except Exception as e:
            print(f"Error getting Intel GPU info: {e}")
        
        return info
    
    def get_nvidia_info(self, device_id: int = 0) -> Dict:
        """Get NVIDIA GPU information using pynvml or sysfs fallback."""
        # Try pynvml first
        if self.nvidia_available:
            try:
                handle = self.pynvml.nvmlDeviceGetHandleByIndex(device_id)
                
                # Get utilization
                utilization = self.pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                # Get memory info
                memory = self.pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                # Get temperature
                temperature = self.pynvml.nvmlDeviceGetTemperature(
                    handle, self.pynvml.NVML_TEMPERATURE_GPU)
                
                # Get power
                try:
                    power = self.pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W
                except:
                    power = 0
                
                # Get clock speeds
                try:
                    gpu_clock = self.pynvml.nvmlDeviceGetClockInfo(
                        handle, self.pynvml.NVML_CLOCK_GRAPHICS)
                    mem_clock = self.pynvml.nvmlDeviceGetClockInfo(
                        handle, self.pynvml.NVML_CLOCK_MEM)
                except:
                    gpu_clock = 0
                    mem_clock = 0
                
                # Get name
                name = self.pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                
                return {
                    'name': name,
                    'gpu_util': utilization.gpu,
                    'memory_util': utilization.memory,
                    'memory_used': memory.used / (1024**2),  # MB
                    'memory_total': memory.total / (1024**2),  # MB
                    'temperature': temperature,
                    'power': power,
                    'gpu_clock': gpu_clock,
                    'memory_clock': mem_clock
                }
            except Exception as e:
                print(f"pynvml failed: {e}, trying sysfs fallback")
        
        # Fallback to sysfs for basic info
        return self._get_nvidia_sysfs_info()
    
    def _get_nvidia_sysfs_info(self) -> Dict:
        """Get basic NVIDIA GPU info from sysfs (no driver needed)."""
        info = {
            'name': 'NVIDIA GPU',
            'gpu_util': 0,
            'memory_util': 0,
            'memory_used': 0,
            'memory_total': 0,
            'temperature': 0,
            'power': 0,
            'gpu_clock': 0,
            'memory_clock': 0
        }
        
        try:
            # Find NVIDIA card in sysfs
            for card_num in range(10):
                vendor_path = f'/sys/class/drm/card{card_num}/device/vendor'
                if os.path.exists(vendor_path):
                    with open(vendor_path, 'r') as f:
                        vendor_id = f.read().strip()
                        if vendor_id in ['0x10de', '10de']:
                            # Found NVIDIA GPU
                            device_path = f'/sys/class/drm/card{card_num}/device'
                            
                            # Get device name from PCI ID
                            device_id_path = f'{device_path}/device'
                            if os.path.exists(device_id_path):
                                with open(device_id_path, 'r') as f:
                                    device_id = f.read().strip()
                                    info['name'] = f'NVIDIA GPU ({device_id})'
                            
                            # Try to get GPU name from lspci
                            try:
                                pci_addr_path = f'{device_path}/uevent'
                                if os.path.exists(pci_addr_path):
                                    with open(pci_addr_path, 'r') as f:
                                        for line in f:
                                            if line.startswith('PCI_SLOT_NAME='):
                                                pci_addr = line.split('=')[1].strip()
                                                result = subprocess.run(['lspci', '-s', pci_addr],
                                                                      capture_output=True, text=True)
                                                if result.returncode == 0:
                                                    # Extract GPU name from lspci output
                                                    match = re.search(r'NVIDIA.*?\[(.*?)\]', result.stdout)
                                                    if match:
                                                        info['name'] = f'NVIDIA {match.group(1)}'
                            except:
                                pass
                            
                            # Note: Without NVIDIA driver, we can't get utilization, memory, etc.
                            # But we can at least show the GPU exists
                            break
                            
        except Exception as e:
            print(f"Error getting NVIDIA sysfs info: {e}")
        
        return info
    
    def get_amd_info(self) -> Dict:
        """Get AMD GPU information using rocm-smi."""
        try:
            result = subprocess.run(['rocm-smi', '--showuse', '--showmeminfo', 'vram',
                                   '--showtemp', '--showpower'],
                                  capture_output=True, text=True, timeout=2)
            
            if result.returncode == 0:
                # Parse rocm-smi output
                output = result.stdout
                info = {
                    'name': 'AMD GPU',
                    'gpu_util': 0,
                    'memory_used': 0,
                    'memory_total': 0,
                    'temperature': 0,
                    'power': 0
                }
                
                # Basic parsing (rocm-smi output varies)
                for line in output.split('\n'):
                    if 'GPU use' in line:
                        match = re.search(r'(\d+)%', line)
                        if match:
                            info['gpu_util'] = int(match.group(1))
                    elif 'Temperature' in line:
                        match = re.search(r'(\d+\.?\d*)', line)
                        if match:
                            info['temperature'] = float(match.group(1))
                
                return info
        except Exception as e:
            print(f"Error getting AMD GPU info: {e}")
        
        return {}
    
    def get_all_info(self) -> Dict:
        """Get GPU information for all available GPUs."""
        gpus = []
        
        if self.intel_available:
            gpu_info = self.get_intel_info()
            if gpu_info:
                gpu_info['id'] = 0
                gpu_info['type'] = 'intel'
                gpus.append(gpu_info)
        
        # For NVIDIA, try even if nvidia_available is False (will use sysfs fallback)
        if self.gpu_type == 'nvidia':
            gpu_info = self.get_nvidia_info(0)
            if gpu_info:
                gpu_info['id'] = 0
                gpu_info['type'] = 'nvidia'
                gpus.append(gpu_info)
        elif self.nvidia_available:
            # If nvidia_available is True, enumerate all devices
            for i in range(self.device_count):
                gpu_info = self.get_nvidia_info(i)
                if gpu_info:
                    gpu_info['id'] = i
                    gpu_info['type'] = 'nvidia'
                    gpus.append(gpu_info)
        
        if self.amd_available:
            gpu_info = self.get_amd_info()
            if gpu_info:
                gpu_info['id'] = 0
                gpu_info['type'] = 'amd'
                gpus.append(gpu_info)
        
        return {
            'gpu_type': self.gpu_type,
            'available': len(gpus) > 0,
            'gpus': gpus
        }
    
    def __del__(self):
        """Cleanup NVML."""
        if self.nvidia_available:
            try:
                self.pynvml.nvmlShutdown()
            except:
                pass


if __name__ == '__main__':
    # Test the monitor
    monitor = GPUMonitor()
    import json
    print(json.dumps(monitor.get_all_info(), indent=2))
