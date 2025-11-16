"""Unit tests for NetworkMonitor with mocked psutil."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import time
import psutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from monitors.network_monitor import NetworkMonitor


class TestNetworkMonitorInit:
    """Test NetworkMonitor initialization."""
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_init_creates_instance(self, mock_time, mock_counters):
        """Test that NetworkMonitor can be instantiated."""
        mock_time.return_value = 1000.0
        
        # Mock network counters
        mock_eth0 = MagicMock()
        mock_eth0.bytes_sent = 1000
        mock_eth0.bytes_recv = 2000
        mock_eth0.packets_sent = 10
        mock_eth0.packets_recv = 20
        
        mock_counters.return_value = {'eth0': mock_eth0}
        
        monitor = NetworkMonitor()
        assert monitor is not None
        assert 'eth0' in monitor.last_counters
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    def test_init_handles_exception(self, mock_counters):
        """Test initialization handles exceptions gracefully."""
        mock_counters.side_effect = Exception("Network error")
        
        monitor = NetworkMonitor()
        assert monitor.last_counters == {}


class TestNetworkMonitorInterfaces:
    """Test interface listing."""
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_interfaces(self, mock_time, mock_counters):
        """Test getting list of network interfaces."""
        mock_time.return_value = 1000.0
        
        # Mock multiple interfaces
        mock_eth0 = MagicMock()
        mock_wlan0 = MagicMock()
        mock_lo = MagicMock()
        
        for mock_iface in [mock_eth0, mock_wlan0, mock_lo]:
            mock_iface.bytes_sent = 0
            mock_iface.bytes_recv = 0
            mock_iface.packets_sent = 0
            mock_iface.packets_recv = 0
        
        mock_counters.return_value = {
            'eth0': mock_eth0,
            'wlan0': mock_wlan0,
            'lo': mock_lo
        }
        
        monitor = NetworkMonitor()
        interfaces = monitor.get_interfaces()
        
        assert isinstance(interfaces, list)
        assert len(interfaces) == 3
        assert 'eth0' in interfaces
        assert 'wlan0' in interfaces
        assert 'lo' in interfaces
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_interfaces_exception(self, mock_time, mock_counters):
        """Test get_interfaces handles exceptions."""
        mock_time.return_value = 1000.0
        mock_counters.side_effect = [
            {},  # For init
            Exception("Network error")  # For get_interfaces call
        ]
        
        monitor = NetworkMonitor()
        interfaces = monitor.get_interfaces()
        
        assert interfaces == []


class TestNetworkMonitorInterfaceStats:
    """Test interface statistics."""
    
    @patch('monitors.network_monitor.psutil.net_if_stats')
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_interface_stats(self, mock_time, mock_counters, mock_if_stats):
        """Test getting interface statistics."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        
        # Mock interface stats
        mock_eth0_stats = MagicMock()
        mock_eth0_stats.isup = True
        mock_eth0_stats.speed = 1000  # Mbps
        mock_eth0_stats.mtu = 1500
        
        mock_if_stats.return_value = {'eth0': mock_eth0_stats}
        
        monitor = NetworkMonitor()
        stats = monitor.get_interface_stats()
        
        assert 'eth0' in stats
        assert stats['eth0']['is_up'] == True
        assert stats['eth0']['speed'] == 1000
        assert stats['eth0']['mtu'] == 1500
    
    @patch('monitors.network_monitor.psutil.net_if_stats')
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_interface_stats_exception(self, mock_time, mock_counters, mock_if_stats):
        """Test interface stats exception handling."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        mock_if_stats.side_effect = Exception("Stats error")
        
        monitor = NetworkMonitor()
        stats = monitor.get_interface_stats()
        
        assert stats == {}


class TestNetworkMonitorIOStats:
    """Test I/O statistics and speed calculation."""
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_io_stats_total(self, mock_time, mock_counters):
        """Test getting total I/O statistics."""
        # Mock time progression
        mock_time.side_effect = [1000.0, 1000.0, 1001.0]  # init, init again, get_io_stats
        
        # Mock counters - init
        mock_init = MagicMock()
        mock_init.bytes_sent = 1000
        mock_init.bytes_recv = 2000
        mock_init.packets_sent = 10
        mock_init.packets_recv = 20
        mock_init.errin = 0
        mock_init.errout = 0
        mock_init.dropin = 0
        mock_init.dropout = 0
        
        # Mock counters - after 1 second
        mock_current = MagicMock()
        mock_current.bytes_sent = 2000  # +1000 bytes
        mock_current.bytes_recv = 3000  # +1000 bytes
        mock_current.packets_sent = 20  # +10 packets
        mock_current.packets_recv = 30  # +10 packets
        mock_current.errin = 0
        mock_current.errout = 0
        mock_current.dropin = 0
        mock_current.dropout = 0
        
        mock_counters.side_effect = [
            {'total': mock_init},  # Init call (pernic=True)
            mock_current  # get_io_stats call (pernic=False)
        ]
        
        monitor = NetworkMonitor()
        stats = monitor.get_io_stats()
        
        assert 'upload_speed' in stats
        assert 'download_speed' in stats
        assert stats['upload_speed'] == 1000.0  # bytes/sec
        assert stats['download_speed'] == 1000.0  # bytes/sec
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_io_stats_specific_interface(self, mock_time, mock_counters):
        """Test getting I/O stats for specific interface."""
        mock_time.side_effect = [1000.0, 1000.0, 1001.0]
        
        # Mock init
        mock_eth0_init = MagicMock()
        mock_eth0_init.bytes_sent = 1000
        mock_eth0_init.bytes_recv = 2000
        mock_eth0_init.packets_sent = 10
        mock_eth0_init.packets_recv = 20
        
        # Mock current
        mock_eth0_current = MagicMock()
        mock_eth0_current.bytes_sent = 3000  # +2000 bytes
        mock_eth0_current.bytes_recv = 5000  # +3000 bytes
        mock_eth0_current.packets_sent = 30
        mock_eth0_current.packets_recv = 50
        mock_eth0_current.errin = 0
        mock_eth0_current.errout = 0
        mock_eth0_current.dropin = 0
        mock_eth0_current.dropout = 0
        
        mock_counters.side_effect = [
            {'eth0': mock_eth0_init},  # Init
            {'eth0': mock_eth0_current}  # get_io_stats
        ]
        
        monitor = NetworkMonitor()
        stats = monitor.get_io_stats('eth0')
        
        assert 'upload_speed' in stats
        assert 'download_speed' in stats
        assert stats['upload_speed'] == 2000.0
        assert stats['download_speed'] == 3000.0
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_io_stats_nonexistent_interface(self, mock_time, mock_counters):
        """Test getting stats for non-existent interface."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        
        monitor = NetworkMonitor()
        stats = monitor.get_io_stats('nonexistent0')
        
        assert stats == {}
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_io_stats_speed_conversion(self, mock_time, mock_counters):
        """Test Mbps speed conversion."""
        mock_time.side_effect = [1000.0, 1000.0, 1001.0]
        
        mock_init = MagicMock()
        mock_init.bytes_sent = 0
        mock_init.bytes_recv = 0
        mock_init.packets_sent = 0
        mock_init.packets_recv = 0
        mock_init.errin = 0
        mock_init.errout = 0
        mock_init.dropin = 0
        mock_init.dropout = 0
        
        # 1 MB/s = 8 Mbps
        mock_current = MagicMock()
        mock_current.bytes_sent = 1024 * 1024  # 1 MB
        mock_current.bytes_recv = 1024 * 1024
        mock_current.packets_sent = 1000
        mock_current.packets_recv = 1000
        mock_current.errin = 0
        mock_current.errout = 0
        mock_current.dropin = 0
        mock_current.dropout = 0
        
        mock_counters.side_effect = [{'total': mock_init}, mock_current]
        
        monitor = NetworkMonitor()
        stats = monitor.get_io_stats()
        
        assert 'upload_speed_mbps' in stats
        assert 'download_speed_mbps' in stats
        # 1 MB/s = 8 Mbps
        assert abs(stats['upload_speed_mbps'] - 8.0) < 0.1
        assert abs(stats['download_speed_mbps'] - 8.0) < 0.1


