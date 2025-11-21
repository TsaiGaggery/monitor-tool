#!/bin/bash
echo "=== System Info ==="
uname -a
cat /etc/os-release

echo -e "\n=== NPU Debug ==="
echo "Listing /sys/class/accel/:"
ls -la /sys/class/accel/ 2>/dev/null

for d in /sys/class/accel/accel*; do
  if [ -e "$d" ]; then
    echo "Checking $d:"
    echo "  Device path: $d/device"
    ls -la "$d/device/" 2>/dev/null
    echo "  Vendor: $(cat "$d/device/vendor" 2>/dev/null)"
    echo "  Device: $(cat "$d/device/device" 2>/dev/null)"
    echo "  Files in device dir:"
    ls "$d/device/" | grep npu
  fi
done

echo -e "\n=== GPU Debug ==="
echo "Listing /sys/class/drm/:"
ls -la /sys/class/drm/ 2>/dev/null

for d in /sys/class/drm/card*; do
  if [ -e "$d" ]; then
    echo "Checking $d:"
    echo "  Vendor: $(cat "$d/device/vendor" 2>/dev/null)"
    echo "  Device: $(cat "$d/device/device" 2>/dev/null)"
    
    echo "  Checking for i915 paths:"
    ls -la "$d/gt/gt0/" 2>/dev/null | grep rc6
    ls -la "$d/power/" 2>/dev/null | grep rc6
    
    echo "  Checking for Xe paths:"
    ls -la "$d/device/tile0/gt0/gtidle/" 2>/dev/null
  fi
done

echo -e "\n=== Kernel Modules ==="
lsmod | grep -E "i915|xe|npu|vpu|intel"
