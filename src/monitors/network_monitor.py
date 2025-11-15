#!/usr/bin/env python3
"""Network monitoring module for tracking interface statistics and connections."""

import psutil
import time
from typing import Dict, List, Optional


class NetworkMonitor:
    """Monitor network interface statistics, speed, and connections."""
    
    def __init__(self):
        """Initialize network monitor."""
        self.last_counters = {}
        self.last_time = time.time()
        self._initialize_counters()
    
    def _initialize_counters(self):
        """Initialize counters for speed calculation."""
        try:
            counters = psutil.net_io_counters(pernic=True)
            self.last_counters = {
                iface: {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv,
                    'packets_sent': stats.packets_sent,
                    'packets_recv': stats.packets_recv,
                }
                for iface, stats in counters.items()
            }
            self.last_time = time.time()
        except Exception as e:
            print(f"Error initializing network counters: {e}")
            self.last_counters = {}
    
    def get_interfaces(self) -> List[str]:
        """Get list of available network interfaces.
        
        Returns:
            List of interface names (e.g., ['eth0', 'wlan0', 'lo'])
        """
        try:
            counters = psutil.net_io_counters(pernic=True)
            # Filter out loopback if needed
            interfaces = [iface for iface in counters.keys()]
            return sorted(interfaces)
        except Exception as e:
            print(f"Error getting network interfaces: {e}")
            return []
    
    def get_interface_stats(self) -> Dict[str, Dict]:
        """Get statistics for all network interfaces.
        
        Returns:
            Dict with interface names as keys and stats dict as values
        """
        try:
            stats_dict = psutil.net_if_stats()
            return {
                iface: {
                    'is_up': stats.isup,
                    'speed': stats.speed,  # Mbps
                    'mtu': stats.mtu,
                }
                for iface, stats in stats_dict.items()
            }
        except Exception as e:
            print(f"Error getting interface stats: {e}")
            return {}
    
    def get_io_stats(self, interface: Optional[str] = None) -> Dict:
        """Get I/O statistics and calculate speeds.
        
        Args:
            interface: Specific interface name, or None for total
            
        Returns:
            Dict containing bytes, packets, speeds, and errors
        """
        try:
            current_time = time.time()
            time_delta = current_time - self.last_time
            
            if time_delta < 0.1:  # Avoid division by very small numbers
                time_delta = 0.1
            
            if interface:
                # Get specific interface
                counters = psutil.net_io_counters(pernic=True)
                if interface not in counters:
                    return {}
                current = counters[interface]
            else:
                # Get total for all interfaces
                current = psutil.net_io_counters(pernic=False)
                interface = 'total'
            
            # Calculate speeds
            last = self.last_counters.get(interface, {
                'bytes_sent': current.bytes_sent,
                'bytes_recv': current.bytes_recv,
                'packets_sent': current.packets_sent,
                'packets_recv': current.packets_recv,
            })
            
            bytes_sent_delta = current.bytes_sent - last.get('bytes_sent', current.bytes_sent)
            bytes_recv_delta = current.bytes_recv - last.get('bytes_recv', current.bytes_recv)
            packets_sent_delta = current.packets_sent - last.get('packets_sent', current.packets_sent)
            packets_recv_delta = current.packets_recv - last.get('packets_recv', current.packets_recv)
            
            # Calculate speeds (bytes/sec)
            upload_speed = bytes_sent_delta / time_delta
            download_speed = bytes_recv_delta / time_delta
            packets_sent_rate = packets_sent_delta / time_delta
            packets_recv_rate = packets_recv_delta / time_delta
            
            # Update last counters
            self.last_counters[interface] = {
                'bytes_sent': current.bytes_sent,
                'bytes_recv': current.bytes_recv,
                'packets_sent': current.packets_sent,
                'packets_recv': current.packets_recv,
            }
            self.last_time = current_time
            
            return {
                'bytes_sent': current.bytes_sent,
                'bytes_recv': current.bytes_recv,
                'packets_sent': current.packets_sent,
                'packets_recv': current.packets_recv,
                'errors_in': current.errin,
                'errors_out': current.errout,
                'drops_in': current.dropin,
                'drops_out': current.dropout,
                'upload_speed': upload_speed,  # bytes/sec
                'download_speed': download_speed,  # bytes/sec
                'upload_speed_mbps': upload_speed * 8 / (1024 * 1024),  # Mbps
                'download_speed_mbps': download_speed * 8 / (1024 * 1024),  # Mbps
                'packets_sent_rate': packets_sent_rate,  # packets/sec
                'packets_recv_rate': packets_recv_rate,  # packets/sec
            }
        except Exception as e:
            print(f"Error getting I/O stats: {e}")
            return {}
    
    def get_connections_count(self) -> Dict:
        """Get count of network connections by type and state.
        
        Returns:
            Dict with connection counts
        """
        try:
            connections = psutil.net_connections(kind='inet')
            
            tcp_count = sum(1 for c in connections if c.type == 1)  # SOCK_STREAM
            udp_count = sum(1 for c in connections if c.type == 2)  # SOCK_DGRAM
            
            # Count TCP states
            tcp_established = sum(1 for c in connections 
                                 if c.type == 1 and c.status == 'ESTABLISHED')
            tcp_listen = sum(1 for c in connections 
                           if c.type == 1 and c.status == 'LISTEN')
            
            return {
                'total': len(connections),
                'tcp': tcp_count,
                'udp': udp_count,
                'tcp_established': tcp_established,
                'tcp_listen': tcp_listen,
            }
        except (psutil.AccessDenied, PermissionError):
            # May need root permissions for all connections
            return {
                'total': 0,
                'tcp': 0,
                'udp': 0,
                'tcp_established': 0,
                'tcp_listen': 0,
                'error': 'Permission denied (may need root)'
            }
        except Exception as e:
            print(f"Error getting connections: {e}")
            return {}
    
    def get_all_info(self, interface: Optional[str] = None) -> Dict:
        """Get comprehensive network information.
        
        Args:
            interface: Specific interface or None for total
            
        Returns:
            Dict with all network information
        """
        return {
            'interfaces': self.get_interfaces(),
            'interface_stats': self.get_interface_stats(),
            'io_stats': self.get_io_stats(interface),
            'connections': self.get_connections_count(),
        }


if __name__ == '__main__':
    # Test the monitor
    monitor = NetworkMonitor()
    import json
    time.sleep(1)  # Wait for initial sampling
    print(json.dumps(monitor.get_all_info(), indent=2))
