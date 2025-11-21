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
        
        # Cache for SSH/ADB process calculation (pid -> {utime, stime, timestamp})
        self._prev_ssh_proc_stats = {}
        self._prev_ssh_total_ticks = 0
        self._prev_adb_proc_stats = {}
        self._prev_adb_total_ticks = 0
        self._adb_use_proc = None  # None=unknown, True=use /proc, False=use top
    
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
            
            # Fetch cmdlines for top processes using /proc/*/cmdline (avoids heavy ps command)
            if top_processes:
                pids = [str(p.pid) for p in top_processes]
                
                # Read /proc/PID/cmdline for each process - much lighter than ps
                # Format: echo marker, then cmdline with \0 converted to space
                cmdline_cmd = " ".join([f"echo 'PID{pid}:' && cat /proc/{pid}/cmdline 2>/dev/null | tr '\\0' ' ' && echo;" for pid in pids])
                stdin, stdout, stderr = self.ssh_client.exec_command(cmdline_cmd)
                
                # Parse output - format is: "PIDxxx:" followed by cmdline on next line
                cmdline_map = {}
                lines = stdout.read().decode('utf-8').splitlines()
                
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line.startswith('PID') and ':' in line:
                        try:
                            pid = int(line[3:line.index(':')])
                            # Next line is the cmdline
                            if i + 1 < len(lines):
                                full_cmd = lines[i + 1].strip()
                                if full_cmd:
                                    cmdline_map[pid] = full_cmd
                            i += 2  # Skip to next PID marker
                        except (ValueError, IndexError):
                            i += 1
                    else:
                        i += 1
                
                # Update cmdlines and extract proper names
                for p in top_processes:
                    if p.pid in cmdline_map:
                        full_cmd = cmdline_map[p.pid]
                        p.cmdline = full_cmd
                        
                        # Extract better name from full command
                        # For native binaries: /usr/bin/python3 -> python3
                        if full_cmd.startswith('/'):
                            p.name = full_cmd.split('/')[-1].split()[0]
            
            return top_processes
                    
        except Exception as e:
            print(f"Error fetching remote processes: {e}")
            return []

    def _get_adb_processes(self) -> List[ProcessInfo]:
        """
        Get processes from Android device via ADB using top command.
        
        Uses top for accurate real-time CPU% readings. The /proc method had issues
        with CPU% calculation accuracy and update frequency on Android.
        """
        if not self.adb_device:
            return []
        
        # Always use top for Android - it's more accurate for CPU%
        return self._get_adb_processes_top()
    
    def _get_adb_processes_proc(self) -> List[ProcessInfo]:
        """Get processes from Android using /proc filesystem (faster, more accurate)."""
        processes = []
        now = datetime.now()
        
        try:
            # Fetch all data in one command (minimize ADB latency)
            # 1. Page size, 2. CPU count, 3. Total CPU stats, 4. All process stats
            cmd = ["adb", "-s", self.adb_device, "shell", 
                   "getconf PAGESIZE; grep -c '^cpu[0-9]' /proc/stat; cat /proc/stat | head -n 1; cat /proc/[0-9]*/stat 2>/dev/null"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                return []
            
            lines = result.stdout.splitlines()
            if len(lines) < 4:
                return []
            
            # Parse header info
            try:
                page_size = int(lines[0].strip())
                cpu_count = int(lines[1].strip())
                
                cpu_line = lines[2].split()
                if cpu_line[0] == 'cpu':
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
                    if rparen_idx == -1:
                        continue
                    
                    parts_after = line[rparen_idx+2:].split()
                    lparen_idx = line.find('(')
                    pid = int(line[:lparen_idx])
                    comm = line[lparen_idx+1:rparen_idx]
                    
                    # Fields after comm (0-indexed in parts_after):
                    # 0: state, 11: utime, 12: stime, 17: num_threads, 20: vsize, 21: rss
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
            
            # Calculate CPU usage
            if self._prev_adb_total_ticks:
                total_delta = total_ticks - self._prev_adb_total_ticks
                
                if total_delta > 0:
                    for pid, curr in curr_proc_stats.items():
                        cpu_percent = 0.0
                        
                        if pid in self._prev_adb_proc_stats:
                            prev = self._prev_adb_proc_stats[pid]
                            proc_delta = curr['total_time'] - prev['total_time']
                            
                            # Normalize to 100% per core
                            cpu_percent = (proc_delta * 100.0 * cpu_count) / total_delta
                            cpu_percent = max(0.0, cpu_percent)
                        
                        proc = ProcessInfo(
                            pid=pid,
                            name=curr['name'],
                            cpu_percent=cpu_percent,
                            memory_rss=curr['rss'],
                            memory_vms=curr['vsize'],
                            cmdline=curr['name'],  # Placeholder
                            status=curr['state'],
                            num_threads=curr['threads'],
                            create_time=0.0,
                            timestamp=now
                        )
                        processes.append(proc)
            
            # Update cache
            self._prev_adb_proc_stats = curr_proc_stats
            self._prev_adb_total_ticks = total_ticks
            
            # First run - return processes with 0 CPU
            if not processes and curr_proc_stats:
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
            
            # Sort and get top N
            top_processes = self._sort_processes(processes)[:self.process_count]
            
            # Fetch full cmdlines for top processes using /proc/*/cmdline (more accurate than ps)
            if top_processes:
                pids = [str(p.pid) for p in top_processes]
                
                # Read /proc/PID/cmdline for each process to get full command with arguments
                # Format: cat /proc/PID/cmdline outputs args separated by \0, we convert to space
                cmdline_cmd = " ".join([f"echo 'PID{pid}:' && cat /proc/{pid}/cmdline 2>/dev/null | tr '\\0' ' ' && echo;" for pid in pids])
                cmdline_result = subprocess.run(
                    ["adb", "-s", self.adb_device, "shell", cmdline_cmd],
                    capture_output=True, text=True, timeout=2
                )
                
                if cmdline_result.returncode == 0:
                    # Parse the output - format is: "PIDxxx:" followed by cmdline on next line
                    cmdline_map = {}
                    lines = cmdline_result.stdout.splitlines()
                    
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if line.startswith('PID') and ':' in line:
                            try:
                                pid = int(line[3:line.index(':')])
                                # Next line is the cmdline
                                if i + 1 < len(lines):
                                    full_cmd = lines[i + 1].strip()
                                    if full_cmd:
                                        cmdline_map[pid] = full_cmd
                                i += 2  # Skip to next PID marker
                            except (ValueError, IndexError):
                                i += 1
                        else:
                            i += 1
                    
                    # Update cmdlines and extract proper names
                    for proc in top_processes:
                        if proc.pid in cmdline_map:
                            full_cmd = cmdline_map[proc.pid]
                            proc.cmdline = full_cmd
                            
                            # Extract better name from full command
                            # For kernel threads: [kworker/R-tpm_d] -> kworker/R-tpm_d (won't have /proc/cmdline)
                            if full_cmd.startswith('[') and full_cmd.endswith(']'):
                                proc.name = full_cmd[1:-1]
                            # For native binaries: /system/bin/surfaceflinger -> surfaceflinger
                            elif full_cmd.startswith('/'):
                                proc.name = full_cmd.split('/')[-1].split()[0]
                            # For Android apps: com.android.chrome:privileged_process1 -> chrome
                            elif '.' in full_cmd or ':' in full_cmd:
                                base = full_cmd.split()[0].split(':')[0]  # Get first word, remove service suffix
                                if '.' in base:
                                    proc.name = base.split('.')[-1]
                                else:
                                    proc.name = base
            
            return top_processes
            
        except Exception as e:
            print(f"Error fetching ADB processes via /proc: {e}")
            # Fallback to top on error
            self._adb_use_proc = False
            return self._get_adb_processes_top()
    
    def _get_adb_processes_top(self) -> List[ProcessInfo]:
        """Get processes from Android device via top command (fallback method)."""
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
                if "PID" in line and ("USER" in line or "ARGS" in line):
                    header_idx = i
                    # Parse headers to find column indices
                    # Example: PID USER PR NI VIRT RES SHR S[%CPU] %MEM TIME+ ARGS
                    # Or: PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ COMMAND
                    headers = line.split()
                    for j, h in enumerate(headers):
                        # Handle S[%CPU] format (state+cpu combined)
                        if 'CPU' in h:
                            col_map['CPU'] = j
                        if 'MEM' in h:
                            col_map['MEM'] = j
                        # Store all headers
                        clean_h = h.replace('%', '').replace('[', '').replace(']', '').strip()
                        col_map[clean_h] = j
                    break
            
            if header_idx == -1:
                return []
                
            # Process data lines
            for line in lines[header_idx+1:]:
                if not line.strip():
                    continue
                    
                try:
                    parts = line.split()
                    if len(parts) < 10:  # Need at least: PID USER PR NI VIRT RES SHR S CPU MEM
                        continue
                    
                    # Fixed column positions based on Android top format:
                    # PID USER PR NI VIRT RES SHR S[%CPU] %MEM TIME+ ARGS
                    # When split: PID USER PR NI VIRT RES SHR S CPU MEM TIME ARGS...
                    pid = int(parts[0])
                    # State is at index 7, CPU at index 8
                    cpu_percent = float(parts[8]) if len(parts) > 8 else 0.0
                    
                    # Memory (RES/RSS) is at index 5
                    def parse_mem(val_str):
                        val_str = val_str.upper()
                        mult = 1
                        if val_str.endswith('G'): mult = 1024*1024*1024; val_str = val_str[:-1]
                        elif val_str.endswith('M'): mult = 1024*1024; val_str = val_str[:-1]
                        elif val_str.endswith('K'): mult = 1024; val_str = val_str[:-1]
                        try:
                            return int(float(val_str) * mult)
                        except:
                            return 0

                    memory_rss = parse_mem(parts[5]) if len(parts) > 5 else 0  # RES
                    memory_vms = parse_mem(parts[4]) if len(parts) > 4 else 0  # VIRT
                    status = parts[7] if len(parts) > 7 else '?'
                    
                    # TIME+ is at index 10, ARGS start at index 11
                    cmdline = " ".join(parts[11:]) if len(parts) > 11 else "unknown"
                    # Extract process name from command
                    if '/' in cmdline:
                        name = cmdline.split('/')[-1].split()[0] if cmdline else "unknown"
                    else:
                        name = cmdline.split()[0] if cmdline else "unknown"
                    
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
            
            # Enhance cmdline with full command from /proc for top processes
            # Sort first to get top N, then fetch their full cmdlines
            if processes:
                processes = self._sort_processes(processes)[:self.process_count]
                
                # Fetch full command lines using /proc/*/cmdline instead of ps
                pids = [str(p.pid) for p in processes]
                cmdline_cmd = " ".join([f"echo 'PID{pid}:' && cat /proc/{pid}/cmdline 2>/dev/null | tr '\\0' ' ' && echo;" for pid in pids])
                
                try:
                    cmdline_result = subprocess.run(
                        ["adb", "-s", self.adb_device, "shell", cmdline_cmd],
                        capture_output=True, text=True, timeout=2
                    )
                    
                    if cmdline_result.returncode == 0:
                        # Parse the output - format is: "PIDxxx:" followed by cmdline on next line
                        cmdline_map = {}
                        lines = cmdline_result.stdout.splitlines()
                        
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            if line.startswith('PID') and ':' in line:
                                try:
                                    pid = int(line[3:line.index(':')])
                                    # Next line is the cmdline
                                    if i + 1 < len(lines):
                                        full_cmd = lines[i + 1].strip()
                                        if full_cmd:
                                            cmdline_map[pid] = full_cmd
                                    i += 2  # Skip to next PID marker
                                except (ValueError, IndexError):
                                    i += 1
                            else:
                                i += 1
                        
                        # Update cmdlines and extract proper names
                        for proc in processes:
                            if proc.pid in cmdline_map:
                                full_cmd = cmdline_map[proc.pid]
                                # Update cmdline if it's more detailed than what top gave us
                                if len(full_cmd) > len(proc.cmdline):
                                    proc.cmdline = full_cmd
                                    
                                    # Extract better name from full command
                                    # For native binaries: /system/bin/surfaceflinger -> surfaceflinger
                                    if full_cmd.startswith('/'):
                                        proc.name = full_cmd.split('/')[-1].split()[0]
                                    # For Android apps: com.android.chrome:privileged_process1 -> chrome
                                    elif '.' in full_cmd or ':' in full_cmd:
                                        base = full_cmd.split()[0].split(':')[0]  # Get first word, remove service suffix
                                        if '.' in base:
                                            proc.name = base.split('.')[-1]
                                        else:
                                            proc.name = base
                except Exception as e:
                    # If /proc reading fails, just use what we got from top
                    print(f"Warning: Could not fetch full cmdlines from /proc: {e}")
                    pass
                    
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
