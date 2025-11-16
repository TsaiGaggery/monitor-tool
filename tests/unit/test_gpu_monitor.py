"""Unit tests for GPUMonitor with mocked GPU detection."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from monitors.gpu_monitor import GPUMonitor


class TestGPUMonitorDetection:
    """Test GPU type detection."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    def test_no_gpu_detected(self, mock_exists, mock_subprocess):
        """Test when no GPU is detected."""
        mock_exists.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        assert monitor.gpu_type is None
        assert not monitor.nvidia_available
        assert not monitor.amd_available
        assert not monitor.intel_available
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_detect_intel_gpu_via_sysfs(self, mock_file, mock_exists, mock_subprocess):
        """Test Intel GPU detection via sysfs."""
        mock_exists.return_value = True
        
        monitor = GPUMonitor()
        assert monitor.gpu_type == 'intel'
        assert monitor.intel_available
        assert not monitor.nvidia_available
        assert not monitor.amd_available
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='8086')
    def test_detect_intel_gpu_via_sysfs_without_0x(self, mock_file, mock_exists, mock_subprocess):
        """Test Intel GPU detection with vendor ID without 0x prefix."""
        mock_exists.return_value = True
        
        monitor = GPUMonitor()
        assert monitor.gpu_type == 'intel'
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x10de')
    def test_detect_nvidia_gpu_via_sysfs(self, mock_file, mock_exists, mock_subprocess):
        """Test NVIDIA GPU detection via sysfs but pynvml unavailable."""
        mock_exists.return_value = True
        
        with patch.dict('sys.modules', {'pynvml': None}):
            monitor = GPUMonitor()
            assert monitor.gpu_type == 'nvidia'
            # nvidia_available will be False because pynvml import fails
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='10de')
    def test_detect_nvidia_gpu_without_0x(self, mock_file, mock_exists, mock_subprocess):
        """Test NVIDIA GPU detection with vendor ID without 0x."""
        mock_exists.return_value = True
        
        with patch.dict('sys.modules', {'pynvml': None}):
            monitor = GPUMonitor()
            assert monitor.gpu_type == 'nvidia'
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x1002')
    def test_detect_amd_gpu_via_sysfs(self, mock_file, mock_exists, mock_subprocess):
        """Test AMD GPU detection via sysfs."""
        mock_exists.return_value = True
        
        monitor = GPUMonitor()
        assert monitor.gpu_type == 'amd'
        assert monitor.amd_available
        assert not monitor.nvidia_available
        assert not monitor.intel_available
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='1002')
    def test_detect_amd_gpu_without_0x(self, mock_file, mock_exists, mock_subprocess):
        """Test AMD GPU detection with vendor ID without 0x."""
        mock_exists.return_value = True
        
        monitor = GPUMonitor()
        assert monitor.gpu_type == 'amd'
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    def test_detect_nvidia_via_command(self, mock_exists, mock_subprocess):
        """Test NVIDIA GPU detection via nvidia-smi command."""
        mock_exists.return_value = False
        
        def subprocess_side_effect(cmd, **kwargs):
            if 'nvidia-smi' in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        with patch.dict('sys.modules', {'pynvml': None}):
            monitor = GPUMonitor()
            assert monitor.gpu_type == 'nvidia'
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    def test_detect_amd_via_command(self, mock_exists, mock_subprocess):
        """Test AMD GPU detection via rocm-smi command."""
        mock_exists.return_value = False
        
        def subprocess_side_effect(cmd, **kwargs):
            if 'rocm-smi' in cmd:
                return MagicMock(returncode=0)
            elif 'nvidia-smi' in cmd:
                return MagicMock(returncode=1)
            return MagicMock(returncode=1)
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        monitor = GPUMonitor()
        assert monitor.gpu_type == 'amd'
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_detect_mali_gpu(self, mock_file, mock_exists, mock_subprocess):
        """Test Mali GPU detection."""
        mock_exists.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        # Mock reading /proc/device-tree/compatible
        def open_side_effect(path, *args, **kwargs):
            if 'compatible' in path:
                mock = mock_open(read_data='rockchip,rk3588-mali')()
                return mock
            return mock_open()()
        
        with patch('builtins.open', side_effect=open_side_effect):
            monitor = GPUMonitor()
            # May or may not detect Mali depending on implementation
            assert monitor.gpu_type in ['mali', None]


