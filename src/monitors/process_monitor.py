"""
Process monitoring module for tracking top CPU/memory consuming processes.
"""

import psutil
import time
import subprocess
import threading
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
        self._lock = threading.Lock()
        
        # Cache for SSH process calculation (pid -> {utime, stime, timestamp})
        self._prev_ssh_proc_stats = {}
        self._prev_ssh_total_ticks = 0
    
    def get_top_processes(self) -> List[ProcessInfo]:
        """
        Get top processes sorted by configured metric.
        
        Returns:
            List of ProcessInfo objects for top processes
        """
        with self._lock:
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
        """Get processes from remote Linux system via SSH using /proc stats for accurate CPU."""
        if not self.ssh_client:
            return []
            
        processes = []
        now = datetime.now()
        
        try:
            # Fetch all necessary data in one command to minimize latency
            # 1. Page size (for memory calculation)
            # 2. CPU count (for normalization)
            # 3. Total CPU stats (for time delta)
            # 4. Process stats (for per-process CPU/mem)
            cmd = "getconf PAGESIZE; grep -c '^cpu[0-9]' /proc/stat; cat /proc/stat | head -n 1; cat /proc/[0-9]*/stat 2>/dev/null"
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            
            lines = stdout.readlines()
            if len(lines) < 4:
                return []
                
            # Parse header info
            try:
                page_size = int(lines[0].strip())
                cpu_count = int(lines[1].strip())
                
                cpu_line = lines[2].split()
                if cpu_line[0] == 'cpu':
                    # user nice sys idle iowait irq softirq steal
                    total_ticks = sum(int(x) for x in cpu_line[1:])
                else:
                    total_ticks = 0
            except ValueError:
                return []
                
            # Parse process stats
            curr_proc_stats = {}
            
            for line in lines[3:]:
                try:
                    # Handle 'comm' which can contain spaces and parentheses
                    rparen_idx = line.rfind(')')
                    if rparen_idx == -1: continue
                    
                    parts_after = line[rparen_idx+2:].split()
                    # pid is before first (
                    lparen_idx = line.find('(')
                    pid = int(line[:lparen_idx])
                    comm = line[lparen_idx+1:rparen_idx]
                    
                    # Fields after comm (0-indexed in parts_after):
                    # 0: state (3rd field)
                    # ...
                    # 11: utime (14th field)
                    # 12: stime (15th field)
                    # 17: num_threads (20th field)
                    # 20: vsize (23rd field)
                    # 21: rss (24th field) - in pages
                    
                    state = parts_after[0]
                    utime = int(parts_after[11])
                    stime = int(parts_after[12])
                    num_threads = int(parts_after[17])
                    vsize = int(parts_after[20])
                    rss_pages = int(parts_after[21])
                    
                    curr_proc_stats[pid] = {
                        'name': comm,
                        'state': state,
                        'utime': utime,
                        'stime': stime,
                        'total_time': utime + stime,
                        'threads': num_threads,
                        'vsize': vsize,
                        'rss': rss_pages * page_size
                    }
                except (ValueError, IndexError):
                    continue
            
            # Calculate CPU usage and create ProcessInfo objects
            if hasattr(self, '_prev_ssh_total_ticks') and self._prev_ssh_total_ticks:
                total_delta = total_ticks - self._prev_ssh_total_ticks
                
                if total_delta > 0:
                    for pid, curr in curr_proc_stats.items():
                        cpu_percent = 0.0
                        
                        # Calculate CPU % if we have previous stats for this PID
                        if pid in self._prev_ssh_proc_stats:
                            prev = self._prev_ssh_proc_stats[pid]
                            proc_delta = curr['total_time'] - prev['total_time']
                            
                            # Normalize to 100% per core (psutil style)
                            # total_delta is sum of all cores, so we multiply by cpu_count
                            cpu_percent = (proc_delta * 100.0 * cpu_count) / total_delta
                            cpu_percent = max(0.0, cpu_percent) # Clamp negative
                        
                        # Create ProcessInfo
                        # Note: cmdline is missing here, we'll fetch it for top processes later
                        proc = ProcessInfo(
                            pid=pid,
                            name=curr['name'],
                            cpu_percent=cpu_percent,
                            memory_rss=curr['rss'],
                            memory_vms=curr['vsize'],
                            cmdline=curr['name'], # Placeholder
                            status=curr['state'],
                            num_threads=curr['threads'],
                            create_time=0.0,
                            timestamp=now
                        )
                        processes.append(proc)
            
            # Update cache
            self._prev_ssh_proc_stats = curr_proc_stats
            self._prev_ssh_total_ticks = total_ticks
            
            # If first run (no processes calculated), return empty or raw list with 0 CPU
            if not processes and curr_proc_stats:
                 # Return processes with 0 CPU for first run to populate list
                 for pid, curr in curr_proc_stats.items():
                    processes.append(ProcessInfo(
                        pid=pid,
                        name=curr['name'],
                        cpu_percent=0.0,
                        memory_rss=curr['rss'],
                        memory_vms=curr['vsize'],
                        cmdline=curr['name'],
                        status=curr['state'],
                        num_threads=curr['threads'],
                        create_time=0.0,
                        timestamp=now
                    ))

            # Sort and take top N
            # We do this here because we need to fetch cmdline for them
            top_processes = self._sort_processes(processes)[:self.process_count]
            
            # Fetch cmdline for top processes
            if top_processes:
                pids = [str(p.pid) for p in top_processes]
                # Use ps to get args for these PIDs
                # ps -p 123,456 -o pid,args
                cmd_args = f"ps -p {','.join(pids)} -o pid,args --no-headers"
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd_args)
                
                arg_map = {}
                for line in stdout.readlines():
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        arg_map[int(parts[0])] = parts[1]
                
                # Update cmdline in top processes
                for p in top_processes:
                    if p.pid in arg_map:
                        p.cmdline = arg_map[p.pid]
            
            return top_processes
                    
        except Exception as e:
            print(f"Error fetching remote processes: {e}")
            return []

    def _get_adb_processes(self) -> List[ProcessInfo]:
        """Get processes from Android device via ADB."""
        if not self.adb_device:
            return []
            
        processes = []
        now = datetime.now()
        
        try:
            # Run top command on Android
            # -b: batch mode
            # -n 1: one iteration
            # -s 9: sort by CPU (usually column 9, but varies)
            # -m 15: max 15 processes (optimization)
            cmd = ["adb", "-s", self.adb_device, "shell", "top", "-b", "-n", "1", "-m", str(self.process_count + 5)]
            
            # If sorting by memory, try to adjust (though top flags vary wildly on Android)
            if self.sort_by == 'memory':
                # Some tops support -o MEM or -s 10
                pass 
                
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                return []
                
            lines = result.stdout.splitlines()
            
            # Find header line to determine columns
            header_idx = -1
            col_map = {}
            
            for i, line in enumerate(lines):
                if "PID" in line and "USER" in line:
                    header_idx = i
                    # Parse headers to find column indices
                    # Example: PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ ARGS
                    headers = line.split()
                    for j, h in enumerate(headers):
                        col_map[h.replace('%', '').strip()] = j
                    break
            
            if header_idx == -1:
                return []
                
            # Process data lines
            for line in lines[header_idx+1:]:
                if not line.strip():
                    continue
                    
                try:
                    parts = line.split()
                    if len(parts) < len(col_map):
                        continue
                        
                    # Extract fields using column map
                    pid = int(parts[col_map.get('PID', 0)])
                    
                    # Name/Command is usually the last part(s)
                    # In toybox top, ARGS/COMMAND is last
                    cmd_idx = col_map.get('ARGS', col_map.get('COMMAND', -1))
                    if cmd_idx != -1:
                        cmdline = " ".join(parts[cmd_idx:])
                        name = parts[cmd_idx].split('/')[-1] # Simple name
                    else:
                        cmdline = parts[-1]
                        name = cmdline
                        
                    # CPU
                    cpu_idx = col_map.get('CPU', -1)
                    cpu_percent = float(parts[cpu_idx]) if cpu_idx != -1 else 0.0
                    
                    # Memory (RES/RSS)
                    # Values can be 100M, 2G, 400K, or just bytes
                    def parse_mem(val_str):
                        val_str = val_str.upper()
                        mult = 1
                        if val_str.endswith('G'): mult = 1024*1024*1024; val_str = val_str[:-1]
                        elif val_str.endswith('M'): mult = 1024*1024; val_str = val_str[:-1]
                        elif val_str.endswith('K'): mult = 1024; val_str = val_str[:-1]
                        return int(float(val_str) * mult)

                    res_idx = col_map.get('RES', col_map.get('RSS', -1))
                    memory_rss = parse_mem(parts[res_idx]) if res_idx != -1 else 0
                    
                    virt_idx = col_map.get('VIRT', col_map.get('VSZ', -1))
                    memory_vms = parse_mem(parts[virt_idx]) if virt_idx != -1 else 0
                    
                    status = parts[col_map.get('S', -1)] if 'S' in col_map else '?'
                    
                    proc = ProcessInfo(
                        pid=pid,
                        name=name,
                        cpu_percent=cpu_percent,
                        memory_rss=memory_rss,
                        memory_vms=memory_vms,
                        cmdline=cmdline,
                        status=status,
                        num_threads=0, # Not usually in top
                        create_time=0.0,
                        timestamp=now
                    )
                    processes.append(proc)
                    
                except (ValueError, IndexError):
                    continue
                    
        except Exception as e:
            print(f"Error fetching ADB processes: {e}")
            return []
            
        return processes
        
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