class TestNetworkMonitorConnections:
    """Test network connections counting."""
    
    @patch('monitors.network_monitor.psutil.net_connections')
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_connections_count(self, mock_time, mock_counters, mock_connections):
        """Test counting network connections."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        
        # Mock connections
        tcp_established = MagicMock(type=1, status='ESTABLISHED')
        tcp_listen = MagicMock(type=1, status='LISTEN')
        udp_conn = MagicMock(type=2, status='NONE')
        
        mock_connections.return_value = [tcp_established, tcp_listen, udp_conn]
        
        monitor = NetworkMonitor()
        counts = monitor.get_connections_count()
        
        assert counts['total'] == 3
        assert counts['tcp'] == 2
        assert counts['udp'] == 1
        assert counts['tcp_established'] == 1
        assert counts['tcp_listen'] == 1
    
    @patch('monitors.network_monitor.psutil.net_connections')
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_connections_permission_denied(self, mock_time, mock_counters, mock_connections):
        """Test connection counting with permission denied."""
        mock_time.return_value = 1000.0
        mock_counters.return_value = {}
        mock_connections.side_effect = psutil.AccessDenied("Need root")
        
        monitor = NetworkMonitor()
        counts = monitor.get_connections_count()
        
        assert counts['total'] == 0
        assert 'error' in counts


class TestNetworkMonitorGetAllInfo:
    """Test get_all_info comprehensive method."""
    
    @patch('monitors.network_monitor.psutil.net_connections')
    @patch('monitors.network_monitor.psutil.net_if_stats')
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_get_all_info(self, mock_time, mock_counters, mock_if_stats, mock_connections):
        """Test getting all network information."""
        mock_time.side_effect = [1000.0, 1001.0]
        
        # Mock init counters
        mock_eth0_init = MagicMock()
        mock_eth0_init.bytes_sent = 1000
        mock_eth0_init.bytes_recv = 2000
        mock_eth0_init.packets_sent = 10
        mock_eth0_init.packets_recv = 20
        
        # Mock current counters
        mock_eth0_current = MagicMock()
        mock_eth0_current.bytes_sent = 2000
        mock_eth0_current.bytes_recv = 3000
        mock_eth0_current.packets_sent = 20
        mock_eth0_current.packets_recv = 30
        mock_eth0_current.errin = 0
        mock_eth0_current.errout = 0
        mock_eth0_current.dropin = 0
        mock_eth0_current.dropout = 0
        
        mock_counters.side_effect = [
            {'eth0': mock_eth0_init},  # Init
            {'eth0': mock_eth0_init},  # get_interfaces
            mock_eth0_current  # get_io_stats
        ]
        
        # Mock interface stats
        mock_stats = MagicMock()
        mock_stats.isup = True
        mock_stats.speed = 1000
        mock_stats.mtu = 1500
        mock_if_stats.return_value = {'eth0': mock_stats}
        
        # Mock connections
        mock_connections.return_value = []
        
        monitor = NetworkMonitor()
        info = monitor.get_all_info()
        
        assert 'interfaces' in info
        assert 'interface_stats' in info
        assert 'io_stats' in info
        assert 'connections' in info
        assert isinstance(info['interfaces'], list)
        assert isinstance(info['interface_stats'], dict)
        assert isinstance(info['io_stats'], dict)
        assert isinstance(info['connections'], dict)


class TestNetworkMonitorEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('monitors.network_monitor.psutil.net_io_counters')
    @patch('monitors.network_monitor.time.time')
    def test_very_small_time_delta(self, mock_time, mock_counters):
        """Test handling of very small time delta."""
        # Very small time delta should be adjusted
        mock_time.side_effect = [1000.0, 1000.0, 1000.05]  # 50ms
        
        mock_init = MagicMock()
        mock_init.bytes_sent = 0
        mock_init.bytes_recv = 0
        mock_init.packets_sent = 0
        mock_init.packets_recv = 0
        mock_init.errin = 0
        mock_init.errout = 0
        mock_init.dropin = 0
        mock_init.dropout = 0
        
        mock_current = MagicMock()
        mock_current.bytes_sent = 100
        mock_current.bytes_recv = 100
        mock_current.packets_sent = 1
        mock_current.packets_recv = 1
        mock_current.errin = 0
        mock_current.errout = 0
        mock_current.dropin = 0
        mock_current.dropout = 0
        
        mock_counters.side_effect = [{'total': mock_init}, mock_current]
        
        monitor = NetworkMonitor()
        stats = monitor.get_io_stats()
        
        # Should use minimum 0.1s time delta
        assert 'upload_speed' in stats
        assert stats['upload_speed'] == 1000.0  # 100 bytes / 0.1s


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
