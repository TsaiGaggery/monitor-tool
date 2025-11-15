#!/usr/bin/env python3
"""Disk monitoring module for tracking I/O statistics and usage."""

import psutil
import time
from typing import Dict, List, Optional


class DiskMonitor:
    """Monitor disk I/O statistics, usage, and performance."""
    
    def __init__(self):
        """Initialize disk monitor."""
        self.last_counters = {}
        self.last_time = time.time()
        self._initialize_counters()
    
    def _initialize_counters(self):
        """Initialize counters for speed calculation."""
        try:
            counters = psutil.disk_io_counters(perdisk=True)
            self.last_counters = {
                disk: {
                    'read_bytes': stats.read_bytes,
                    'write_bytes': stats.write_bytes,
                    'read_count': stats.read_count,
                    'write_count': stats.write_count,
                }
                for disk, stats in counters.items()
            }
            self.last_time = time.time()
        except Exception as e:
            print(f"Error initializing disk counters: {e}")
            self.last_counters = {}
    
    def get_disks(self, exclude_virtual: bool = True) -> List[str]:
        """Get list of available disk devices.
        
        Args:
            exclude_virtual: Filter out virtual devices (loop, ram, etc.)
            
        Returns:
            List of disk names (e.g., ['sda', 'nvme0n1'])
        """
        try:
            counters = psutil.disk_io_counters(perdisk=True)
            disks = list(counters.keys())
            
            if exclude_virtual:
                # Filter out virtual/loopback devices
                virtual_prefixes = ('loop', 'ram', 'dm-', 'sr', 'zram')
                disks = [d for d in disks if not d.startswith(virtual_prefixes)]
            
            return sorted(disks)
        except Exception as e:
            print(f"Error getting disk list: {e}")
            return []
    
    def get_partitions(self) -> List[Dict]:
        """Get list of disk partitions with mount points.
        
        Returns:
            List of partition info dicts
        """
        try:
            partitions = psutil.disk_partitions(all=False)
            return [
                {
                    'device': p.device,
                    'mountpoint': p.mountpoint,
                    'fstype': p.fstype,
                    'opts': p.opts,
                }
                for p in partitions
            ]
        except Exception as e:
            print(f"Error getting partitions: {e}")
            return []
    
    def get_partition_usage(self, path: str = '/') -> Dict:
        """Get usage statistics for a partition.
        
        Args:
            path: Mount point path (default: '/')
            
        Returns:
            Dict with usage information
        """
        try:
            usage = psutil.disk_usage(path)
            return {
                'total': usage.total / (1024**3),  # GB
                'used': usage.used / (1024**3),
                'free': usage.free / (1024**3),
                'percent': usage.percent,
                'path': path,
            }
        except Exception as e:
            print(f"Error getting partition usage for {path}: {e}")
            return {}
    
    def get_all_partition_usage(self) -> List[Dict]:
        """Get usage for all mounted partitions.
        
        Returns:
            List of usage dicts for each partition
        """
        partitions = self.get_partitions()
        usage_list = []
        
        for partition in partitions:
            mountpoint = partition['mountpoint']
            usage = self.get_partition_usage(mountpoint)
            if usage:
                usage['device'] = partition['device']
                usage['fstype'] = partition['fstype']
                usage_list.append(usage)
        
        return usage_list
    
    def get_io_stats(self, disk: Optional[str] = None) -> Dict:
        """Get I/O statistics and calculate speeds.
        
        Args:
            disk: Specific disk name, or None for total
            
        Returns:
            Dict containing I/O statistics and speeds
        """
        try:
            current_time = time.time()
            time_delta = current_time - self.last_time
            
            if time_delta < 0.1:  # Avoid division by very small numbers
                time_delta = 0.1
            
            if disk:
                # Get specific disk
                counters = psutil.disk_io_counters(perdisk=True)
                if disk not in counters:
                    return {}
                current = counters[disk]
            else:
                # Get total for all disks
                current = psutil.disk_io_counters(perdisk=False)
                disk = 'total'
            
            # Calculate speeds
            last = self.last_counters.get(disk, {
                'read_bytes': current.read_bytes,
                'write_bytes': current.write_bytes,
                'read_count': current.read_count,
                'write_count': current.write_count,
            })
            
            read_bytes_delta = current.read_bytes - last.get('read_bytes', current.read_bytes)
            write_bytes_delta = current.write_bytes - last.get('write_bytes', current.write_bytes)
            read_count_delta = current.read_count - last.get('read_count', current.read_count)
            write_count_delta = current.write_count - last.get('write_count', current.write_count)
            
            # Calculate speeds
            read_speed = read_bytes_delta / time_delta  # bytes/sec
            write_speed = write_bytes_delta / time_delta  # bytes/sec
            read_iops = read_count_delta / time_delta  # operations/sec
            write_iops = write_count_delta / time_delta  # operations/sec
            
            # Update last counters
            self.last_counters[disk] = {
                'read_bytes': current.read_bytes,
                'write_bytes': current.write_bytes,
                'read_count': current.read_count,
                'write_count': current.write_count,
            }
            self.last_time = current_time
            
            result = {
                'read_bytes': current.read_bytes,
                'write_bytes': current.write_bytes,
                'read_count': current.read_count,
                'write_count': current.write_count,
                'read_speed': read_speed,  # bytes/sec
                'write_speed': write_speed,  # bytes/sec
                'read_speed_mb': read_speed / (1024 * 1024),  # MB/s
                'write_speed_mb': write_speed / (1024 * 1024),  # MB/s
                'read_iops': read_iops,
                'write_iops': write_iops,
            }
            
            # Add time info if available
            if hasattr(current, 'read_time'):
                result['read_time'] = current.read_time
                result['write_time'] = current.write_time
            
            if hasattr(current, 'busy_time'):
                result['busy_time'] = current.busy_time
            
            return result
            
        except Exception as e:
            print(f"Error getting I/O stats: {e}")
            return {}
    
    def get_io_utilization(self, disk: Optional[str] = None) -> float:
        """Calculate I/O utilization percentage.
        
        Args:
            disk: Specific disk or None for total
            
        Returns:
            I/O utilization percentage (0-100)
        """
        try:
            stats = self.get_io_stats(disk)
            if not stats or 'busy_time' not in stats:
                return 0.0
            
            # Calculate utilization based on busy time
            # This is a simplified calculation
            busy_time = stats.get('busy_time', 0)
            if busy_time > 0:
                # Estimate utilization (this varies by system)
                return min(100.0, (busy_time / 1000.0) % 100)
            return 0.0
        except Exception:
            return 0.0
    
    def get_all_info(self, disk: Optional[str] = None) -> Dict:
        """Get comprehensive disk information.
        
        Args:
            disk: Specific disk or None for total
            
        Returns:
            Dict with all disk information
        """
        return {
            'disks': self.get_disks(),
            'partitions': self.get_partitions(),
            'partition_usage': self.get_all_partition_usage(),
            'io_stats': self.get_io_stats(disk),
        }


if __name__ == '__main__':
    # Test the monitor
    monitor = DiskMonitor()
    import json
    time.sleep(1)  # Wait for initial sampling
    print(json.dumps(monitor.get_all_info(), indent=2))
