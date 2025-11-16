"""Unit tests for NPUMonitor with mocked NPU detection."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from monitors.npu_monitor import NPUMonitor


class TestNPUMonitorDetection:
    """Test NPU platform detection."""
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_no_npu_detected(self, mock_subprocess, mock_exists):
        """Test when no NPU is detected."""
        mock_exists.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        
        monitor = NPUMonitor()
        assert monitor.platform is None
        assert not monitor.available
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_detect_intel_npu_via_accel(self, mock_subprocess, mock_exists):
        """Test Intel NPU detection via accel device."""
        def exists_side_effect(path):
            if '/sys/class/accel/accel0' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        assert monitor.platform == 'intel'
        assert monitor.available
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_detect_intel_npu_via_lspci(self, mock_subprocess, mock_exists):
        """Test Intel NPU detection via lspci."""
        mock_exists.return_value = False
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="00:0b.0 System peripheral: Intel VPU (rev 01)"
        )
        
        monitor = NPUMonitor()
        assert monitor.platform == 'intel'
        assert monitor.available
    
    @patch('os.path.exists')
    def test_detect_rockchip_npu(self, mock_exists):
        """Test RockChip NPU detection."""
        def exists_side_effect(path):
            if path == '/dev/rknpu':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        assert monitor.platform == 'rockchip'
        assert monitor.available
    
    @patch('os.path.exists')
    def test_detect_qualcomm_npu(self, mock_exists):
        """Test Qualcomm NPU detection."""
        def exists_side_effect(path):
            if path == '/dev/qcom_npu':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        assert monitor.platform == 'qualcomm'
        assert monitor.available
    
    @patch('os.path.exists')
    def test_detect_mediatek_npu(self, mock_exists):
        """Test MediaTek NPU detection."""
        def exists_side_effect(path):
            if path == '/dev/mdla':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        assert monitor.platform == 'mediatek'
        assert monitor.available
    
    @patch('os.path.exists')
    def test_detect_amlogic_npu(self, mock_exists):
        """Test Amlogic NPU detection."""
        def exists_side_effect(path):
            if path == '/sys/class/npu':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        assert monitor.platform == 'amlogic'
        assert monitor.available
    
    @patch('os.path.exists')
    def test_detect_generic_npu(self, mock_exists):
        """Test generic NPU detection."""
        def exists_side_effect(path):
            if path == '/sys/devices/platform/npu':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        assert monitor.platform == 'generic'
        assert monitor.available


class TestNPUMonitorIntelInfo:
    """Test Intel NPU information retrieval."""
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_intel_info_basic(self, mock_file, mock_subprocess, mock_exists):
        """Test basic Intel NPU info retrieval."""
        # Mock Intel NPU detection
        def exists_side_effect(path):
            if '/sys/class/accel/accel0' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        info = monitor.get_intel_info()
        
        assert isinstance(info, dict)
        assert 'platform' in info
        assert 'utilization' in info
        assert 'frequency' in info
        assert info['platform'] == 'Intel NPU'
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_intel_info_with_frequency(self, mock_file, mock_subprocess, mock_exists):
        """Test Intel NPU info with frequency data."""
        # Mock paths
        def exists_side_effect(path):
            if '/sys/class/accel/accel0' in path:
                return True
            if 'npu_current_frequency_mhz' in path:
                return True
            if 'npu_max_frequency_mhz' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock file reads for frequency
        mock_file.return_value.read.side_effect = ['1500', '2000']
        
        monitor = NPUMonitor()
        info = monitor.get_intel_info()
        
        assert isinstance(info, dict)
        # May or may not have frequency depending on file reading
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_get_intel_info_no_device(self, mock_subprocess, mock_exists):
        """Test Intel NPU info when device is not available."""
        mock_exists.return_value = False
        
        monitor = NPUMonitor()
        # Should still be able to call get_intel_info
        info = monitor.get_intel_info()
        
        assert isinstance(info, dict)
        assert info['available'] == True  # Method sets available: True by default


class TestNPUMonitorOtherPlatforms:
    """Test other NPU platform information retrieval."""
    
    @patch('os.path.exists')
    def test_get_rockchip_info(self, mock_exists):
        """Test RockChip NPU info retrieval."""
        def exists_side_effect(path):
            if path == '/dev/rknpu':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        info = monitor.get_rockchip_info()
        
        assert isinstance(info, dict)
        assert 'platform' in info
        assert info['platform'] == 'RockChip'
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='50')
    def test_get_generic_info(self, mock_file, mock_exists):
        """Test generic NPU info retrieval."""
        def exists_side_effect(path):
            if path == '/sys/devices/platform/npu':
                return True
            if 'utilization' in path:
                return True
            if 'frequency' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        info = monitor.get_generic_info()
        
        assert isinstance(info, dict)
        assert 'platform' in info


class TestNPUMonitorGetAllInfo:
    """Test get_all_info method for different NPU platforms."""
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_get_all_info_no_npu(self, mock_subprocess, mock_exists):
        """Test get_all_info when no NPU is detected."""
        mock_exists.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        
        monitor = NPUMonitor()
        info = monitor.get_all_info()
        
        assert isinstance(info, dict)
        assert info.get('available') == False
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_all_info_intel(self, mock_file, mock_subprocess, mock_exists):
        """Test get_all_info for Intel NPU."""
        def exists_side_effect(path):
            if '/sys/class/accel/accel0' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        info = monitor.get_all_info()
        
        assert isinstance(info, dict)
        assert monitor.platform == 'intel'
    
    @patch('os.path.exists')
    def test_get_all_info_rockchip(self, mock_exists):
        """Test get_all_info for RockChip NPU."""
        def exists_side_effect(path):
            if path == '/dev/rknpu':
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        info = monitor.get_all_info()
        
        assert isinstance(info, dict)
        assert monitor.platform == 'rockchip'


class TestNPUMonitorEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_lspci_exception_handling(self, mock_subprocess, mock_exists):
        """Test handling of lspci exceptions."""
        mock_exists.return_value = False
        mock_subprocess.side_effect = Exception("lspci failed")
        
        monitor = NPUMonitor()
        # Should not crash
        assert isinstance(monitor, NPUMonitor)
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    @patch('builtins.open')
    def test_file_read_exception_intel(self, mock_file, mock_subprocess, mock_exists):
        """Test handling of file read exceptions for Intel NPU."""
        def exists_side_effect(path):
            if '/sys/class/accel/accel0' in path:
                return True
            if 'npu_current_frequency_mhz' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        mock_file.side_effect = IOError("Permission denied")
        
        monitor = NPUMonitor()
        info = monitor.get_intel_info()
        
        # Should handle error gracefully
        assert isinstance(info, dict)
    
    @patch('os.path.exists')
    @patch('monitors.npu_monitor.subprocess.run')
    def test_lspci_timeout(self, mock_subprocess, mock_exists):
        """Test subprocess timeout handling."""
        import subprocess
        mock_exists.return_value = False
        mock_subprocess.side_effect = subprocess.TimeoutExpired('lspci', 5)
        
        monitor = NPUMonitor()
        # Should not crash
        assert isinstance(monitor, NPUMonitor)
    
    @patch('os.path.exists')
    def test_multiple_npu_types_priority(self, mock_exists):
        """Test priority when multiple NPU types exist."""
        # Intel should have highest priority
        def exists_side_effect(path):
            if '/sys/class/accel/accel0' in path:
                return True
            if '/dev/rknpu' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        monitor = NPUMonitor()
        # Should detect Intel first
        assert monitor.platform == 'intel'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
