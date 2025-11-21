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
import shutil
import curses
import threading
import getpass
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_source import MonitorDataSource, LocalDataSource, AndroidDataSource, RemoteLinuxDataSource
from storage import DataLogger, DataExporter
from controllers import FrequencyController, ADBFrequencyController
from monitoring_snapshot import MonitoringSnapshot


class CLIMonitor:
    """CLI-based system monitor without GUI."""
    
    def __init__(self, data_source: MonitorDataSource = None, update_interval: float = 1.0, enable_logging: bool = False):
        """Initialize CLI monitor.
        
        Args:
            data_source: Data source for monitoring (defaults to LocalDataSource)
            update_interval: Update interval in seconds
            enable_logging: Enable SQLite logging (deprecated, always enabled)
        """
        self.update_interval = update_interval
        self.enable_logging = enable_logging  # Kept for compatibility, but ignored
        self.running = False
        
        # Get terminal size
        self.term_width, self.term_height = shutil.get_terminal_size((80, 24))
        
        # Initialize data source
        if data_source is None:
            self.data_source = LocalDataSource()
        else:
            self.data_source = data_source
        
        # Connect to data source
        if not self.data_source.is_connected():
            self.data_source.connect()
        
        # Initialize frequency controller based on data source
        if isinstance(self.data_source, LocalDataSource):
            # Local Ubuntu system
            self.freq_controller = FrequencyController()
        elif isinstance(self.data_source, AndroidDataSource):
            # Android device via ADB
            device_id = f"{self.data_source.device_ip}:{self.data_source.port}"
            adb_freq_ctrl = ADBFrequencyController(device_id)
            
            # Only use if available (has root + script working)
            if adb_freq_ctrl.is_available:
                self.freq_controller = adb_freq_ctrl
                print(f"✅ Android frequency control enabled")
            else:
                self.freq_controller = None
                print(f"⚠️  Android frequency control disabled (requires root)")
        elif isinstance(self.data_source, RemoteLinuxDataSource):
            # Remote Linux via SSH - frequency control not supported yet
            self.freq_controller = None
            print(f"⚠️  Frequency control not supported for remote Linux")
        else:
            self.freq_controller = None
        
        # Initialize storage
        # Only use local database for LocalDataSource
        # Remote data (Android/SSH) is not stored locally
        if isinstance(self.data_source, LocalDataSource):
            self.logger = DataLogger()
        else:
            self.logger = None  # Remote mode - no local logging
        
        # Track session start time for export
        self.session_start_time = None
        
        # Session data exporter (always available for manual saves)
        self.data_exporter = DataExporter(data_source=self.data_source)
        
        # Save status for UI
        self.save_status_message = None
        self.save_status_time = 0
        
        # Background logging thread
        self.logging_thread = None
        self.logging_lock = threading.Lock()
        self.latest_data = None
        
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
        
    def _get_all_data(self) -> MonitoringSnapshot:
        """Get all monitoring data in unified format.
        
        Returns:
            MonitoringSnapshot with all available data
        """
        # Process any queued samples for SSH/Android (if applicable)
        if hasattr(self.data_source, 'process_queued_samples'):
            self.data_source.process_queued_samples()
        
        # Get unified snapshot from data source
        snapshot = MonitoringSnapshot.from_data_source(self.data_source)
        
        return snapshot
        
    def display_once(self, format: str = 'text', output_file: Optional[str] = None):
        """Display monitoring data once.
        
        Args:
            format: Output format ('text', 'json', 'simple')
            output_file: Optional file to write output to
        """
        snapshot = self._get_all_data()
        
        if format == 'json':
            output = json.dumps(snapshot.to_dict(), indent=2)
        elif format == 'simple':
            output = self._format_simple(snapshot)
        else:  # text
            output = self._format_dashboard(snapshot)
            
        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            print(f"✓ Output written to {output_file}")
        else:
            print(output)
            
    def _format_simple(self, snapshot: MonitoringSnapshot) -> str:
        """Format data in simple one-line format."""
        cpu = snapshot.cpu
        mem = snapshot.memory['memory']
        gpu = snapshot.gpu
        net = snapshot.network
        disk = snapshot.disk
        
        parts = [
            f"CPU: {cpu['usage']['total']:.1f}%",
            f"Mem: {mem['percent']:.1f}%",
        ]
        
        # Add CPU power if available
        cpu_power = cpu.get('power_watts')
        if cpu_power is not None and cpu_power > 0:
            parts[0] = f"CPU: {cpu['usage']['total']:.1f}% ({cpu_power:.1f}W)"
        
        if gpu['available'] and gpu['gpus']:
            gpu_util = gpu['gpus'][0].get('gpu_util', 0)
            parts.append(f"GPU: {gpu_util}%")
            
        if net['io_stats']:
            net_up = net['io_stats'].get('upload_speed', 0) / (1024 * 1024)  # bytes/s to MB/s
            net_down = net['io_stats'].get('download_speed', 0) / (1024 * 1024)  # bytes/s to MB/s
            parts.append(f"Net: ↑{net_up:.1f} ↓{net_down:.1f} MB/s")
            
        if disk['io_stats']:
            disk_read = disk['io_stats'].get('read_speed', 0) / (1024 * 1024)  # bytes/s to MB/s
            disk_write = disk['io_stats'].get('write_speed', 0) / (1024 * 1024)  # bytes/s to MB/s
            parts.append(f"Disk: R{disk_read:.1f} W{disk_write:.1f} MB/s")
            
        return " | ".join(parts)
        
    def _format_dashboard(self, snapshot: MonitoringSnapshot) -> str:
        """Format data as a well-organized dashboard with two-column layout."""
        lines = []
        width = self.term_width
        half_width = width // 2 - 2
        
        # Header
        lines.append("=" * width)
        title = f" System Monitor - {snapshot.timestamp}"
        lines.append(title.ljust(width))
        lines.append("=" * width)
        
        # Prepare sections
        left_lines = []
        right_lines = []
        
        # LEFT COLUMN - CPU
        cpu = snapshot.cpu
        left_lines.append("📊 CPU")
        left_lines.append(f"  Overall: {self._format_bar(cpu['usage']['total'], 20)}")
        left_lines.append(f"  Cores: {cpu['cpu_count']} (Phys: {cpu['physical_count']})")
        left_lines.append(f"  Freq: {cpu['frequency']['average']:.0f} MHz")
        
        # Temperature
        temps = cpu['temperature']
        if temps:
            for sensor_name, readings in temps.items():
                if readings:
                    temp = readings[0]['current']
                    left_lines.append(f"  Temp: {temp:.1f}°C")
                break
        
        # Power (Intel RAPL)
        power = cpu.get('power_watts')
        if power is not None and power > 0:
            left_lines.append(f"  Power: {power:.1f} W")
        
        # Per-core usage (all cores, compact format)
        left_lines.append("  Cores:")
        cores = cpu['usage']['per_core']
        for i in range(0, len(cores), 2):
            core_line = f"  {i:2d}:{cores[i]:4.0f}%"
            if i + 1 < len(cores):
                core_line += f" {i+1:2d}:{cores[i+1]:4.0f}%"
            left_lines.append(core_line)
        
        # RIGHT COLUMN - Memory
        mem_data = snapshot.memory
        mem = mem_data['memory']
        swap = mem_data['swap']
        
        right_lines.append("💾 Memory")
        right_lines.append(f"  RAM: {self._format_bar(mem['percent'], 20)}")
        
        # Show memory speed if available
        mem_speed = mem.get('speed', 0)
        if mem_speed > 0:
            right_lines.append(f"  {mem['used']:.1f} / {mem['total']:.1f} GB @ {mem_speed} MT/s")
        else:
            right_lines.append(f"  {mem['used']:.1f} / {mem['total']:.1f} GB")
            
        if swap['total'] > 0 and swap['percent'] > 1:
            right_lines.append(f"  Swap: {swap['percent']:.1f}%")
            right_lines.append(f"  {swap['used']:.1f} / {swap['total']:.1f} GB")
        
        # GPU in right column
        gpu = snapshot.gpu
        if gpu['available'] and gpu['gpus']:
            right_lines.append("")
            right_lines.append("🎮 GPU")
            for i, gpu_data in enumerate(gpu['gpus'][:1]):  # Show first GPU only
                name = gpu_data.get('name', 'GPU')[:20]  # Truncate long names
                right_lines.append(f"  {name}")
                
                util = gpu_data.get('gpu_util', 0)
                right_lines.append(f"  Load: {self._format_bar(util, 20)}")
                
                mem_used = gpu_data.get('memory_used', 0)
                mem_total = gpu_data.get('memory_total', 1)
                mem_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0
                right_lines.append(f"  VRAM: {mem_pct:4.1f}%")
                right_lines.append(f"  {mem_used:.0f}/{mem_total:.0f} MB")
                
                # GPU Clock - always show for Intel GPU (0 when idle is valid)
                clock = gpu_data.get('clock_graphics', 0) or gpu_data.get('gpu_clock', 0)
                # Always show GPU clock (0 MHz means idle, which is valid info)
                right_lines.append(f"  GPU Clock: {clock} MHz")
                
                # Memory Clock - only show if non-zero (Intel integrated GPU doesn't have separate memory clock)
                mem_clock = gpu_data.get('clock_memory', 0) or gpu_data.get('memory_clock', 0)
                if mem_clock > 0:
                    right_lines.append(f"  Mem Clock: {mem_clock} MHz")
        
        # Combine left and right columns
        lines.append("".ljust(width))
        
        # Add section headers on the same line
        header_line = f"{'📊 CPU':<{half_width}}  {'💾 Memory':<{half_width}}"
        lines.append(header_line.ljust(width))
        
        # Skip the first line (title) from both columns as we already added them
        left_content = left_lines[1:]  # Skip "📊 CPU"
        right_content = right_lines[1:]  # Skip "💾 Memory"
        
        max_lines = max(len(left_content), len(right_content))
        for i in range(max_lines):
            left = left_content[i] if i < len(left_content) else ""
            right = right_content[i] if i < len(right_content) else ""
            combined = f"{left:<{half_width}}  {right:<{half_width}}"
            lines.append(combined.ljust(width))
        
        # NPU Section (if available, full width)
        npu = snapshot.npu
        if npu.get('available'):
            lines.append("".ljust(width))
            lines.append("🧠 NPU".ljust(width))
            lines.append(f"  Device: {npu.get('device_name', 'Unknown')}".ljust(width))
            util = npu.get('utilization', 0)
            lines.append(f"  Usage: {self._format_bar(util, 30)}".ljust(width))
            if npu.get('power', 0) > 0:
                lines.append(f"  Power: {npu['power']:.2f} W".ljust(width))
        
        # Network Section (simplified)
        net = snapshot.network
        if net['io_stats']:
            io = net['io_stats']
            # Convert bytes/sec to MB/s (1 MB = 1024 * 1024 bytes)
            up = io.get('upload_speed', 0) / (1024 * 1024)
            down = io.get('download_speed', 0) / (1024 * 1024)
            
            lines.append("".ljust(width))
            lines.append("🌐 Network".ljust(width))
            lines.append(f"  ↑ {up:6.2f} MB/s    ↓ {down:6.2f} MB/s".ljust(width))
            lines.append(f"  Packets: TX {io['packets_sent']:,} / RX {io['packets_recv']:,}".ljust(width))
        
        # Show active interfaces (compact)
        if net['interfaces'] and net['interface_stats']:
            active_ifaces = [(name, net['interface_stats'].get(name, {})) 
                           for name in net['interfaces'] 
                           if net['interface_stats'].get(name, {}).get('is_up', False)][:3]
            if active_ifaces:
                iface_list = ", ".join([name for name, _ in active_ifaces])
                lines.append(f"  Active: {iface_list}".ljust(width))
        
        # Disk Section (simplified)
        disk = snapshot.disk
        if disk['io_stats']:
            io = disk['io_stats']
            # Prefer pre-calculated MB/s values if available
            read_speed = io.get('read_speed_mb', io.get('read_speed', 0) / (1024 * 1024))
            write_speed = io.get('write_speed_mb', io.get('write_speed', 0) / (1024 * 1024))
            lines.append("".ljust(width))
            lines.append("💿 Disk I/O".ljust(width))
            lines.append(f"  R {read_speed:6.2f} MB/s ({io['read_iops']:5.0f} IOPS)    W {write_speed:6.2f} MB/s ({io['write_iops']:5.0f} IOPS)".ljust(width))
        
        # Partition usage (compact, main partitions only)
        if disk['partition_usage']:
            main_parts = [p for p in disk['partition_usage'] 
                         if not p['path'].startswith('/snap')][:3]
            if main_parts:
                lines.append("  Storage:".ljust(width))
                for part in main_parts:
                    path = part['path'][:20]  # Truncate long paths
                    lines.append(f"    {path:20s} {self._format_bar(part['percent'], 12)} {part['used']:5.0f}/{part['total']:5.0f} GB".ljust(width))
        
        # Tier 1 Metrics Section (if available)
        tier1 = snapshot.tier1
        if tier1 and any(tier1.values()):
            lines.append("".ljust(width))
            lines.append("📊 System Metrics (Tier 1)".ljust(width))
            
            # Context switches (show prominently)
            ctx_switches = tier1.get('context_switches', 0)
            if ctx_switches > 0:
                lines.append(f"  Context Switches: {ctx_switches:,}/s".ljust(width))
            
            # Load average
            load_avg = tier1.get('load_avg', {}) or tier1.get('load_average', {})
            if load_avg:
                load_1 = load_avg.get('1min', 0)
                load_5 = load_avg.get('5min', 0)
                load_15 = load_avg.get('15min', 0)
                if any([load_1, load_5, load_15]):
                    lines.append(f"  Load Average: {load_1:.2f} (1m)  {load_5:.2f} (5m)  {load_15:.2f} (15m)".ljust(width))
            
            # Process counts (handle both field name variations)
            process_counts = tier1.get('process_counts', {}) or tier1.get('processes', {})
            if process_counts:
                running = process_counts.get('running', 0)
                blocked = process_counts.get('blocked', 0)
                total = process_counts.get('total', 0)
                if total > 0:
                    lines.append(f"  Processes: {total} total, {running} running, {blocked} blocked".ljust(width))
                elif running or blocked:
                    lines.append(f"  Processes: {running} running, {blocked} blocked".ljust(width))
            
            # Interrupts (top 5)
            interrupts = tier1.get('interrupts', {})
            if interrupts and 'interrupts' in interrupts:
                irq_list = interrupts['interrupts']
                if irq_list:
                    lines.append("  Top Interrupts (counts/sec):".ljust(width))
                    for irq in irq_list[:5]:  # Top 5
                        name = irq.get('name', 'Unknown')[:25]
                        # Try rate first (delta), fallback to total
                        count = irq.get('rate', irq.get('total', 0))
                        lines.append(f"    {name:25s} {count:>10,}".ljust(width))
        
        # Footer
        lines.append("".ljust(width))
        lines.append("=" * width)
        
        # Show save status if active (within last 5 seconds)
        if self.save_status_message and (time.time() - self.save_status_time < 5.0):
            lines.append(f" {self.save_status_message}".ljust(width))
            
        footer = f"⏱  {self.update_interval}s | 'q' quit | 'c' CPU | 'g' GPU | 's' Save"
        lines.append(footer.ljust(width))
        
        # Pad to terminal height to prevent scrolling
        while len(lines) < self.term_height - 1:
            lines.append("".ljust(width))
        
        return "\n".join(lines)
    
    def _background_logging_worker(self):
        """Background thread worker for continuous data logging."""
        next_log_time = time.time()
        logging_start_time = time.time()  # Track when logging actually started (PC time)
        android_start_timestamp_ms = None  # Track Android device start time (for ADB mode)
        last_logged_device_timestamp_ms = None  # Track last device timestamp to avoid duplicate samples
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if it's time to collect and log data
                if current_time >= next_log_time:
                    # Get monitoring data as unified snapshot
                    snapshot = self._get_all_data()
                    
                    # Calculate time_seconds for session tracking
                    if hasattr(self.data_source, 'get_timestamp_ms'):
                        # Android mode: use device timestamp
                        android_timestamp_ms = self.data_source.get_timestamp_ms()
                        if android_start_timestamp_ms is None:
                            android_start_timestamp_ms = android_timestamp_ms
                        snapshot.time_seconds = (android_timestamp_ms - android_start_timestamp_ms) / 1000.0
                        
                        # Skip logging if device timestamp hasn't changed (duplicate sample)
                        # This happens when PC logs faster than device produces new samples
                        if last_logged_device_timestamp_ms is not None and android_timestamp_ms == last_logged_device_timestamp_ms:
                            # Update display but don't log duplicate to database/exporter
                            with self.logging_lock:
                                self.latest_data = snapshot
                            next_log_time += self.update_interval
                            continue
                        
                        last_logged_device_timestamp_ms = android_timestamp_ms
                    else:
                        # Local/SSH mode: use PC time
                        snapshot.time_seconds = current_time - logging_start_time
                    
                    # Store latest data for UI thread (thread-safe)
                    with self.logging_lock:
                        self.latest_data = snapshot
                    
                    # Log data to database (only for local monitoring)
                    if self.logger:
                        self.logger.log_data(
                            cpu_info=snapshot.cpu,
                            memory_info=snapshot.memory,
                            gpu_info=snapshot.gpu,
                            npu_info=snapshot.npu,
                            tier1_info=snapshot.tier1  # Tier1 now automatically included!
                        )
                    
                    # Add to session exporter (for Android/SSH export)
                    # For LocalDataSource, we rely on SQLite DB to avoid double storage in memory
                    if self.data_exporter and not isinstance(self.data_source, LocalDataSource):
                        self.data_exporter.add_sample(snapshot.to_dict())
                    
                    # Schedule next log time (prevents drift)
                    next_log_time += self.update_interval
                    
                    # If we're falling behind, reset to current time
                    if next_log_time < current_time:
                        next_log_time = current_time + self.update_interval
                else:
                    # Sleep until next log time (with small buffer to avoid oversleeping)
                    sleep_time = next_log_time - time.time() - 0.01
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        # Very close to next log time, yield CPU briefly
                        time.sleep(0.001)
                
            except Exception as e:
                # Don't crash the logging thread on errors
                import traceback
                print(f"\n[Background] Logging error: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                # Reset next log time on error
                next_log_time = time.time() + self.update_interval
    
    def run_interactive(self, export_format: Optional[str] = None, export_output: Optional[str] = None):
        """Run interactive monitoring with live updates using curses.
        
        Args:
            export_format: Export format when exiting (csv/json/html)
            export_output: Output filename for export
        """
        # Record session start time (UTC for SQLite compatibility)
        from datetime import datetime, timezone, timedelta
        # SQLite CURRENT_TIMESTAMP is UTC, so we need to store UTC time for comparison
        utc_now = datetime.now(timezone.utc)
        self.session_start_time = utc_now.strftime('%Y-%m-%d %H:%M:%S')
        
        # Update data exporter start time (for Android mode)
        if self.data_exporter:
            self.data_exporter.start_time = datetime.now()
        
        # Set running flag before starting background thread
        self.running = True
        
        # Pre-populate latest_data before starting background thread
        self.latest_data = self._get_all_data()
        
        # Start background logging thread
        self.logging_thread = threading.Thread(
            target=self._background_logging_worker,
            daemon=True
        )
        self.logging_thread.start()
        
        try:
            curses.wrapper(lambda stdscr: self._run_curses(stdscr, export_format, export_output))
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            # Wait for logging thread to finish
            if self.logging_thread and self.logging_thread.is_alive():
                self.logging_thread.join(timeout=2.0)
        
        # Export on exit if requested (only this session's data)
        if export_format:
            print(f"\n📊 Exporting session data...")
            # Use local time for database query (DataLogger uses localtime)
            local_now = datetime.now()
            session_end_time = local_now.strftime('%Y-%m-%d %H:%M:%S')
            # Display local time for user
            local_start = utc_now.astimezone()
            local_end = local_now
            print(f"   Session: {local_start.strftime('%Y-%m-%d %H:%M:%S')} to {local_end.strftime('%Y-%m-%d %H:%M:%S')} (local time)")
            
            # Convert UTC session_start_time to local time for database query
            utc_start = datetime.strptime(self.session_start_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            local_start_time = utc_start.astimezone().strftime('%Y-%m-%d %H:%M:%S')
            
            self.export_data(
                format=export_format, 
                output_file=export_output,
                start_time=local_start_time,
                end_time=session_end_time
            )
        
        print("\n✓ Monitor stopped")
    
    def _show_cpu_control_menu(self, stdscr):
        """Show CPU frequency and governor control menu."""
        # Save current settings
        old_curs = curses.curs_set(0)
        try:
            curses.curs_set(1)  # Show cursor
        except:
            pass
        
        stdscr.nodelay(0)    # Blocking input
        stdscr.timeout(-1)   # Wait indefinitely for input
        
        height, width = stdscr.getmaxyx()
        
        # Get current info
        freq_range = self.freq_controller.get_cpu_freq_range()
        governors = self.freq_controller.get_available_cpu_governors()
        current_gov = self.freq_controller.get_current_cpu_governor()
        
        while True:
            stdscr.clear()
            
            # Title
            title = "=== CPU Control Menu ==="
            stdscr.addstr(0, (width - len(title)) // 2, title)
            
            # Current status
            row = 2
            stdscr.addstr(row, 2, f"Current Governor: {current_gov}")
            row += 1
            if freq_range:
                stdscr.addstr(row, 2, f"Freq Range: {freq_range.get('scaling_min', 0):.0f} - {freq_range.get('scaling_max', 0):.0f} MHz")
                row += 1
                stdscr.addstr(row, 2, f"HW Limits: {freq_range.get('hardware_min', 0):.0f} - {freq_range.get('hardware_max', 0):.0f} MHz")
                row += 2
            
            # Menu options
            stdscr.addstr(row, 2, "1. Set Governor")
            row += 1
            stdscr.addstr(row, 2, "2. Set Frequency Range")
            row += 1
            stdscr.addstr(row, 2, "3. Performance Mode (max freq)")
            row += 1
            stdscr.addstr(row, 2, "4. Powersave Mode")
            row += 1
            stdscr.addstr(row, 2, "q. Back to Monitor")
            row += 2
            
            stdscr.addstr(row, 2, "Choice: ")
            stdscr.refresh()
            
            # Get input - use getch() for single character
            key = stdscr.getch()
            choice = chr(key) if key < 256 else ''
            
            if choice == 'q' or choice == '':
                break
            elif choice == '1':
                # Set governor
                self._set_governor_interactive(stdscr, governors)
                current_gov = self.freq_controller.get_current_cpu_governor()
            elif choice == '2':
                # Set frequency range
                self._set_cpu_freq_interactive(stdscr, freq_range)
                freq_range = self.freq_controller.get_cpu_freq_range()
            elif choice == '3':
                # Performance mode
                if self.freq_controller.set_cpu_performance_mode():
                    stdscr.addstr(row + 2, 2, "✓ Set to Performance mode (press any key)")
                    current_gov = 'performance'
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed (check sudo permissions) (press any key)")
                stdscr.refresh()
                stdscr.getch()
            elif choice == '4':
                # Powersave mode
                if self.freq_controller.set_cpu_powersave_mode():
                    stdscr.addstr(row + 2, 2, "✓ Set to Powersave mode (press any key)")
                    current_gov = 'powersave'
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed (check sudo permissions) (press any key)")
                stdscr.refresh()
                stdscr.getch()
        
        # Restore settings
        try:
            curses.curs_set(0)  # Hide cursor
        except:
            pass
        stdscr.nodelay(1)    # Non-blocking input
        stdscr.timeout(100)  # Restore timeout

    
    def _set_governor_interactive(self, stdscr, governors):
        """Interactive governor selection."""
        # Enable echo for input
        curses.echo()
        
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        
        row = 2
        stdscr.addstr(row, 2, "Available Governors:")
        row += 1
        
        for i, gov in enumerate(governors, 1):
            stdscr.addstr(row, 4, f"{i}. {gov}")
            row += 1
        
        row += 1
        stdscr.addstr(row, 2, "Select governor (number): ")
        stdscr.refresh()
        
        choice = stdscr.getstr(row, 28, 5).decode('utf-8').strip()
        
        # Disable echo
        curses.noecho()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(governors):
                gov = governors[idx]
                if self.freq_controller.set_cpu_governor(gov):
                    stdscr.addstr(row + 2, 2, f"✓ Governor set to {gov} (press any key)")
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed to set governor (press any key)")
            else:
                stdscr.addstr(row + 2, 2, "✗ Invalid choice (press any key)")
        except ValueError:
            stdscr.addstr(row + 2, 2, "✗ Invalid input (press any key)")
        
        stdscr.refresh()
        stdscr.getch()
    
    def _set_cpu_freq_interactive(self, stdscr, freq_range):
        """Interactive CPU frequency range setting."""
        # Enable echo for input
        curses.echo()
        
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        
        row = 2
        hw_min = freq_range.get('hardware_min', 800)
        hw_max = freq_range.get('hardware_max', 5000)
        
        stdscr.addstr(row, 2, f"Hardware limits: {hw_min:.0f} - {hw_max:.0f} MHz")
        row += 2
        
        stdscr.addstr(row, 2, f"Min frequency (MHz): ")
        stdscr.refresh()
        min_str = stdscr.getstr(row, 23, 10).decode('utf-8').strip()
        
        row += 1
        stdscr.addstr(row, 2, f"Max frequency (MHz): ")
        stdscr.refresh()
        max_str = stdscr.getstr(row, 23, 10).decode('utf-8').strip()
        
        # Disable echo
        curses.noecho()
        
        try:
            min_freq = int(min_str)
            max_freq = int(max_str)
            
            if min_freq > max_freq:
                stdscr.addstr(row + 2, 2, "✗ Min cannot be greater than max (press any key)")
            elif min_freq < hw_min or max_freq > hw_max:
                stdscr.addstr(row + 2, 2, f"✗ Out of range {hw_min:.0f}-{hw_max:.0f} (press any key)")
            else:
                if self.freq_controller.set_cpu_freq_range(min_freq, max_freq):
                    stdscr.addstr(row + 2, 2, f"✓ Frequency range set to {min_freq}-{max_freq} MHz (press any key)")
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed to set frequency (press any key)")
        except ValueError:
            stdscr.addstr(row + 2, 2, "✗ Invalid input (press any key)")
        
        stdscr.refresh()
        stdscr.getch()
    
    def _show_gpu_control_menu(self, stdscr):
        """Show GPU frequency control menu."""
        # Save current settings
        try:
            curses.curs_set(1)  # Show cursor
        except:
            pass
        
        stdscr.nodelay(0)    # Blocking input
        stdscr.timeout(-1)   # Wait indefinitely
        
        height, width = stdscr.getmaxyx()
        
        # Get current info
        freq_range = self.freq_controller.get_gpu_freq_range()
        
        if not freq_range:
            stdscr.clear()
            stdscr.addstr(2, 2, "✗ GPU frequency control not available")
            stdscr.addstr(3, 2, "Press any key to return...")
            stdscr.refresh()
            stdscr.getch()
            try:
                curses.curs_set(0)
            except:
                pass
            stdscr.nodelay(1)
            stdscr.timeout(100)
            return
        
        while True:
            stdscr.clear()
            
            # Title
            title = "=== GPU Control Menu ==="
            stdscr.addstr(0, (width - len(title)) // 2, title)
            
            # Current status
            row = 2
            stdscr.addstr(row, 2, f"GPU Type: {freq_range.get('type', 'Unknown')}")
            row += 1
            stdscr.addstr(row, 2, f"Card: {freq_range.get('card', 'Unknown')}")
            row += 1
            stdscr.addstr(row, 2, f"Current: {freq_range.get('current', 0)} MHz")
            row += 1
            stdscr.addstr(row, 2, f"Range: {freq_range.get('scaling_min', 0)} - {freq_range.get('scaling_max', 0)} MHz")
            row += 1
            stdscr.addstr(row, 2, f"HW Limits: {freq_range.get('hardware_min', 0)} - {freq_range.get('hardware_max', 0)} MHz")
            row += 2
            
            # Menu options
            stdscr.addstr(row, 2, "1. Set GPU Frequency Range")
            row += 1
            stdscr.addstr(row, 2, "2. Lock to Max Frequency")
            row += 1
            stdscr.addstr(row, 2, "3. Lock to Min Frequency")
            row += 1
            stdscr.addstr(row, 2, "q. Back to Monitor")
            row += 2
            
            stdscr.addstr(row, 2, "Choice: ")
            stdscr.refresh()
            
            # Get input - use getch() for single character
            key = stdscr.getch()
            choice = chr(key) if key < 256 else ''
            
            if choice == 'q' or choice == '':
                break
            elif choice == '1':
                # Set frequency range
                self._set_gpu_freq_interactive(stdscr, freq_range)
                freq_range = self.freq_controller.get_gpu_freq_range()
            elif choice == '2':
                # Max frequency
                hw_max = freq_range.get('hardware_max', 0)
                if self.freq_controller.set_gpu_freq_range(hw_max, hw_max):
                    stdscr.addstr(row + 2, 2, f"✓ GPU locked to max {hw_max} MHz (press any key)")
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed (check sudo permissions) (press any key)")
                stdscr.refresh()
                stdscr.getch()
                freq_range = self.freq_controller.get_gpu_freq_range()
            elif choice == '3':
                # Min frequency
                hw_min = freq_range.get('hardware_min', 0)
                if self.freq_controller.set_gpu_freq_range(hw_min, hw_min):
                    stdscr.addstr(row + 2, 2, f"✓ GPU locked to min {hw_min} MHz (press any key)")
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed (check sudo permissions) (press any key)")
                stdscr.refresh()
                stdscr.getch()
                freq_range = self.freq_controller.get_gpu_freq_range()
        
        # Restore settings
        try:
            curses.curs_set(0)  # Hide cursor
        except:
            pass
        stdscr.nodelay(1)    # Non-blocking input
        stdscr.timeout(100)  # Restore timeout
    
    def _set_gpu_freq_interactive(self, stdscr, freq_range):
        """Interactive GPU frequency range setting."""
        # Enable echo for input
        curses.echo()
        
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        
        row = 2
        hw_min = freq_range.get('hardware_min', 0)
        hw_max = freq_range.get('hardware_max', 0)
        
        stdscr.addstr(row, 2, f"Hardware limits: {hw_min} - {hw_max} MHz")
        row += 2
        
        stdscr.addstr(row, 2, f"Min frequency (MHz): ")
        stdscr.refresh()
        min_str = stdscr.getstr(row, 23, 10).decode('utf-8').strip()
        
        row += 1
        stdscr.addstr(row, 2, f"Max frequency (MHz): ")
        stdscr.refresh()
        max_str = stdscr.getstr(row, 23, 10).decode('utf-8').strip()
        
        # Disable echo
        curses.noecho()
        
        try:
            min_freq = int(min_str)
            max_freq = int(max_str)
            
            if min_freq > max_freq:
                stdscr.addstr(row + 2, 2, "✗ Min cannot be greater than max (press any key)")
            elif min_freq < hw_min or max_freq > hw_max:
                stdscr.addstr(row + 2, 2, f"✗ Out of range {hw_min}-{hw_max} (press any key)")
            else:
                if self.freq_controller.set_gpu_freq_range(min_freq, max_freq):
                    stdscr.addstr(row + 2, 2, f"✓ GPU frequency set to {min_freq}-{max_freq} MHz (press any key)")
                else:
                    stdscr.addstr(row + 2, 2, "✗ Failed to set frequency (press any key)")
        except ValueError:
            stdscr.addstr(row + 2, 2, "✗ Invalid input (press any key)")
        
        stdscr.refresh()
        stdscr.getch()

    def _show_save_menu(self, stdscr):
        """Show save menu."""
        # Save current settings
        try:
            curses.curs_set(1)  # Show cursor
        except:
            pass
        
        stdscr.nodelay(0)    # Blocking input
        stdscr.timeout(-1)   # Wait indefinitely
        
        height, width = stdscr.getmaxyx()
        
        while True:
            stdscr.clear()
            
            # Title
            title = "=== Save Data Menu ==="
            stdscr.addstr(0, (width - len(title)) // 2, title)
            
            row = 2
            stdscr.addstr(row, 2, "Select format to save:")
            row += 2
            
            stdscr.addstr(row, 2, "1. Save All (CSV, JSON, HTML)")
            row += 1
            stdscr.addstr(row, 2, "2. Save to JSON")
            row += 1
            stdscr.addstr(row, 2, "3. Save to CSV")
            row += 1
            stdscr.addstr(row, 2, "4. Save to HTML")
            row += 1
            stdscr.addstr(row, 2, "q. Cancel")
            row += 2
            
            stdscr.addstr(row, 2, "Choice: ")
            stdscr.refresh()
            
            key = stdscr.getch()
            choice = chr(key) if key < 256 else ''
            
            formats = []
            if choice == 'q' or choice == '':
                break
            elif choice == '1':
                formats = ['csv', 'json', 'html']
                break
            elif choice == '2':
                formats = ['json']
                break
            elif choice == '3':
                formats = ['csv']
                break
            elif choice == '4':
                formats = ['html']
                break
        
        # Restore settings
        try:
            curses.curs_set(0)  # Hide cursor
        except:
            pass
        stdscr.nodelay(1)    # Non-blocking input
        stdscr.timeout(100)  # Restore timeout
        
        return formats

    def _save_data_async(self, formats: List[str]):
        """Save data in a background thread."""
        def save_worker():
            # Redirect stdout to prevent messing up curses display
            import io
            from contextlib import redirect_stdout
            
            f = io.StringIO()
            try:
                with redirect_stdout(f):
                    self.save_status_message = "💾 Saving data..."
                    self.save_status_time = time.time()
                    
                    saved_files = []
                    
                    # Use local time for filename timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    
                    for fmt in formats:
                        filename = f"monitoring_data_{timestamp}.{fmt}"
                        if fmt == 'csv':
                            path = self.data_exporter.export_csv(filename=filename)
                            saved_files.append(os.path.basename(path))
                        elif fmt == 'json':
                            path = self.data_exporter.export_json(filename=filename)
                            saved_files.append(os.path.basename(path))
                        elif fmt == 'html':
                            path = self.data_exporter.export_html(filename=filename)
                            saved_files.append(os.path.basename(path))
                    
                    if saved_files:
                        self.save_status_message = f"✓ Saved: {', '.join(saved_files)}"
                    else:
                        self.save_status_message = "⚠️ No data saved"
                    self.save_status_time = time.time()
                
            except Exception as e:
                self.save_status_message = f"❌ Save failed: {str(e)}"
                self.save_status_time = time.time()
        
        threading.Thread(target=save_worker, daemon=True).start()
    
    def _run_curses(self, stdscr, export_format: Optional[str] = None, export_output: Optional[str] = None):
        """Run monitoring loop with curses for flicker-free updates."""
        # Note: self.running is already set to True in run_interactive()
        
        # Configure curses
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        stdscr.timeout(100) # Refresh timeout
        
        # Get screen size
        height, width = stdscr.getmaxyx()
        self.term_height = height
        self.term_width = width
        
        export_msg = f" | Export on exit: {export_format.upper()}" if export_format else ""
        stdscr.addstr(0, 0, f"🚀 Starting CLI Monitor (Press 'q' to stop{export_msg})...")
        stdscr.refresh()
        time.sleep(1)
        
        last_update = time.time()
        
        while self.running:
            try:
                # Check for user input (Ctrl+C or 'q' to quit)
                # Non-blocking: getch() returns -1 if no key pressed
                key = stdscr.getch()
                if key == ord('q') or key == 3:  # 'q' or Ctrl+C
                    break
                elif key == ord('c'):  # CPU control menu
                    self._show_cpu_control_menu(stdscr)
                    stdscr.clear()  # Clear after menu
                    last_update = time.time()  # Reset timer after menu
                elif key == ord('g'):  # GPU control menu
                    self._show_gpu_control_menu(stdscr)
                    stdscr.clear()  # Clear after menu
                    last_update = time.time()  # Reset timer after menu
                elif key == ord('s'):  # Save data menu
                    formats = self._show_save_menu(stdscr)
                    if formats:
                        self._save_data_async(formats)
                    stdscr.clear()  # Clear after menu
                    last_update = time.time()  # Reset timer after menu
                
                # Get latest data from background thread (thread-safe)
                with self.logging_lock:
                    snapshot = self.latest_data
                
                # Skip if no data available yet
                if snapshot is None:
                    time.sleep(0.05)
                    continue
                
                # Check if it's time to update display
                current_time = time.time()
                if current_time - last_update < self.update_interval:
                    # Don't sleep here - just continue to check for input again
                    # This makes the loop more responsive to 'q' key presses
                    continue
                
                last_update = current_time
                
                # Clear screen and draw dashboard
                stdscr.clear()
                dashboard = self._format_dashboard(snapshot)
                
                # Draw each line
                for i, line in enumerate(dashboard.split('\n')):
                    if i < height:
                        try:
                            stdscr.addstr(i, 0, line[:width-1])
                        except curses.error:
                            pass  # Ignore errors at screen edge
                
                stdscr.refresh()
                
                # No sleep here - controlled by last_update timing
                
            except KeyboardInterrupt:
                break
        
        self.running = False
        
    def export_data(self, format: str = 'csv', output_file: Optional[str] = None, 
                   start_time: Optional[str] = None, end_time: Optional[str] = None):
        """Export logged data.
        
        Args:
            format: Export format ('csv', 'json', or 'html')
            output_file: Output file path (auto-generated if None)
            start_time: Start time filter (ISO format)
            end_time: End time filter (ISO format)
        """
        # For HTML export, we need to use the session-based DataExporter
        if format == 'html':
            # Check if local database exists (only for LocalDataSource)
            if not self.logger:
                # Android mode - use session data collected during monitoring
                if not self.data_exporter or not self.data_exporter.session_data:
                    print(f"❌ No monitoring data to export")
                    return
                
                if not output_file:
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_file = f"android_report_{timestamp}.html"
                
                # Export using collected session data (use_android_db=False to skip DB pull)
                success = self.data_exporter.export_html(output_file, use_android_db=False)
                if success:
                    print(f"✓ HTML report exported to {output_file}")
                else:
                    print(f"❌ Export failed")
                return
            
            # Local mode - load data from local database and export
            try:
                import sqlite3
                conn = sqlite3.connect(self.logger.db_path)
                cursor = conn.cursor()
                
                # Build query with time filters
                query = "SELECT * FROM monitoring_data"
                params = []
                if start_time or end_time:
                    conditions = []
                    if start_time:
                        conditions.append("timestamp >= ?")
                        params.append(start_time)
                    if end_time:
                        conditions.append("timestamp <= ?")
                        params.append(end_time)
                    query += " WHERE " + " AND ".join(conditions)
                query += " ORDER BY timestamp"
                
                # Debug: print query details
                if start_time or end_time:
                    print(f"   Query: {query}")
                    print(f"   Params: {params}")
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                conn.close()
                
                print(f"   Found {len(rows)} data points")
                
                if not rows:
                    print("❌ No data found for the specified time range")
                    return
                
                # Create exporter and add samples
                exporter = DataExporter(data_source=self.data_source)
                first_timestamp = None  # Renamed to avoid conflict with parameter
                
                for i, row in enumerate(rows):
                    data = dict(zip(columns, row))
                    
                    # Parse full data from JSON field
                    try:
                        full_data = json.loads(data.get('data_json', '{}'))
                    except:
                        full_data = {}
                    
                    # Calculate time_seconds from start
                    timestamp_str = data.get('timestamp', '')
                    if first_timestamp is None and timestamp_str:
                        # Database stores local time, parse as local
                        from datetime import datetime, timezone
                        local_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        first_timestamp = local_time
                    
                    if first_timestamp and timestamp_str:
                        local_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        time_seconds = (local_time - first_timestamp).total_seconds()
                        # Timestamp is already in local time
                        timestamp_local = timestamp_str
                    else:
                        time_seconds = i
                        timestamp_local = timestamp_str
                    
                    # Build sample in GUI format (with full data from JSON)
                    sample = {
                        'timestamp': timestamp_local,
                        'time_seconds': time_seconds,
                        'cpu': full_data.get('cpu', {}),
                        'memory': full_data.get('memory', {}),
                        'gpu': full_data.get('gpu', {}),
                        'npu': full_data.get('npu', {}),
                    }
                    exporter.add_sample(sample)
                
                # Export to HTML
                if not output_file:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_file = f"monitor_report_{timestamp}.html"
                
                filepath = exporter.export_html(output_file)
                print(f"✓ HTML report exported to {filepath}")
                return
                
            except Exception as e:
                print(f"❌ HTML export failed: {e}")
                import traceback
                traceback.print_exc()
                return
        
        # For CSV/JSON, use the database exporter
        if not self.logger:
            print(f"❌ CSV/JSON export not available for Android monitoring")
            print(f"   Use HTML export instead: --export-format html")
            return
        
        exporter = DataExporter(db_path=self.logger.db_path, data_source=self.data_source)
        
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
  
  # Monitor Android device via ADB
  %(prog)s --adb --ip 192.168.1.68
  
  # Monitor remote Linux via SSH
  %(prog)s --ssh --host 192.168.1.100 --user username
  
  # Monitor Android device with custom port
  %(prog)s --adb --ip 172.25.65.75 --port 5555
  
  # With faster updates
  %(prog)s --interval 0.5
  
  # Run and export HTML when you press 'q' to exit
  %(prog)s --export-format html --output report.html
  
  # Android monitoring with export on exit
  %(prog)s --adb --ip 192.168.1.68 --export-format html
  
  # SSH monitoring with export on exit
  %(prog)s --ssh --host 192.168.1.100 --user admin -e html
  
  # Run and export CSV on exit
  %(prog)s -e csv
  
  # Single snapshot in JSON format
  %(prog)s --once --format json
  
  # Simple one-line output (good for scripts)
  %(prog)s --once --format simple
  
Note: Logging is always enabled. Use --export-format to auto-export when you quit.
        """
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=float,
        default=1.0,
        help='Update interval in seconds (default: 1.0)'
    )
    
    parser.add_argument(
        '--adb',
        action='store_true',
        help='Monitor Android device via ADB'
    )
    
    parser.add_argument(
        '--ip',
        type=str,
        default='192.168.1.68',
        help='Android device IP address (default: 192.168.1.68)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5555,
        help='ADB port (default: 5555)'
    )
    
    # SSH remote Linux support
    parser.add_argument(
        '--ssh',
        action='store_true',
        help='Monitor remote Linux system via SSH'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        help='Remote Linux host (IP or hostname)'
    )
    
    parser.add_argument(
        '--user',
        type=str,
        help='SSH username'
    )
    
    parser.add_argument(
        '--ssh-port',
        type=int,
        default=22,
        help='SSH port (default: 22)'
    )
    
    parser.add_argument(
        '--key',
        type=str,
        help='Path to SSH private key'
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
        help='Output format for --once mode (default: text)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Write output to file'
    )
    
    parser.add_argument(
        '--export-format', '-e',
        choices=['csv', 'json', 'html'],
        help='Export logged data from database (csv/json/html)'
    )
    
    parser.add_argument(
        '--export-only',
        action='store_true',
        help='Only export data, do not start monitoring. Use with --export-format.'
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
    
    # Load configuration
    config_path = Path(__file__).parent.parent / 'config' / 'default.yaml'
    enable_tier1 = False
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            # tier1_metrics is under monitoring section
            enable_tier1 = config.get('monitoring', {}).get('tier1_metrics', {}).get('enabled', False)
    except ImportError:
        # yaml module not installed, use default
        pass
    except Exception as e:
        print(f"⚠️  Warning: Could not load config file: {e}")
        print(f"   Using default tier1_metrics.enabled = False")
    
    # Create data source based on mode
    if args.ssh:
        if not args.host or not args.user:
            print("❌ Error: --host and --user are required for SSH mode")
            print("   Example: monitor-tool-cli --ssh --host 192.168.1.100 --user username")
            return 1
        
        print(f"🐧 Remote Linux Monitor Mode")
        print(f"📡 Host: {args.user}@{args.host}:{args.ssh_port}")
        
        # Try to connect with up to 3 password attempts
        data_source = None
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            # Get password or key passphrase
            password = None
            if args.key:
                # Using SSH key - may need passphrase
                if attempt == 1:
                    # First try without passphrase
                    password = None
                else:
                    # Key needs passphrase
                    print(f"⚠️  Key requires passphrase. Attempt {attempt}/{max_attempts}")
                    password = getpass.getpass(f"🔑 Passphrase for SSH key: ")
            else:
                # Using password authentication
                if attempt == 1:
                    password = getpass.getpass(f"🔒 SSH password for {args.user}@{args.host}: ")
                else:
                    print(f"⚠️  Authentication failed. Attempt {attempt}/{max_attempts}")
                    password = getpass.getpass(f"🔒 SSH password for {args.user}@{args.host}: ")
            
            data_source = RemoteLinuxDataSource(
                host=args.host,
                username=args.user,
                password=password,
                port=args.ssh_port,
                key_path=args.key,
                enable_tier1=enable_tier1
            )
            
            # Try to connect
            print(f"🔌 Connecting to {args.user}@{args.host}:{args.ssh_port}...")
            if data_source.connect():
                print("✅ Connection successful!")
                break
            else:
                print(f"❌ Connection failed")
                data_source.disconnect()
                data_source = None
        
        # If all attempts failed, exit
        if data_source is None:
            if args.key:
                print(f"❌ SSH key authentication failed after {max_attempts} attempts")
            else:
                print(f"❌ Failed to connect after {max_attempts} attempts")
            return 1
            
    elif args.adb:
        print(f"🤖 Android Monitor Mode")
        print(f"📱 Device: {args.ip}:{args.port}")
        data_source = AndroidDataSource(args.ip, args.port, enable_tier1=enable_tier1)
    else:
        data_source = LocalDataSource(enable_tier1=enable_tier1)
    
    # Create monitor instance (logging always enabled)
    monitor = CLIMonitor(data_source=data_source, update_interval=args.interval)
    
    try:
        if args.export_only:
            # Export-only mode: directly export from database without monitoring
            if not args.export_format:
                print("❌ Error: --export-only requires --export-format")
                return 1
            
            print(f"\n📊 Exporting session data...")
            if args.start_time or args.end_time:
                print(f"   Time range: {args.start_time or 'beginning'} to {args.end_time or 'now'}")
            else:
                print(f"   Exporting all data from database")
            
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
            # Interactive mode (with optional export on exit)
            monitor.run_interactive(
                export_format=args.export_format,
                export_output=args.output
            )
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == '__main__':
    sys.exit(main())
