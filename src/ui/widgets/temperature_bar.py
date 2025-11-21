#!/usr/bin/env python3
"""Temperature bar widget with color-coded visualization."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette


class TemperatureBar(QWidget):
    """A horizontal temperature bar with color-coding based on temperature levels."""
    
    def __init__(self, label: str, max_temp: int = 100, parent=None):
        """
        Initialize temperature bar.
        
        Args:
            label: Label text (e.g., "CPU", "GPU")
            max_temp: Maximum temperature for the bar (default: 100°C)
            parent: Parent widget
        """
        super().__init__(parent)
        self.max_temp = max_temp
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        self.label = QLabel(f"{label}:")
        self.label.setMinimumWidth(80)
        self.label.setStyleSheet("font-size: 24px; font-weight: 500;")
        layout.addWidget(self.label)
        
        # Progress bar
        self.bar = QProgressBar()
        self.bar.setMinimum(0)
        self.bar.setMaximum(max_temp)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setMinimumHeight(36)
        self.bar.setMaximumHeight(36)
        layout.addWidget(self.bar, stretch=1)
        
        # Temperature value label
        self.value_label = QLabel("-")
        self.value_label.setMinimumWidth(100)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet("font-size: 24px; font-weight: 500;")
        layout.addWidget(self.value_label)
    
    def update_temperature(self, temp: float):
        """
        Update the temperature display.
        
        Args:
            temp: Temperature in Celsius
        """
        if temp <= 0:
            self.bar.setValue(0)
            self.value_label.setText("-")
            self.bar.setStyleSheet("")
            return
        
        # Update value
        self.bar.setValue(int(min(temp, self.max_temp)))
        self.value_label.setText(f"{temp:.1f}°C")
        
        # Color coding based on temperature ranges
        if temp < 50:
            # Green - Cool
            color = "#4CAF50"
        elif temp < 70:
            # Yellow - Warm
            color = "#FFC107"
        elif temp < 85:
            # Orange - Hot
            color = "#FF9800"
        else:
            # Red - Critical
            color = "#F44336"
        
        # Apply style
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2b2b2b;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)


class TemperaturePanel(QWidget):
    """Panel showing multiple temperature bars."""
    
    def __init__(self, parent=None):
        """Initialize temperature panel."""
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Title
        title = QLabel("🌡️ Temperature Monitoring")
        title.setStyleSheet("font-weight: bold; font-size: 32px;")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        
        # Temperature bars
        self.cpu_bar = TemperatureBar("CPU")
        self.gpu_bar = TemperatureBar("GPU")
        self.disk_bar = TemperatureBar("Disk", max_temp=80)
        self.npu_bar = TemperatureBar("NPU")
        
        layout.addWidget(self.cpu_bar)
        layout.addWidget(self.gpu_bar)
        layout.addWidget(self.disk_bar)
        layout.addWidget(self.npu_bar)
        
        # Initially hide GPU/NPU bars (show only if available)
        self.gpu_bar.hide()
        self.npu_bar.hide()
        self.disk_bar.hide()
    
    def update_temperatures(self, cpu_temp: float = 0, gpu_temp: float = 0, 
                           disk_temp: float = 0, npu_temp: float = 0):
        """
        Update all temperature displays.
        
        Args:
            cpu_temp: CPU temperature in Celsius
            gpu_temp: GPU temperature in Celsius
            disk_temp: Disk temperature in Celsius
            npu_temp: NPU temperature in Celsius
        """
        self.cpu_bar.update_temperature(cpu_temp)
        
        if gpu_temp > 0:
            self.gpu_bar.show()
            self.gpu_bar.update_temperature(gpu_temp)
        
        if disk_temp > 0:
            self.disk_bar.show()
            self.disk_bar.update_temperature(disk_temp)
        
        if npu_temp > 0:
            self.npu_bar.show()
            self.npu_bar.update_temperature(npu_temp)
