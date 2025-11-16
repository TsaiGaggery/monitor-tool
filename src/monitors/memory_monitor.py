#!/usr/bin/env python3
"""Memory monitoring module for RAM and swap usage."""

import psutil
import subprocess
from typing import Dict, Optional


class MemoryMonitor:
    """Monitor system memory and swap usage."""
    
    def __init__(self):
        self._memory_speed = None
        self._get_memory_speed()
    
    def _get_memory_speed(self) -> Optional[int]:
        """Get RAM speed from dmidecode (requires sudo or setuid)."""
        if self._memory_speed is not None:
            return self._memory_speed
            
        try:
            # Try dmidecode to get memory speed
            result = subprocess.run(
                ['dmidecode', '-t', 'memory'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                # Look for "Configured Memory Speed" or "Speed" line
                for line in result.stdout.split('\n'):
                    if 'Configured Memory Speed:' in line:
                        # Extract speed (e.g., "2667 MT/s" -> 2667)
                        parts = line.split(':')[1].strip().split()
                        if parts and parts[0].isdigit():
                            self._memory_speed = int(parts[0])
                            return self._memory_speed
                    elif 'Speed:' in line and 'MT/s' in line:
                        # Fallback to Speed if Configured not found
                        if self._memory_speed is None:
                            parts = line.split(':')[1].strip().split()
                            if parts and parts[0].isdigit():
                                self._memory_speed = int(parts[0])
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return self._memory_speed
    
    def get_memory_info(self) -> Dict:
        """Get RAM usage information."""
        mem = psutil.virtual_memory()
        return {
            'total': mem.total / (1024**3),  # GB
            'available': mem.available / (1024**3),
            'used': mem.used / (1024**3),
            'free': mem.free / (1024**3),
            'percent': mem.percent,
            'buffers': mem.buffers / (1024**3) if hasattr(mem, 'buffers') else 0,
            'cached': mem.cached / (1024**3) if hasattr(mem, 'cached') else 0
        }
    
    def get_swap_info(self) -> Dict:
        """Get swap usage information."""
        swap = psutil.swap_memory()
        return {
            'total': swap.total / (1024**3),  # GB
            'used': swap.used / (1024**3),
            'free': swap.free / (1024**3),
            'percent': swap.percent
        }
    
    def get_all_info(self) -> Dict:
        """Get all memory information."""
        info = {
            'memory': self.get_memory_info(),
            'swap': self.get_swap_info()
        }
        
        # Add memory speed if available
        speed = self._get_memory_speed()
        if speed:
            info['memory']['speed'] = speed  # MT/s
            
        return info


if __name__ == '__main__':
    # Test the monitor
    monitor = MemoryMonitor()
    import json
    print(json.dumps(monitor.get_all_info(), indent=2))
