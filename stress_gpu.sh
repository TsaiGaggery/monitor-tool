#!/bin/bash
# GPU Stress Test Script for Intel GPU

echo "=== Intel GPU Stress Test ==="
echo ""

# Check what GPU stress tools are available
echo "Checking available GPU stress tools..."
echo ""

# Method 1: glxgears (simple OpenGL test)
if command -v glxgears &> /dev/null; then
    echo "✓ glxgears available (basic OpenGL)"
    echo "  Usage: glxgears -fullscreen"
else
    echo "✗ glxgears not found"
    echo "  Install: sudo apt install mesa-utils"
fi

# Method 2: glmark2 (comprehensive OpenGL benchmark)
if command -v glmark2 &> /dev/null; then
    echo "✓ glmark2 available (OpenGL benchmark)"
    echo "  Usage: glmark2"
else
    echo "✗ glmark2 not found"
    echo "  Install: sudo apt install glmark2"
fi

# Method 3: intel_gpu_top (Intel GPU monitoring)
if command -v intel_gpu_top &> /dev/null; then
    echo "✓ intel_gpu_top available (Intel GPU monitor)"
else
    echo "✗ intel_gpu_top not found"
    echo "  Install: sudo apt install intel-gpu-tools"
fi

# Method 4: vkcube (Vulkan test)
if command -v vkcube &> /dev/null; then
    echo "✓ vkcube available (Vulkan)"
else
    echo "✗ vkcube not found"
    echo "  Install: sudo apt install vulkan-tools"
fi

echo ""
echo "=== Choose stress test method ==="
echo "1) glxgears (light load, simple spinning gears)"
echo "2) glmark2 (heavy load, comprehensive benchmark)"
echo "3) vkcube (Vulkan spinning cube)"
echo "4) Custom: Run multiple glxgears instances"
echo "5) Just monitor current GPU state"
read -p "Select option [1-5]: " option

case $option in
    1)
        echo ""
        echo "Starting glxgears..."
        echo "Press Ctrl+C to stop"
        glxgears -fullscreen
        ;;
    2)
        if command -v glmark2 &> /dev/null; then
            echo ""
            echo "Starting glmark2 benchmark..."
            glmark2
        else
            echo "glmark2 not installed. Installing..."
            sudo apt install -y glmark2
            glmark2
        fi
        ;;
    3)
        if command -v vkcube &> /dev/null; then
            echo ""
            echo "Starting vkcube..."
            vkcube
        else
            echo "vkcube not installed. Installing..."
            sudo apt install -y vulkan-tools
            vkcube
        fi
        ;;
    4)
        echo ""
        echo "Starting 4 glxgears instances for higher GPU load..."
        for i in {1..4}; do
            glxgears &
        done
        echo "Running... Press Enter to stop all instances"
        read
        killall glxgears
        ;;
    5)
        echo ""
        echo "=== Current GPU State ==="
        if [ -f /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq ]; then
            echo -n "Actual Frequency: "
            cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq
            echo " MHz"
            
            echo -n "Current Setting: "
            cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq
            echo " MHz"
            
            echo -n "Min Frequency: "
            cat /sys/class/drm/card0/device/tile0/gt0/freq0/min_freq
            echo " MHz"
            
            echo -n "Max Frequency: "
            cat /sys/class/drm/card0/device/tile0/gt0/freq0/max_freq
            echo " MHz"
        else
            echo "Intel Xe GPU frequency info not found"
        fi
        
        echo ""
        echo "GPU is showing 0% because act_freq = 0 (GPU is idle/in C6 state)"
        echo "This is CORRECT behavior when no graphics workload is running."
        ;;
    *)
        echo "Invalid option"
        ;;
esac
