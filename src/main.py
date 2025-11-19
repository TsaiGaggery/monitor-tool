#!/usr/bin/env python3
"""Main entry point for System Monitor Tool."""

import sys
import os
import argparse
import getpass
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.styles import apply_dark_theme
from data_source import LocalDataSource, AndroidDataSource, RemoteLinuxDataSource


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
    
    # SSH remote Linux support
    parser.add_argument('--ssh', action='store_true',
                       help='Monitor remote Linux system via SSH')
    parser.add_argument('--host', type=str,
                       help='Remote Linux host (IP or hostname)')
    parser.add_argument('--user', type=str,
                       help='SSH username')
    parser.add_argument('--ssh-port', type=int, default=22,
                       help='SSH port (default: 22)')
    parser.add_argument('--key', type=str,
                       help='Path to SSH private key')
    
    # Parse known args (allow Qt args to pass through)
    args, unknown = parser.parse_known_args()
    
    # Load configuration
    config_path = Path(__file__).parent.parent / 'config' / 'default.yaml'
    enable_tier1 = False
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            # tier1_metrics is under monitoring section
            enable_tier1 = config.get('monitoring', {}).get('tier1_metrics', {}).get('enabled', False)
    except ImportError:
        # yaml module not installed, use default
        pass
    except Exception as e:
        print(f"⚠️  Warning: Could not load config file: {e}")
        print(f"   Using default tier1_metrics.enabled = False")
    
    # Reconstruct sys.argv for QApplication
    sys.argv = [sys.argv[0]] + unknown
    
    app = QApplication(sys.argv)
    app.setApplicationName("System Monitor Tool")
    app.setOrganizationName("MonitorTool")
    
    # Apply dark theme
    chart_colors = apply_dark_theme(app)
    
    # Create data source based on mode
    if args.ssh:
        if not args.host or not args.user:
            print("❌ Error: --host and --user are required for SSH mode")
            print("   Example: monitor-tool --ssh --host 192.168.1.100 --user username")
            sys.exit(1)
        
        print(f"🐧 Remote Linux Monitor Mode")
        print(f"📡 Host: {args.user}@{args.host}:{args.ssh_port}")
        
        # Try to connect with up to 3 password attempts
        data_source = None
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            # Get password or key passphrase
            password = None
            if args.key:
                # Using SSH key - may need passphrase
                if attempt == 1:
                    # First try without passphrase
                    password = None
                else:
                    # Key needs passphrase
                    print(f"⚠️  Key requires passphrase. Attempt {attempt}/{max_attempts}")
                    password = getpass.getpass(f"🔑 Passphrase for SSH key: ")
            else:
                # Using password authentication
                if attempt == 1:
                    password = getpass.getpass(f"🔒 SSH password for {args.user}@{args.host}: ")
                else:
                    print(f"⚠️  Authentication failed. Attempt {attempt}/{max_attempts}")
                    password = getpass.getpass(f"🔒 SSH password for {args.user}@{args.host}: ")
            
            data_source = RemoteLinuxDataSource(
                host=args.host,
                username=args.user,
                password=password,
                port=args.ssh_port,
                key_path=args.key,
                enable_tier1=enable_tier1
            )
            
            # Try to connect
            print(f"🔌 Connecting to {args.user}@{args.host}:{args.ssh_port}...")
            if data_source.connect():
                print("✅ Connection successful!")
                break
            else:
                print(f"❌ Connection failed")
                data_source.disconnect()
                data_source = None
        
        # If all attempts failed, exit
        if data_source is None:
            if args.key:
                print(f"❌ SSH key authentication failed after {max_attempts} attempts")
            else:
                print(f"❌ Failed to connect after {max_attempts} attempts")
            sys.exit(1)
            
    elif args.adb:
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

