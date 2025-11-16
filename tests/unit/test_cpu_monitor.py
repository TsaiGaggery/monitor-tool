"""Unit tests for CPUMonitor with mocked psutil."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from monitors.cpu_monitor import CPUMonitor


class TestCPUMonitorBasic:
    """Test basic CPUMonitor functionality."""
    
    @patch('monitors.cpu_monitor.psutil')
    def test_init_creates_instance(self, mock_psutil):
        """Test that CPUMonitor can be instantiated."""
        mock_psutil.cpu_count.return_value = 4
        monitor = CPUMonitor()
        assert monitor is not None
        assert monitor.cpu_count == 4
    
    @patch('monitors.cpu_monitor.psutil')
    def test_get_all_info_returns_dict(self, mock_psutil):
        """Test get_all_info returns dictionary."""
        # Mock psutil calls
        mock_psutil.cpu_count.side_effect = lambda logical=True: 8 if logical else 4
        mock_psutil.cpu_percent.side_effect = [50.0, [25.0, 50.0, 75.0, 100.0, 10.0, 20.0, 30.0, 40.0]]
        
        # Mock frequency
        freq_mocks = []
        for i in range(8):
            f = MagicMock()
            f.current = 2400.0
            f.min = 800.0
            f.max = 3600.0
            freq_mocks.append(f)
        mock_psutil.cpu_freq.return_value = freq_mocks
        
        monitor = CPUMonitor()
        info = monitor.get_all_info()
        
        # Should have main keys
        assert isinstance(info, dict)
        assert 'cpu_count' in info
        assert 'physical_count' in info


class TestCPUMonitorMockedData:
    """Test CPUMonitor with fully mocked data."""
    
    @patch('monitors.cpu_monitor.psutil')
    def test_mock_cpu_usage(self, mock_psutil):
        """Test mocked CPU usage."""
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_percent.return_value = 42.5
        
        monitor = CPUMonitor()
        usage = monitor.get_usage()
        
        assert 'total' in usage or 'overall' in usage
        # Just check it returns something reasonable
        assert isinstance(usage, dict)
    
    @patch('monitors.cpu_monitor.psutil')
    @pytest.mark.parametrize("cpu_count", [2, 4, 8, 16])
    def test_various_cpu_counts(self, mock_psutil, cpu_count):
        """Test with various CPU counts."""
        mock_psutil.cpu_count.return_value = cpu_count
        
        monitor = CPUMonitor()
        assert monitor.cpu_count == cpu_count


class TestCPUMonitorThreadSafety:
    """Test thread safety (basic checks)."""
    
    @patch('monitors.cpu_monitor.psutil')
    def test_multiple_calls_dont_crash(self, mock_psutil):
        """Test multiple rapid calls don't cause issues."""
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_percent.return_value = 50.0
        
        monitor = CPUMonitor()
        
        # Call multiple times
        for _ in range(10):
            monitor.get_usage()
        
        # Should complete without error
        assert True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
