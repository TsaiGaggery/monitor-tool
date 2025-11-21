import pytest
import os
from src.data_source import AndroidDataSource

@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get('ADB_TEST_IP'), reason="ADB_TEST_IP not set")
def test_adb_process_monitoring():
    """Integration test for ADB process monitoring.
    
    Requires environment variables:
    - ADB_TEST_IP
    """
    device_ip = os.environ.get('ADB_TEST_IP')
    port = int(os.environ.get('ADB_TEST_PORT', 5555))
    
    print(f"Connecting to {device_ip}:{port}...")
    
    ds = AndroidDataSource(device_ip=device_ip, port=port)
    
    try:
        assert ds.connect() is True
        print("Connected successfully.")
        
        # Wait a bit for data
        import time
        time.sleep(2)
        
        # Get process info
        processes = ds.get_process_info()
        print(f"Got {len(processes)} processes.")
        
        assert len(processes) > 0
        
        # Check first process structure
        p = processes[0]
        assert hasattr(p, 'pid')
        assert hasattr(p, 'name')
        assert hasattr(p, 'cpu_percent')
        
        print("Top process:", p.name, p.cpu_percent, "%")
        
    finally:
        # Cleanup if needed
        pass
