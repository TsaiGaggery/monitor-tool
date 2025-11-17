#!/usr/bin/env python3
"""Main entry point for System Monitor Tool."""

import sys
import os
import argparse

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.styles import apply_dark_theme
from data_source import LocalDataSource, AndroidDataSource


def main():
    """Main function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='System Monitor Tool')
    parser.add_argument('--adb', action='store_true', 
                       help='Monitor Android device via ADB')
    parser.add_argument('--ip', type=str, default='192.168.1.68',
                       help='Android device IP address (default: 192.168.1.68)')
    parser.add_argument('--port', type=int, default=5555,
                       help='ADB port (default: 5555)')
    
    # Parse known args (allow Qt args to pass through)
    args, unknown = parser.parse_known_args()
    
    # Reconstruct sys.argv for QApplication
    sys.argv = [sys.argv[0]] + unknown
    
    app = QApplication(sys.argv)
    app.setApplicationName("System Monitor Tool")
    app.setOrganizationName("MonitorTool")
    
    # Apply dark theme
    chart_colors = apply_dark_theme(app)
    
    # Create data source based on mode
    if args.adb:
        print(f"🤖 Android Monitor Mode")
        print(f"📱 Device: {args.ip}:{args.port}")
        data_source = AndroidDataSource(args.ip, args.port)
    else:
        data_source = LocalDataSource()
    
    # Create window with data source
    window = MainWindow(data_source=data_source)
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

