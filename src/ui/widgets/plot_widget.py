#!/usr/bin/env python3
"""Real-time plot widget for monitoring data."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
import pyqtgraph as pg
from collections import deque
import numpy as np


class MonitorPlotWidget(QWidget):
    """Widget for displaying real-time monitoring plots."""
    
    def __init__(self, title: str, max_points: int = 60, y_label: str = "Usage (%)", parent=None):
        super().__init__(parent)
        self.title = title
        self.max_points = max_points
        self.y_label = y_label
        self.data_buffer = deque(maxlen=max_points)
        self.time_buffer = deque(maxlen=max_points)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(self.title, color='k', size='12pt')
        self.plot_widget.setLabel('left', self.y_label, color='k')
        self.plot_widget.setLabel('bottom', 'Time (s)', color='k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Set Y range based on label type
        if 'MHz' in self.y_label or 'Frequency' in self.y_label:
            self.plot_widget.enableAutoRange(axis='y')
        else:
            self.plot_widget.setYRange(0, 100)
        
        # Create plot curve
        pen = pg.mkPen(color='b', width=2)
        self.curve = self.plot_widget.plot(pen=pen)
        
        layout.addWidget(self.plot_widget)
    
    def update_data(self, value: float, timestamp: float = None):
        """Update plot with new data point."""
        if timestamp is None:
            if self.time_buffer:
                timestamp = self.time_buffer[-1] + 1
            else:
                timestamp = 0
        
        self.data_buffer.append(value)
        self.time_buffer.append(timestamp)
        
        # Update plot
        if len(self.data_buffer) > 0:
            x = np.array(self.time_buffer)
            y = np.array(self.data_buffer)
            self.curve.setData(x, y)
    
    def clear(self):
        """Clear all data."""
        self.data_buffer.clear()
        self.time_buffer.clear()
        self.curve.setData([], [])


class MultiLinePlotWidget(QWidget):
    """Widget for displaying multiple lines on the same plot."""
    
    def __init__(self, title: str, line_names: list, max_points: int = 60, parent=None):
        super().__init__(parent)
        self.title = title
        self.line_names = line_names
        self.max_points = max_points
        self.data_buffers = {name: deque(maxlen=max_points) for name in line_names}
        self.time_buffer = deque(maxlen=max_points)
        self.curves = {}
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(self.title, color='k', size='12pt')
        self.plot_widget.setLabel('left', 'Usage (%)', color='k')
        self.plot_widget.setLabel('bottom', 'Time (s)', color='k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(0, 100)
        self.plot_widget.addLegend()
        
        # Create curves for each line
        colors = ['b', 'r', 'g', 'c', 'm', 'y', 'w']
        for i, name in enumerate(self.line_names):
            pen = pg.mkPen(color=colors[i % len(colors)], width=2)
            self.curves[name] = self.plot_widget.plot(pen=pen, name=name)
        
        layout.addWidget(self.plot_widget)
    
    def update_data(self, values: dict, timestamp: float = None):
        """Update plot with new data points."""
        if timestamp is None:
            if self.time_buffer:
                timestamp = self.time_buffer[-1] + 1
            else:
                timestamp = 0
        
        self.time_buffer.append(timestamp)
        
        for name, value in values.items():
            if name in self.data_buffers:
                self.data_buffers[name].append(value)
        
        # Update all curves
        if len(self.time_buffer) > 0:
            x = np.array(self.time_buffer)
            for name, curve in self.curves.items():
                if len(self.data_buffers[name]) > 0:
                    y = np.array(self.data_buffers[name])
                    curve.setData(x, y)
    
    def clear(self):
        """Clear all data."""
        for buffer in self.data_buffers.values():
            buffer.clear()
        self.time_buffer.clear()
        for curve in self.curves.values():
            curve.setData([], [])
