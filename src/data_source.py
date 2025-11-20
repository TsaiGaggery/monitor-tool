"""Data Source Proxy - Abstract interface for monitoring data sources.

This module provides a unified interface for different monitoring data sources:
- Local system (psutil)
- Android device (ADB)
- Remote Linux (SSH)
- Remote Windows (WMI/SSH)

The proxy pattern allows the UI to remain unchanged regardless of data source.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import time


class MonitorDataSource(ABC):
    """Abstract base class for monitoring data sources."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the data source.
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from the data source."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to data source.
        
        Returns:
            bool: True if connected
        """
        pass
    
    @abstractmethod
    def get_cpu_info(self) -> Dict:
        """Get CPU information.
        
        Returns:
            Dict: CPU information in standard format
        """
        pass
    
    @abstractmethod
    def get_memory_info(self) -> Dict:
        """Get memory information.
        
        Returns:
            Dict: Memory information in standard format
        """
        pass
    
    @abstractmethod
    def get_gpu_info(self) -> Dict:
        """Get GPU information.
        
        Returns:
            Dict: GPU information in standard format
        """
        pass
    
    @abstractmethod
    def get_npu_info(self) -> Dict:
        """Get NPU information.
        
        Returns:
            Dict: NPU information in standard format
        """
        pass
    
    @abstractmethod
    def get_network_info(self) -> Dict:
        """Get network information.
        
        Returns:
            Dict: Network information in standard format
        """
        pass
    
    @abstractmethod
    def get_disk_info(self) -> Dict:
        """Get disk information.
        
        Returns:
            Dict: Disk information in standard format
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Get human-readable name of data source.
        
        Returns:
            str: Data source name (e.g., "Local System", "Android 192.168.1.68")
        """
        pass


class LocalDataSource(MonitorDataSource):
    """Local system data source using psutil."""
    
    def __init__(self, enable_tier1: bool = False):
        """Initialize local data source.
        
        Args:
            enable_tier1: Enable Tier 1 metrics (context switches, load avg, process counts)
        """
        from monitors import (CPUMonitor, MemoryMonitor, GPUMonitor, 
                            NPUMonitor, NetworkMonitor, DiskMonitor)
        
        self.cpu_monitor = CPUMonitor()
        self.memory_monitor = MemoryMonitor()
        self.gpu_monitor = GPUMonitor()
        self.npu_monitor = NPUMonitor()
        self.network_monitor = NetworkMonitor()
        self.disk_monitor = DiskMonitor()
        self._connected = True
        self.enable_tier1 = enable_tier1
    
    def connect(self) -> bool:
        """Connect to local system (always successful)."""
        self._connected = True
        return True
    
    def disconnect(self):
        """Disconnect from local system (no-op)."""
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information from local system."""
        return self.cpu_monitor.get_all_info()
    
    def get_memory_info(self) -> Dict:
        """Get memory information from local system."""
        return self.memory_monitor.get_all_info()
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information from local system."""
        return self.gpu_monitor.get_all_info()
    
    def get_npu_info(self) -> Dict:
        """Get NPU information from local system."""
        return self.npu_monitor.get_all_info()
    
    def get_network_info(self) -> Dict:
        """Get network information from local system."""
        all_info = self.network_monitor.get_all_info()
        # Flatten io_stats to top level for backward compatibility
        io_stats = all_info.get('io_stats', {})
        return {
            'upload_speed': io_stats.get('upload_speed', 0),
            'download_speed': io_stats.get('download_speed', 0),
            'connections': all_info.get('connections', {'total': 0, 'tcp_established': 0}),
            'interfaces': all_info.get('interfaces', []),
            'interface_stats': all_info.get('interface_stats', {}),
            'io_stats': io_stats
        }
    
    def get_disk_info(self) -> Dict:
        """Get disk information from local system."""
        all_info = self.disk_monitor.get_all_info()
        # Flatten io_stats to top level for backward compatibility
        io_stats = all_info.get('io_stats', {})
        partitions_list = all_info.get('partition_usage', [])
        # Convert list to dict with mount points as keys
        partitions_dict = {}
        for part in partitions_list:
            partitions_dict[part.get('mountpoint', '/')] = part
        return {
            'read_speed_mb': io_stats.get('read_speed_mb', 0),
            'write_speed_mb': io_stats.get('write_speed_mb', 0),
            'partitions': partitions_dict,
            'disks': all_info.get('disks', []),
            'io_stats': io_stats,
            'partition_usage': partitions_list
        }
    
    def get_source_name(self) -> str:
        """Get data source name."""
        return "Local System"
    
    def get_tier1_info(self) -> Dict:
        """Get Tier 1 metrics from local system.
        
        Returns:
            Dictionary containing tier1 metrics including context switches,
            load average, process counts, per-core IRQ/SoftIRQ, and interrupts.
        """
        if not self.enable_tier1:
            return {}
        
        # Warm-up: If this is the very first call, take a baseline sample
        # so subsequent calls will have meaningful rates (not zero)
        if not hasattr(self, '_prev_interrupts'):
            # Initialize baseline by reading interrupts once
            try:
                with open('/proc/interrupts', 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        header_parts = lines[0].split()
                        num_cpus = sum(1 for part in header_parts if part.startswith('CPU'))
                        
                        self._prev_interrupts = {}
                        for line in lines[1:]:
                            parts = line.split()
                            if len(parts) < num_cpus + 2:
                                continue
                            irq_name = parts[0].rstrip(':')
                            try:
                                total = sum(int(parts[1 + i]) for i in range(num_cpus))
                                self._prev_interrupts[irq_name] = total
                            except (ValueError, IndexError):
                                continue
                        
                        self._prev_interrupts_time_ms = int(__import__('time').time() * 1000)
            except Exception:
                self._prev_interrupts = {}
                self._prev_interrupts_time_ms = int(__import__('time').time() * 1000)
        
        import psutil
        
        # Get CPU stats (context switches, interrupts)
        cpu_info = self.cpu_monitor.get_all_info()
        stats = cpu_info.get('stats', {})
        usage = cpu_info.get('usage', {})
        load_avg = usage.get('load_avg', (0, 0, 0))
        per_core = cpu_info.get('per_core', [])
        
        # Get process counts
        procs_running = 0
        procs_blocked = 0
        try:
            for proc in psutil.process_iter(['status']):
                status = proc.info.get('status', '')
                if status == psutil.STATUS_RUNNING:
                    procs_running += 1
                elif status in [psutil.STATUS_DISK_SLEEP, psutil.STATUS_STOPPED]:
                    procs_blocked += 1
        except Exception:
            pass
        
        # Extract per-core IRQ and SoftIRQ percentages from per_core data
        # Note: psutil returns cumulative time, we need to calculate % ourselves
        # Using psutil.cpu_times_percent() for instant percentages
        per_core_irq_pct = []
        per_core_softirq_pct = []
        
        try:
            # Get per-core CPU time percentages (non-blocking, uses internal delta tracking)
            per_core_pct = psutil.cpu_times_percent(interval=None, percpu=True)
            for core_pct in per_core_pct:
                per_core_irq_pct.append(getattr(core_pct, 'irq', 0))
                per_core_softirq_pct.append(getattr(core_pct, 'softirq', 0))
        except Exception as e:
            print(f"Error getting per-core IRQ/SoftIRQ percentages: {e}")
            # Fallback: use zeros
            num_cores = cpu_info.get('cpu_count', 0)
            per_core_irq_pct = [0.0] * num_cores
            per_core_softirq_pct = [0.0] * num_cores
        
        # Parse /proc/interrupts for interrupt distribution (SSH-compatible format)
        interrupts = {}
        try:
            with open('/proc/interrupts', 'r') as f:
                lines = f.readlines()
                if len(lines) > 0:
                    # First line has CPU headers
                    header_parts = lines[0].split()
                    num_cpus = sum(1 for part in header_parts if part.startswith('CPU'))
                    
                    # Parse interrupt lines
                    interrupt_data = []
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) < num_cpus + 2:
                            continue
                        
                        # IRQ number or name
                        irq_name = parts[0].rstrip(':')
                        
                        try:
                            # Per-CPU interrupt counts
                            per_cpu = []
                            total = 0
                            primary_cpu = 0
                            max_count = 0
                            
                            for cpu_idx in range(num_cpus):
                                count = int(parts[1 + cpu_idx])
                                per_cpu.append(count)
                                total += count
                                if count > max_count:
                                    max_count = count
                                    primary_cpu = cpu_idx
                            
                            # Get description (everything after the per-CPU counts)
                            # Skip the interrupt type field (e.g., "IR-PCI-MSI")
                            desc_start_idx = num_cpus + 2  # Skip IRQ name + CPU counts + type
                            desc = ' '.join(parts[desc_start_idx:]) if len(parts) > desc_start_idx else ''
                            
                            interrupt_data.append({
                                'irq': irq_name,
                                'total': total,
                                'per_cpu': per_cpu,
                                'primary_cpu': primary_cpu,
                                'description': desc
                            })
                        except (ValueError, IndexError):
                            continue
                    
                    # Calculate rates (interrupts per second) from delta
                    # Create a dictionary for quick lookup of previous values
                    if not hasattr(self, '_prev_interrupts'):
                        self._prev_interrupts = {}
                        self._prev_interrupts_time_ms = int(time.time() * 1000)
                    
                    current_time_ms = int(time.time() * 1000)
                    time_delta_sec = (current_time_ms - self._prev_interrupts_time_ms) / 1000.0
                    
                    # Calculate rate for each interrupt
                    for irq_data in interrupt_data:
                        irq_key = irq_data['irq']
                        curr_total = irq_data['total']
                        
                        if irq_key in self._prev_interrupts and time_delta_sec > 0:
                            prev_total = self._prev_interrupts[irq_key]
                            delta = curr_total - prev_total
                            if delta >= 0:
                                irq_data['rate'] = int(delta / time_delta_sec)
                            else:
                                irq_data['rate'] = 0
                        else:
                            # First sample or counter wrapped - no rate available
                            irq_data['rate'] = 0
                        
                        # Update previous value
                        self._prev_interrupts[irq_key] = curr_total
                    
                    # Update timestamp for next delta calculation
                    self._prev_interrupts_time_ms = current_time_ms
                    
                    # Sort by RATE (current activity) not total (cumulative since boot)
                    interrupt_data.sort(key=lambda x: x.get('rate', 0), reverse=True)
                    top_interrupts = interrupt_data[:10]
                    
                    # Format as JSON with structure matching SSH format
                    interrupts = {
                        'interrupts': [
                            {
                                'name': irq['description'][:50] if irq['description'] else irq['irq'],  # Truncate long names
                                'irq': irq['irq'],
                                'total': irq['total'],
                                'rate': irq.get('rate', 0),  # Include rate for CLI display
                                'cpu': irq['primary_cpu'],
                                'per_cpu': irq['per_cpu']
                            }
                            for irq in top_interrupts
                        ]
                    }
        except Exception as e:
            print(f"Error collecting interrupt data: {e}")
            interrupts = {}
        
        tier1_data = {
            'context_switches': stats.get('ctx_switches', 0),
            'load_avg': {
                '1min': load_avg[0] if len(load_avg) > 0 else 0,
                '5min': load_avg[1] if len(load_avg) > 1 else 0,
                '15min': load_avg[2] if len(load_avg) > 2 else 0
            },
            'process_counts': {
                'running': procs_running,
                'blocked': procs_blocked,
                'total': len(psutil.pids())
            },
            'per_core_irq_pct': per_core_irq_pct,
            'per_core_softirq_pct': per_core_softirq_pct,
            'interrupts': interrupts,
            # Include timestamp_ms for consistency (local uses host time in milliseconds)
            'timestamp_ms': int(time.time() * 1000)
        }
        
        return tier1_data


class AndroidDataSource(MonitorDataSource):
    """Android device data source via ADB (raw data version)."""
    
    def __init__(self, device_ip: str, port: int = 5555, enable_tier1: bool = False):
        """Initialize Android data source.
        
        Args:
            device_ip: Android device IP address
            port: ADB port (default: 5555)
            enable_tier1: Enable Tier 1 metrics (context switches, load avg, etc.)
        """
        from monitors.adb_monitor_raw import ADBMonitorRaw
        
        self.device_ip = device_ip
        self.port = port
        self.enable_tier1 = enable_tier1
        self.adb_monitor = None
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to Android device via ADB."""
        try:
            from monitors.adb_monitor_raw import ADBMonitorRaw
            
            # ADBMonitorRaw automatically starts streaming in __init__
            self.adb_monitor = ADBMonitorRaw(self.device_ip, self.port, enable_tier1=self.enable_tier1)
            self._connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to Android device: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Android device."""
        if self.adb_monitor:
            self.adb_monitor.stop_streaming()
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to Android device."""
        return self._connected and self.adb_monitor is not None
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information from Android device."""
        if not self.is_connected():
            return self._empty_cpu_info()
        
        cpu_info = self.adb_monitor.get_cpu_info()
        
        # Calculate monitor CPU usage from Android script data
        raw_data = self.adb_monitor.get_latest_data()
        if raw_data:
            cpu_raw = raw_data.get('cpu_raw', {})
            cpu_count = cpu_info.get('cpu_count', 1)
            monitor_cpu_usage = self._calculate_monitor_cpu_usage(raw_data, cpu_raw, cpu_count)
            cpu_info['monitor_cpu_usage'] = monitor_cpu_usage
        
        return cpu_info
    
    def _calculate_monitor_cpu_usage(self, raw_data: Dict, cpu_raw: Dict, cpu_count: int) -> float:
        """Calculate monitor script CPU usage from raw data.
        
        Returns per-core CPU percentage (normalized by cpu_count) to match local monitoring behavior.
        """
        monitor_utime = raw_data.get('monitor_cpu_utime', 0)
        monitor_stime = raw_data.get('monitor_cpu_stime', 0)
        
        # If no previous data, save current and return 0
        if not hasattr(self, '_prev_monitor_utime'):
            self._prev_monitor_utime = monitor_utime
            self._prev_monitor_stime = monitor_stime
            self._prev_cpu_total = sum([
                cpu_raw.get('user', 0), cpu_raw.get('nice', 0), cpu_raw.get('sys', 0),
                cpu_raw.get('idle', 0), cpu_raw.get('iowait', 0), cpu_raw.get('irq', 0),
                cpu_raw.get('softirq', 0), cpu_raw.get('steal', 0)
            ])
            return 0.0
        
        # Calculate current total CPU ticks
        curr_total = sum([
            cpu_raw.get('user', 0), cpu_raw.get('nice', 0), cpu_raw.get('sys', 0),
            cpu_raw.get('idle', 0), cpu_raw.get('iowait', 0), cpu_raw.get('irq', 0),
            cpu_raw.get('softirq', 0), cpu_raw.get('steal', 0)
        ])
        
        # Calculate deltas
        delta_monitor = (monitor_utime + monitor_stime) - (self._prev_monitor_utime + self._prev_monitor_stime)
        delta_total = curr_total - self._prev_cpu_total
        
        # Save current for next calculation
        self._prev_monitor_utime = monitor_utime
        self._prev_monitor_stime = monitor_stime
        self._prev_cpu_total = curr_total
        
        # Calculate percentage (multiply by cpu_count to get per-core percentage)
        # delta_total is total ticks across ALL cores, so we normalize to single-core equivalent
        if delta_total > 0 and cpu_count > 0:
            # This gives percentage as if running on a single core (matches psutil behavior)
            monitor_cpu_pct = (delta_monitor * 100.0 * cpu_count) / delta_total
            return max(0.0, min(100.0, monitor_cpu_pct))
        
        return 0.0
    
    def get_memory_info(self) -> Dict:
        """Get memory information from Android device."""
        if not self.is_connected():
            return self._empty_memory_info()
        return self.adb_monitor.get_memory_info()
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information from Android device."""
        if not self.is_connected():
            return {'available': False, 'gpus': []}
        return self.adb_monitor.get_gpu_info()
    
    def get_npu_info(self) -> Dict:
        """Get NPU information (not available on Android)."""
        return {'available': False}
    
    def get_network_info(self) -> Dict:
        """Get network information from Android device."""
        if not self.is_connected():
            return self._empty_network_info()
        net_info = self.adb_monitor.get_network_info()
        # Ensure proper structure
        return {
            'upload_speed': net_info.get('upload_speed', 0),
            'download_speed': net_info.get('download_speed', 0),
            'connections': net_info.get('connections', {'total': 0, 'tcp_established': 0}),
            'interfaces': net_info.get('interfaces', []),
            'interface_stats': net_info.get('interface_stats', {}),
            'io_stats': net_info.get('io_stats', {})
        }
    
    def get_disk_info(self) -> Dict:
        """Get disk information from Android device."""
        if not self.is_connected():
            return self._empty_disk_info()
        disk_info = self.adb_monitor.get_disk_info()
        # Ensure proper structure
        partitions_list = disk_info.get('partition_usage', [])
        partitions_dict = {}
        for part in partitions_list:
            partitions_dict[part.get('mountpoint', '/')] = part
        return {
            'read_speed_mb': disk_info.get('read_speed_mb', 0),
            'write_speed_mb': disk_info.get('write_speed_mb', 0),
            'partitions': partitions_dict,
            'disks': disk_info.get('disks', []),
            'io_stats': disk_info.get('io_stats', {}),
            'partition_usage': partitions_list
        }
    
    def get_tier1_info(self) -> Dict:
        """Get Tier 1 metrics from Android device.
        
        Returns:
            Dictionary containing tier1 metrics including context switches,
            load average, process counts, and interrupts
        """
        if not self.is_connected() or not self.enable_tier1:
            return {}
        
        # Warm-up: Initialize baseline on first call for meaningful rates
        if not hasattr(self, '_prev_android_interrupts'):
            raw_data_init = self.adb_monitor.get_latest_data()
            if raw_data_init:
                self._prev_android_interrupts = {}
                interrupt_data = raw_data_init.get('interrupt_data')
                if interrupt_data and isinstance(interrupt_data, dict):
                    irq_list = interrupt_data.get('interrupts', [])
                    for irq in irq_list:
                        irq_key = irq.get('irq', '') or irq.get('name', '')
                        self._prev_android_interrupts[irq_key] = irq.get('total', 0)
                self._prev_ctxt = raw_data_init.get('ctxt', 0)
                self._prev_ctxt_timestamp_ms = raw_data_init.get('timestamp_ms', 0)
                
                # Wait for next update cycle to get fresh data (device script updates every 1 sec)
                import time
                time.sleep(1.2)  # Wait for next sample to ensure we get fresh data
        
        # Get raw data from Android monitor
        raw_data = self.adb_monitor.get_latest_data()
        if not raw_data:
            return {}
        
        # Calculate context switches per second (need delta from previous sample)
        ctxt = raw_data.get('ctxt', 0)
        timestamp_ms = raw_data.get('timestamp_ms', 0)
        
        # Store previous timestamp BEFORE updating (for interrupt rate calculation)
        prev_timestamp_for_irq = self._prev_ctxt_timestamp_ms if hasattr(self, '_prev_ctxt_timestamp_ms') else timestamp_ms
        
        ctx_switches_per_sec = 0
        if hasattr(self, '_prev_ctxt') and hasattr(self, '_prev_ctxt_timestamp_ms'):
            delta_ctxt = ctxt - self._prev_ctxt
            delta_time_ms = timestamp_ms - self._prev_ctxt_timestamp_ms
            if delta_time_ms > 0 and delta_ctxt > 0:
                ctx_switches_per_sec = int((delta_ctxt * 1000.0) / delta_time_ms)
        
        self._prev_ctxt = ctxt
        self._prev_ctxt_timestamp_ms = timestamp_ms
        
        # Build tier1 data structure
        tier1_data = {
            'context_switches': ctx_switches_per_sec,
            'load_avg': {
                '1min': raw_data.get('load_avg_1m', 0),
                '5min': raw_data.get('load_avg_5m', 0),
                '15min': raw_data.get('load_avg_15m', 0)
            },
            'process_counts': {
                'running': raw_data.get('procs_running', 0),
                'blocked': raw_data.get('procs_blocked', 0),
                'total': 0  # Not available from Android monitoring
            }
        }
        
        # Add interrupt data if available and calculate rates
        interrupt_data = raw_data.get('interrupt_data')
        if interrupt_data and isinstance(interrupt_data, dict) and 'interrupts' in interrupt_data:
            # Calculate rates (interrupts per second) from delta
            if not hasattr(self, '_prev_android_interrupts'):
                self._prev_android_interrupts = {}
            
            irq_list = interrupt_data.get('interrupts', [])
            
            # Calculate rate for each interrupt
            for irq in irq_list:
                irq_key = irq.get('irq', '') or irq.get('name', '')
                curr_total = irq.get('total', 0)
                
                if irq_key in self._prev_android_interrupts and timestamp_ms > prev_timestamp_for_irq:
                    prev_total = self._prev_android_interrupts[irq_key]
                    delta = curr_total - prev_total
                    delta_time_ms = timestamp_ms - prev_timestamp_for_irq
                    if delta >= 0 and delta_time_ms > 0:
                        irq['rate'] = int((delta * 1000.0) / delta_time_ms)
                    else:
                        irq['rate'] = 0
                else:
                    # First sample - no rate available
                    irq['rate'] = 0
                
                # Update previous value
                self._prev_android_interrupts[irq_key] = curr_total
            
            # Sort by RATE (current activity) not total (cumulative)
            irq_list.sort(key=lambda x: x.get('rate', 0), reverse=True)
            
            # Update the interrupt data with sorted list
            interrupt_data['interrupts'] = irq_list
            tier1_data['interrupts'] = interrupt_data
        
        # Add per-core IRQ/softirq percentages if available
        per_core_irq = raw_data.get('per_core_irq_pct')
        per_core_softirq = raw_data.get('per_core_softirq_pct')
        if per_core_irq:
            tier1_data['per_core_irq_pct'] = per_core_irq
        if per_core_softirq:
            tier1_data['per_core_softirq_pct'] = per_core_softirq
        
        # Include device timestamp_ms for accurate rate calculation in exporter
        # CRITICAL: Interrupt counts are collected on device time, so we must use
        # device timestamp_ms (not host time_seconds) for rate calculations
        tier1_data['timestamp_ms'] = timestamp_ms
        
        return tier1_data
    
    def get_timestamp_ms(self) -> int:
        """Get Android device timestamp in milliseconds."""
        if not self.is_connected():
            return 0
        return self.adb_monitor.get_timestamp_ms()
    
    def get_source_name(self) -> str:
        """Get data source name."""
        return f"Android Device ({self.device_ip}:{self.port})"
    
    def _empty_cpu_info(self) -> Dict:
        """Return empty CPU info."""
        return {
            'cpu_count': 0,
            'physical_count': 0,
            'usage': {'total': 0, 'per_core': []},
            'frequency': {'average': 0, 'per_core': []},
            'temperature': {}
        }
    
    def _empty_memory_info(self) -> Dict:
        """Return empty memory info."""
        return {
            'memory': {'total': 0, 'used': 0, 'free': 0, 'available': 0, 'percent': 0, 'speed': 0},
            'swap': {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
        }
    
    def _empty_network_info(self) -> Dict:
        """Return empty network info."""
        return {
            'upload_speed': 0,
            'download_speed': 0,
            'connections': {'total': 0, 'tcp_established': 0},
            'interfaces': [],
            'interface_stats': {},
            'io_stats': {'upload_speed': 0, 'download_speed': 0, 'packets_sent': 0, 'packets_recv': 0}
        }
    
    def _empty_disk_info(self) -> Dict:
        """Return empty disk info."""
        return {
            'read_speed_mb': 0,
            'write_speed_mb': 0,
            'partitions': {},
            'disks': [],
            'io_stats': {
                'read_speed': 0, 'write_speed': 0,
                'read_speed_mb': 0, 'write_speed_mb': 0,
                'read_iops': 0, 'write_iops': 0
            },
            'partition_usage': []
        }


class RemoteLinuxDataSource(MonitorDataSource):
    """Remote Linux system data source via SSH.
    
    Streams JSON data from remote Linux host using linux_monitor_remote.sh script.
    Similar architecture to AndroidDataSource (ADBMonitorRaw).
    """
    
    def __init__(self, host: str, port: int = 22, username: str = None, password: str = None,
                 key_path: str = None, interval: int = 1, enable_tier1: bool = False):
        """Initialize remote Linux data source.
        
        Args:
            host: Remote host address
            port: SSH port (default: 22)
            username: SSH username
            password: SSH password (optional if using key)
            key_path: Path to SSH private key (optional if using password)
            interval: Monitoring interval in seconds
            enable_tier1: Enable Tier 1 metrics (context switches, load avg, process counts, IRQ%)
        """
        from monitors.ssh_monitor_raw import SSHMonitorRaw
        
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.interval = interval
        self.enable_tier1 = enable_tier1
        
        # For DataExporter to identify this as SSH data source
        self.ssh_host = host  # Similar to device_ip for Android
        
        self.ssh_monitor = SSHMonitorRaw(
            host=host,
            user=username,
            password=password,
            key_path=key_path,
            port=port,
            interval=interval,
            enable_tier1=enable_tier1
        )
        
        self._connected = False
        self.session_start_time = None  # Track when monitoring session started
        
        # Previous values for delta calculations (use separate timestamps for different metrics)
        self._prev_cpu_raw = None
        self._prev_per_core_raw = None
        self._prev_cpu_time = None  # Separate timestamp for CPU
        self._prev_cpu_power_uj = None  # Previous CPU energy counter
        self._prev_net_bytes = None
        self._prev_net_time = None  # Separate timestamp for network
        self._prev_disk_sectors = None
        self._prev_disk_time = None  # Separate timestamp for disk
        
        # Cache for last calculated values (to handle duplicate timestamps)
        self._cached_cpu_info = None
        self._cached_network_info = None
        self._cached_disk_info = None
        self._cached_tier1_info = None
    
    def connect(self) -> bool:
        """Connect to remote Linux system via SSH."""
        if self.ssh_monitor.connect():
            self.ssh_monitor.start_monitoring()
            self._connected = True
            
            # Wait for initial data to arrive (actively poll for up to 5 seconds)
            for _ in range(50):  # 50 * 0.1s = 5s max
                time.sleep(0.1)
                first_data = self.ssh_monitor.get_latest_data()
                if first_data:
                    # Record session start time from REMOTE timestamp, not local wall-clock
                    # This ensures session_start_time matches the first DB sample timestamp
                    from datetime import datetime
                    if self.session_start_time is None:
                        # Use remote timestamp from first sample (seconds precision)
                        remote_ts = first_data.get('timestamp_ms', 0) // 1000
                        if remote_ts > 0:
                            self.session_start_time = datetime.fromtimestamp(remote_ts)
                        else:
                            # Fallback to local time if no remote timestamp
                            self.session_start_time = datetime.now()
                    
                    # Data received, wait a bit more for GPU/NPU detection
                    time.sleep(2.0)
                    break
            
            return True
        return False
    
    def disconnect(self):
        """Disconnect from remote system."""
        self.ssh_monitor.disconnect()
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    def process_queued_samples(self):
        """Process all queued samples from SSH monitor to prevent data loss.
        
        This should be called before reading data to ensure all samples
        from the remote stream have been processed. Returns the list of
        samples for the UI to process individually.
        
        Returns:
            List of queued samples to process
        """
        if hasattr(self.ssh_monitor, 'get_queued_samples'):
            return self.ssh_monitor.get_queued_samples()
        return []
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information from remote system."""
        raw_data = self.ssh_monitor.get_latest_data()
        if not raw_data:
            return self._empty_cpu_info()
        
        # Parse CPU raw data
        cpu_raw = raw_data.get('cpu_raw', {})
        per_core_raw = raw_data.get('per_core_raw', [])
        per_core_freq = raw_data.get('per_core_freq_khz', [])
        cpu_temp = raw_data.get('cpu_temp_millideg', 0)
        cpu_power_uj = raw_data.get('cpu_power_uj', 0)
        timestamp_ms = raw_data.get('timestamp_ms', 0)
        
        # Check if we already processed this timestamp
        if self._prev_cpu_time == timestamp_ms and self._cached_cpu_info:
            return self._cached_cpu_info
        
        # Calculate CPU Power (Watts)
        power_watts = 0.0
        if self._prev_cpu_power_uj is not None and self._prev_cpu_time is not None:
            time_delta = (timestamp_ms - self._prev_cpu_time) / 1000.0
            if time_delta > 0 and cpu_power_uj > self._prev_cpu_power_uj:
                energy_delta = cpu_power_uj - self._prev_cpu_power_uj
                power_watts = (energy_delta / 1_000_000.0) / time_delta
        
        self._prev_cpu_power_uj = cpu_power_uj
        
        # Calculate CPU usage (using remote device timestamp)
        cpu_usage = self._calculate_cpu_usage(cpu_raw, per_core_raw, timestamp_ms)
        
        # Parse frequencies
        freq_list = [freq / 1000.0 for freq in per_core_freq]  # kHz -> MHz
        avg_freq = sum(freq_list) / len(freq_list) if freq_list else 0
        
        # Format temperature to match psutil format
        temp_sensors = {}
        if cpu_temp > 0:
            temp_sensors['cpu_thermal'] = [
                {'label': 'Package id 0', 'current': cpu_temp / 1000.0}
            ]
        
        # Calculate monitor CPU usage
        cpu_count = len(per_core_raw)
        monitor_cpu_usage = self._calculate_monitor_cpu_usage(raw_data, cpu_raw, cpu_count)
        
        result = {
            'cpu_count': cpu_count,
            'physical_count': len(per_core_raw),  # Simplified
            'usage': {
                'total': cpu_usage['total'],
                'per_core': cpu_usage['per_core']
            },
            'frequency': {
                'average': avg_freq,
                'per_core': freq_list
            },
            'temperature': temp_sensors,
            'power_watts': power_watts,
            'monitor_cpu_usage': monitor_cpu_usage
        }
        
        self._cached_cpu_info = result
        return result
    
    def _calculate_cpu_usage(self, cpu_raw: Dict, per_core_raw: list, timestamp_ms: int) -> Dict:
        """Calculate CPU usage from raw data (using correct delta algorithm).
        
        Args:
            cpu_raw: Raw CPU stats
            per_core_raw: Raw per-core CPU stats
            timestamp_ms: Timestamp from remote device (milliseconds)
        """
        # Initialize result
        result = {'total': 0.0, 'per_core': []}
        
        # Calculate total CPU usage
        if self._prev_cpu_raw and self._prev_cpu_time:
            # Use remote device timestamp (convert ms to seconds)
            time_delta = (timestamp_ms - self._prev_cpu_time) / 1000.0
            
            if time_delta > 0:
                # Calculate deltas for each field
                d_user = cpu_raw.get('user', 0) - self._prev_cpu_raw.get('user', 0)
                d_nice = cpu_raw.get('nice', 0) - self._prev_cpu_raw.get('nice', 0)
                d_sys = cpu_raw.get('sys', 0) - self._prev_cpu_raw.get('sys', 0)
                d_idle = cpu_raw.get('idle', 0) - self._prev_cpu_raw.get('idle', 0)
                d_iowait = cpu_raw.get('iowait', 0) - self._prev_cpu_raw.get('iowait', 0)
                d_irq = cpu_raw.get('irq', 0) - self._prev_cpu_raw.get('irq', 0)
                d_softirq = cpu_raw.get('softirq', 0) - self._prev_cpu_raw.get('softirq', 0)
                d_steal = cpu_raw.get('steal', 0) - self._prev_cpu_raw.get('steal', 0)
                
                # Total = all time
                d_total = d_user + d_nice + d_sys + d_idle + d_iowait + d_irq + d_softirq + d_steal
                
                # Active = total - idle (iowait is active time waiting for I/O)
                d_active = d_total - d_idle
                
                if d_total > 0:
                    result['total'] = (d_active * 100.0) / d_total
        
        # Calculate per-core usage
        if self._prev_per_core_raw and len(self._prev_per_core_raw) == len(per_core_raw):
            for i, (prev_core, curr_core) in enumerate(zip(self._prev_per_core_raw, per_core_raw)):
                d_user = curr_core.get('user', 0) - prev_core.get('user', 0)
                d_nice = curr_core.get('nice', 0) - prev_core.get('nice', 0)
                d_sys = curr_core.get('sys', 0) - prev_core.get('sys', 0)
                d_idle = curr_core.get('idle', 0) - prev_core.get('idle', 0)
                d_iowait = curr_core.get('iowait', 0) - prev_core.get('iowait', 0)
                d_irq = curr_core.get('irq', 0) - prev_core.get('irq', 0)
                d_softirq = curr_core.get('softirq', 0) - prev_core.get('softirq', 0)
                d_steal = curr_core.get('steal', 0) - prev_core.get('steal', 0)
                
                d_total = d_user + d_nice + d_sys + d_idle + d_iowait + d_irq + d_softirq + d_steal
                d_active = d_total - d_idle
                
                if d_total > 0:
                    usage = (d_active * 100.0) / d_total
                    result['per_core'].append(usage)
                else:
                    result['per_core'].append(0.0)
        else:
            result['per_core'] = [0.0] * len(per_core_raw)
        
        # Save current as previous (use remote device timestamp in milliseconds)
        self._prev_cpu_raw = cpu_raw.copy()
        self._prev_per_core_raw = [core.copy() for core in per_core_raw]
        self._prev_cpu_time = timestamp_ms
        
        return result
    
    def _calculate_monitor_cpu_usage(self, raw_data: Dict, cpu_raw: Dict, cpu_count: int) -> float:
        """Calculate monitor script CPU usage from raw data.
        
        Returns per-core CPU percentage (normalized by cpu_count) to match local monitoring behavior.
        
        Args:
            raw_data: Raw monitoring data containing monitor_cpu_utime and monitor_cpu_stime
            cpu_raw: Current CPU raw stats for total ticks calculation
            cpu_count: Number of CPU cores (for normalization)
            
        Returns:
            Monitor CPU usage percentage (0-100, per-core equivalent)
        """
        monitor_utime = raw_data.get('monitor_cpu_utime', 0)
        monitor_stime = raw_data.get('monitor_cpu_stime', 0)
        
        # If no previous data, save current and return 0
        if not hasattr(self, '_prev_monitor_utime'):
            self._prev_monitor_utime = monitor_utime
            self._prev_monitor_stime = monitor_stime
            self._prev_cpu_total = sum([
                cpu_raw.get('user', 0), cpu_raw.get('nice', 0), cpu_raw.get('sys', 0),
                cpu_raw.get('idle', 0), cpu_raw.get('iowait', 0), cpu_raw.get('irq', 0),
                cpu_raw.get('softirq', 0), cpu_raw.get('steal', 0)
            ])
            return 0.0
        
        # Calculate current total CPU ticks
        curr_total = sum([
            cpu_raw.get('user', 0), cpu_raw.get('nice', 0), cpu_raw.get('sys', 0),
            cpu_raw.get('idle', 0), cpu_raw.get('iowait', 0), cpu_raw.get('irq', 0),
            cpu_raw.get('softirq', 0), cpu_raw.get('steal', 0)
        ])
        
        # Calculate deltas
        delta_monitor = (monitor_utime + monitor_stime) - (self._prev_monitor_utime + self._prev_monitor_stime)
        delta_total = curr_total - self._prev_cpu_total
        
        # Save current for next calculation
        self._prev_monitor_utime = monitor_utime
        self._prev_monitor_stime = monitor_stime
        self._prev_cpu_total = curr_total
        
        # Calculate percentage (multiply by cpu_count to get per-core percentage)
        # delta_total is total ticks across ALL cores, so we normalize to single-core equivalent
        if delta_total > 0 and cpu_count > 0:
            # This gives percentage as if running on a single core (matches psutil behavior)
            monitor_cpu_pct = (delta_monitor * 100.0 * cpu_count) / delta_total
            return max(0.0, min(100.0, monitor_cpu_pct))
        
        return 0.0
    
    def get_memory_info(self) -> Dict:
        """Get memory information from remote system."""
        raw_data = self.ssh_monitor.get_latest_data()
        if not raw_data:
            return self._empty_memory_info()
        
        # Convert kB to bytes first
        mem_total_bytes = raw_data.get('mem_total_kb', 0) * 1024  # kB -> bytes
        mem_free_bytes = raw_data.get('mem_free_kb', 0) * 1024
        mem_available_bytes = raw_data.get('mem_available_kb', 0) * 1024
        
        mem_used_bytes = mem_total_bytes - mem_available_bytes
        mem_percent = (mem_used_bytes / mem_total_bytes * 100.0) if mem_total_bytes > 0 else 0.0
        
        # Convert to GB to match Local/Android format
        GB = 1024 ** 3
        
        return {
            'memory': {
                'total': mem_total_bytes / GB,
                'used': mem_used_bytes / GB,
                'free': mem_free_bytes / GB,
                'available': mem_available_bytes / GB,
                'percent': mem_percent,
                'speed': 0  # Not available
            },
            'swap': {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0
            }
        }
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information from remote system."""
        # Use pre-computed GPU info from SSHMonitorRaw (calculated in _process_raw_data)
        gpu_info = self.ssh_monitor.get_gpu_info()
        
        if not gpu_info or not gpu_info.get('available', False):
            return {'available': False, 'gpus': []}
        
        # Convert to standard format
        return {
            'available': True,
            'gpu_type': 'intel' if 'intel' in gpu_info.get('name', '').lower() else 'nvidia',
            'gpus': [{
                'index': 0,
                'name': gpu_info.get('name', 'Unknown GPU'),
                'gpu_util': gpu_info.get('gpu_util', 0),
                'memory_used': gpu_info.get('memory_used', 0),
                'memory_total': 0,  # Not easily available for Intel
                'temperature': gpu_info.get('temperature', 0),
                'gpu_clock': gpu_info.get('gpu_clock', 0)
            }]
        }
    
    def get_npu_info(self) -> Dict:
        """Get NPU information from remote system."""
        # Use pre-computed NPU info from SSHMonitorRaw (calculated in _process_raw_data)
        npu_info = self.ssh_monitor.get_npu_info()
        
        if not npu_info or not npu_info.get('available', False):
            return {'available': False, 'platform': None}
        
        # Already in correct format from SSHMonitorRaw
        return npu_info
    
    def get_network_info(self) -> Dict:
        """Get network information from remote system."""
        raw_data = self.ssh_monitor.get_latest_data()
        if not raw_data:
            return self._empty_network_info()
        
        net_rx = raw_data.get('net_rx_bytes', 0)
        net_tx = raw_data.get('net_tx_bytes', 0)
        timestamp_ms = raw_data.get('timestamp_ms', 0)  # Use REMOTE timestamp, not local time
        
        # Check if we already processed this timestamp
        if self._prev_net_time == timestamp_ms and self._cached_network_info:
            return self._cached_network_info
        
        # Calculate speeds
        upload_speed = 0.0
        download_speed = 0.0
        
        if self._prev_net_bytes and self._prev_net_time:
            time_delta = (timestamp_ms - self._prev_net_time) / 1000.0  # Convert ms to seconds
            if time_delta > 0:
                download_speed = (net_rx - self._prev_net_bytes[0]) / time_delta
                upload_speed = (net_tx - self._prev_net_bytes[1]) / time_delta
        
        self._prev_net_bytes = (net_rx, net_tx)
        self._prev_net_time = timestamp_ms  # Store remote timestamp in milliseconds
        
        result = {
            'upload_speed': upload_speed,
            'download_speed': download_speed,
            'connections': {'total': 0, 'tcp_established': 0},
            'interfaces': [],
            'interface_stats': {},
            'io_stats': {
                'upload_speed': upload_speed,
                'download_speed': download_speed,
                'packets_sent': 0,
                'packets_recv': 0
            }
        }
        
        self._cached_network_info = result
        return result
    
    def get_disk_info(self) -> Dict:
        """Get disk information from remote system."""
        raw_data = self.ssh_monitor.get_latest_data()
        if not raw_data:
            return self._empty_disk_info()
        
        disk_read = raw_data.get('disk_read_sectors', 0)
        disk_write = raw_data.get('disk_write_sectors', 0)
        timestamp_ms = raw_data.get('timestamp_ms', 0)
        
        # Check if we already processed this timestamp
        if self._prev_disk_time == timestamp_ms and self._cached_disk_info:
            return self._cached_disk_info
        
        # Calculate speeds (sectors = 512 bytes, use remote device timestamp)
        read_speed = 0.0
        write_speed = 0.0
        
        if self._prev_disk_sectors and self._prev_disk_time:
            # Use remote device timestamp (convert ms to seconds)
            time_delta = (timestamp_ms - self._prev_disk_time) / 1000.0
            if time_delta > 0:
                read_speed = (disk_read - self._prev_disk_sectors[0]) * 512 / time_delta
                write_speed = (disk_write - self._prev_disk_sectors[1]) * 512 / time_delta
        
        self._prev_disk_sectors = (disk_read, disk_write)
        self._prev_disk_time = timestamp_ms  # Store remote timestamp in milliseconds
        
        result = {
            'read_speed_mb': read_speed / (1024 * 1024),
            'write_speed_mb': write_speed / (1024 * 1024),
            'partitions': {},
            'disks': [],
            'io_stats': {
                'read_speed': read_speed,
                'write_speed': write_speed,
                'read_speed_mb': read_speed / (1024 * 1024),
                'write_speed_mb': write_speed / (1024 * 1024),
                'read_iops': 0,
                'write_iops': 0
            },
            'partition_usage': []
        }
        
        self._cached_disk_info = result
        return result
    
    def get_tier1_info(self) -> Dict:
        """Get Tier 1 metrics from remote Linux system.
        
        Returns:
            Dictionary containing tier1 metrics including context switches,
            load average, process counts, and interrupts
        """
        if not self.is_connected() or not self.enable_tier1:
            return {}
        
        # Warm-up: Initialize baseline on first call for meaningful rates
        if not hasattr(self, '_prev_ssh_interrupts'):
            raw_data_init = self.ssh_monitor.get_latest_data()
            if raw_data_init:
                self._prev_ssh_interrupts = {}
                interrupt_data = raw_data_init.get('interrupt_data')
                if interrupt_data and isinstance(interrupt_data, dict):
                    irq_list = interrupt_data.get('interrupts', [])
                    for irq in irq_list:
                        irq_key = irq.get('irq', '') or irq.get('name', '')
                        self._prev_ssh_interrupts[irq_key] = irq.get('total', 0)
                self._prev_ssh_ctxt = raw_data_init.get('ctxt', 0)
                self._prev_ssh_ctxt_timestamp_ms = raw_data_init.get('timestamp_ms', 0)
                
                # Initial baseline set, next call will have valid delta
                # IMPORTANT: Wait a bit so next call gets fresh data with different timestamp
                import time
                time.sleep(0.1)  # 100ms wait ensures next sample is fresh
                
        # Get raw data from SSH monitor
        raw_data = self.ssh_monitor.get_latest_data()
        if not raw_data:
            return {}
        
        timestamp_ms = raw_data.get('timestamp_ms', 0)
        
        # Check if we already processed this timestamp
        #if hasattr(self, '_prev_ssh_ctxt_timestamp_ms') and self._prev_ssh_ctxt_timestamp_ms == timestamp_ms and self._cached_tier1_info:
        #    return self._cached_tier1_info
        
        # Calculate context switches per second (need delta from previous sample)
        ctxt = raw_data.get('ctxt', 0)
        
        ctx_switches_per_sec = 0
        if hasattr(self, '_prev_ssh_ctxt') and hasattr(self, '_prev_ssh_ctxt_timestamp_ms'):
            delta_ctxt = ctxt - self._prev_ssh_ctxt
            delta_time_ms = timestamp_ms - self._prev_ssh_ctxt_timestamp_ms
            if delta_time_ms > 0 and delta_ctxt > 0:
                ctx_switches_per_sec = int((delta_ctxt * 1000.0) / delta_time_ms)
        
        # FIX: Update timestamp BEFORE interrupt calculation (not after)
        prev_timestamp_for_irq = self._prev_ssh_ctxt_timestamp_ms if hasattr(self, '_prev_ssh_ctxt_timestamp_ms') else 0

        self._prev_ssh_ctxt = ctxt
        self._prev_ssh_ctxt_timestamp_ms = timestamp_ms
        
        # Build tier1 data structure
        tier1_data = {
            'context_switches': ctx_switches_per_sec,
            'load_avg': {
                '1min': raw_data.get('load_avg_1m', 0),
                '5min': raw_data.get('load_avg_5m', 0),
                '15min': raw_data.get('load_avg_15m', 0)
            },
            'process_counts': {
                'running': raw_data.get('procs_running', 0),
                'blocked': raw_data.get('procs_blocked', 0),
                'total': 0  # Not available from remote monitoring
            }
        }
        
        # Add interrupt data if available and calculate rates
        interrupt_data = raw_data.get('interrupt_data')
        if interrupt_data and isinstance(interrupt_data, dict) and 'interrupts' in interrupt_data:
            # Calculate rates (interrupts per second) from delta
            if not hasattr(self, '_prev_ssh_interrupts'):
                self._prev_ssh_interrupts = {}
            
            irq_list = interrupt_data.get('interrupts', [])
            
            # Calculate rate for each interrupt
            for irq in irq_list:
                irq_key = irq.get('irq', '') or irq.get('name', '')
                curr_total = irq.get('total', 0)
                
                if irq_key in self._prev_ssh_interrupts and prev_timestamp_for_irq > 0 and timestamp_ms > prev_timestamp_for_irq:
                    prev_total = self._prev_ssh_interrupts[irq_key]
                    delta = curr_total - prev_total
                    delta_time_ms = timestamp_ms - prev_timestamp_for_irq
                    if delta >= 0 and delta_time_ms > 0:
                        irq['rate'] = int((delta * 1000.0) / delta_time_ms)
                    else:
                        irq['rate'] = 0
                else:
                    # First sample - no rate available
                    irq['rate'] = 0
                
                # Update previous value
                self._prev_ssh_interrupts[irq_key] = curr_total
            
            # Sort by RATE (current activity) not total (cumulative)
            irq_list.sort(key=lambda x: x.get('rate', 0), reverse=True)
            
            # Update the interrupt data with sorted list
            interrupt_data['interrupts'] = irq_list
            tier1_data['interrupts'] = interrupt_data
        
        # Add per-core IRQ/softirq percentages if available
        per_core_irq = raw_data.get('per_core_irq_pct')
        if per_core_irq:
            try:
                tier1_data['per_core_irq_pct'] = [float(x) for x in per_core_irq.split(',') if x]
            except:
                tier1_data['per_core_irq_pct'] = []
        
        per_core_softirq = raw_data.get('per_core_softirq_pct')
        if per_core_softirq:
            try:
                tier1_data['per_core_softirq_pct'] = [float(x) for x in per_core_softirq.split(',') if x]
            except:
                tier1_data['per_core_softirq_pct'] = []
        
        # FIX: Remove caching - return fresh data
        return tier1_data
    
    def get_source_name(self) -> str:
        """Get data source name."""
        return f"Remote Linux ({self.host}:{self.port})"
    
    def get_timestamp_ms(self) -> int:
        """Get remote Linux device timestamp in milliseconds (UTC).
        
        Returns:
            UTC timestamp in milliseconds from remote device
        """
        raw_data = self.ssh_monitor.get_latest_data()
        if raw_data:
            return raw_data.get('timestamp_ms', 0)
        return 0
    
    def _empty_cpu_info(self) -> Dict:
        """Return empty CPU info."""
        return {
            'cpu_count': 0,
            'physical_count': 0,
            'usage': {'total': 0, 'per_core': []},
            'frequency': {'average': 0, 'per_core': []},
            'temperature': {}
        }
    
    def _empty_memory_info(self) -> Dict:
        """Return empty memory info."""
        return {
            'memory': {'total': 0, 'used': 0, 'free': 0, 'available': 0, 'percent': 0, 'speed': 0},
            'swap': {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
        }
    
    def _empty_network_info(self) -> Dict:
        """Return empty network info."""
        return {
            'upload_speed': 0,
            'download_speed': 0,
            'connections': {'total': 0, 'tcp_established': 0},
            'interfaces': [],
            'interface_stats': {},
            'io_stats': {'upload_speed': 0, 'download_speed': 0, 'packets_sent': 0, 'packets_recv': 0}
        }
    
    def _empty_disk_info(self) -> Dict:
        """Return empty disk info."""
        return {
            'read_speed_mb': 0,
            'write_speed_mb': 0,
            'partitions': {},
            'disks': [],
            'io_stats': {
                'read_speed': 0, 'write_speed': 0,
                'read_speed_mb': 0, 'write_speed_mb': 0,
                'read_iops': 0, 'write_iops': 0
            },
            'partition_usage': []
        }


class RemoteWindowsDataSource(MonitorDataSource):
    """Remote Windows system data source via WMI/SSH.
    
    TODO: Implement WMI or SSH-based monitoring for remote Windows systems.
    """
    
    def __init__(self, host: str, username: str = None, password: str = None):
        """Initialize remote Windows data source.
        
        Args:
            host: Remote host address
            username: Windows username
            password: Windows password
        """
        self.host = host
        self.username = username
        self.password = password
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to remote Windows system."""
        # TODO: Implement WMI connection using wmi or pypsexec
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def disconnect(self):
        """Disconnect from remote system."""
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information from remote system."""
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def get_memory_info(self) -> Dict:
        """Get memory information from remote system."""
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information from remote system."""
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def get_npu_info(self) -> Dict:
        """Get NPU information from remote system."""
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def get_network_info(self) -> Dict:
        """Get network information from remote system."""
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def get_disk_info(self) -> Dict:
        """Get disk information from remote system."""
        raise NotImplementedError("Remote Windows monitoring not yet implemented")
    
    def get_source_name(self) -> str:
        """Get data source name."""
        return f"Remote Windows ({self.host})"


