#!/usr/bin/env python3
"""CLI monitoring tool for headless/server environments.

This provides a terminal-based monitoring interface without GUI dependencies.
Features:
- Real-time text-based dashboard (like htop/top)
- JSON/CSV export support
- Configurable update interval
- Select specific monitors to display
"""

import sys
import os
import time
import argparse
import signal
import json
from datetime import datetime
from typing import Dict, List, Optional

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitors import CPUMonitor, MemoryMonitor, GPUMonitor, NPUMonitor, NetworkMonitor, DiskMonitor
from storage import DataLogger, DataExporter


class CLIMonitor:
    """CLI-based system monitor without GUI."""
    
    def __init__(self, update_interval: float = 1.0, enable_logging: bool = False):
        """Initialize CLI monitor.
        
        Args:
            update_interval: Update interval in seconds
            enable_logging: Enable SQLite logging
        """
        self.update_interval = update_interval
        self.enable_logging = enable_logging
        self.running = False
        
        # Initialize monitors
        self.cpu_monitor = CPUMonitor()
        self.memory_monitor = MemoryMonitor()
        self.gpu_monitor = GPUMonitor()
        self.npu_monitor = NPUMonitor()
        self.network_monitor = NetworkMonitor()
        self.disk_monitor = DiskMonitor()
        
        # Initialize logger if enabled
        self.logger = DataLogger() if enable_logging else None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\n\n🛑 Shutting down...")
        self.running = False
        
    def _clear_screen(self):
        """Clear terminal screen."""
        os.system('clear' if os.name != 'nt' else 'cls')
        
    def _format_bytes(self, bytes_val: float, suffix: str = 'B') -> str:
        """Format bytes to human-readable format."""
        for unit in ['', 'K', 'M', 'G', 'T']:
            if abs(bytes_val) < 1024.0:
                return f"{bytes_val:.2f} {unit}{suffix}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} P{suffix}"
        
    def _format_bar(self, percent: float, width: int = 20) -> str:
        """Create a text-based progress bar."""
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percent:5.1f}%"
        
    def _get_all_data(self) -> Dict:
        """Get all monitoring data."""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu': self.cpu_monitor.get_all_info(),
            'memory': self.memory_monitor.get_all_info(),
            'gpu': self.gpu_monitor.get_all_info(),
            'npu': self.npu_monitor.get_all_info(),
            'network': self.network_monitor.get_all_info(),
            'disk': self.disk_monitor.get_all_info(),
        }
        
    def display_once(self, format: str = 'text', output_file: Optional[str] = None):
        """Display monitoring data once.
        
        Args:
            format: Output format ('text', 'json', 'simple')
            output_file: Optional file to write output to
        """
        data = self._get_all_data()
        
        if format == 'json':
            output = json.dumps(data, indent=2)
        elif format == 'simple':
            output = self._format_simple(data)
        else:  # text
            output = self._format_dashboard(data)
            
        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            print(f"✓ Output written to {output_file}")
        else:
            print(output)
            
    def _format_simple(self, data: Dict) -> str:
        """Format data in simple one-line format."""
        cpu = data['cpu']
        mem = data['memory']['memory']
        gpu = data['gpu']
        net = data['network']
        disk = data['disk']
        
        parts = [
            f"CPU: {cpu['usage']['total']:.1f}%",
            f"Mem: {mem['percent']:.1f}%",
        ]
        
        if gpu['available'] and gpu['gpus']:
            gpu_util = gpu['gpus'][0].get('gpu_util', 0)
            parts.append(f"GPU: {gpu_util}%")
            
        if net['io_stats']:
            net_up = net['io_stats'].get('upload_speed', 0)
            net_down = net['io_stats'].get('download_speed', 0)
            parts.append(f"Net: ↑{net_up:.1f} ↓{net_down:.1f} MB/s")
            
        if disk['io_stats']:
            disk_read = disk['io_stats'].get('read_speed', 0)
            disk_write = disk['io_stats'].get('write_speed', 0)
            parts.append(f"Disk: R{disk_read:.1f} W{disk_write:.1f} MB/s")
            
        return " | ".join(parts)
        
    def _format_dashboard(self, data: Dict) -> str:
        """Format data as a full dashboard."""
        lines = []
        lines.append("=" * 80)
        lines.append(f" System Monitor - {data['timestamp']}")
        lines.append("=" * 80)
        
        # CPU Section
        cpu = data['cpu']
        lines.append("\n📊 CPU")
        lines.append(f"  Overall: {self._format_bar(cpu['usage']['total'])}")
        lines.append(f"  Cores: {cpu['cpu_count']} (Physical: {cpu['physical_count']})")
        lines.append(f"  Frequency: {cpu['frequency']['average']:.0f} MHz")
        
        # Show top 8 cores
        lines.append("  Per-core usage:")
        for i in range(min(8, len(cpu['usage']['per_core']))):
            usage = cpu['usage']['per_core'][i]
            lines.append(f"    Core {i:2d}: {self._format_bar(usage, 15)}")
            
        # Temperature
        temps = cpu['temperature']
        if temps:
            for sensor_name, readings in temps.items():
                if readings:
                    temp = readings[0]['current']
                    label = readings[0]['label']
                    lines.append(f"  {label}: {temp:.1f}°C")
                    
        # Memory Section
        mem_data = data['memory']
        mem = mem_data['memory']
        swap = mem_data['swap']
        
        lines.append("\n💾 Memory")
        lines.append(f"  RAM:  {self._format_bar(mem['percent'])}")
        lines.append(f"        {mem['used']:.2f} / {mem['total']:.2f} GB (Available: {mem['available']:.2f} GB)")
        if swap['total'] > 0:
            lines.append(f"  Swap: {self._format_bar(swap['percent'])}")
            lines.append(f"        {swap['used']:.2f} / {swap['total']:.2f} GB")
            
        # GPU Section
        gpu = data['gpu']
        if gpu['available'] and gpu['gpus']:
            lines.append("\n🎮 GPU")
            for gpu_info in gpu['gpus']:
                lines.append(f"  GPU {gpu_info['id']} ({gpu_info['type']})")
                if 'name' in gpu_info:
                    lines.append(f"    Name: {gpu_info['name']}")
                    
                gpu_util = gpu_info.get('gpu_util', 0)
                lines.append(f"    Usage: {self._format_bar(gpu_util)}")
                
                if 'temperature' in gpu_info and gpu_info['temperature'] > 0:
                    lines.append(f"    Temp: {gpu_info['temperature']}°C")
                    
                if 'memory_total' in gpu_info and gpu_info['memory_total'] > 0:
                    mem_used = gpu_info.get('memory_used', 0)
                    mem_total = gpu_info['memory_total']
                    mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
                    lines.append(f"    Memory: {self._format_bar(mem_percent)}")
                    lines.append(f"            {mem_used:.0f} / {mem_total:.0f} MB")
                    
                if 'gpu_clock' in gpu_info and gpu_info['gpu_clock'] > 0:
                    lines.append(f"    Clock: {gpu_info['gpu_clock']} MHz")
                    
        # NPU Section
        npu = data['npu']
        if npu.get('available'):
            lines.append("\n🧠 NPU")
            lines.append(f"  Platform: {npu.get('platform', 'Unknown')}")
            util = npu.get('utilization', 0)
            lines.append(f"  Usage: {self._format_bar(util)}")
            if 'frequency' in npu and npu['frequency'] > 0:
                lines.append(f"  Frequency: {npu['frequency']} MHz")
            if 'power' in npu and npu['power'] > 0:
                lines.append(f"  Power: {npu['power']:.2f} W")
                
        # Network Section
        net = data['network']
        if net['io_stats']:
            io = net['io_stats']
            lines.append("\n🌐 Network")
            lines.append(f"  Upload:   {io['upload_speed']:8.2f} MB/s  (Total: {self._format_bytes(io['bytes_sent'])})")
            lines.append(f"  Download: {io['download_speed']:8.2f} MB/s  (Total: {self._format_bytes(io['bytes_recv'])})")
            lines.append(f"  Packets:  Sent {io['packets_sent']:,} / Recv {io['packets_recv']:,}")
            
        # Active interfaces
        if net['interfaces']:
            lines.append("  Active Interfaces:")
            for iface in net['interfaces'][:5]:  # Show top 5
                lines.append(f"    {iface['name']}: {iface['status']}")
                
        # Disk Section
        disk = data['disk']
        if disk['io_stats']:
            io = disk['io_stats']
            lines.append("\n💿 Disk I/O")
            lines.append(f"  Read:  {io['read_speed']:8.2f} MB/s  ({io['read_iops']:6.0f} IOPS)")
            lines.append(f"  Write: {io['write_speed']:8.2f} MB/s  ({io['write_iops']:6.0f} IOPS)")
            lines.append(f"  Total: Read {self._format_bytes(io['read_bytes'])} / Write {self._format_bytes(io['write_bytes'])}")
            
        # Partition usage
        if disk['partitions']:
            lines.append("  Partitions:")
            for part in disk['partitions'][:5]:  # Show top 5
                lines.append(f"    {part['mountpoint']:20s} {self._format_bar(part['percent'], 10)}")
                lines.append(f"      {self._format_bytes(part['used'])} / {self._format_bytes(part['total'])} ({part['fstype']})")
                
        lines.append("\n" + "=" * 80)
        return "\n".join(lines)
        
    def run_interactive(self):
        """Run interactive monitoring with live updates."""
        self.running = True
        print("🚀 Starting CLI Monitor (Press Ctrl+C to stop)...\n")
        time.sleep(1)
        
        try:
            while self.running:
                self._clear_screen()
                data = self._get_all_data()
                
                # Log data if enabled
                if self.logger:
                    self.logger.log_data(
                        cpu_usage=data['cpu']['usage']['total'],
                        memory_usage=data['memory']['memory']['percent'],
                        gpu_usage=data['gpu']['gpus'][0].get('gpu_util', 0) if data['gpu']['available'] and data['gpu']['gpus'] else 0,
                        npu_usage=data['npu'].get('utilization', 0),
                        network_upload=data['network']['io_stats'].get('upload_speed', 0) if data['network']['io_stats'] else 0,
                        network_download=data['network']['io_stats'].get('download_speed', 0) if data['network']['io_stats'] else 0,
                        disk_read=data['disk']['io_stats'].get('read_speed', 0) if data['disk']['io_stats'] else 0,
                        disk_write=data['disk']['io_stats'].get('write_speed', 0) if data['disk']['io_stats'] else 0,
                    )
                    
                print(self._format_dashboard(data))
                print(f"\n⏱  Update interval: {self.update_interval}s | Logging: {'ON' if self.logger else 'OFF'}")
                
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            pass
            
        print("\n✓ Monitor stopped")
        
    def export_data(self, format: str = 'csv', output_file: Optional[str] = None, 
                   start_time: Optional[str] = None, end_time: Optional[str] = None):
        """Export logged data.
        
        Args:
            format: Export format ('csv' or 'json')
            output_file: Output file path (auto-generated if None)
            start_time: Start time filter (ISO format)
            end_time: End time filter (ISO format)
        """
        if not self.logger:
            print("❌ Logging is not enabled. Cannot export data.")
            return
            
        exporter = DataExporter(self.logger.db_path)
        
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = 'csv' if format == 'csv' else 'json'
            output_file = f"monitor_data_{timestamp}.{ext}"
            
        success = exporter.export(output_file, format, start_time, end_time)
        
        if success:
            print(f"✓ Data exported to {output_file}")
        else:
            print(f"❌ Export failed")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='CLI System Monitor - Headless monitoring without GUI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive dashboard (like htop)
  %(prog)s
  
  # With faster updates
  %(prog)s --interval 0.5
  
  # Enable logging to SQLite
  %(prog)s --log
  
  # Single snapshot in JSON format
  %(prog)s --once --format json
  
  # Export logged data to CSV
  %(prog)s --export --format csv --output report.csv
  
  # Simple one-line output (good for scripts)
  %(prog)s --once --format simple
        """
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=float,
        default=1.0,
        help='Update interval in seconds (default: 1.0)'
    )
    
    parser.add_argument(
        '--log', '-l',
        action='store_true',
        help='Enable SQLite logging'
    )
    
    parser.add_argument(
        '--once', '-1',
        action='store_true',
        help='Display once and exit (no interactive mode)'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['text', 'json', 'simple'],
        default='text',
        help='Output format (default: text)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Write output to file'
    )
    
    parser.add_argument(
        '--export', '-e',
        action='store_true',
        help='Export logged data (requires --log to have been used previously)'
    )
    
    parser.add_argument(
        '--export-format',
        choices=['csv', 'json'],
        default='csv',
        help='Export format (default: csv)'
    )
    
    parser.add_argument(
        '--start-time',
        type=str,
        help='Export start time (ISO format: YYYY-MM-DD HH:MM:SS)'
    )
    
    parser.add_argument(
        '--end-time',
        type=str,
        help='Export end time (ISO format: YYYY-MM-DD HH:MM:SS)'
    )
    
    args = parser.parse_args()
    
    # Create monitor instance
    monitor = CLIMonitor(
        update_interval=args.interval,
        enable_logging=args.log
    )
    
    try:
        if args.export:
            # Export mode
            monitor.export_data(
                format=args.export_format,
                output_file=args.output,
                start_time=args.start_time,
                end_time=args.end_time
            )
        elif args.once:
            # Single display mode
            monitor.display_once(format=args.format, output_file=args.output)
        else:
            # Interactive mode
            monitor.run_interactive()
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == '__main__':
    sys.exit(main())
