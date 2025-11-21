import pytest
import os
from src.data_source import RemoteLinuxDataSource

@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get('SSH_TEST_HOST'), reason="SSH_TEST_HOST not set")
def test_ssh_process_monitoring():
    """Integration test for SSH process monitoring.
    
    Requires environment variables:
    - SSH_TEST_HOST
    - SSH_TEST_USER
    - SSH_TEST_PASSWORD or SSH_TEST_KEY
    """
    host = os.environ.get('SSH_TEST_HOST')
    user = os.environ.get('SSH_TEST_USER')
    password = os.environ.get('SSH_TEST_PASSWORD')
    key_path = os.environ.get('SSH_TEST_KEY')
    
    print(f"Connecting to {user}@{host}...")
    
    ds = RemoteLinuxDataSource(
        host=host,
        username=user,
        password=password,
        key_path=key_path
    )
    
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
        ds.disconnect()
