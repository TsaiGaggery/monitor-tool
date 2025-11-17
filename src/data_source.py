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
    
    def __init__(self):
        """Initialize local data source."""
        from monitors import (CPUMonitor, MemoryMonitor, GPUMonitor, 
                            NPUMonitor, NetworkMonitor, DiskMonitor)
        
        self.cpu_monitor = CPUMonitor()
        self.memory_monitor = MemoryMonitor()
        self.gpu_monitor = GPUMonitor()
        self.npu_monitor = NPUMonitor()
        self.network_monitor = NetworkMonitor()
        self.disk_monitor = DiskMonitor()
        self._connected = True
    
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


class AndroidDataSource(MonitorDataSource):
    """Android device data source via ADB (raw data version)."""
    
    def __init__(self, device_ip: str, port: int = 5555):
        """Initialize Android data source.
        
        Args:
            device_ip: Android device IP address
            port: ADB port (default: 5555)
        """
        from monitors.adb_monitor_raw import ADBMonitorRaw
        
        self.device_ip = device_ip
        self.port = port
        self.adb_monitor = None
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to Android device via ADB."""
        try:
            from monitors.adb_monitor_raw import ADBMonitorRaw
            
            # ADBMonitorRaw automatically starts streaming in __init__
            self.adb_monitor = ADBMonitorRaw(self.device_ip, self.port)
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
        return self.adb_monitor.get_cpu_info()
    
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
    
    TODO: Implement SSH-based monitoring for remote Linux systems.
    """
    
    def __init__(self, host: str, port: int = 22, username: str = None, password: str = None):
        """Initialize remote Linux data source.
        
        Args:
            host: Remote host address
            port: SSH port (default: 22)
            username: SSH username
            password: SSH password (or use key-based auth)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to remote Linux system via SSH."""
        # TODO: Implement SSH connection using paramiko
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def disconnect(self):
        """Disconnect from remote system."""
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information from remote system."""
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def get_memory_info(self) -> Dict:
        """Get memory information from remote system."""
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def get_gpu_info(self) -> Dict:
        """Get GPU information from remote system."""
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def get_npu_info(self) -> Dict:
        """Get NPU information from remote system."""
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def get_network_info(self) -> Dict:
        """Get network information from remote system."""
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def get_disk_info(self) -> Dict:
        """Get disk information from remote system."""
        raise NotImplementedError("Remote Linux monitoring not yet implemented")
    
    def get_source_name(self) -> str:
        """Get data source name."""
        return f"Remote Linux ({self.host}:{self.port})"


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
