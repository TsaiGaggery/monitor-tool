"""Unit tests for MemoryMonitor with mocked psutil."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from monitors.memory_monitor import MemoryMonitor


class TestMemoryMonitorInit:
    """Test MemoryMonitor initialization."""
    
    @patch('monitors.memory_monitor.subprocess.run')
    def test_init_creates_instance(self, mock_subprocess):
        """Test that MemoryMonitor can be instantiated."""
        monitor = MemoryMonitor()
        assert monitor is not None
    
    @patch('monitors.memory_monitor.subprocess.run')
    def test_init_tries_to_get_memory_speed(self, mock_subprocess):
        """Test that initialization attempts to get memory speed."""
        # Mock dmidecode output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Configured Memory Speed: 2667 MT/s"
        mock_subprocess.return_value = mock_result
        
        monitor = MemoryMonitor()
        assert mock_subprocess.called


class TestMemoryMonitorMemoryInfo:
    """Test memory information retrieval."""
    
    @patch('monitors.memory_monitor.subprocess.run')
    @patch('monitors.memory_monitor.psutil.virtual_memory')
    def test_get_memory_info_returns_dict(self, mock_vmem, mock_subprocess):
        """Test get_memory_info returns dictionary with expected keys."""
        # Mock virtual_memory
        mem_mock = MagicMock()
        mem_mock.total = 16 * (1024**3)  # 16 GB
        mem_mock.available = 8 * (1024**3)  # 8 GB
        mem_mock.used = 8 * (1024**3)
        mem_mock.free = 8 * (1024**3)
        mem_mock.percent = 50.0
        mem_mock.buffers = 1 * (1024**3)
        mem_mock.cached = 2 * (1024**3)
        mock_vmem.return_value = mem_mock
        
        monitor = MemoryMonitor()
        info = monitor.get_memory_info()
        
        assert 'total' in info
        assert 'available' in info
        assert 'used' in info
        assert 'free' in info
        assert 'percent' in info
        assert info['percent'] == 50.0
    
    @patch('monitors.memory_monitor.subprocess.run')
    @patch('monitors.memory_monitor.psutil.virtual_memory')
    @pytest.mark.parametrize("total_gb,used_gb,expected_percent", [
        (16, 8, 50.0),
        (32, 16, 50.0),
        (8, 2, 25.0),
    ])
    def test_get_memory_info_various_values(self, mock_vmem, mock_subprocess, 
                                           total_gb, used_gb, expected_percent):
        """Test get_memory_info with various memory values."""
        mem_mock = MagicMock()
        mem_mock.total = total_gb * (1024**3)
        mem_mock.used = used_gb * (1024**3)
        mem_mock.available = (total_gb - used_gb) * (1024**3)
        mem_mock.free = (total_gb - used_gb) * (1024**3)
        mem_mock.percent = expected_percent
        mem_mock.buffers = 0
        mem_mock.cached = 0
        mock_vmem.return_value = mem_mock
        
        monitor = MemoryMonitor()
        info = monitor.get_memory_info()
        
        assert info['total'] == pytest.approx(total_gb, rel=0.01)
        assert info['percent'] == expected_percent


class TestMemoryMonitorSwapInfo:
    """Test swap information retrieval."""
    
    @patch('monitors.memory_monitor.subprocess.run')
    @patch('monitors.memory_monitor.psutil.swap_memory')
    def test_get_swap_info_returns_dict(self, mock_swap, mock_subprocess):
        """Test get_swap_info returns dictionary with expected keys."""
        # Mock swap_memory
        swap_mock = MagicMock()
        swap_mock.total = 4 * (1024**3)  # 4 GB
        swap_mock.used = 1 * (1024**3)
        swap_mock.free = 3 * (1024**3)
        swap_mock.percent = 25.0
        mock_swap.return_value = swap_mock
        
        monitor = MemoryMonitor()
        info = monitor.get_swap_info()
        
        assert 'total' in info
        assert 'used' in info
        assert 'free' in info
        assert 'percent' in info
        assert info['percent'] == 25.0
    
    @patch('monitors.memory_monitor.subprocess.run')
    @patch('monitors.memory_monitor.psutil.swap_memory')
    def test_get_swap_info_no_swap(self, mock_swap, mock_subprocess):
        """Test get_swap_info when no swap is configured."""
        swap_mock = MagicMock()
        swap_mock.total = 0
        swap_mock.used = 0
        swap_mock.free = 0
        swap_mock.percent = 0.0
        mock_swap.return_value = swap_mock
        
        monitor = MemoryMonitor()
        info = monitor.get_swap_info()
        
        assert info['total'] == 0
        assert info['percent'] == 0.0


class TestMemoryMonitorMemorySpeed:
    """Test memory speed detection."""
    
    @patch('monitors.memory_monitor.subprocess.run')
    def test_get_memory_speed_from_dmidecode(self, mock_subprocess):
        """Test memory speed detection from dmidecode."""
        # Mock successful dmidecode output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
Memory Device
    Size: 8192 MB
    Configured Memory Speed: 2667 MT/s
"""
        mock_subprocess.return_value = mock_result
        
        monitor = MemoryMonitor()
        assert monitor._memory_speed == 2667
    
    @patch('monitors.memory_monitor.subprocess.run')
    def test_get_memory_speed_fallback_to_speed(self, mock_subprocess):
        """Test fallback to Speed: field."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
Memory Device
    Size: 8192 MB
    Speed: 3200 MT/s
"""
        mock_subprocess.return_value = mock_result
        
        monitor = MemoryMonitor()
        assert monitor._memory_speed == 3200
    
    @patch('monitors.memory_monitor.subprocess.run')
    def test_get_memory_speed_no_dmidecode(self, mock_subprocess):
        """Test when dmidecode is not available."""
        mock_subprocess.side_effect = FileNotFoundError()
        
        monitor = MemoryMonitor()
        assert monitor._memory_speed is None
    
    @patch('monitors.memory_monitor.subprocess.run')
    def test_get_memory_speed_timeout(self, mock_subprocess):
        """Test timeout handling."""
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired('dmidecode', 2)
        
        monitor = MemoryMonitor()
        assert monitor._memory_speed is None


