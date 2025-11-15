#!/usr/bin/env python3
"""Main window for the monitoring tool."""

import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QLabel, QGroupBox, QGridLayout,
                             QStatusBar, QAction, QMessageBox, QApplication)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

from monitors import CPUMonitor, GPUMonitor, MemoryMonitor, NPUMonitor, NetworkMonitor, DiskMonitor
from controllers import FrequencyController
from storage import DataLogger, DataExporter
from ui.widgets.plot_widget import MonitorPlotWidget, MultiLinePlotWidget
from ui.widgets.control_panel import ControlPanel
from ui.widgets.info_card import InfoCard
from ui.styles import apply_dark_theme, CHART_COLORS

import time


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor Tool - Pro Edition")
        self.setGeometry(100, 100, 1200, 800)
        
        # Store chart colors
        self.chart_colors = CHART_COLORS
        
        # Initialize monitors
        self.cpu_monitor = CPUMonitor()
        self.gpu_monitor = GPUMonitor()
        self.memory_monitor = MemoryMonitor()
        self.npu_monitor = NPUMonitor()
        self.network_monitor = NetworkMonitor()
        self.disk_monitor = DiskMonitor()
        self.freq_controller = FrequencyController()
        self.data_logger = DataLogger()
        self.data_exporter = DataExporter()
        
        # Timing
        self.start_time = time.time()
        
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
        if self.gpu_monitor.gpu_type:
            gpu_tab = self.create_gpu_tab()
            self.tabs.addTab(gpu_tab, "GPU")
        
        # NPU tab (if available)
        if self.npu_monitor.available:
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
        if self.gpu_monitor.gpu_type:
            self.gpu_card = InfoCard("GPU", "🎮")
            self.gpu_card.set_color("#FF9800")
            cards_layout.addWidget(self.gpu_card)
        
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
        self.overview_network_plot = MultiLinePlotWidget("Network Speed", 
                                                         y_label="Upload (MB/s)",
                                                         y_label2="Download (MB/s)")
        self.overview_disk_plot = MultiLinePlotWidget("Disk I/O", 
                                                      y_label="Read (MB/s)",
                                                      y_label2="Write (MB/s)")
        charts_layout.addWidget(self.overview_network_plot, 1, 0)
        charts_layout.addWidget(self.overview_disk_plot, 1, 1)
        
        # Row 3: GPU and NPU (if available)
        if self.gpu_monitor.gpu_type:
            self.overview_gpu_plot = MultiLinePlotWidget("GPU Usage & Frequency",
                                                         y_label="Usage (%)",
                                                         y_label2="Freq (MHz)")
            charts_layout.addWidget(self.overview_gpu_plot, 2, 0)
        
        if self.npu_monitor.available:
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
        
        self.cpu_cores_label = QLabel(f"Cores: {self.cpu_monitor.cpu_count}")
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
        
        npu_info = self.npu_monitor.get_all_info()
        platform = npu_info.get('platform', 'Unknown')
        
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
        self.network_speed_plot = MultiLinePlotWidget("Network Speed", 
                                                      y_label="Upload (MB/s)",
                                                      y_label2="Download (MB/s)")
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
        # Get current time
        current_time = time.time() - self.start_time
        
        # CPU data
        cpu_info = self.cpu_monitor.get_all_info()
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
        
        # CPU governor
        governor = self.freq_controller.get_current_cpu_governor()
        if governor:
            self.cpu_governor_label.setText(f"Governor: {governor}")
        
        # Memory data
        memory_info = self.memory_monitor.get_all_info()
        mem = memory_info['memory']
        swap = memory_info['swap']
        
        # Update memory tab labels
        self.mem_total_label.setText(f"{mem['total']:.1f} GB")
        self.mem_used_label.setText(f"{mem['used']:.1f} GB ({mem['percent']:.1f}%)")
        self.mem_free_label.setText(f"{mem['free']:.1f} GB")
        self.swap_label.setText(f"{swap['used']:.1f} / {swap['total']:.1f} GB")
        
        # GPU data
        gpu_info = self.gpu_monitor.get_all_info()
        if gpu_info.get('available'):
            gpus = gpu_info['gpus']
            if gpus:
                gpu = gpus[0]
                gpu_util = gpu.get('gpu_util', 0)
                
                if hasattr(self, 'gpu_name_label'):
                    self.gpu_name_label.setText(f"GPU: {gpu.get('name', 'Unknown')}")
                    self.gpu_usage_label.setText(f"{gpu_util}%")
                    
                    gpu_freq = gpu.get('gpu_clock', 0)
                    if gpu_freq > 0:
                        self.gpu_freq_label.setText(f"{gpu_freq} MHz")
                    else:
                        self.gpu_freq_label.setText("N/A")
                    
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
        if self.npu_monitor.available:
            npu_info = self.npu_monitor.get_all_info()
            if npu_info.get('available'):
                util = npu_info.get('utilization', 0)
                freq = npu_info.get('frequency', 0)
                
                self.npu_usage_label.setText(f"{util:.1f}%")
                self.npu_freq_label.setText(f"{freq:.0f} MHz")
                
                # Update NPU plot with usage and frequency
                self.npu_usage_plot.update_data(util, freq, current_time)
        
        # Network data
        network_info = self.network_monitor.get_io_stats()
        upload_speed_mb = network_info.get('upload_speed', 0) / (1024 * 1024)  # Convert to MB/s
        download_speed_mb = network_info.get('download_speed', 0) / (1024 * 1024)
        connections = self.network_monitor.get_connections_count()
        
        # Update network labels
        self.network_interface_label.setText("Total")
        self.network_upload_label.setText(f"{upload_speed_mb:.2f} MB/s")
        self.network_download_label.setText(f"{download_speed_mb:.2f} MB/s")
        self.network_connections_label.setText(f"{connections.get('total', 0)} ({connections.get('tcp_established', 0)} TCP)")
        
        # Update network card
        self.network_card.update_values(
            f"↑{upload_speed_mb:.1f} MB/s",
            f"↓{download_speed_mb:.1f} MB/s"
        )
        
        # Disk data
        disk_info = self.disk_monitor.get_io_stats()
        read_speed_mb = disk_info.get('read_speed_mb', 0)
        write_speed_mb = disk_info.get('write_speed_mb', 0)
        root_usage = self.disk_monitor.get_partition_usage('/')
        
        # Update disk labels
        self.disk_device_label.setText("Total")
        self.disk_read_label.setText(f"{read_speed_mb:.2f} MB/s")
        self.disk_write_label.setText(f"{write_speed_mb:.2f} MB/s")
        if root_usage:
            self.disk_usage_label.setText(f"{root_usage['used']:.1f} / {root_usage['total']:.1f} GB ({root_usage['percent']:.1f}%)")
        
        # Update disk card
        self.disk_card.update_values(
            f"R:{read_speed_mb:.1f} MB/s",
            f"W:{write_speed_mb:.1f} MB/s"
        )
        
        # Update info cards
        self.cpu_card.update_values(f"{cpu_usage:.1f}%", f"{cpu_freq:.0f} MHz")
        self.memory_card.update_values(f"{mem['percent']:.1f}%", f"{mem['used']:.1f} GB")
        
        if self.gpu_monitor.gpu_type and hasattr(self, 'gpu_card'):
            gpu_info_card = self.gpu_monitor.get_all_info()
            if gpu_info_card.get('available') and gpu_info_card['gpus']:
                gpu = gpu_info_card['gpus'][0]
                gpu_util = gpu.get('gpu_util', 0)
                gpu_temp = gpu.get('temperature', 0)
                if gpu_temp > 0:
                    self.gpu_card.update_values(f"{gpu_util}%", f"{gpu_temp}°C")
                else:
                    self.gpu_card.update_values(f"{gpu_util}%", "N/A")
        
        # Update plots
        self.overview_cpu_plot.update_data(cpu_usage, current_time)
        self.overview_memory_plot.update_data(mem['percent'], current_time)
        self.overview_network_plot.update_data(upload_speed_mb, download_speed_mb, current_time)
        self.overview_disk_plot.update_data(read_speed_mb, write_speed_mb, current_time)
        
        if self.gpu_monitor.gpu_type and hasattr(self, 'overview_gpu_plot'):
            if gpu_info.get('available') and gpu_info['gpus']:
                gpu = gpu_info['gpus'][0]
                gpu_util = gpu.get('gpu_util', 0)
                gpu_freq = gpu.get('gpu_clock', 0)
                self.overview_gpu_plot.update_data(gpu_util, gpu_freq, current_time)
        
        if self.npu_monitor.available and hasattr(self, 'overview_npu_plot'):
            npu_info_plot = self.npu_monitor.get_all_info()
            if npu_info_plot.get('available'):
                util = npu_info_plot.get('utilization', 0)
                freq = npu_info_plot.get('frequency', 0)
                self.overview_npu_plot.update_data(util, freq, current_time)
        
        self.cpu_usage_plot.update_data(cpu_usage, current_time)
        self.cpu_freq_plot.update_data(cpu_freq, current_time)
        self.memory_usage_plot.update_data(mem['percent'], current_time)
        self.network_speed_plot.update_data(upload_speed_mb, download_speed_mb, current_time)
        self.disk_io_plot.update_data(read_speed_mb, write_speed_mb, current_time)
        
        # Log data to database
        self.data_logger.log_data(cpu_info, memory_info, gpu_info, 
                                  npu_info if self.npu_monitor.available else None)
        
        # Add data to exporter
        export_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'time_seconds': current_time,
            'cpu': cpu_info,
            'memory': memory_info,
            'gpu': gpu_info,
            'network': network_info,
            'disk': disk_info
        }
        if self.npu_monitor.available:
            export_data['npu'] = npu_info
        self.data_exporter.add_sample(export_data)
        
        # Update status bar
        status_msg = (
            f"Last update: {time.strftime('%H:%M:%S')} | "
            f"CPU: {cpu_usage:.1f}% | "
            f"Mem: {mem['percent']:.1f}% | "
            f"Net: ↑{upload_speed_mb:.1f}/↓{download_speed_mb:.1f} MB/s | "
            f"Disk: R{read_speed_mb:.1f}/W{write_speed_mb:.1f} MB/s"
        )
        
        # Add GPU info if available
        if self.gpu_monitor.gpu_type and gpu_info.get('available') and gpu_info['gpus']:
            gpu = gpu_info['gpus'][0]
            gpu_util = gpu.get('gpu_util', 0)
            status_msg += f" | GPU: {gpu_util}%"
        
        # Add NPU info if available
        if self.npu_monitor.available:
            npu_info_status = self.npu_monitor.get_all_info()
            if npu_info_status.get('available'):
                npu_util = npu_info_status.get('utilization', 0)
                status_msg += f" | NPU: {npu_util:.1f}%"
        
        self.status_bar.showMessage(status_msg)
    
    def cleanup_data(self):
        """Cleanup old monitoring data."""
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
            
            # Export to all formats
            csv_path = self.data_exporter.export_csv()
            json_path = self.data_exporter.export_json()
            html_path = self.data_exporter.export_html()
            
            # Show success message with all paths
            QMessageBox.information(self, 'Export Successful', 
                                   f'Data exported to all formats:\n\n'
                                   f'CSV:  {csv_path}\n'
                                   f'JSON: {json_path}\n'
                                   f'HTML: {html_path}\n\n'
                                   f'Samples: {len(self.data_exporter.session_data)}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def export_csv(self):
        """Export monitoring data to CSV."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            filepath = self.data_exporter.export_csv()
            QMessageBox.information(self, 'Export Successful', 
                                   f'Data exported to:\n{filepath}\n\n'
                                   f'Samples: {len(self.data_exporter.session_data)}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def export_json(self):
        """Export monitoring data to JSON."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            filepath = self.data_exporter.export_json()
            QMessageBox.information(self, 'Export Successful', 
                                   f'Data exported to:\n{filepath}\n\n'
                                   f'Samples: {len(self.data_exporter.session_data)}')
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Error exporting data: {str(e)}')
    
    def export_html(self):
        """Export monitoring data to HTML report."""
        try:
            if not self.data_exporter.session_data:
                QMessageBox.warning(self, 'No Data', 'No monitoring data to export')
                return
            
            filepath = self.data_exporter.export_html()
            QMessageBox.information(self, 'Export Successful', 
                                   f'Report generated:\n{filepath}\n\n'
                                   f'Samples: {len(self.data_exporter.session_data)}')
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
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.update_timer.stop()
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
