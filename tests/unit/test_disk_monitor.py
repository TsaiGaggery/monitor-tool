"""Unit tests for DiskMonitor with mocked psutil."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from monitors.disk_monitor import DiskMonitor


class TestDiskMonitorInit:
    """Test DiskMonitor initialization."""
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_init_creates_instance(self, mock_time, mock_counters):
        """Test that DiskMonitor can be instantiated."""
        mock_time.return_value = 1000.0
        
        mock_sda = MagicMock()
        mock_sda.read_bytes = 1000
        mock_sda.write_bytes = 2000
        mock_sda.read_count = 10
        mock_sda.write_count = 20
        
        mock_counters.return_value = {'sda': mock_sda}
        
        monitor = DiskMonitor()
        assert monitor is not None
        assert 'sda' in monitor.last_counters
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    def test_init_handles_exception(self, mock_counters):
        """Test initialization handles exceptions gracefully."""
        mock_counters.side_effect = Exception("Disk error")
        
        monitor = DiskMonitor()
        assert monitor.last_counters == {}


class TestDiskMonitorGetDisks:
    """Test disk listing."""
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_disks_exclude_virtual(self, mock_time, mock_counters):
        """Test getting disk list excluding virtual devices."""
        mock_time.return_value = 1000.0
        
        mock_sda = MagicMock()
        mock_loop0 = MagicMock()
        mock_nvme = MagicMock()
        
        for mock_disk in [mock_sda, mock_loop0, mock_nvme]:
            mock_disk.read_bytes = 0
            mock_disk.write_bytes = 0
            mock_disk.read_count = 0
            mock_disk.write_count = 0
        
        mock_counters.return_value = {
            'sda': mock_sda,
            'loop0': mock_loop0,
            'nvme0n1': mock_nvme
        }
        
        monitor = DiskMonitor()
        disks = monitor.get_disks(exclude_virtual=True)
        
        assert 'sda' in disks
        assert 'nvme0n1' in disks
        assert 'loop0' not in disks
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_disks_include_virtual(self, mock_time, mock_counters):
        """Test getting disk list including virtual devices."""
        mock_time.return_value = 1000.0
        
        mock_loop0 = MagicMock()
        mock_loop0.read_bytes = 0
        mock_loop0.write_bytes = 0
        mock_loop0.read_count = 0
        mock_loop0.write_count = 0
        
        mock_counters.return_value = {'loop0': mock_loop0}
        
        monitor = DiskMonitor()
        disks = monitor.get_disks(exclude_virtual=False)
        
        assert 'loop0' in disks


class TestDiskMonitorPartitions:
    """Test partition information."""
    
    @patch('monitors.disk_monitor.psutil.disk_partitions')
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_partitions(self, mock_time, mock_counters, mock_partitions):
        """Test getting partition list."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        
        mock_part = MagicMock()
        mock_part.device = '/dev/sda1'
        mock_part.mountpoint = '/'
        mock_part.fstype = 'ext4'
        mock_part.opts = 'rw,relatime'
        
        mock_partitions.return_value = [mock_part]
        
        monitor = DiskMonitor()
        partitions = monitor.get_partitions()
        
        assert len(partitions) == 1
        assert partitions[0]['device'] == '/dev/sda1'
        assert partitions[0]['mountpoint'] == '/'
        assert partitions[0]['fstype'] == 'ext4'


class TestDiskMonitorPartitionUsage:
    """Test partition usage statistics."""
    
    @patch('monitors.disk_monitor.psutil.disk_usage')
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_partition_usage(self, mock_time, mock_counters, mock_usage):
        """Test getting partition usage."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        
        mock_usage_obj = MagicMock()
        mock_usage_obj.total = 100 * (1024**3)  # 100 GB
        mock_usage_obj.used = 50 * (1024**3)   # 50 GB
        mock_usage_obj.free = 50 * (1024**3)
        mock_usage_obj.percent = 50.0
        
        mock_usage.return_value = mock_usage_obj
        
        monitor = DiskMonitor()
        usage = monitor.get_partition_usage('/')
        
        assert usage['total'] == pytest.approx(100.0, rel=0.1)
        assert usage['used'] == pytest.approx(50.0, rel=0.1)
        assert usage['free'] == pytest.approx(50.0, rel=0.1)
        assert usage['percent'] == 50.0
        assert usage['path'] == '/'
    
    @patch('monitors.disk_monitor.psutil.disk_partitions')
    @patch('monitors.disk_monitor.psutil.disk_usage')
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_all_partition_usage(self, mock_time, mock_counters, mock_usage, mock_partitions):
        """Test getting usage for all partitions."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        
        # Mock partitions
        mock_part = MagicMock()
        mock_part.device = '/dev/sda1'
        mock_part.mountpoint = '/'
        mock_part.fstype = 'ext4'
        mock_partitions.return_value = [mock_part]
        
        # Mock usage
        mock_usage_obj = MagicMock()
        mock_usage_obj.total = 100 * (1024**3)
        mock_usage_obj.used = 50 * (1024**3)
        mock_usage_obj.free = 50 * (1024**3)
        mock_usage_obj.percent = 50.0
        mock_usage.return_value = mock_usage_obj
        
        monitor = DiskMonitor()
        usage_list = monitor.get_all_partition_usage()
        
        assert len(usage_list) == 1
        assert usage_list[0]['device'] == '/dev/sda1'
        assert usage_list[0]['fstype'] == 'ext4'


