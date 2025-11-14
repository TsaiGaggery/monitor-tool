#!/usr/bin/env python3
"""Memory monitoring module for RAM and swap usage."""

import psutil
from typing import Dict


class MemoryMonitor:
    """Monitor system memory and swap usage."""
    
    def __init__(self):
        pass
    
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
        return {
            'memory': self.get_memory_info(),
            'swap': self.get_swap_info()
        }


if __name__ == '__main__':
    # Test the monitor
    monitor = MemoryMonitor()
    import json
    print(json.dumps(monitor.get_all_info(), indent=2))
