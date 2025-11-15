#!/usr/bin/env python3
"""Debug Xe GPU memory reading."""

import os
import sys
sys.path.insert(0, 'src')

from monitors.gpu_monitor import GPUMonitor

def main():
    monitor = GPUMonitor()
    print("=" * 60)
    print("Debugging Xe GPU Memory Reading")
    print("=" * 60)
    print()
    
    # Test the function
    print("1. Testing _get_xe_gpu_memory(0):")
    mem = monitor._get_xe_gpu_memory(0)
    print(f"   Result: {mem}")
    print()
    
    # Manual check
    print("2. Manual fdinfo scan:")
    total_used = 0
    process_count = 0
    
    for pid_dir in os.listdir('/proc'):
        if not pid_dir.isdigit():
            continue
        
        fdinfo_dir = f'/proc/{pid_dir}/fdinfo'
        if not os.path.exists(fdinfo_dir):
            continue
        
        try:
            for fd_file in os.listdir(fdinfo_dir):
                fd_path = os.path.join(fdinfo_dir, fd_file)
                try:
                    with open(fd_path, 'r') as f:
                        content = f.read()
                        if 'drm-driver:' in content and 'xe' in content:
                            process_count += 1
                            print(f"   Found Xe in PID {pid_dir}, FD {fd_file}")
                            
                            # Show content
                            for line in content.split('\n'):
                                if 'drm-' in line:
                                    print(f"     {line}")
                            
                            # Parse memory
                            for line in content.split('\n'):
                                if line.startswith('drm-total-system:'):
                                    mem_kb = int(line.split(':')[1].strip())
                                    total_used += mem_kb * 1024
                                    print(f"     -> Adding {mem_kb} KB")
                            print()
                            
                            if process_count >= 3:  # Limit output
                                break
                except (PermissionError, FileNotFoundError, ValueError):
                    continue
            
            if process_count >= 3:
                break
        except (PermissionError, FileNotFoundError):
            continue
    
    print(f"3. Summary:")
    print(f"   Processes with Xe GPU: {process_count}")
    print(f"   Total memory used: {total_used} bytes ({total_used / (1024*1024):.2f} MB)")
    print()
    
    # Get GPU info
    print("4. Full GPU info:")
    info = monitor.get_intel_info()
    import json
    print(json.dumps(info, indent=2))

if __name__ == '__main__':
    main()
