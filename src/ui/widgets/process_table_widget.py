#!/usr/bin/env python3
"""Process table widget for displaying top processes."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

class ProcessTableWidget(QWidget):
    """Widget displaying top processes in a table."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel("Top Processes")
        self.title_label.setAlignment(Qt.AlignLeft)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 32px; margin-bottom: 10px; padding-left: 2px;")
        layout.addWidget(self.title_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Mem (MB)", "Command"])
        
        # Configure header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # PID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # CPU
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Mem
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Command
        
        # Hide vertical header (row numbers)
        self.table.verticalHeader().setVisible(False)
        
        # Read-only
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Set much larger font for table (2x) with better row height
        self.table.setStyleSheet("""
            QTableWidget {
                font-size: 24px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        self.table.verticalHeader().setDefaultSectionSize(50)
        
        layout.addWidget(self.table)
        
        # Colors for severity
        self.colors = {
            'critical': QColor(255, 100, 100, 50),  # Light Red
            'warning': QColor(255, 200, 100, 50),   # Light Orange
            'normal': QColor(0, 0, 0, 0)            # Transparent
        }
        
    def update_data(self, processes):
        """Update table with new process data.
        
        Args:
            processes: List of ProcessInfo objects or dicts
        """
        if not processes:
            self.table.setRowCount(0)
            return
            
        self.table.setRowCount(len(processes))
        self.table.setSortingEnabled(False)  # Disable sorting during update
        
        for row, proc in enumerate(processes):
            # Handle both object and dict access
            if hasattr(proc, 'pid'):
                pid = proc.pid
                name = proc.name
                cpu = proc.cpu_percent
                mem_rss = proc.memory_rss
                cmdline = proc.cmdline
                # Calculate severity if available, otherwise default to normal
                # Assuming the process object might have a severity attribute or we calculate it
                # For now, we'll rely on the caller or simple logic if needed.
                # But wait, ProcessMonitor has get_severity. 
                # The widget shouldn't depend on ProcessMonitor instance directly if possible,
                # but it needs to know severity.
                # Let's assume the passed object might have it or we pass a tuple.
                # Actually, let's just use the values to determine color if severity isn't passed.
                # Or better, let's assume the caller might pass severity in a wrapper or we calculate simple thresholds here for UI.
                # Re-reading TASK-003, ProcessMonitor has get_severity.
                # Re-reading TASK-007, "Implement color coding for severity".
                # We'll implement a simple helper or expect the data to contain it.
                # Let's stick to raw data for now and maybe add a severity check if we have access to config.
                # For simplicity in this widget, let's assume 'critical' > 80% CPU, 'warning' > 50%.
                severity = 'normal'
                if cpu > 80: severity = 'critical'
                elif cpu > 50: severity = 'warning'
            else:
                pid = proc.get('pid')
                name = proc.get('name')
                cpu = proc.get('cpu_percent', 0)
                mem_rss = proc.get('memory_rss', 0)
                cmdline = proc.get('cmdline', '')
                severity = proc.get('severity', 'normal')

            # PID
            pid_item = QTableWidgetItem(str(pid))
            pid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 0, pid_item)
            
            # Name
            name_item = QTableWidgetItem(str(name))
            name_item.setToolTip(f"Process: {name}")
            self.table.setItem(row, 1, name_item)
            
            # CPU
            cpu_item = QTableWidgetItem(f"{cpu:.1f}")
            cpu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, cpu_item)
            
            # Memory
            mem_mb = mem_rss / (1024 * 1024)
            mem_item = QTableWidgetItem(f"{mem_mb:.1f}")
            mem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, mem_item)
            
            # Command line (full command with arguments)
            # cmdline should contain the full command with args, not just the name
            # If cmdline is empty or same as name, show name instead
            if cmdline and str(cmdline).strip() and str(cmdline) != str(name):
                cmd_display = str(cmdline)[:200]  # Limit to 200 chars for display
            else:
                # Fallback to name if cmdline is missing/empty
                cmd_display = str(name)
            
            cmd_item = QTableWidgetItem(cmd_display)
            cmd_item.setToolTip(str(cmdline) if cmdline else str(name))  # Full command on hover
            self.table.setItem(row, 4, cmd_item)
            
            # Color coding
            bg_color = self.colors.get(severity, self.colors['normal'])
            for col in range(5):
                item = self.table.item(row, col)
                item.setBackground(QBrush(bg_color))
