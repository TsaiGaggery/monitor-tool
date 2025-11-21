#!/usr/bin/env python3
"""ADB Frequency controller for Android devices."""

import subprocess
from typing import List, Optional


class ADBFrequencyController:
    """Control CPU/GPU frequencies on Android device via ADB."""
    
    def __init__(self, device_id: str):
        """Initialize ADB frequency controller.
        
        Args:
            device_id: ADB device ID (e.g., "192.168.1.68:5555")
        """
        self.device_id = device_id
        self.script_path = "/data/local/tmp/android_freq_controller.sh"
        self.has_root = False  # Will be checked
        self.is_available = False  # Will be set after verification
        self.cpu_count = 0
        
        # Check if frequency control is available (root + script)
        self._verify_availability()
    
    def _verify_availability(self):
        """Verify that frequency control is available on device.
        
        Checks:
        1. Root access (su 0)
        2. Script exists and is executable
        3. Can read CPU frequency info
        """
        try:
            # Quick test: try to get CPU governor (requires root)
            # Use short timeout (2s) for fast failure
            result = self._run_adb_command("get_cpu_governor", timeout=2)
            
            if result and result not in ["", "ERROR:", "FAILED:"]:
                # Success! We have root and the script works
                self.has_root = True
                self.is_available = True
                
                # Now get full device info (with normal timeout)
                self._init_device_info()
            else:
                # No root or script not working
                self.has_root = False
                self.is_available = False
                print("⚠️  Android frequency control unavailable (no root or script error)")
                
        except Exception as e:
            self.has_root = False
            self.is_available = False
            print(f"⚠️  Android frequency control unavailable: {e}")
    
    def _init_device_info(self):
        """Get device information like CPU count (called after verification)."""
        result = self._run_adb_command("get_all", timeout=2)
        if result:
            for line in result.split('\n'):
                if line.startswith('CPU Count:'):
                    self.cpu_count = int(line.split(':')[1].strip())
    
    def _run_adb_command(self, *args, timeout: int = 5) -> Optional[str]:
        """Run android_freq_controller.sh command via ADB.
        
        Args:
            *args: Command and arguments to pass to the script
            timeout: Command timeout in seconds (default: 5)
            
        Returns:
            Command output or None if failed
        """
        if not self.is_available and args[0] != "get_cpu_governor":
            # If already verified as unavailable, don't waste time
            return None
            
        try:
            # Build ADB shell command
            script_cmd = f"su 0 sh {self.script_path} {' '.join(args)}"
            
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell", script_cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                # Only print error during verification, not after
                if args[0] == "get_cpu_governor":
                    pass  # Silent fail during verification
                else:
                    print(f"⚠️  ADB command failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print(f"⚠️  ADB command timeout (>{timeout}s)")
            return None
        except Exception as e:
            if args[0] != "get_cpu_governor":
                print(f"⚠️  Error running ADB command: {e}")
            return None
    
    def get_available_cpu_governors(self) -> List[str]:
        """Get list of available CPU governors."""
        if not self.is_available:
            return []
            
        result = self._run_adb_command("get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Available Governors:'):
                    governors = line.split(':', 1)[1].strip()
                    return governors.split()
        return []
    
    def get_current_cpu_governor(self, cpu_id: int = 0) -> Optional[str]:
        """Get current CPU governor."""
        if not self.is_available:
            return None
            
        result = self._run_adb_command("get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Current Governor:'):
                    return line.split(':', 1)[1].strip()
        return None
    
    def set_cpu_governor(self, governor: str, cpu_id: Optional[int] = None) -> bool:
        """Set CPU governor for all CPUs.
        
        Args:
            governor: Governor name (e.g., "performance", "powersave")
            cpu_id: Ignored (always sets all CPUs on Android)
            
        Returns:
            True if successful
        """
        if not self.is_available:
            return False
            
        result = self._run_adb_command("set_cpu_governor", governor)
        return result is not None and result.startswith("OK:")
    
    def get_available_cpu_epp(self) -> List[str]:
        """Get list of available CPU EPP preferences."""
        if not self.is_available:
            return []
            
        result = self._run_adb_command("get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Available EPP:'):
                    epp = line.split(':', 1)[1].strip()
                    if epp != "N/A":
                        return epp.split()
        return []
    
    def get_current_cpu_epp(self, cpu_id: int = 0) -> Optional[str]:
        """Get current CPU EPP preference."""
        if not self.is_available:
            return None
            
        result = self._run_adb_command("get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Current EPP:'):
                    epp = line.split(':', 1)[1].strip()
                    return epp if epp != "N/A" else None
        return None
    
    def set_cpu_epp(self, epp: str, cpu_id: Optional[int] = None) -> bool:
        """Set CPU EPP preference for all CPUs.
        
        Args:
            epp: EPP name (e.g., "performance", "balance_performance", "default")
            cpu_id: Ignored (always sets all CPUs)
            
        Returns:
            True if successful
        """
        if not self.is_available:
            return False
            
        result = self._run_adb_command("set_cpu_epp", epp)
        return result is not None and result.startswith("OK:")

    def get_cpu_freq_range(self) -> dict:
        """Get min/max frequency range for CPUs."""
        if not self.is_available:
            return {
                'hardware_min': 0,
                'hardware_max': 5000,
                'scaling_min': 0,
                'scaling_max': 5000
            }
            
        result = self._run_adb_command("get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('Frequency Range:'):
                    # Parse: "Frequency Range: HW_MIN:400 HW_MAX:4400 SCALING_MIN:400 SCALING_MAX:4400"
                    parts = line.split(':', 1)[1].strip().split()
                    freq_dict = {}
                    for part in parts:
                        key, val = part.split(':')
                        freq_dict[key.lower()] = int(val)
                    
                    return {
                        'hardware_min': freq_dict.get('hw_min', 0),
                        'hardware_max': freq_dict.get('hw_max', 5000),
                        'scaling_min': freq_dict.get('scaling_min', 0),
                        'scaling_max': freq_dict.get('scaling_max', 5000)
                    }
        
        return {
            'hardware_min': 0,
            'hardware_max': 5000,
            'scaling_min': 0,
            'scaling_max': 5000
        }
    
    def set_cpu_freq_range(self, min_freq: int, max_freq: int) -> bool:
        """Set CPU frequency range (MHz).
        
        Args:
            min_freq: Minimum frequency in MHz
            max_freq: Maximum frequency in MHz
            
        Returns:
            True if successful
        """
        if not self.is_available:
            return False
            
        result = self._run_adb_command("set_cpu_freq_range", str(min_freq), str(max_freq))
        return result is not None and result.startswith("OK:")
    
    def set_cpu_performance_mode(self) -> bool:
        """Set CPU to performance mode."""
        return self.set_cpu_governor("performance")
    
    def set_cpu_powersave_mode(self) -> bool:
        """Set CPU to powersave mode (Governor=powersave, EPP=balance_performance)."""
        # 1. Set governor to powersave
        gov_success = self.set_cpu_governor("powersave")
        
        # 2. Set EPP to balance_performance (restore "balanced" behavior)
        if gov_success:
            # Try to set EPP to balance_performance, fallback to default or power if not available
            target_epp = "balance_performance"
            available_epp = self.get_available_cpu_epp()
            
            if target_epp not in available_epp:
                if "default" in available_epp:
                    target_epp = "default"
                elif "balance_power" in available_epp:
                    target_epp = "balance_power"
            
            self.set_cpu_epp(target_epp)
            
        return gov_success
    
    def get_gpu_freq_range(self) -> Optional[dict]:
        """Get GPU frequency range."""
        if not self.is_available:
            return None
            
        result = self._run_adb_command("get_all")
        if result:
            for line in result.split('\n'):
                if line.startswith('GPU Frequency:'):
                    # Parse: "GPU Frequency: TYPE:i915 HW_MIN:100 HW_MAX:1200 SCALING_MIN:100 SCALING_MAX:1200 CURRENT:450"
                    parts = line.split(':', 1)[1].strip().split()
                    freq_dict = {}
                    for part in parts:
                        key, val = part.split(':')
                        freq_dict[key.lower()] = val if key == 'TYPE' else int(val)
                    
                    if freq_dict:
                        return {
                            'driver': freq_dict.get('type', 'unknown'),
                            'hardware_min': freq_dict.get('hw_min', 0),
                            'hardware_max': freq_dict.get('hw_max', 2000),
                            'scaling_min': freq_dict.get('scaling_min', 0),
                            'scaling_max': freq_dict.get('scaling_max', 2000),
                            'current': freq_dict.get('current', 0)
                        }
        
        return None
    
    def set_gpu_freq_range(self, min_freq: int, max_freq: int) -> bool:
        """Set GPU frequency range (MHz).
        
        Args:
            min_freq: Minimum frequency in MHz
            max_freq: Maximum frequency in MHz
            
        Returns:
            True if successful
        """
        if not self.is_available:
            return False
            
        result = self._run_adb_command("set_gpu_freq_range", str(min_freq), str(max_freq))
        return result is not None and result.startswith("OK:")
    
    def get_gpu_driver_type(self) -> str:
        """Get GPU driver type (i915 or xe)."""
        gpu_info = self.get_gpu_freq_range()
        if gpu_info:
            return gpu_info.get('driver', 'unknown')
        return 'unknown'