class TestDiskMonitorIOStats:
    """Test disk I/O statistics."""
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_io_stats_total(self, mock_time, mock_counters):
        """Test getting total I/O statistics."""
        mock_time.side_effect = [1000.0, 1000.0, 1001.0]
        
        # Mock init
        mock_init = MagicMock()
        mock_init.read_bytes = 1000
        mock_init.write_bytes = 2000
        mock_init.read_count = 10
        mock_init.write_count = 20
        mock_init.read_time = 100
        mock_init.write_time = 200
        
        # Mock current
        mock_current = MagicMock()
        mock_current.read_bytes = 2000  # +1000 bytes
        mock_current.write_bytes = 4000  # +2000 bytes
        mock_current.read_count = 20
        mock_current.write_count = 40
        mock_current.read_time = 200
        mock_current.write_time = 400
        
        mock_counters.side_effect = [
            {'total': mock_init},
            mock_current
        ]
        
        monitor = DiskMonitor()
        stats = monitor.get_io_stats()
        
        assert 'read_speed' in stats
        assert 'write_speed' in stats
        assert stats['read_speed'] == 1000.0  # bytes/sec
        assert stats['write_speed'] == 2000.0  # bytes/sec
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_io_stats_specific_disk(self, mock_time, mock_counters):
        """Test getting I/O stats for specific disk."""
        mock_time.side_effect = [1000.0, 1000.0, 1001.0]
        
        mock_sda_init = MagicMock()
        mock_sda_init.read_bytes = 1000
        mock_sda_init.write_bytes = 2000
        mock_sda_init.read_count = 10
        mock_sda_init.write_count = 20
        mock_sda_init.read_time = 100
        mock_sda_init.write_time = 200
        
        mock_sda_current = MagicMock()
        mock_sda_current.read_bytes = 3000
        mock_sda_current.write_bytes = 5000
        mock_sda_current.read_count = 30
        mock_sda_current.write_count = 50
        mock_sda_current.read_time = 300
        mock_sda_current.write_time = 500
        
        mock_counters.side_effect = [
            {'sda': mock_sda_init},
            {'sda': mock_sda_current}
        ]
        
        monitor = DiskMonitor()
        stats = monitor.get_io_stats('sda')
        
        assert 'read_speed' in stats
        assert 'write_speed' in stats
        assert stats['read_speed'] == 2000.0
        assert stats['write_speed'] == 3000.0


class TestDiskMonitorGetAllInfo:
    """Test get_all_info comprehensive method."""
    
    @patch('monitors.disk_monitor.psutil.disk_partitions')
    @patch('monitors.disk_monitor.psutil.disk_usage')
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_all_info(self, mock_time, mock_counters, mock_usage, mock_partitions):
        """Test getting all disk information."""
        mock_time.side_effect = [1000.0, 1000.0, 1001.0]
        
        # Mock IO counters
        mock_sda_init = MagicMock()
        mock_sda_init.read_bytes = 0
        mock_sda_init.write_bytes = 0
        mock_sda_init.read_count = 0
        mock_sda_init.write_count = 0
        mock_sda_init.read_time = 0
        mock_sda_init.write_time = 0
        
        mock_sda_current = MagicMock()
        mock_sda_current.read_bytes = 1000
        mock_sda_current.write_bytes = 2000
        mock_sda_current.read_count = 10
        mock_sda_current.write_count = 20
        mock_sda_current.read_time = 100
        mock_sda_current.write_time = 200
        
        mock_counters.side_effect = [
            {'sda': mock_sda_init},  # Init
            {'sda': mock_sda_init},  # get_disks
            {},  # get_all_partition_usage -> get_partitions
            {'sda': mock_sda_current}  # get_io_stats
        ]
        
        # Mock partitions
        mock_partitions.return_value = []
        
        monitor = DiskMonitor()
        info = monitor.get_all_info()
        
        assert 'disks' in info
        assert 'partitions' in info
        assert 'io_stats' in info
        assert isinstance(info['disks'], list)
        assert isinstance(info['partitions'], list)
        assert isinstance(info['io_stats'], dict)


class TestDiskMonitorEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_disks_exception(self, mock_time, mock_counters):
        """Test disk listing exception handling."""
        mock_time.return_value = 1000.0
        mock_counters.side_effect = [
            {},  # Init
            Exception("Disk error")  # get_disks
        ]
        
        monitor = DiskMonitor()
        disks = monitor.get_disks()
        
        assert disks == []
    
    @patch('monitors.disk_monitor.psutil.disk_partitions')
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_partitions_exception(self, mock_time, mock_counters, mock_partitions):
        """Test partition listing exception handling."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        mock_partitions.side_effect = Exception("Partition error")
        
        monitor = DiskMonitor()
        partitions = monitor.get_partitions()
        
        assert partitions == []
    
    @patch('monitors.disk_monitor.psutil.disk_usage')
    @patch('monitors.disk_monitor.psutil.disk_io_counters')
    @patch('monitors.disk_monitor.time.time')
    def test_get_partition_usage_exception(self, mock_time, mock_counters, mock_usage):
        """Test partition usage exception handling."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        mock_usage.side_effect = Exception("Usage error")
        
        monitor = DiskMonitor()
        usage = monitor.get_partition_usage('/nonexistent')
        
        assert usage == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