class TestMemoryMonitorAllInfo:
    """Test get_all_info method."""
    
    @patch('monitors.memory_monitor.subprocess.run')
    @patch('monitors.memory_monitor.psutil.virtual_memory')
    @patch('monitors.memory_monitor.psutil.swap_memory')
    def test_get_all_info_complete(self, mock_swap, mock_vmem, mock_subprocess):
        """Test get_all_info returns complete information."""
        # Mock memory
        mem_mock = MagicMock()
        mem_mock.total = 16 * (1024**3)
        mem_mock.available = 8 * (1024**3)
        mem_mock.used = 8 * (1024**3)
        mem_mock.free = 8 * (1024**3)
        mem_mock.percent = 50.0
        mem_mock.buffers = 0
        mem_mock.cached = 0
        mock_vmem.return_value = mem_mock
        
        # Mock swap
        swap_mock = MagicMock()
        swap_mock.total = 4 * (1024**3)
        swap_mock.used = 1 * (1024**3)
        swap_mock.free = 3 * (1024**3)
        swap_mock.percent = 25.0
        mock_swap.return_value = swap_mock
        
        # Mock dmidecode
        dmidecode_result = MagicMock()
        dmidecode_result.returncode = 0
        dmidecode_result.stdout = "Configured Memory Speed: 2667 MT/s"
        mock_subprocess.return_value = dmidecode_result
        
        monitor = MemoryMonitor()
        info = monitor.get_all_info()
        
        # Should have both memory and swap
        assert 'memory' in info
        assert 'swap' in info
        assert info['memory']['percent'] == 50.0
        assert info['swap']['percent'] == 25.0
        
        # Should have memory speed
        assert 'speed' in info['memory']
        assert info['memory']['speed'] == 2667
    
    @patch('monitors.memory_monitor.subprocess.run')
    @patch('monitors.memory_monitor.psutil.virtual_memory')
    @patch('monitors.memory_monitor.psutil.swap_memory')
    def test_get_all_info_no_speed(self, mock_swap, mock_vmem, mock_subprocess):
        """Test get_all_info when memory speed is not available."""
        # Mock memory
        mem_mock = MagicMock()
        mem_mock.total = 16 * (1024**3)
        mem_mock.available = 8 * (1024**3)
        mem_mock.used = 8 * (1024**3)
        mem_mock.free = 8 * (1024**3)
        mem_mock.percent = 50.0
        mem_mock.buffers = 0
        mem_mock.cached = 0
        mock_vmem.return_value = mem_mock
        
        # Mock swap
        swap_mock = MagicMock()
        swap_mock.total = 0
        swap_mock.used = 0
        swap_mock.free = 0
        swap_mock.percent = 0.0
        mock_swap.return_value = swap_mock
        
        # Mock dmidecode not available
        mock_subprocess.side_effect = FileNotFoundError()
        
        monitor = MemoryMonitor()
        info = monitor.get_all_info()
        
        assert 'memory' in info
        assert 'swap' in info
        # Speed should not be present if not available
        assert 'speed' not in info['memory'] or info['memory'].get('speed') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
