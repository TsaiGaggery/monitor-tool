#!/usr/bin/env python3
"""Main entry point for System Monitor Tool."""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.styles import apply_dark_theme


def main():
    """Main function."""
    app = QApplication(sys.argv)
    app.setApplicationName("System Monitor Tool")
    app.setOrganizationName("MonitorTool")
    
    # Apply dark theme
    chart_colors = apply_dark_theme(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
