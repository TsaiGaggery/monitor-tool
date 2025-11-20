"""
Unified monitoring data snapshot.

Provides a standardized data structure that all data sources (Local, SSH, Android)
populate, making UI and export code source-agnostic.
"""

import time
from typing import Dict, Optional, Any


class MonitoringSnapshot:
    """Unified snapshot of monitoring data across all source types.
    
    All data sources return this standardized format, making UI/export code
    source-agnostic. When adding new metrics, add them here once and they'll
    automatically flow through all consumers (CLI, export, logging).
    """
    
    def __init__(self):
        """Initialize empty snapshot."""
        self.timestamp: str = time.strftime('%Y-%m-%d %H:%M:%S')
        self.time_seconds: float = 0
        
        # Core metrics (always present, may be empty dicts)
        self.cpu: Dict[str, Any] = {}
        self.memory: Dict[str, Any] = {}
        self.gpu: Dict[str, Any] = {}
        self.npu: Dict[str, Any] = {}
        self.network: Dict[str, Any] = {}
        self.disk: Dict[str, Any] = {}
        
        # Optional tier1 metrics (None if not available/enabled)
        self.tier1: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_data_source(cls, data_source: Any) -> 'MonitoringSnapshot':
        """Factory method to create snapshot from any data source.
        
        Args:
            data_source: A MonitorDataSource instance (Local, SSH, or Android)
            
        Returns:
            MonitoringSnapshot with all available data populated
        """
        snapshot = cls()
        
        try:
            # Collect core metrics (these should always be present)
            snapshot.cpu = data_source.get_cpu_info() or {}
            snapshot.memory = data_source.get_memory_info() or {}
            snapshot.gpu = data_source.get_gpu_info() or {}
            snapshot.npu = data_source.get_npu_info() or {}
            snapshot.network = data_source.get_network_info() or {}
            snapshot.disk = data_source.get_disk_info() or {}
            
            # Collect tier1 if available (may not be implemented on all sources)
            if hasattr(data_source, 'get_tier1_info'):
                tier1_data = data_source.get_tier1_info()
                # Only add if not empty/None (check dict has keys, not if values are truthy)
                if tier1_data:
                    snapshot.tier1 = tier1_data
            
        except Exception as e:
            # If collection fails, log but don't crash - return partial data
            print(f"Warning: Error collecting monitoring data: {e}")
        
        return snapshot
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for export/logging.
        
        Returns:
            Dictionary with all monitoring data
        """
        result = {
            'timestamp': self.timestamp,
            'time_seconds': self.time_seconds,
            'cpu': self.cpu,
            'memory': self.memory,
            'gpu': self.gpu,
            'npu': self.npu,
            'network': self.network,
            'disk': self.disk
        }
        
        # Only include tier1 if present
        if self.tier1 is not None:
            result['tier1'] = self.tier1
        
        return result
    
    def has_data(self) -> bool:
        """Check if snapshot has any meaningful data.
        
        Returns:
            True if any metric section has data
        """
        return any([
            self.cpu,
            self.memory,
            self.gpu,
            self.npu,
            self.network,
            self.disk,
            self.tier1
        ])
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        sections = []
        if self.cpu:
            sections.append('cpu')
        if self.memory:
            sections.append('memory')
        if self.gpu:
            sections.append('gpu')
        if self.npu:
            sections.append('npu')
        if self.network:
            sections.append('network')
        if self.disk:
            sections.append('disk')
        if self.tier1:
            sections.append('tier1')
        
        return f"MonitoringSnapshot({self.timestamp}, sections={sections})"
