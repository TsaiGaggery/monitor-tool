import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from monitors.adb_monitor_raw import ADBMonitorRaw

class TestADBMonitorRawLogic:
    @pytest.fixture
    def monitor(self):
        with patch('subprocess.run') as mock_run, patch('threading.Thread'):
            # Configure mock to simulate successful connection
            mock_run.return_value.stdout = "connected to 127.0.0.1:5555"
            
            # Mock start_streaming to avoid waiting
            with patch.object(ADBMonitorRaw, 'start_streaming') as mock_start:
                monitor = ADBMonitorRaw('127.0.0.1')
                # Stop the streaming thread/process mock to avoid side effects
                monitor._running = False
                return monitor

    def test_process_persistence(self, monitor):
        import inspect
        print(f"DEBUG: ADBMonitorRaw file: {inspect.getfile(ADBMonitorRaw)}")
        print(f"DEBUG: monitor object: {monitor}")
        
        # Initial state: empty
        assert monitor.get_process_info() == []

        # Simulate stream: Process line
        process_line = {"type":"process","pid":1,"name":"proc1","cpu":10.0,"mem":1024,"cmd":"proc1"}
        monitor._process_process_line(process_line)
        
        # Verify temp batch
        assert len(monitor._temp_process_batch) == 1
        
        # Simulate stream: Metrics line (triggers commit in _stream_worker)
        # We manually trigger the commit logic here since we are not running _stream_worker
        with monitor._data_lock:
             if monitor._temp_process_batch:
                 monitor._process_info = list(monitor._temp_process_batch)
                 monitor._temp_process_batch = []

        # Sample 1: Metrics
        sample1 = {
            'timestamp_ms': 1000,
            'cpu_raw': {'user': 10, 'nice': 0, 'sys': 10, 'idle': 80, 'iowait': 0, 'irq': 0, 'softirq': 0, 'steal': 0},
            'per_core_raw': [],
            'per_core_freq_khz': [],
            'cpu_temp_millideg': 40000,
            'gpu_freq_mhz': 0,
            'net_rx_bytes': 1000,
            'net_tx_bytes': 1000,
            'disk_read_sectors': 100,
            'disk_write_sectors': 100,
            'mem_total_kb': 8000000,
            'mem_used_kb': 4000000,
            'mem_free_kb': 4000000,
            'mem_available_kb': 4000000,
            'swap_total_kb': 0,
            'swap_used_kb': 0,
            'swap_free_kb': 0,
            'gpu_memory_used_bytes': 0,
            'gpu_memory_total_bytes': 0
        }
        
        monitor._process_raw_data(sample1)
        
        assert len(monitor.get_process_info()) == 1
        assert monitor.get_process_info()[0].name == 'proc1'

        # Sample 2: Without processes (sparse update)
        # No process lines received, so temp batch is empty
        # Commit logic runs but doesn't change _process_info
        with monitor._data_lock:
             if monitor._temp_process_batch:
                 monitor._process_info = list(monitor._temp_process_batch)
                 monitor._temp_process_batch = []

        sample2 = {
            'timestamp_ms': 2000,
            'cpu_raw': {'user': 20, 'nice': 0, 'sys': 20, 'idle': 60, 'iowait': 0, 'irq': 0, 'softirq': 0, 'steal': 0},
            'per_core_raw': [],
            'per_core_freq_khz': [],
            'cpu_temp_millideg': 41000,
            'gpu_freq_mhz': 0,
            'net_rx_bytes': 2000,
            'net_tx_bytes': 2000,
            'disk_read_sectors': 200,
            'disk_write_sectors': 200,
            'mem_total_kb': 8000000,
            'mem_used_kb': 4100000,
            'mem_free_kb': 3900000,
            'mem_available_kb': 3900000,
            'swap_total_kb': 0,
            'swap_used_kb': 0,
            'swap_free_kb': 0,
            'gpu_memory_used_bytes': 0,
            'gpu_memory_total_bytes': 0
        }
        
        monitor._process_raw_data(sample2)
        # Should still return the old processes
        assert len(monitor.get_process_info()) == 1
        assert monitor.get_process_info()[0].name == 'proc1'

        # Sample 3: With new processes
        # Simulate stream: Process line
        process_line2 = {"type":"process","pid":2,"name":"proc2","cpu":20.0,"mem":2048,"cmd":"proc2"}
        monitor._process_process_line(process_line2)
        
        # Simulate stream: Metrics line (triggers commit)
        with monitor._data_lock:
             if monitor._temp_process_batch:
                 monitor._process_info = list(monitor._temp_process_batch)
                 monitor._temp_process_batch = []

        sample3 = {
            'timestamp_ms': 3000,
            'cpu_raw': {'user': 30, 'nice': 0, 'sys': 30, 'idle': 40, 'iowait': 0, 'irq': 0, 'softirq': 0, 'steal': 0},
            'per_core_raw': [],
            'per_core_freq_khz': [],
            'cpu_temp_millideg': 42000,
            'gpu_freq_mhz': 0,
            'net_rx_bytes': 3000,
            'net_tx_bytes': 3000,
            'disk_read_sectors': 300,
            'disk_write_sectors': 300,
            'mem_total_kb': 8000000,
            'mem_used_kb': 4200000,
            'mem_free_kb': 3800000,
            'mem_available_kb': 3800000,
            'swap_total_kb': 0,
            'swap_used_kb': 0,
            'swap_free_kb': 0,
            'gpu_memory_used_bytes': 0,
            'gpu_memory_total_bytes': 0
        }
        
        monitor._process_raw_data(sample3)
        assert len(monitor.get_process_info()) == 1
        assert monitor.get_process_info()[0].name == 'proc2'
