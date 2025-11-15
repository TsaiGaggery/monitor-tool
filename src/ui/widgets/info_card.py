#!/usr/bin/env python3
"""Info card widget for displaying system metrics in the overview."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class InfoCard(QFrame):
    """A card widget displaying a metric with title and values."""
    
    def __init__(self, title: str, icon: str = "", parent=None):
        """Initialize info card.
        
        Args:
            title: Card title (e.g., "CPU", "Memory")
            icon: Optional icon/emoji to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Title with icon
        title_text = f"{icon} {title}" if icon else title
        self.title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Primary value (large)
        self.primary_label = QLabel("-")
        primary_font = QFont()
        primary_font.setPointSize(18)
        primary_font.setBold(True)
        self.primary_label.setFont(primary_font)
        self.primary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.primary_label)
        
        # Secondary value (small)
        self.secondary_label = QLabel("")
        secondary_font = QFont()
        secondary_font.setPointSize(9)
        self.secondary_label.setFont(secondary_font)
        self.secondary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.secondary_label)
        
        # Set minimum size
        self.setMinimumWidth(120)
        self.setMinimumHeight(100)
    
    def update_values(self, primary: str, secondary: str = ""):
        """Update card values.
        
        Args:
            primary: Main value to display (e.g., "45.2%")
            secondary: Secondary value (e.g., "2.4 GHz")
        """
        self.primary_label.setText(primary)
        self.secondary_label.setText(secondary)
    
    def set_color(self, color: str):
        """Set the accent color for the card.
        
        Args:
            color: Color name or hex code
        """
        self.setStyleSheet(f"""
            InfoCard {{
                border: 2px solid {color};
                border-radius: 8px;
                background-color: #2b2b2b;
            }}
        """)
