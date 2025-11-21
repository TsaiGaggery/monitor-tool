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

    def test_get_ssh_processes(self, config):
        # Mock SSH client
        mock_ssh = MagicMock()
        
        # Mock output for the first call (initialization)
        # 1. Page size
        # 2. CPU count
        # 3. Total CPU stats
        # 4. Process stats
        output_lines_1 = [
            "4096\n",
            "4\n",
            "cpu  1000 0 1000 8000 0 0 0 0\n", # Total: 10000 ticks
            # pid (comm) state ppid ... utime stime ... num_threads ... starttime vsize rss
            # Fields: 0=pid, 1=comm, 2=state, 13=utime, 14=stime, 19=threads, 21=start, 22=vsize, 23=rss
            # We need to construct a valid stat line.
            # 1234 (python) S 1 0 0 0 0 0 0 0 0 0 100 100 0 0 0 0 4 0 0 20480 1000\n
            "1234 (python) S 1 0 0 0 0 0 0 0 0 0 100 100 0 0 0 0 4 0 0 20480 1000\n",
            "5678 (java) R 1 0 0 0 0 0 0 0 0 0 200 200 0 0 0 0 10 0 0 102400 5000\n"
        ]
        
        # Mock output for the second call (delta calculation)
        output_lines_2 = [
            "4096\n",
            "4\n",
            "cpu  2000 0 2000 16000 0 0 0 0\n", # Total: 20000 ticks (Delta: 10000)
            # python: +50 ticks (250 total) -> 50/10000 * 100 * 4 = 2.0%
            "1234 (python) S 1 0 0 0 0 0 0 0 0 0 125 125 0 0 0 0 4 0 0 20480 1000\n",
            # java: +200 ticks (600 total) -> 200/10000 * 100 * 4 = 8.0%
            "5678 (java) R 1 0 0 0 0 0 0 0 0 0 300 300 0 0 0 0 10 0 0 102400 5000\n"
        ]
        
        # Mock output for cmdline fetch
        cmdline_output = [
            "1234 python main.py\n",
            "5678 java -jar app.jar\n"
        ]
        
        # Setup mock side effects
        mock_stdout_1 = MagicMock()
        mock_stdout_1.readlines.return_value = output_lines_1
        
        mock_stdout_2 = MagicMock()
        mock_stdout_2.readlines.return_value = output_lines_2
        
        mock_stdout_cmd = MagicMock()
        mock_stdout_cmd.readlines.return_value = cmdline_output
        
        # Sequence of calls:
        # 1. get_top_processes -> exec_command (stats) -> returns output_lines_1
        #    -> exec_command (cmdline) -> returns cmdline_output
        # 2. get_top_processes -> exec_command (stats) -> returns output_lines_2
        #    -> exec_command (cmdline) -> returns cmdline_output
        
        mock_ssh.exec_command.side_effect = [
            (None, mock_stdout_1, None),
            (None, mock_stdout_cmd, None),
            (None, mock_stdout_2, None),
            (None, mock_stdout_cmd, None)
        ]
        
        monitor = ProcessMonitor(config, mode='ssh', ssh_client=mock_ssh)
        
        # First call initializes cache
        processes_1 = monitor.get_top_processes()
        assert len(processes_1) == 2
        assert processes_1[0].cpu_percent == 0.0 # First run has 0 CPU
        
        # Advance time to bypass cache check
        monitor._last_update = 0
        
        # Second call calculates delta
        processes_2 = monitor.get_top_processes()
        
        assert len(processes_2) == 2
        
        # Check parsing and calculation
        p_java = next(p for p in processes_2 if p.pid == 5678)
        assert p_java.name == 'java'
        assert abs(p_java.cpu_percent - 8.0) < 0.1
        assert p_java.memory_rss == 5000 * 4096
        assert p_java.status == 'R'
        assert p_java.num_threads == 10
        assert 'java -jar app.jar' in p_java.cmdline
        
        p_python = next(p for p in processes_2 if p.pid == 1234)
        assert abs(p_python.cpu_percent - 2.0) < 0.1
        
        # Verify command execution
        assert mock_ssh.exec_command.call_count == 4
        args = mock_ssh.exec_command.call_args_list[2][0][0] # Third call (second stats call)
        assert 'cat /proc/stat' in args

    @patch('subprocess.run')
    def test_get_adb_processes(self, mock_run, config):
        # Mock ADB output
        # Header + 2 processes
        stdout_output = """
Tasks: 589 total,   1 running, 584 sleeping,   0 stopped,   0 zombie
Mem:   5854652k total,  5643212k used,   211440k free,    89420k buffers
Swap:  2621436k total,   642140k used,  1979296k free,  2341240k cached
800%cpu  17%user   0%nice  13%sys 768%idle   0%iowait   0%irq   2%softirq
  PID USER         PR  NI VIRT  RES  SHR S %CPU %MEM     TIME+ ARGS
12345 system       10 -10 4.5G 150M 100M S 15.3   2.5   0:15.32 com.android.systemui
 6789 u0_a123      20   0 1.2G  50M  20M R  5.0   0.8   0:02.10 com.example.app
"""
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout_output)
        
        monitor = ProcessMonitor(config, mode='adb', adb_device='192.168.1.100:5555')
        processes = monitor.get_top_processes()
        
        assert len(processes) == 2
        
        # Check parsing
        p1 = next(p for p in processes if p.pid == 12345)
        assert p1.name == 'com.android.systemui'
        assert p1.cpu_percent == 15.3
        assert p1.memory_rss == 150 * 1024 * 1024
        assert p1.status == 'S'
        
        # Verify command execution
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'adb'
        assert 'top' in args
