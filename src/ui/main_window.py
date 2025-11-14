#!/usr/bin/env python3
"""Main window for the monitoring tool."""

import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QLabel, QGroupBox, QGridLayout,
                             QStatusBar, QAction, QMessageBox, QApplication)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

from monitors import CPUMonitor, GPUMonitor, MemoryMonitor, NPUMonitor
from controllers import FrequencyController
from storage import DataLogger
from ui.widgets.plot_widget import MonitorPlotWidget, MultiLinePlotWidget
from ui.widgets.control_panel import ControlPanel

import time


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize monitors
        self.cpu_monitor = CPUMonitor()
        self.gpu_monitor = GPUMonitor()
        self.memory_monitor = MemoryMonitor()
        self.npu_monitor = NPUMonitor()
        self.freq_controller = FrequencyController()
        self.data_logger = DataLogger()
        
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
        """Create overview tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info labels
        info_group = QGroupBox("System Information")
        info_layout = QGridLayout()
        
        self.cpu_info_label = QLabel("CPU: -")
        self.memory_info_label = QLabel("Memory: -")
        self.gpu_info_label = QLabel("GPU: -")
        
        info_layout.addWidget(QLabel("CPU Usage:"), 0, 0)
        info_layout.addWidget(self.cpu_info_label, 0, 1)
        info_layout.addWidget(QLabel("Memory:"), 1, 0)
        info_layout.addWidget(self.memory_info_label, 1, 1)
        info_layout.addWidget(QLabel("GPU:"), 2, 0)
        info_layout.addWidget(self.gpu_info_label, 2, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Overview plots
        self.overview_cpu_plot = MonitorPlotWidget("CPU Usage (%)")
        self.overview_memory_plot = MonitorPlotWidget("Memory Usage (%)")
        
        layout.addWidget(self.overview_cpu_plot)
        layout.addWidget(self.overview_memory_plot)
        
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
        self.gpu_temp_label = QLabel("Temperature: -")
        self.gpu_mem_label = QLabel("Memory: -")
        
        info_layout.addWidget(self.gpu_name_label, 0, 0, 1, 2)
        info_layout.addWidget(QLabel("Usage:"), 1, 0)
        info_layout.addWidget(self.gpu_usage_label, 1, 1)
        info_layout.addWidget(QLabel("Temperature:"), 2, 0)
        info_layout.addWidget(self.gpu_temp_label, 2, 1)
        info_layout.addWidget(QLabel("Memory:"), 3, 0)
        info_layout.addWidget(self.gpu_mem_label, 3, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # GPU usage plot
        self.gpu_usage_plot = MonitorPlotWidget("GPU Usage (%)")
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
        
        # NPU usage plot
        self.npu_usage_plot = MonitorPlotWidget("NPU Usage (%)")
        layout.addWidget(self.npu_usage_plot)
        
        return widget
    
    def init_menu(self):
        """Initialize menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        cleanup_action = QAction('Cleanup Old Data', self)
        cleanup_action.triggered.connect(self.cleanup_data)
        tools_menu.addAction(cleanup_action)
        
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
        
        # Update CPU labels
        self.cpu_info_label.setText(f"{cpu_usage:.1f}%")
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
        
        # Update memory labels
        self.memory_info_label.setText(
            f"{mem['used']:.1f} / {mem['total']:.1f} GB ({mem['percent']:.1f}%)")
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
                self.gpu_info_label.setText(f"{gpu_util}%")
                
                if hasattr(self, 'gpu_name_label'):
                    self.gpu_name_label.setText(f"GPU: {gpu.get('name', 'Unknown')}")
                    self.gpu_usage_label.setText(f"{gpu_util}%")
                    
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
                    
                    # Update GPU plot
                    self.gpu_usage_plot.update_data(gpu_util, current_time)
        else:
            self.gpu_info_label.setText("N/A")
        
        # NPU data
        if self.npu_monitor.available:
            npu_info = self.npu_monitor.get_all_info()
            if npu_info.get('available'):
                util = npu_info.get('utilization', 0)
                freq = npu_info.get('frequency', 0)
                
                self.npu_usage_label.setText(f"{util}%")
                self.npu_freq_label.setText(f"{freq:.0f} MHz")
                
                # Update NPU plot
                self.npu_usage_plot.update_data(util, current_time)
        
        # Update plots
        self.overview_cpu_plot.update_data(cpu_usage, current_time)
        self.overview_memory_plot.update_data(mem['percent'], current_time)
        self.cpu_usage_plot.update_data(cpu_usage, current_time)
        self.cpu_freq_plot.update_data(cpu_freq, current_time)
        self.memory_usage_plot.update_data(mem['percent'], current_time)
        
        # Log data to database
        self.data_logger.log_data(cpu_info, memory_info, gpu_info, 
                                  npu_info if self.npu_monitor.available else None)
        
        # Update status bar
        self.status_bar.showMessage(
            f"Last update: {time.strftime('%H:%M:%S')} | "
            f"CPU: {cpu_usage:.1f}% | Memory: {mem['percent']:.1f}%")
    
    def cleanup_data(self):
        """Cleanup old monitoring data."""
        reply = QMessageBox.question(self, 'Cleanup Data',
                                    'Remove data older than 7 days?',
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.data_logger.cleanup_old_data(7)
            QMessageBox.information(self, 'Success', 'Old data cleaned up successfully')
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, 'About System Monitor Tool',
                         'System Monitor Tool v1.0\n\n'
                         'Real-time CPU/GPU/NPU/Memory monitoring\n'
                         'with frequency control capabilities.\n\n'
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
