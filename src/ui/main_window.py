#!/usr/bin/env python3
"""Main window for the monitoring tool."""

import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QLabel, QGroupBox, QGridLayout,
                             QStatusBar, QAction, QMessageBox, QApplication)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

from data_source import MonitorDataSource, LocalDataSource, AndroidDataSource, RemoteLinuxDataSource
from controllers import FrequencyController, ADBFrequencyController, SSHFrequencyController
from storage import DataLogger, DataExporter
from ui.widgets.plot_widget import MonitorPlotWidget, MultiLinePlotWidget
from ui.widgets.control_panel import ControlPanel
from ui.widgets.info_card import InfoCard
from ui.styles import apply_dark_theme, CHART_COLORS

import time


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, data_source: MonitorDataSource = None):
        """Initialize main window.
        
        Args:
            data_source: Data source for monitoring (defaults to LocalDataSource)
        """
        super().__init__()
        
        # Initialize data source
        if data_source is None:
            self.data_source = LocalDataSource()
        else:
            self.data_source = data_source
        
        # Connect to data source
        if not self.data_source.is_connected():
            self.data_source.connect()
        
        # Set window title based on data source
        self.setWindowTitle(f"System Monitor Tool - {self.data_source.get_source_name()}")
        self.setGeometry(100, 100, 1200, 800)
        
        # Store chart colors
        self.chart_colors = CHART_COLORS
        
        # Initialize frequency controller
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
            # Remote Linux system via SSH
            ssh_freq_ctrl = SSHFrequencyController(
                host=self.data_source.ssh_monitor.host,
                port=self.data_source.ssh_monitor.port,
                user=self.data_source.ssh_monitor.user
            )
            
            # Only use if available (cpufreq support)
            if ssh_freq_ctrl.is_available:
                self.freq_controller = ssh_freq_ctrl
                
                if ssh_freq_ctrl.has_sudo:
                    print(f"✅ SSH frequency control enabled (full access)")
                else:
                    print(f"⚠️  SSH frequency control enabled (read-only, no sudo)")
                    # Show setup dialog if no sudo
                    self._show_sudo_setup_dialog()
            else:
                self.freq_controller = None
                print(f"⚠️  SSH frequency control disabled (no cpufreq support)")
        else:
            self.freq_controller = None
        
        # Initialize storage
        # Only use local database for LocalDataSource
        # Android data is stored on Android device, not locally
        if isinstance(self.data_source, LocalDataSource):
            self.data_logger = DataLogger()
        else:
            self.data_logger = None  # Android mode - no local logging
        
        self.data_exporter = DataExporter(data_source=self.data_source)
        self._last_remote_timestamp_ms = None
        
        # Timing
        self.start_time = time.time()
        
        # Pre-fetch initial data to determine available features
        self._initial_cpu_info = self.data_source.get_cpu_info()
        self._initial_gpu_info = self.data_source.get_gpu_info()
        self._initial_npu_info = self.data_source.get_npu_info()
        
        # Initialize UI
        self.init_ui()
        self.init_menu()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(1000)  # Update every 1 second
        
        # Initial update
        self.update_data()
    
    def init_ui(self):
        """Initialize UI components."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Left side - Monitoring tabs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Overview tab
        overview_tab = self.create_overview_tab()
        self.tabs.addTab(overview_tab, "Overview")
        
        # CPU tab
        cpu_tab = self.create_cpu_tab()
        self.tabs.addTab(cpu_tab, "CPU")
        
        # Memory tab
        memory_tab = self.create_memory_tab()
        self.tabs.addTab(memory_tab, "Memory")
        
        # GPU tab (if available)
        if self._initial_gpu_info.get('available', False):
            gpu_tab = self.create_gpu_tab()
            self.tabs.addTab(gpu_tab, "GPU")
        
        # NPU tab (if available)
        if self._initial_npu_info.get('available', False):
            npu_tab = self.create_npu_tab()
            self.tabs.addTab(npu_tab, "NPU")
        
        # Network tab
        network_tab = self.create_network_tab()
        self.tabs.addTab(network_tab, "Network")
        
        # Disk tab
        disk_tab = self.create_disk_tab()
        self.tabs.addTab(disk_tab, "Disk")
        
        left_layout.addWidget(self.tabs)
        
        # Right side - Control panel
        self.control_panel = ControlPanel(self.freq_controller)
        
        # Add to main layout
        main_layout.addWidget(left_widget, stretch=3)
        main_layout.addWidget(self.control_panel, stretch=1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def create_overview_tab(self) -> QWidget:
        """Create overview tab with all system metrics."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info cards section
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        
        # CPU Card
        self.cpu_card = InfoCard("CPU", "📊")
        self.cpu_card.set_color("#4CAF50")
        cards_layout.addWidget(self.cpu_card)
        
        # Memory Card
        self.memory_card = InfoCard("Memory", "💾")
        self.memory_card.set_color("#2196F3")
        cards_layout.addWidget(self.memory_card)
        
        # GPU Card (if available)
        if self._initial_gpu_info.get('available', False):
            self.gpu_card = InfoCard("GPU", "🎮")
            self.gpu_card.set_color("#FF9800")
            cards_layout.addWidget(self.gpu_card)
        
        # NPU Card (if available)
        if self._initial_npu_info.get('available', False):
            self.npu_card = InfoCard("NPU", "🧠")
            self.npu_card.set_color("#00BCD4")
            cards_layout.addWidget(self.npu_card)
        
        # Network Card
        self.network_card = InfoCard("Network", "🌐")
        self.network_card.set_color("#9C27B0")
        cards_layout.addWidget(self.network_card)
        
        # Disk Card
        self.disk_card = InfoCard("Disk", "💿")
        self.disk_card.set_color("#F44336")
        cards_layout.addWidget(self.disk_card)
        
        layout.addLayout(cards_layout)
        
        # Charts section - 2x3 grid
        charts_group = QGroupBox("Real-time Monitoring")
        charts_layout = QGridLayout()
        charts_layout.setSpacing(10)
        
        # Row 1: CPU and Memory
        self.overview_cpu_plot = MonitorPlotWidget("CPU Usage (%)")
        self.overview_memory_plot = MonitorPlotWidget("Memory Usage (%)")
        charts_layout.addWidget(self.overview_cpu_plot, 0, 0)
        charts_layout.addWidget(self.overview_memory_plot, 0, 1)
        
        # Row 2: Network and Disk
        # Use KB/s for network to avoid scientific notation on small values
        self.overview_network_plot = MultiLinePlotWidget("Network Speed", 
                                                         y_label="Upload (KB/s)",
                                                         y_label2="Download (KB/s)")
        self.overview_disk_plot = MultiLinePlotWidget("Disk I/O", 
                                                      y_label="Read (MB/s)",
                                                      y_label2="Write (MB/s)")
        charts_layout.addWidget(self.overview_network_plot, 1, 0)
        charts_layout.addWidget(self.overview_disk_plot, 1, 1)
        
        # Row 3: GPU and NPU (if available)
        if self._initial_gpu_info.get('available', False):
            self.overview_gpu_plot = MultiLinePlotWidget("GPU Usage & Frequency",
                                                         y_label="Usage (%)",
                                                         y_label2="Freq (MHz)")
            charts_layout.addWidget(self.overview_gpu_plot, 2, 0)
        
        if self._initial_npu_info.get('available', False):
            self.overview_npu_plot = MultiLinePlotWidget("NPU Usage & Frequency",
                                                         y_label="Usage (%)",
                                                         y_label2="Freq (MHz)")
            charts_layout.addWidget(self.overview_npu_plot, 2, 1)
        
        charts_group.setLayout(charts_layout)
        layout.addWidget(charts_group)
        
        return widget
    
    def create_cpu_tab(self) -> QWidget:
        """Create CPU monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # CPU info
        info_group = QGroupBox("CPU Information")
        info_layout = QGridLayout()
        
        cpu_count = self._initial_cpu_info.get('cpu_count', 0)
        self.cpu_cores_label = QLabel(f"Cores: {cpu_count}")
        self.cpu_freq_label = QLabel("Frequency: -")
        self.cpu_temp_label = QLabel("Temperature: -")
        self.cpu_governor_label = QLabel("Governor: -")
        
        info_layout.addWidget(self.cpu_cores_label, 0, 0)
        info_layout.addWidget(self.cpu_freq_label, 0, 1)
        info_layout.addWidget(self.cpu_temp_label, 1, 0)
        info_layout.addWidget(self.cpu_governor_label, 1, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # CPU usage plot
        self.cpu_usage_plot = MonitorPlotWidget("CPU Usage (%)")
        layout.addWidget(self.cpu_usage_plot)
        
        # CPU frequency plot
        self.cpu_freq_plot = MonitorPlotWidget("CPU Frequency (MHz)", y_label="Frequency (MHz)")
        layout.addWidget(self.cpu_freq_plot)
        
        return widget
    
    def create_memory_tab(self) -> QWidget:
        """Create memory monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Memory info
        info_group = QGroupBox("Memory Information")
        info_layout = QGridLayout()
        
        self.mem_total_label = QLabel("Total: -")
        self.mem_used_label = QLabel("Used: -")
        self.mem_free_label = QLabel("Free: -")
        self.swap_label = QLabel("Swap: -")
        
        info_layout.addWidget(QLabel("Total:"), 0, 0)
        info_layout.addWidget(self.mem_total_label, 0, 1)
        info_layout.addWidget(QLabel("Used:"), 1, 0)
        info_layout.addWidget(self.mem_used_label, 1, 1)
        info_layout.addWidget(QLabel("Free:"), 2, 0)
        info_layout.addWidget(self.mem_free_label, 2, 1)
        info_layout.addWidget(QLabel("Swap:"), 3, 0)
        info_layout.addWidget(self.swap_label, 3, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Memory usage plot
        self.memory_usage_plot = MonitorPlotWidget("Memory Usage (%)")
        layout.addWidget(self.memory_usage_plot)
        
        return widget
    
    def create_gpu_tab(self) -> QWidget:
        """Create GPU monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # GPU info
        info_group = QGroupBox("GPU Information")
        info_layout = QGridLayout()
        
        self.gpu_name_label = QLabel("GPU: -")
        self.gpu_usage_label = QLabel("Usage: -")
        self.gpu_freq_label = QLabel("Frequency: -")
        self.gpu_temp_label = QLabel("Temperature: -")
        self.gpu_mem_label = QLabel("Memory: -")
        
        info_layout.addWidget(self.gpu_name_label, 0, 0, 1, 2)
        info_layout.addWidget(QLabel("Usage:"), 1, 0)
        info_layout.addWidget(self.gpu_usage_label, 1, 1)
        info_layout.addWidget(QLabel("Frequency:"), 2, 0)
        info_layout.addWidget(self.gpu_freq_label, 2, 1)
        info_layout.addWidget(QLabel("Temperature:"), 3, 0)
        info_layout.addWidget(self.gpu_temp_label, 3, 1)
        info_layout.addWidget(QLabel("Memory:"), 4, 0)
        info_layout.addWidget(self.gpu_mem_label, 4, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # GPU usage and frequency plots
        self.gpu_usage_plot = MonitorPlotWidget("GPU Usage (%) & Frequency (MHz)", dual_axis=True)
        layout.addWidget(self.gpu_usage_plot)
        
        return widget
    
    def create_npu_tab(self) -> QWidget:
        """Create NPU monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # NPU info
        info_group = QGroupBox("NPU Information")
        info_layout = QGridLayout()
        
        platform = self._initial_npu_info.get('platform', 'Unknown')
        
        self.npu_platform_label = QLabel(f"Platform: {platform}")
        self.npu_usage_label = QLabel("Usage: -")
        self.npu_freq_label = QLabel("Frequency: -")
        
        info_layout.addWidget(self.npu_platform_label, 0, 0, 1, 2)
        info_layout.addWidget(QLabel("Usage:"), 1, 0)
        info_layout.addWidget(self.npu_usage_label, 1, 1)
        info_layout.addWidget(QLabel("Frequency:"), 2, 0)
        info_layout.addWidget(self.npu_freq_label, 2, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # NPU usage and frequency plots
        self.npu_usage_plot = MonitorPlotWidget("NPU Usage (%) & Frequency (MHz)", dual_axis=True)
        layout.addWidget(self.npu_usage_plot)
        
        return widget
    
    def create_network_tab(self) -> QWidget:
        """Create network monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Network info
        info_group = QGroupBox("Network Information")
        info_layout = QGridLayout()
        
        self.network_interface_label = QLabel("Interface: -")
        self.network_upload_label = QLabel("Upload: -")
        self.network_download_label = QLabel("Download: -")
        self.network_connections_label = QLabel("Connections: -")
        
        info_layout.addWidget(QLabel("Interface:"), 0, 0)
        info_layout.addWidget(self.network_interface_label, 0, 1)
        info_layout.addWidget(QLabel("Upload Speed:"), 1, 0)
        info_layout.addWidget(self.network_upload_label, 1, 1)
        info_layout.addWidget(QLabel("Download Speed:"), 2, 0)
        info_layout.addWidget(self.network_download_label, 2, 1)
        info_layout.addWidget(QLabel("Active Connections:"), 3, 0)
        info_layout.addWidget(self.network_connections_label, 3, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Network speed plot (dual axis: upload and download)
        # Use KB/s for better readability with small values
        self.network_speed_plot = MultiLinePlotWidget("Network Speed", 
                                                      y_label="Upload (KB/s)",
                                                      y_label2="Download (KB/s)")
        layout.addWidget(self.network_speed_plot)
        
        return widget
    
    def create_disk_tab(self) -> QWidget:
        """Create disk I/O monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Disk info
        info_group = QGroupBox("Disk I/O Information")
        info_layout = QGridLayout()
        
        self.disk_device_label = QLabel("Device: -")
        self.disk_read_label = QLabel("Read Speed: -")
        self.disk_write_label = QLabel("Write Speed: -")
        self.disk_usage_label = QLabel("Root Usage: -")
        
        info_layout.addWidget(QLabel("Device:"), 0, 0)
        info_layout.addWidget(self.disk_device_label, 0, 1)
        info_layout.addWidget(QLabel("Read Speed:"), 1, 0)
        info_layout.addWidget(self.disk_read_label, 1, 1)
        info_layout.addWidget(QLabel("Write Speed:"), 2, 0)
        info_layout.addWidget(self.disk_write_label, 2, 1)
        info_layout.addWidget(QLabel("Root Usage:"), 3, 0)
        info_layout.addWidget(self.disk_usage_label, 3, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Disk I/O plot (dual axis: read and write)
        self.disk_io_plot = MultiLinePlotWidget("Disk I/O", 
                                                y_label="Read (MB/s)",
                                                y_label2="Write (MB/s)")
        layout.addWidget(self.disk_io_plot)
        
        return widget
    
    def init_menu(self):
        """Initialize menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        # Export submenu
        export_menu = file_menu.addMenu('Export Data')
        
        # Export All action (default - Ctrl+E)
        export_all_action = QAction('Export All Formats', self)
        export_all_action.setShortcut('Ctrl+E')
        export_all_action.triggered.connect(self.export_all)
        export_menu.addAction(export_all_action)
        
        export_menu.addSeparator()
        
        export_csv_action = QAction('Export to CSV', self)
        export_csv_action.triggered.connect(self.export_csv)
        export_menu.addAction(export_csv_action)
        
        export_json_action = QAction('Export to JSON', self)
        export_json_action.triggered.connect(self.export_json)
        export_menu.addAction(export_json_action)
        
        export_html_action = QAction('Export to HTML Report', self)
        export_html_action.triggered.connect(self.export_html)
        export_menu.addAction(export_html_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        cleanup_action = QAction('Cleanup Old Data', self)
        cleanup_action.triggered.connect(self.cleanup_data)
        tools_menu.addAction(cleanup_action)
        
        clear_export_action = QAction('Clear Export Session', self)
        clear_export_action.triggered.connect(self.clear_export_session)
        tools_menu.addAction(clear_export_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def update_data(self):
        """Update all monitoring data."""
        # For remote sources with queued samples, process each one to prevent data loss
        queued_samples = []
        if hasattr(self.data_source, 'process_queued_samples'):
            queued_samples = self.data_source.process_queued_samples()
        
        # If no queued samples, process current state as normal
        if not queued_samples:
            self._update_display_and_export()
            return
        
        # Process each queued sample individually
        for raw_sample in queued_samples:
            # Temporarily set this as the "current" sample for processing
            # This is a bit hacky but avoids rewriting all get_*_info methods
            if hasattr(self.data_source, 'ssh_monitor'):
                self.data_source.ssh_monitor._latest_raw_data = raw_sample
            
            self._update_display_and_export()
    
    def _update_display_and_export(self):
        """Update displays and add sample to exporter."""
        # Get current time
        current_time = time.time() - self.start_time
        
        # CPU data
        cpu_info = self.data_source.get_cpu_info()
        cpu_usage = cpu_info['usage']['total']
        cpu_freq = cpu_info['frequency']['average']
        
        # Update CPU tab labels
        self.cpu_freq_label.setText(f"Frequency: {cpu_freq:.0f} MHz")
        
        # CPU temperature
        temp_data = cpu_info['temperature']
        if temp_data:
            first_sensor = next(iter(temp_data.values()), [])
            if first_sensor:
                temp = first_sensor[0]['current']
                self.cpu_temp_label.setText(f"Temperature: {temp:.1f}°C")
        
        # CPU governor (skip in ADB mode)
        if self.freq_controller:
            governor = self.freq_controller.get_current_cpu_governor()
            if governor:
                self.cpu_governor_label.setText(f"Governor: {governor}")
        else:
            self.cpu_governor_label.setText(f"Governor: N/A (Android)")
        
        # Memory data
        memory_info = self.data_source.get_memory_info()
        mem = memory_info['memory']
        swap = memory_info['swap']
        
        # Memory is already in GB from all data sources (Local, Android, SSH)
        # Update memory tab labels
        self.mem_total_label.setText(f"{mem['total']:.1f} GB")
        self.mem_used_label.setText(f"{mem['used']:.1f} GB ({mem['percent']:.1f}%)")
        self.mem_free_label.setText(f"{mem['free']:.1f} GB")
        self.swap_label.setText(f"{swap['used']:.1f} / {swap['total']:.1f} GB")
        
        # GPU data
        gpu_info = self.data_source.get_gpu_info()
        if gpu_info.get('available'):
            gpus = gpu_info['gpus']
            if gpus:
                gpu = gpus[0]
                gpu_util = gpu.get('gpu_util', 0)
                
                if hasattr(self, 'gpu_name_label'):
                    self.gpu_name_label.setText(f"GPU: {gpu.get('name', 'Unknown')}")
                    self.gpu_usage_label.setText(f"{gpu_util}%")
                    
                    gpu_freq = gpu.get('gpu_clock', 0)
                    # Always show frequency, even if 0 (driver may not support act_freq)
                    self.gpu_freq_label.setText(f"{gpu_freq} MHz")
                    
                    temp = gpu.get('temperature', 0)
                    if temp > 0:
                        self.gpu_temp_label.setText(f"{temp}°C")
                    else:
                        self.gpu_temp_label.setText("N/A (driver required)")
                    
                    mem_used = gpu.get('memory_used', 0)
                    mem_total = gpu.get('memory_total', 0)
                    if mem_total > 0:
                        self.gpu_mem_label.setText(f"{mem_used:.0f} / {mem_total:.0f} MB")
                    else:
                        self.gpu_mem_label.setText("N/A (driver required)")
                    
                    # Update GPU plot with usage and frequency
                    self.gpu_usage_plot.update_data(gpu_util, gpu_freq, current_time)
        
        # NPU data
        npu_info = self.data_source.get_npu_info()
        if npu_info.get('available'):
            util = npu_info.get('utilization', 0)
            freq = npu_info.get('frequency', 0)
            
            # Only update if NPU UI elements exist (in NPU tab)
            if hasattr(self, 'npu_usage_label'):
                self.npu_usage_label.setText(f"{util:.1f}%")
            if hasattr(self, 'npu_freq_label'):
                self.npu_freq_label.setText(f"{freq:.0f} MHz")
            if hasattr(self, 'npu_usage_plot'):
                self.npu_usage_plot.update_data(util, freq, current_time)
        
        # Network data
        network_info = self.data_source.get_network_info()
        upload_speed_bytes = network_info.get('upload_speed', 0)  # bytes/sec
        download_speed_bytes = network_info.get('download_speed', 0)  # bytes/sec
        connections = network_info.get('connections', {'total': 0, 'tcp_established': 0})
        
        # Convert to appropriate unit (KB/s or MB/s)
        def format_speed(bytes_per_sec):
            mb_per_sec = bytes_per_sec / (1024 * 1024)
            kb_per_sec = bytes_per_sec / 1024
            if mb_per_sec >= 0.01:
                return f"{mb_per_sec:.2f} MB/s"
            else:
                return f"{kb_per_sec:.2f} KB/s"
        
        # For charts: use KB/s to avoid scientific notation
        upload_speed_kb = upload_speed_bytes / 1024  # KB/s for chart
        download_speed_kb = download_speed_bytes / 1024  # KB/s for chart
        
        # Update network labels with better formatting
        self.network_interface_label.setText("Total")
        self.network_upload_label.setText(format_speed(upload_speed_bytes))
        self.network_download_label.setText(format_speed(download_speed_bytes))
        self.network_connections_label.setText(f"{connections.get('total', 0)} ({connections.get('tcp_established', 0)} TCP)")
        
        # Update network card with better formatting
        self.network_card.update_values(
            f"↑{format_speed(upload_speed_bytes)}",
            f"↓{format_speed(download_speed_bytes)}"
        )
        
        # Disk data
        disk_info = self.data_source.get_disk_info()
        read_speed_mb = disk_info.get('read_speed_mb', 0)
        write_speed_mb = disk_info.get('write_speed_mb', 0)
        root_usage = disk_info.get('partitions', {}).get('/', {})
        
        # Update disk labels
        self.disk_device_label.setText("Total")
        self.disk_read_label.setText(f"{read_speed_mb:.2f} MB/s")
        self.disk_write_label.setText(f"{write_speed_mb:.2f} MB/s")
        if root_usage:
            self.disk_usage_label.setText(f"{root_usage.get('used', 0):.1f} / {root_usage.get('total', 0):.1f} GB ({root_usage.get('percent', 0):.1f}%)")
        
        # Update disk card
        self.disk_card.update_values(
            f"R:{read_speed_mb:.2f} MB/s",
            f"W:{write_speed_mb:.2f} MB/s"
        )
        
        # Update info cards
        self.cpu_card.update_values(f"{cpu_usage:.1f}%", f"{cpu_freq:.0f} MHz")
        # Memory is already in GB from all data sources
        self.memory_card.update_values(f"{mem['percent']:.1f}%", f"{mem['used']:.1f} GB")
        
        if self._initial_gpu_info.get('available', False) and hasattr(self, 'gpu_card'):
            if gpu_info.get('available') and gpu_info['gpus']:
                gpu = gpu_info['gpus'][0]
                gpu_util = gpu.get('gpu_util', 0)
                gpu_freq = gpu.get('gpu_clock', 0)
                # Show frequency in overview card
                self.gpu_card.update_values(f"{gpu_util}%", f"{gpu_freq} MHz")
        
        if self._initial_npu_info.get('available', False) and hasattr(self, 'npu_card'):
            if npu_info.get('available'):
                npu_util = npu_info.get('utilization', 0)
                npu_freq = npu_info.get('frequency', 0)
                self.npu_card.update_values(f"{npu_util:.1f}%", f"{npu_freq:.0f} MHz")
        
        # Update plots
        self.overview_cpu_plot.update_data(cpu_usage, current_time)
        self.overview_memory_plot.update_data(mem['percent'], current_time)
        self.overview_network_plot.update_data(upload_speed_kb, download_speed_kb, current_time)
        self.overview_disk_plot.update_data(read_speed_mb, write_speed_mb, current_time)
        
        if self._initial_gpu_info.get('available', False) and hasattr(self, 'overview_gpu_plot'):
            if gpu_info.get('available') and gpu_info['gpus']:
                gpu = gpu_info['gpus'][0]
                gpu_util = gpu.get('gpu_util', 0)
                gpu_freq = gpu.get('gpu_clock', 0)
                self.overview_gpu_plot.update_data(gpu_util, gpu_freq, current_time)
        
        if self._initial_npu_info.get('available', False) and hasattr(self, 'overview_npu_plot'):
            if npu_info.get('available'):
                util = npu_info.get('utilization', 0)
                freq = npu_info.get('frequency', 0)
                self.overview_npu_plot.update_data(util, freq, current_time)
        
        self.cpu_usage_plot.update_data(cpu_usage, current_time)
        self.cpu_freq_plot.update_data(cpu_freq, current_time)
        self.memory_usage_plot.update_data(mem['percent'], current_time)
        self.network_speed_plot.update_data(upload_speed_kb, download_speed_kb, current_time)
        self.disk_io_plot.update_data(read_speed_mb, write_speed_mb, current_time)
        
        # Log data to database (only for local monitoring)
        if self.data_logger:
            self.data_logger.log_data(cpu_info, memory_info, gpu_info, 
                                      npu_info if npu_info.get('available', False) else None)
        
        # Add data to exporter (only when we have a new remote timestamp)
        export_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'time_seconds': current_time,
            'cpu': cpu_info,
            'memory': memory_info,
            'gpu': gpu_info,
            'network': network_info,
            'disk': disk_info
        }
        
        # Add UTC timestamp from device (Android/SSH) if available
        should_add_sample = True
        if hasattr(self.data_source, 'get_timestamp_ms'):
            timestamp_ms = self.data_source.get_timestamp_ms()
            if timestamp_ms > 0:
                # Convert milliseconds to seconds for UTC timestamp
                export_data['utc_timestamp'] = timestamp_ms // 1000
                if self._last_remote_timestamp_ms == timestamp_ms:
                    should_add_sample = False
                else:
                    self._last_remote_timestamp_ms = timestamp_ms
        
        if npu_info.get('available', False):
            export_data['npu'] = npu_info
        
        if should_add_sample:
            self.data_exporter.add_sample(export_data)
        
        # Update status bar
        # Format network speed for status bar - clearer format
        def format_speed_short(bytes_per_sec):
            mb = bytes_per_sec / (1024 * 1024)
            kb = bytes_per_sec / 1024
            if mb >= 1.0:
                return f"{mb:.1f}M"
            else:
                return f"{kb:.0f}K"
        
        status_msg = (
            f"Last update: {time.strftime('%H:%M:%S')} | "
            f"CPU: {cpu_usage:.1f}% | "
            f"Mem: {mem['percent']:.1f}% | "
            f"Net: ↑{format_speed_short(upload_speed_bytes)}/↓{format_speed_short(download_speed_bytes)} | "
            f"Disk: R{read_speed_mb:.1f}/W{write_speed_mb:.1f} MB/s"
        )
        
        # Add GPU info if available
        if self._initial_gpu_info.get('available', False) and gpu_info.get('available') and gpu_info['gpus']:
            gpu = gpu_info['gpus'][0]
            gpu_util = gpu.get('gpu_util', 0)
            status_msg += f" | GPU: {gpu_util}%"
        
        # Add NPU info if available
        if self._initial_npu_info.get('available', False):
            if npu_info.get('available'):
                npu_util = npu_info.get('utilization', 0)
                status_msg += f" | NPU: {npu_util:.1f}%"
        
        self.status_bar.showMessage(status_msg)
    
    def cleanup_data(self):
        """Cleanup old monitoring data."""
        if not self.data_logger:
            QMessageBox.warning(self, 'Not Available', 
                              'Cleanup is only available for local monitoring.\n'
                              'Android data is stored on the device.')
            return
        
        reply = QMessageBox.question(self, 'Cleanup Data',
                                    'Remove data older than 7 days?',
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.data_logger.cleanup_old_data(7)
            QMessageBox.information(self, 'Success', 'Old data cleaned up successfully')
    
    def export_all(self):
        """Export monitoring data to all formats (CSV, JSON, HTML)."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            # Get actual export count (accounts for DB sources vs session data)
            actual_count = self.data_exporter.get_export_sample_count()
            
            # Export to all formats (default behavior: use DB for remote, session for local)
            csv_path = self.data_exporter.export_csv()
            json_path = self.data_exporter.export_json()
            html_path = self.data_exporter.export_html()
            
            # Show success message with all paths and actual sample count
            QMessageBox.information(self, 'Export Successful', 
                                   f'Data exported to all formats:\n\n'
                                   f'CSV:  {csv_path}\n'
                                   f'JSON: {json_path}\n'
                                   f'HTML: {html_path}\n\n'
                                   f'Samples: {actual_count}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def export_csv(self):
        """Export monitoring data to CSV."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            actual_count = self.data_exporter.get_export_sample_count()
            filepath = self.data_exporter.export_csv()
            QMessageBox.information(self, 'Export Successful', 
                                   f'Data exported to:\n{filepath}\n\n'
                                   f'Samples: {actual_count}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def export_json(self):
        """Export monitoring data to JSON."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            actual_count = self.data_exporter.get_export_sample_count()
            filepath = self.data_exporter.export_json()
            QMessageBox.information(self, 'Export Successful', 
                                   f'Data exported to:\n{filepath}\n\n'
                                   f'Samples: {actual_count}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def export_html(self):
        """Export monitoring data to HTML report."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            actual_count = self.data_exporter.get_export_sample_count(use_android_db=False)
            # Use session_data directly, don't pull from Android DB (use_android_db=False)
            filepath = self.data_exporter.export_html(use_android_db=False)
            QMessageBox.information(self, 'Export Successful', 
                                   f'Report generated:\n{filepath}\n\n'
                                   f'Samples: {actual_count}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def clear_export_session(self):
        """Clear current export session data."""
        reply = QMessageBox.question(self, 'Clear Session',
                                    'Clear current export session data?\n'
                                    'This will reset the data collection for exports.',
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.data_exporter.clear_session()
            QMessageBox.information(self, 'Session Cleared', 'Export session data has been cleared')
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, 'About System Monitor Tool',
                         'System Monitor Tool - Pro Edition v1.0\n\n'
                         'Real-time CPU/GPU/NPU/Memory monitoring\n'
                         'with frequency control capabilities.\n\n'
                         'Supports Intel i915 and Xe GPUs\n'
                         'Export to CSV, JSON, and HTML formats\n\n'
                         'Built with PyQt5 and pyqtgraph')
    
    def _show_sudo_setup_dialog(self):
        """Show dialog to setup passwordless sudo for SSH frequency control."""
        from ui.setup_sudo_dialog import SetupSudoDialog
        
        if not isinstance(self.data_source, RemoteLinuxDataSource):
            return
        
        dialog = SetupSudoDialog(
            host=self.data_source.ssh_monitor.host,
            port=self.data_source.ssh_monitor.port,
            user=self.data_source.ssh_monitor.user,
            parent=self
        )
        
        # Show dialog (non-blocking for first time, just info)
        if dialog.exec_() == dialog.Accepted:
            # User completed setup, re-initialize freq controller
            print("🔄 Re-initializing frequency controller...")
            
            ssh_freq_ctrl = SSHFrequencyController(
                host=self.data_source.ssh_monitor.host,
                port=self.data_source.ssh_monitor.port,
                user=self.data_source.ssh_monitor.user
            )
            
            if ssh_freq_ctrl.has_sudo:
                self.freq_controller = ssh_freq_ctrl
                print(f"✅ SSH frequency control now has full access!")
                
                # Update control panel
                if hasattr(self, 'control_panel'):
                    self.control_panel.freq_controller = ssh_freq_ctrl
                    self.control_panel.update_governor_info()
                
                QMessageBox.information(
                    self,
                    "Frequency Control Enabled",
                    "✅ Frequency control is now fully enabled!\n\n"
                    "You can now adjust CPU governor and frequency settings."
                )
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.update_timer.stop()
        # Only close logger if it exists (None in Android mode)
        if self.data_logger:
            self.data_logger.close()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
