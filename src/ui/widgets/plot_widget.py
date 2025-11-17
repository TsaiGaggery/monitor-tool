#!/usr/bin/env python3
"""Real-time plot widget for monitoring data."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
import pyqtgraph as pg
from collections import deque
import numpy as np
from ui.styles import CHART_COLORS


class MonitorPlotWidget(QWidget):
    """Widget for displaying real-time monitoring plots."""
    
    def __init__(self, title: str, max_points: int = 60, y_label: str = "Usage (%)", dual_axis: bool = False, parent=None):
        super().__init__(parent)
        self.title = title
        self.max_points = max_points
        self.y_label = y_label
        self.dual_axis = dual_axis
        self.data_buffer = deque(maxlen=max_points)
        self.data_buffer2 = deque(maxlen=max_points) if dual_axis else None  # Second series for dual axis
        self.time_buffer = deque(maxlen=max_points)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Determine colors based on title (needed for both title and plot)
        title_lower = self.title.lower()
        line_color = '#4ecdc4'  # default gpu color
        
        if 'cpu' in title_lower:
            line_color = CHART_COLORS['cpu']
        elif 'gpu' in title_lower:
            line_color = CHART_COLORS['gpu']
        elif 'memory' in title_lower or 'mem' in title_lower:
            line_color = CHART_COLORS['memory']
        elif 'npu' in title_lower:
            line_color = CHART_COLORS['npu']
        elif 'temp' in title_lower:
            line_color = CHART_COLORS['temperature']
        elif 'power' in title_lower:
            line_color = CHART_COLORS['power']
        elif 'freq' in title_lower:
            line_color = '#14ffec'
        
        # Add custom title with color legend for dual-axis mode
        if self.dual_axis:
            freq_color = "#ffd93d"  # Yellow
            
            # Create HTML title with colored lines
            title_label = QLabel()
            title_html = f'''
            <div style="text-align: center; padding: 5px; font-size: 12pt; color: #e0e0e0;">
                {self.title}
                <span style="margin-left: 20px;">
                    <span style="color: {line_color}; font-weight: bold;">━━</span> Usage
                    <span style="margin-left: 15px; color: {freq_color}; font-weight: bold;">━━</span> Frequency
                </span>
            </div>
            '''
            title_label.setText(title_html)
            title_label.setStyleSheet("background-color: #1e1e1e;")
            layout.addWidget(title_label)
        
        # Create plot widget with dark theme
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e1e')
        
        # Only set title if not dual-axis (dual-axis uses custom label above)
        if not self.dual_axis:
            self.plot_widget.setTitle(self.title, color='#e0e0e0', size='12pt')
        
        self.plot_widget.setLabel('bottom', 'Time (s)', color='#e0e0e0')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.getAxis('bottom').setPen('#3a3a3a')
        self.plot_widget.getAxis('bottom').setTextPen('#e0e0e0')
        
        if self.dual_axis:
            # Dual axis mode: Usage (%) on left, Frequency (MHz) on right
            self.plot_widget.setLabel('left', 'Usage (%)', color='#e0e0e0')
            self.plot_widget.getAxis('left').setPen('#3a3a3a')
            self.plot_widget.getAxis('left').setTextPen('#e0e0e0')
            self.plot_widget.setYRange(0, 100)
            
            # Create second Y-axis for frequency
            self.viewbox2 = pg.ViewBox()
            self.plot_widget.scene().addItem(self.viewbox2)
            self.plot_widget.getAxis('right').linkToView(self.viewbox2)
            self.viewbox2.setXLink(self.plot_widget)
            self.plot_widget.getAxis('right').setLabel('Frequency (MHz)', color='#e0e0e0')
            self.plot_widget.showAxis('right')
            self.plot_widget.getAxis('right').setPen('#3a3a3a')
            self.plot_widget.getAxis('right').setTextPen('#e0e0e0')
            
            # Update views when plot is resized
            def update_views():
                self.viewbox2.setGeometry(self.plot_widget.getViewBox().sceneBoundingRect())
                self.viewbox2.linkedViewChanged(self.plot_widget.getViewBox(), self.viewbox2.XAxis)
            
            update_views()
            self.plot_widget.getViewBox().sigResized.connect(update_views)
            
            # Create two curves with different colors (not line styles)
            # Usage: original color (solid)
            # Frequency: contrasting bright color (solid)
            pen1 = pg.mkPen(color=line_color, width=2.5)
            pen2 = pg.mkPen(color='#ffd93d', width=2.5)  # Bright yellow for frequency
            self.curve = self.plot_widget.plot(pen=pen1, name='Usage')
            self.curve2 = pg.PlotCurveItem(pen=pen2, name='Frequency')
            self.viewbox2.addItem(self.curve2)
            
            # Add legend
            legend = self.plot_widget.addLegend(offset=(10, 10))
            legend.setLabelTextColor('#e0e0e0')
        else:
            # Single axis mode
            self.plot_widget.setLabel('left', self.y_label, color='#e0e0e0')
            self.plot_widget.getAxis('left').setPen('#3a3a3a')
            self.plot_widget.getAxis('left').setTextPen('#e0e0e0')
            
            # Set Y range based on label type
            if 'MHz' in self.y_label or 'Frequency' in self.y_label:
                self.plot_widget.enableAutoRange(axis='y')
            else:
                self.plot_widget.setYRange(0, 100)
            
            pen = pg.mkPen(color=line_color, width=2)
            self.curve = self.plot_widget.plot(pen=pen)
        
        layout.addWidget(self.plot_widget)
    
    def update_data(self, value: float, value2: float = None, timestamp: float = None):
        """Update plot with new data point(s).
        
        Args:
            value: Primary value (usage %)
            value2: Secondary value (frequency MHz), used only if dual_axis=True
            timestamp: Time stamp for x-axis
        """
        if timestamp is None:
            if self.time_buffer:
                timestamp = self.time_buffer[-1] + 1
            else:
                timestamp = 0
        
        self.data_buffer.append(value)
        self.time_buffer.append(timestamp)
        
        if self.dual_axis and value2 is not None:
            self.data_buffer2.append(value2)
        
        # Update plot
        if len(self.data_buffer) > 0:
            x = np.array(self.time_buffer)
            y = np.array(self.data_buffer)
            self.curve.setData(x, y)
            
            if self.dual_axis and len(self.data_buffer2) > 0:
                y2 = np.array(self.data_buffer2)
                self.curve2.setData(x, y2)
    
    def clear(self):
        """Clear all data."""
        self.data_buffer.clear()
        self.time_buffer.clear()
        self.curve.setData([], [])
        
        if self.dual_axis:
            self.data_buffer2.clear()
            self.curve2.setData([], [])


class MultiLinePlotWidget(QWidget):
    """Widget for displaying two lines on dual axes (e.g., upload/download, read/write)."""
    
    def __init__(self, title: str, y_label: str = "Primary", y_label2: str = "Secondary", 
                 max_points: int = 60, parent=None):
        """Initialize multi-line plot widget with dual axes.
        
        Args:
            title: Plot title
            y_label: Left Y-axis label
            y_label2: Right Y-axis label
            max_points: Maximum number of data points to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.title = title
        self.y_label = y_label
        self.y_label2 = y_label2
        self.max_points = max_points
        self.data_buffer1 = deque(maxlen=max_points)
        self.data_buffer2 = deque(maxlen=max_points)
        self.time_buffer = deque(maxlen=max_points)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Determine colors based on title
        title_lower = self.title.lower()
        color1 = CHART_COLORS['cpu']  # Default first line color
        color2 = CHART_COLORS['gpu']  # Default second line color
        
        if 'network' in title_lower:
            color1 = '#4ecdc4'  # Cyan for upload
            color2 = '#ff6b6b'  # Red for download (more contrast)
        elif 'disk' in title_lower or 'io' in title_lower:
            color1 = '#ff6b6b'  # Red for read
            color2 = '#ffd93d'  # Yellow for write
        
        # Create custom title with color legend
        title_label = QLabel()
        title_html = f'''
        <div style="text-align: center; padding: 5px; font-size: 12pt; color: #e0e0e0;">
            {self.title}
            <span style="margin-left: 20px;">
                <span style="color: {color1}; font-weight: bold;">━━</span> {self.y_label}
                <span style="margin-left: 15px; color: {color2}; font-weight: bold;">━━</span> {self.y_label2}
            </span>
        </div>
        '''
        title_label.setText(title_html)
        title_label.setStyleSheet("background-color: #1e1e1e;")
        layout.addWidget(title_label)
        
        # Create plot widget with dark theme
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e1e')
        self.plot_widget.setLabel('bottom', 'Time (s)', color='#e0e0e0')
        self.plot_widget.setLabel('left', self.y_label, color='#e0e0e0')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.getAxis('bottom').setPen('#3a3a3a')
        self.plot_widget.getAxis('bottom').setTextPen('#e0e0e0')
        self.plot_widget.getAxis('left').setPen('#3a3a3a')
        self.plot_widget.getAxis('left').setTextPen('#e0e0e0')
        
        # Create second Y-axis
        self.viewbox2 = pg.ViewBox()
        self.plot_widget.scene().addItem(self.viewbox2)
        self.plot_widget.getAxis('right').linkToView(self.viewbox2)
        self.viewbox2.setXLink(self.plot_widget)
        self.plot_widget.getAxis('right').setLabel(self.y_label2, color='#e0e0e0')
        self.plot_widget.showAxis('right')
        self.plot_widget.getAxis('right').setPen('#3a3a3a')
        self.plot_widget.getAxis('right').setTextPen('#e0e0e0')
        
        # Set Y-axis range based on plot type
        title_lower = self.title.lower()
        if 'network' in title_lower:
            # Network uses KB/s: enable auto-range starting from reasonable range
            # Don't set hard limits - let it scale automatically
            self.plot_widget.enableAutoRange(axis='y', enable=True)
            self.viewbox2.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        elif 'disk' in title_lower or 'io' in title_lower:
            # Disk uses MB/s: enable auto-range
            self.plot_widget.enableAutoRange(axis='y', enable=True)
            self.viewbox2.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        
        # Update views when plot is resized
        def update_views():
            self.viewbox2.setGeometry(self.plot_widget.getViewBox().sceneBoundingRect())
            self.viewbox2.linkedViewChanged(self.plot_widget.getViewBox(), self.viewbox2.XAxis)
        
        update_views()
        self.plot_widget.getViewBox().sigResized.connect(update_views)
        
        # Create two curves
        pen1 = pg.mkPen(color=color1, width=2.5)
        pen2 = pg.mkPen(color=color2, width=2.5)
        self.curve1 = self.plot_widget.plot(pen=pen1, name=self.y_label)
        self.curve2 = pg.PlotCurveItem(pen=pen2, name=self.y_label2)
        self.viewbox2.addItem(self.curve2)
        
        layout.addWidget(self.plot_widget)
    
    def update_data(self, value1: float, value2: float, timestamp: float = None):
        """Update plot with new data points.
        
        Args:
            value1: First value (left axis)
            value2: Second value (right axis)
            timestamp: Time stamp for x-axis
        """
        if timestamp is None:
            if self.time_buffer:
                timestamp = self.time_buffer[-1] + 1
            else:
                timestamp = 0
        
        self.data_buffer1.append(value1)
        self.data_buffer2.append(value2)
        self.time_buffer.append(timestamp)
        
        # Update plot
        if len(self.data_buffer1) > 0:
            x = np.array(self.time_buffer)
            y1 = np.array(self.data_buffer1)
            y2 = np.array(self.data_buffer2)
            self.curve1.setData(x, y1)
            self.curve2.setData(x, y2)
    
    def clear(self):
        """Clear all data."""
        self.data_buffer1.clear()
        self.data_buffer2.clear()
        self.time_buffer.clear()
        self.curve1.setData([], [])
        self.curve2.setData([], [])
