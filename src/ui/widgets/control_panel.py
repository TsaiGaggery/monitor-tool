#!/usr/bin/env python3
"""Control panel widget for frequency and governor control."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QComboBox, QPushButton, QSlider, QSpinBox,
                             QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal


class ControlPanel(QWidget):
    """Widget for controlling CPU/GPU frequencies and governors."""
    
    # Signals
    governor_changed = pyqtSignal(str)
    cpu_freq_changed = pyqtSignal(int, int)  # min, max
    
    def __init__(self, freq_controller, parent=None):
        super().__init__(parent)
        self.freq_controller = freq_controller
        self.init_ui()
        if self.freq_controller is not None:
            self.update_governor_info()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        
        # If no frequency controller, show disabled message
        if self.freq_controller is None:
            disabled_label = QLabel(
                "⚠️ Frequency control not available\n\n"
                "Requirements:\n"
                "• Local: Run with sudo/root\n"
                "• Android: Root access (su) required"
            )
            disabled_label.setStyleSheet("color: #888; padding: 10px;")
            disabled_label.setWordWrap(True)
            layout.addWidget(disabled_label)
            layout.addStretch()
            return
        
        # CPU Governor Control
        gov_group = QGroupBox("CPU Governor")
        gov_layout = QVBoxLayout()
        
        # Governor selection
        gov_select_layout = QHBoxLayout()
        gov_select_layout.addWidget(QLabel("Governor:"))
        
        self.governor_combo = QComboBox()
        governors = self.freq_controller.get_available_cpu_governors()
        if governors:
            self.governor_combo.addItems(governors)
            current = self.freq_controller.get_current_cpu_governor()
            if current:
                index = self.governor_combo.findText(current)
                if index >= 0:
                    self.governor_combo.setCurrentIndex(index)
        
        gov_select_layout.addWidget(self.governor_combo)
        
        apply_gov_btn = QPushButton("Apply")
        apply_gov_btn.clicked.connect(self.apply_governor)
        gov_select_layout.addWidget(apply_gov_btn)
        
        gov_layout.addLayout(gov_select_layout)
        
        # Current governor display
        self.current_gov_label = QLabel("Current: -")
        gov_layout.addWidget(self.current_gov_label)
        
        # Quick preset buttons
        preset_layout = QHBoxLayout()
        
        perf_btn = QPushButton("Performance")
        perf_btn.clicked.connect(self.set_performance)
        preset_layout.addWidget(perf_btn)
        
        powersave_btn = QPushButton("Powersave")
        powersave_btn.clicked.connect(self.set_powersave)
        preset_layout.addWidget(powersave_btn)
        
        gov_layout.addLayout(preset_layout)
        
        gov_group.setLayout(gov_layout)
        layout.addWidget(gov_group)
        
        # CPU Frequency Control
        freq_group = QGroupBox("CPU Frequency Range (MHz)")
        freq_layout = QVBoxLayout()
        
        # Get frequency range
        freq_range = self.freq_controller.get_cpu_freq_range()
        hw_min = int(freq_range.get('hardware_min', 0))
        hw_max = int(freq_range.get('hardware_max', 5000))
        
        # Min frequency
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min:"))
        
        self.min_freq_spin = QSpinBox()
        self.min_freq_spin.setRange(hw_min, hw_max)
        self.min_freq_spin.setValue(int(freq_range.get('scaling_min', hw_min)))
        self.min_freq_spin.setSuffix(" MHz")
        min_layout.addWidget(self.min_freq_spin)
        
        freq_layout.addLayout(min_layout)
        
        # Max frequency
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max:"))
        
        self.max_freq_spin = QSpinBox()
        self.max_freq_spin.setRange(hw_min, hw_max)
        self.max_freq_spin.setValue(int(freq_range.get('scaling_max', hw_max)))
        self.max_freq_spin.setSuffix(" MHz")
        max_layout.addWidget(self.max_freq_spin)
        
        freq_layout.addLayout(max_layout)
        
        # Apply button
        apply_freq_btn = QPushButton("Apply Frequency Range")
        apply_freq_btn.clicked.connect(self.apply_frequency)
        freq_layout.addWidget(apply_freq_btn)
        
        # Hardware limits display
        self.hw_limits_label = QLabel(f"Hardware: {hw_min} - {hw_max} MHz")
        freq_layout.addWidget(self.hw_limits_label)
        
        freq_group.setLayout(freq_layout)
        layout.addWidget(freq_group)
        
        # GPU Frequency Control
        gpu_freq_range = self.freq_controller.get_gpu_freq_range()
        if gpu_freq_range:
            gpu_group = QGroupBox("GPU Frequency Range (MHz)")
            gpu_layout = QVBoxLayout()
            
            gpu_hw_min = int(gpu_freq_range.get('hardware_min', 0))
            gpu_hw_max = int(gpu_freq_range.get('hardware_max', 3000))
            
            # Min frequency
            gpu_min_layout = QHBoxLayout()
            gpu_min_layout.addWidget(QLabel("Min:"))
            
            self.gpu_min_freq_spin = QSpinBox()
            self.gpu_min_freq_spin.setRange(gpu_hw_min, gpu_hw_max)
            self.gpu_min_freq_spin.setValue(int(gpu_freq_range.get('scaling_min', gpu_hw_min)))
            self.gpu_min_freq_spin.setSuffix(" MHz")
            self.gpu_min_freq_spin.setSingleStep(50)
            gpu_min_layout.addWidget(self.gpu_min_freq_spin)
            
            gpu_layout.addLayout(gpu_min_layout)
            
            # Max frequency
            gpu_max_layout = QHBoxLayout()
            gpu_max_layout.addWidget(QLabel("Max:"))
            
            self.gpu_max_freq_spin = QSpinBox()
            self.gpu_max_freq_spin.setRange(gpu_hw_min, gpu_hw_max)
            self.gpu_max_freq_spin.setValue(int(gpu_freq_range.get('scaling_max', gpu_hw_max)))
            self.gpu_max_freq_spin.setSuffix(" MHz")
            self.gpu_max_freq_spin.setSingleStep(50)
            gpu_max_layout.addWidget(self.gpu_max_freq_spin)
            
            gpu_layout.addLayout(gpu_max_layout)
            
            # Apply button
            apply_gpu_freq_btn = QPushButton("Apply GPU Frequency Range")
            apply_gpu_freq_btn.clicked.connect(self.apply_gpu_frequency)
            gpu_layout.addWidget(apply_gpu_freq_btn)
            
            # Hardware limits display
            gpu_type = gpu_freq_range.get('type', 'unknown')
            self.gpu_hw_limits_label = QLabel(f"Hardware: {gpu_hw_min} - {gpu_hw_max} MHz ({gpu_type})")
            gpu_layout.addWidget(self.gpu_hw_limits_label)
            
            gpu_group.setLayout(gpu_layout)
            layout.addWidget(gpu_group)
        
        # Warning label
        warning_label = QLabel("⚠️ Frequency control requires root/sudo privileges")
        warning_label.setStyleSheet("color: orange; font-weight: bold;")
        layout.addWidget(warning_label)
        
        # Add stretch
        layout.addStretch()
    
    def apply_governor(self):
        """Apply selected governor."""
        governor = self.governor_combo.currentText()
        if governor:
            success = self.freq_controller.set_cpu_governor(governor)
            if success:
                QMessageBox.information(self, "Success", 
                                      f"Governor set to {governor}")
                self.update_governor_info()
                self.governor_changed.emit(governor)
            else:
                QMessageBox.warning(self, "Error", 
                                  "Failed to set governor. Check permissions.")
    
    def set_performance(self):
        """Set performance mode."""
        success = self.freq_controller.set_cpu_performance_mode()
        if success:
            QMessageBox.information(self, "Success", 
                                  "Set to Performance mode")
            self.update_governor_info()
        else:
            QMessageBox.warning(self, "Error", 
                              "Failed to set performance mode. Check permissions.")
    
    def set_powersave(self):
        """Set powersave mode."""
        success = self.freq_controller.set_cpu_powersave_mode()
        if success:
            QMessageBox.information(self, "Success", 
                                  "Set to Powersave mode")
            self.update_governor_info()
        else:
            QMessageBox.warning(self, "Error", 
                              "Failed to set powersave mode. Check permissions.")
    
    def apply_frequency(self):
        """Apply frequency range."""
        min_freq = self.min_freq_spin.value()
        max_freq = self.max_freq_spin.value()
        
        if min_freq > max_freq:
            QMessageBox.warning(self, "Error", 
                              "Min frequency cannot be greater than max frequency")
            return
        
        success = self.freq_controller.set_cpu_freq_range(min_freq, max_freq)
        if success:
            QMessageBox.information(self, "Success", 
                                  f"CPU frequency range set to {min_freq}-{max_freq} MHz")
            self.cpu_freq_changed.emit(min_freq, max_freq)
        else:
            QMessageBox.warning(self, "Error", 
                              "Failed to set frequency range. Check permissions.")
    
    def apply_gpu_frequency(self):
        """Apply GPU frequency range."""
        if not hasattr(self, 'gpu_min_freq_spin'):
            return
        
        min_freq = self.gpu_min_freq_spin.value()
        max_freq = self.gpu_max_freq_spin.value()
        
        if min_freq > max_freq:
            QMessageBox.warning(self, "Error", 
                              "Min frequency cannot be greater than max frequency")
            return
        
        success = self.freq_controller.set_gpu_freq_range(min_freq, max_freq)
        if success:
            QMessageBox.information(self, "Success", 
                                  f"GPU frequency range set to {min_freq}-{max_freq} MHz")
        else:
            QMessageBox.warning(self, "Error", 
                              "Failed to set GPU frequency range. Check permissions and sudoers configuration.")
    
    def update_governor_info(self):
        """Update current governor display."""
        current = self.freq_controller.get_current_cpu_governor()
        if current:
            self.current_gov_label.setText(f"Current: {current}")
