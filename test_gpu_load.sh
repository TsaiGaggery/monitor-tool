#!/bin/bash
# GPU Load Test - Start a simple GPU workload to test monitoring

echo "=== GPU Load Test ==="
echo ""
echo "Starting GPU workload using glxgears (if available)..."
echo "Monitor the GPU usage in the dashboard."
echo ""

# Check if glxgears is available
if command -v glxgears &> /dev/null; then
    echo "Starting glxgears for 10 seconds..."
    timeout 10 glxgears &
    GEARS_PID=$!
    
    echo "Monitoring GPU while glxgears is running..."
    for i in {1..10}; do
        sleep 1
        echo -n "."
    done
    echo ""
    
    # Wait for glxgears to finish
    wait $GEARS_PID 2>/dev/null
    echo "GPU load test complete"
else
    echo "glxgears not found. Install mesa-utils:"
    echo "  sudo apt install mesa-utils"
    echo ""
    echo "Alternative: Run any graphics application to generate GPU load"
fi

echo ""
echo "Current GPU status:"
cd ~/monitor-tool && ./venv/bin/python3 -c "
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from monitors import GPUMonitor
gpu = GPUMonitor()
info = gpu.get_all_info()
if info.get('gpus'):
    g = info['gpus'][0]
    print(f\"GPU: {g['name']}\")
    print(f\"Usage: {g['gpu_util']}%\")
    print(f\"Frequency: {g['gpu_clock']} MHz\")
"
