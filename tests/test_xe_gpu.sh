#!/bin/bash
# Test script for Intel Xe GPU monitoring

echo "=== Intel Xe GPU Test ==="
echo ""

echo "1. GPU Device Info:"
lspci | grep -i vga
echo ""

echo "2. DRM Card Info:"
ls -la /sys/class/drm/ | grep card
echo ""

echo "3. Debugfs Structure:"
sudo ls -la /sys/kernel/debug/dri/0/ | grep -E "gt|i915|clients"
echo ""

echo "4. GT0 Contents:"
sudo ls -la /sys/kernel/debug/dri/0/gt0/
echo ""

echo "5. Hardware Engines:"
echo "--- RCS0 (Render Engine) ---"
sudo cat /sys/kernel/debug/dri/0/gt0/hw_engines | grep -A 5 "^rcs0"
echo ""

echo "6. Client Information:"
sudo cat /sys/kernel/debug/dri/0/clients
echo ""

echo "7. GPU Statistics:"
if [ -f /sys/kernel/debug/dri/0/gt0/stats ]; then
    sudo cat /sys/kernel/debug/dri/0/gt0/stats
fi
echo ""

echo "8. Frequency Info (searching):"
find /sys/class/drm/card0 -type f 2>/dev/null | grep -i freq | head -20
find /sys/devices -name "*gpu*" -o -name "*gt*" 2>/dev/null | grep -E "freq|mhz" | head -20
echo ""

echo "9. Device Tree:"
ls -la /sys/class/drm/card0/device/ | head -30
