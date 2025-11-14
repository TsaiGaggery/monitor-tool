#!/bin/bash
# Monitor Tool Status Check

echo "=== Monitor Tool Status Check ==="
echo ""

# Check if monitor tool is running on Intel machine
echo "Checking Intel machine (172.25.65.75)..."
ssh intel@172.25.65.75 "
echo 'Monitor tool processes:'
ps aux | grep -E 'monitor-tool|main.py' | grep -v grep

echo ''
echo 'GPU Detection Test:'
cd ~/monitor-tool && ./venv/bin/python3 -c \"
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from monitors import GPUMonitor
gpu = GPUMonitor()
info = gpu.get_all_info()
print(f'GPU Type: {gpu.gpu_type}')
print(f'Available: {info.get(\\\"available\\\")}')
if info.get('gpus'):
    for g in info['gpus']:
        print(f'  - {g[\\\"name\\\"]}: {g[\\\"gpu_clock\\\"]} MHz')
\"
"

echo ""
echo "To restart monitor tool on Intel machine:"
echo "  ssh intel@172.25.65.75"
echo "  pkill -f 'python.*main.py'"
echo "  cd ~/monitor-tool && ./monitor-tool"