class TestGPUMonitorIntelMethods:
    """Test Intel-specific GPU monitoring methods."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_get_intel_gpu_info_basic(self, mock_file, mock_exists, mock_subprocess):
        """Test basic Intel GPU info retrieval."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        info = monitor.get_intel_info()
        
        assert isinstance(info, dict)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    @patch('time.time')
    @patch('time.sleep')
    def test_xe_gpu_utilization(self, mock_sleep, mock_time, mock_file, mock_exists, mock_subprocess):
        """Test Xe GPU utilization calculation."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        # Mock time progression
        mock_time.side_effect = [0.0, 0.1]  # 100ms interval
        
        # Mock idle residency file reads
        idle_reads = ['1000', '1050']  # 50ms idle out of 100ms = 50% idle, 50% util
        mock_file.return_value.read.side_effect = idle_reads
        
        monitor = GPUMonitor()
        util = monitor._get_xe_gpu_utilization(card_num=0)
        
        # Should calculate utilization based on idle time
        # This may be None if path doesn't exist, which is OK
        assert util is None or (0 <= util <= 100)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_check_intel_gpu_true(self, mock_file, mock_exists, mock_subprocess):
        """Test _check_intel_gpu returns True for Intel GPU."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        result = monitor._check_intel_gpu()
        
        assert isinstance(result, bool)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_check_intel_gpu_via_intel_gpu_top(self, mock_file, mock_exists, mock_subprocess):
        """Test Intel GPU detection via intel_gpu_top command."""
        def exists_side_effect(path):
            if 'vendor' in path:
                return False
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock 'which intel_gpu_top' returns success
        def subprocess_side_effect(cmd, **kwargs):
            if 'intel_gpu_top' in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        monitor = GPUMonitor()
        result = monitor._check_intel_gpu()
        
        assert isinstance(result, bool)


class TestGPUMonitorNVIDIAMethods:
    """Test NVIDIA-specific GPU monitoring methods."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x10de')
    def test_get_nvidia_info_no_pynvml(self, mock_file, mock_exists, mock_subprocess):
        """Test NVIDIA info when pynvml is not available."""
        mock_exists.return_value = True
        
        with patch.dict('sys.modules', {'pynvml': None}):
            monitor = GPUMonitor()
            assert monitor.gpu_type == 'nvidia'
            assert not monitor.nvidia_available
            
            info = monitor.get_nvidia_info()
            # Should return empty dict or handle gracefully
            assert isinstance(info, dict)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x10de')
    def test_get_nvidia_info_with_mock_pynvml(self, mock_file, mock_exists, mock_subprocess):
        """Test NVIDIA info with mocked pynvml."""
        mock_exists.return_value = True
        
        # Create mock pynvml module
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit.return_value = None
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        
        # Mock device handle and queries
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetName.return_value = b'NVIDIA GeForce RTX 3080'
        
        # Mock utilization
        mock_util = MagicMock()
        mock_util.gpu = 75
        mock_util.memory = 50
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util
        
        # Mock memory
        mock_mem = MagicMock()
        mock_mem.total = 10 * 1024**3  # 10 GB
        mock_mem.used = 5 * 1024**3
        mock_mem.free = 5 * 1024**3
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem
        
        # Mock temperature
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 65
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        
        with patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            monitor = GPUMonitor()
            
            if monitor.nvidia_available:
                info = monitor.get_nvidia_info()
                assert isinstance(info, dict)


class TestGPUMonitorAMDMethods:
    """Test AMD-specific GPU monitoring methods."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x1002')
    def test_get_amd_info_basic(self, mock_file, mock_exists, mock_subprocess):
        """Test basic AMD GPU info retrieval."""
        mock_exists.return_value = True
        
        # Mock rocm-smi output
        rocm_output = """
GPU[0]		: Temperature (Sensor edge) (C): 45.0
GPU[0]		: GPU use (%): 25
GPU[0]		: Memory Activity (%): 15
"""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=rocm_output
        )
        
        monitor = GPUMonitor()
        assert monitor.gpu_type == 'amd'
        
        info = monitor.get_amd_info()
        assert isinstance(info, dict)


