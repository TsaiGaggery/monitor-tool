
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from monitors.adb_monitor_raw import ADBMonitorRaw
import monitors.adb_monitor_raw
import monitors

def test():
    print(f"monitors package: {monitors.__file__}")
    print(f"adb_monitor_raw module: {monitors.adb_monitor_raw.__file__}")
    
    with open(monitors.adb_monitor_raw.__file__, 'r') as f:
        content = f.read()
        print("--- File Content Start ---")
        # Print lines around where get_process_info should be
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "def get_process_info" in line:
                print(f"{i+1}: {line}")
        print("--- File Content End ---")

    with patch('subprocess.run') as mock_run, patch('threading.Thread'):
        mock_run.return_value.stdout = "connected to 127.0.0.1:5555"
        monitor = ADBMonitorRaw('127.0.0.1')
        print(f"Has get_process_info: {hasattr(monitor, 'get_process_info')}")
        print(f"Has _process_info: {hasattr(monitor, '_process_info')}")
        print(dir(monitor))

if __name__ == "__main__":
    test()
