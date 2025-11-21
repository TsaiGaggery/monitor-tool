"""
Process monitoring module for tracking top CPU/memory consuming processes.
"""

import psutil
import time
from typing import List, Dict, Optional, Union
from datetime import datetime
from dataclasses import dataclass

@dataclass
class ProcessInfo:
    """Data class for process information."""
    pid: int
    name: str
    cpu_percent: float
    memory_rss: int
    memory_vms: int
    cmdline: str
    status: str
    num_threads: int
    create_time: float
    timestamp: datetime

class ProcessMonitor:
    """
    Monitor top processes by CPU and memory usage.
    
    Features:
    - Real-time process tracking
    - Configurable number of processes
    - Multiple sort modes (CPU, memory, combined)
    - Thread-safe operation
    - Mode support: local, SSH, ADB
    """
    
    def __init__(self, config: dict, mode: str = 'local', 
                 ssh_client=None, adb_device=None):
        """
        Initialize ProcessMonitor.
        
        Args:
            config: Configuration dictionary from tier2.process_monitoring
            mode: Operation mode ('local', 'ssh', 'adb')
            ssh_client: SSH client for remote monitoring (optional)
            adb_device: ADB device for Android monitoring (optional)
        """
        self.enabled = config.get('enabled', True)
        self.update_interval = config.get('update_interval', 1000) / 1000.0
        self.process_count = config.get('process_count', 5)
        self.sort_by = config.get('sort_by', 'cpu')
        self.cmdline_max_length = config.get('cmdline_max_length', 50)
        self.thresholds = config.get('thresholds', {})
        
        self.mode = mode
        self.ssh_client = ssh_client
        self.adb_device = adb_device
        
        self._last_update = 0
        self._process_cache: List[ProcessInfo] = []
    
    def get_top_processes(self) -> List[ProcessInfo]:
        """
        Get top processes sorted by configured metric.
        
        Returns:
            List of ProcessInfo objects for top processes
        """
        current_time = time.time()
        if current_time - self._last_update < self.update_interval:
            return self._process_cache
        
        if self.mode == 'local':
            processes = self._get_local_processes()
        elif self.mode == 'ssh':
            processes = self._get_ssh_processes()
        elif self.mode == 'adb':
            processes = self._get_adb_processes()
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")
        
        # Sort and filter
        processes = self._sort_processes(processes)[:self.process_count]
        
        self._process_cache = processes
        self._last_update = current_time
        
        return processes
    
    def _get_local_processes(self) -> List[ProcessInfo]:
        """Get processes from local system using psutil."""
        processes = []
        now = datetime.now()
        
        # Iterate over all running processes
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 
                                         'memory_info', 'cmdline', 
                                         'status', 'num_threads', 'create_time']):
            try:
                info = proc.info
                cmdline = ' '.join(info['cmdline'] or [])
                if len(cmdline) > self.cmdline_max_length:
                    cmdline = cmdline[:self.cmdline_max_length] + '...'
                
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    cpu_percent=info['cpu_percent'] or 0.0,
                    memory_rss=info['memory_info'].rss,
                    memory_vms=info['memory_info'].vms,
                    cmdline=cmdline,
                    status=info['status'],
                    num_threads=info['num_threads'] or 0,
                    create_time=info['create_time'] or 0.0,
                    timestamp=now
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return processes
    
    def _get_ssh_processes(self) -> List[ProcessInfo]:
        """Get processes from remote Linux system via SSH."""
        # Placeholder for TASK-004
        return []
    
    def _get_adb_processes(self) -> List[ProcessInfo]:
        """Get processes from Android device via ADB."""
        # Placeholder for TASK-005
        return []
        
    def _sort_processes(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Sort processes based on configuration."""
        if self.sort_by == 'cpu':
            return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)
        elif self.sort_by == 'memory':
            return sorted(processes, key=lambda p: p.memory_rss, reverse=True)
        elif self.sort_by == 'combined':
            # Simple combined score: cpu% + (mem_rss / 100MB)
            return sorted(processes, 
                          key=lambda p: p.cpu_percent + (p.memory_rss / (100 * 1024 * 1024)), 
                          reverse=True)
        else:
            return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)

    def get_severity(self, process: ProcessInfo) -> str:
        """
        Determine severity level for a process based on thresholds.
        
        Returns:
            'critical', 'warning', or 'normal'
        """
        cpu_crit = self.thresholds.get('cpu_critical', 80.0)
        cpu_warn = self.thresholds.get('cpu_warning', 50.0)
        mem_crit = self.thresholds.get('memory_critical', 2 * 1024 * 1024 * 1024)
        mem_warn = self.thresholds.get('memory_warning', 1 * 1024 * 1024 * 1024)
        
        if process.cpu_percent >= cpu_crit or process.memory_rss >= mem_crit:
            return 'critical'
        elif process.cpu_percent >= cpu_warn or process.memory_rss >= mem_warn:
            return 'warning'
        else:
            return 'normal'