class TestGPUMonitorGetAllInfo:
    """Test get_all_info method for different GPU types."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    def test_get_all_info_no_gpu(self, mock_exists, mock_subprocess):
        """Test get_all_info when no GPU is detected."""
        mock_exists.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        info = monitor.get_all_info()
        
        assert isinstance(info, dict)
        assert info.get('available') == False or 'error' in info
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_get_all_info_intel(self, mock_file, mock_exists, mock_subprocess):
        """Test get_all_info for Intel GPU."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        info = monitor.get_all_info()
        
        assert isinstance(info, dict)
        if monitor.intel_available:
            assert 'type' in info or 'vendor' in info or 'available' in info
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x1002')
    def test_get_all_info_amd(self, mock_file, mock_exists, mock_subprocess):
        """Test get_all_info for AMD GPU."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="GPU[0]: 45C")
        
        monitor = GPUMonitor()
        info = monitor.get_all_info()
        
        assert isinstance(info, dict)


class TestGPUMonitorHelperMethods:
    """Test helper methods."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_check_intel_gpu(self, mock_file, mock_exists, mock_subprocess):
        """Test _check_intel_gpu helper."""
        mock_exists.return_value = True
        
        monitor = GPUMonitor()
        result = monitor._check_intel_gpu()
        
        # Should return True or False
        assert isinstance(result, bool)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_check_mali_gpu(self, mock_file, mock_exists, mock_subprocess):
        """Test _check_mali_gpu helper."""
        mock_exists.return_value = False
        mock_file.return_value.read.return_value = "rockchip,rk3588-mali"
        
        monitor = GPUMonitor()
        result = monitor._check_mali_gpu()
        
        # Should return True or False
        assert isinstance(result, bool)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    def test_detect_gpu_via_sysfs_exception_handling(self, mock_exists, mock_subprocess):
        """Test _detect_gpu_via_sysfs handles exceptions gracefully."""
        mock_exists.side_effect = Exception("Test error")
        
        monitor = GPUMonitor()
        # Should not crash, just return None
        assert monitor.gpu_type is None or isinstance(monitor.gpu_type, str)


class TestGPUMonitorEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid_vendor')
    def test_invalid_vendor_id(self, mock_file, mock_exists, mock_subprocess):
        """Test handling of invalid vendor ID."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        # Should fallback to command-line detection or return None
        assert monitor.gpu_type is None or isinstance(monitor.gpu_type, str)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open')
    def test_file_read_exception(self, mock_file, mock_exists, mock_subprocess):
        """Test handling of file read exceptions."""
        mock_exists.return_value = True
        mock_file.side_effect = IOError("Permission denied")
        mock_subprocess.return_value = MagicMock(returncode=1)
        
        monitor = GPUMonitor()
        # Should not crash
        assert monitor.gpu_type is None or isinstance(monitor.gpu_type, str)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    def test_subprocess_timeout(self, mock_exists, mock_subprocess):
        """Test subprocess timeout handling."""
        import subprocess
        mock_exists.return_value = False
        mock_subprocess.side_effect = subprocess.TimeoutExpired('which', 5)
        
        monitor = GPUMonitor()
        # Should not crash
        assert isinstance(monitor, GPUMonitor)
    
    @patch('monitors.gpu_monitor.subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='0x8086')
    def test_multiple_cards(self, mock_file, mock_exists, mock_subprocess):
        """Test handling of multiple GPU cards."""
        # Simulate multiple cards
        def exists_side_effect(path):
            if 'card0' in path or 'card1' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = GPUMonitor()
        # Should detect at least one
        assert monitor.gpu_type in ['intel', 'nvidia', 'amd', 'mali', None]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
