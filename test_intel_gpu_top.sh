#!/bin/bash
# Test intel_gpu_top JSON output

echo "Testing intel_gpu_top JSON mode..."
echo ""

# Run for 2 seconds to get sample data
timeout 2 intel_gpu_top -J -s 500 -o - 2>/dev/null || echo "Failed (may need sudo)"
