import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.monitors.process_monitor import ProcessMonitor, ProcessInfo

class TestProcessMonitor:
    @pytest.fixture
    def config(self):
        return {
            'enabled': True,
            'update_interval': 1000,
            'process_count': 5,
            'sort_by': 'cpu',
            'cmdline_max_length': 50,
            'thresholds': {
                'cpu_warning': 50.0,
                'cpu_critical': 80.0,
                'memory_warning': 1024 * 1024 * 1024,
                'memory_critical': 2 * 1024 * 1024 * 1024
            }
        }

    def test_initialization(self, config):
        monitor = ProcessMonitor(config)
        assert monitor.enabled is True
        assert monitor.process_count == 5
        assert monitor.sort_by == 'cpu'
        assert monitor.mode == 'local'

    @patch('psutil.process_iter')
    def test_get_local_processes(self, mock_process_iter, config):
        # Mock psutil processes
        mock_procs = []
        for i in range(10):
            p = MagicMock()
            p.info = {
                'pid': i,
                'name': f'proc_{i}',
                'cpu_percent': float(i * 10),
                'memory_info': MagicMock(rss=100*1024*1024, vms=200*1024*1024),
                'cmdline': [f'proc_{i}', 'arg'],
                'status': 'running',
                'num_threads': 2,
                'create_time': 1000.0
            }
            mock_procs.append(p)
        
        mock_process_iter.return_value = mock_procs
        
        monitor = ProcessMonitor(config)
        processes = monitor.get_top_processes()
        
        assert len(processes) == 5
        assert processes[0].cpu_percent == 90.0  # Highest CPU first
        assert processes[0].name == 'proc_9'

    def test_sort_by_memory(self, config):
        config['sort_by'] = 'memory'
        monitor = ProcessMonitor(config)
        
        procs = [
            ProcessInfo(1, 'p1', 10.0, 100, 0, '', '', 0, 0, datetime.now()),
            ProcessInfo(2, 'p2', 20.0, 200, 0, '', '', 0, 0, datetime.now()),
            ProcessInfo(3, 'p3', 5.0, 300, 0, '', '', 0, 0, datetime.now())
        ]
        
        sorted_procs = monitor._sort_processes(procs)
        assert sorted_procs[0].name == 'p3'  # Highest memory
        assert sorted_procs[1].name == 'p2'
        assert sorted_procs[2].name == 'p1'

    def test_severity(self, config):
        monitor = ProcessMonitor(config)
        
        normal = ProcessInfo(1, 'n', 10.0, 100, 0, '', '', 0, 0, datetime.now())
        warning = ProcessInfo(2, 'w', 60.0, 100, 0, '', '', 0, 0, datetime.now())
        critical = ProcessInfo(3, 'c', 90.0, 100, 0, '', '', 0, 0, datetime.now())
        
        assert monitor.get_severity(normal) == 'normal'
        assert monitor.get_severity(warning) == 'warning'
        assert monitor.get_severity(critical) == 'critical'
