# Data Source Proxy Architecture

## Overview

The monitor-tool now uses a **Data Source Proxy Pattern** to abstract data collection from different sources. This enables monitoring of:

- **Local System**: Using psutil-based monitors (default)
- **Android Devices**: Via ADB streaming (implemented)
- **Remote Linux**: Via SSH (planned)
- **Remote Windows**: Via WMI (planned)

## Architecture

```
┌─────────────────────┐
│  MainWindow (UI)    │
│  ┌───────────────┐  │
│  │ data_source   │  │  ← Single proxy instance
│  └───────┬───────┘  │
└──────────┼──────────┘
           │
           ▼
┌──────────────────────┐
│ MonitorDataSource    │  ← Abstract base class
│ (ABC)                │
└──────────┬───────────┘
           │
           ├─► LocalDataSource ────► psutil monitors
           │
           ├─► AndroidDataSource ──► ADB streaming
           │
           ├─► RemoteLinuxDataSource  (TODO: SSH)
           │
           └─► RemoteWindowsDataSource (TODO: WMI)
```

## Interface

All data sources implement the same interface:

```python
class MonitorDataSource(ABC):
    def connect(self) -> bool
    def disconnect(self)
    def is_connected(self) -> bool
    def get_cpu_info(self) -> Dict
    def get_memory_info(self) -> Dict
    def get_gpu_info(self) -> Dict
    def get_npu_info(self) -> Dict
    def get_network_info(self) -> Dict
    def get_disk_info(self) -> Dict
    def get_source_name(self) -> str
```

## Usage

### Local Monitoring (Default)

```bash
python3 src/main.py
```

```python
from data_source import LocalDataSource

ds = LocalDataSource()
ds.connect()
cpu_info = ds.get_cpu_info()
```

### Android Monitoring

```bash
python3 src/main.py --adb --ip 192.168.1.68
```

```python
from data_source import AndroidDataSource

ds = AndroidDataSource("192.168.1.68", 5555)
ds.connect()  # Starts ADB streaming
cpu_info = ds.get_cpu_info()
```

### Custom Data Source

Create a custom data source by inheriting from `MonitorDataSource`:

```python
class RemoteLinuxDataSource(MonitorDataSource):
    def __init__(self, host: str, user: str):
        self.ssh_client = SSHClient()
        # ...
    
    def connect(self) -> bool:
        # SSH connection logic
        pass
    
    def get_cpu_info(self) -> Dict:
        # SSH command execution
        pass
```

## Benefits

1. **Extensibility**: Easy to add new data sources (SSH, WMI, cloud APIs)
2. **Clean UI Code**: UI is completely agnostic to data source
3. **Testability**: Mock data sources for testing
4. **Consistency**: Single interface for all sources
5. **Flexibility**: Switch between sources without UI changes

## Migration from Old Architecture

### Before (Direct Monitors)

```python
class MainWindow:
    def __init__(self):
        self.cpu_monitor = CPUMonitor()
        self.memory_monitor = MemoryMonitor()
        self.gpu_monitor = GPUMonitor()
        # ...
    
    def update_data(self):
        cpu_info = self.cpu_monitor.get_all_info()
        mem_info = self.memory_monitor.get_all_info()
```

### After (Proxy Pattern)

```python
class MainWindow:
    def __init__(self, data_source=None):
        if data_source is None:
            data_source = LocalDataSource()
        self.data_source = data_source
        self.data_source.connect()
    
    def update_data(self):
        cpu_info = self.data_source.get_cpu_info()
        mem_info = self.data_source.get_memory_info()
```

## Data Format

All data sources return data in a standardized format:

### CPU Info
```python
{
    'cpu_count': 12,
    'physical_count': 6,
    'usage': {'total': 25.5, 'per_core': [...]},
    'frequency': {'average': 2400, 'per_core': [...]},
    'temperature': {...}
}
```

### Memory Info
```python
{
    'memory': {
        'total': 62.5, 'used': 20.9, 'free': 41.6,
        'available': 41.6, 'percent': 33.4
    },
    'swap': {'total': 2.0, 'used': 0.5, 'free': 1.5, 'percent': 25.0}
}
```

### Network Info
```python
{
    'upload_speed': 102400,      # bytes/sec
    'download_speed': 204800,    # bytes/sec
    'connections': {'total': 150, 'tcp_established': 80},
    'interfaces': [...],
    'interface_stats': {...}
}
```

### Disk Info
```python
{
    'read_speed_mb': 10.5,
    'write_speed_mb': 5.2,
    'partitions': {'/': {'used': 50.0, 'total': 100.0, 'percent': 50.0}},
    'io_stats': {...}
}
```

## Testing

Run the test suite:

```bash
python3 tests/test_data_source.py
```

Tests verify:
- ✅ LocalDataSource returns valid data
- ✅ AndroidDataSource handles disconnected state
- ✅ Data format consistency
- ✅ Source name reporting

## Future Enhancements

1. **Remote Linux (SSH)**:
   - Execute monitoring commands over SSH
   - Parse remote psutil output
   - Handle authentication (key-based, password)

2. **Remote Windows (WMI)**:
   - Use WMI queries for Windows metrics
   - Handle PowerShell remoting
   - Cross-platform compatibility

3. **Cloud Monitoring**:
   - AWS CloudWatch integration
   - Azure Monitor integration
   - Google Cloud Monitoring

4. **Data Caching**:
   - Cache remote data to reduce network calls
   - Configurable refresh intervals
   - Stale data detection

5. **Connection Pooling**:
   - Reuse SSH/WMI connections
   - Connection health checks
   - Automatic reconnection

## Files Changed

- `src/data_source.py`: **NEW** - Data source abstraction layer
- `src/main.py`: Updated to use data_source pattern
- `src/ui/main_window.py`: Refactored to use data_source proxy
- `tests/test_data_source.py`: **NEW** - Test suite
