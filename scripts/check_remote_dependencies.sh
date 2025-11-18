#!/bin/bash
# Check dependencies for linux_monitor_remote.sh

echo "Checking dependencies for remote Linux monitoring..."
echo "=================================================="
echo ""

MISSING=0

# Check bash
if command -v bash >/dev/null 2>&1; then
    echo "✓ bash: $(bash --version | head -1)"
else
    echo "✗ bash: NOT FOUND (REQUIRED)"
    MISSING=$((MISSING + 1))
fi

# Check awk
if command -v awk >/dev/null 2>&1; then
    echo "✓ awk: $(awk --version 2>&1 | head -1)"
else
    echo "✗ awk: NOT FOUND (REQUIRED)"
    MISSING=$((MISSING + 1))
fi

# Check grep
if command -v grep >/dev/null 2>&1; then
    echo "✓ grep: $(grep --version | head -1)"
else
    echo "✗ grep: NOT FOUND (REQUIRED)"
    MISSING=$((MISSING + 1))
fi

# Check sqlite3
if command -v sqlite3 >/dev/null 2>&1; then
    echo "✓ sqlite3: $(sqlite3 --version)"
else
    echo "✗ sqlite3: NOT FOUND (REQUIRED)"
    MISSING=$((MISSING + 1))
fi

# Check cat, date, echo (usually built-in or coreutils)
if command -v cat >/dev/null 2>&1; then
    echo "✓ cat: available"
else
    echo "✗ cat: NOT FOUND (REQUIRED)"
    MISSING=$((MISSING + 1))
fi

if command -v date >/dev/null 2>&1; then
    echo "✓ date: available"
else
    echo "✗ date: NOT FOUND (REQUIRED)"
    MISSING=$((MISSING + 1))
fi

# Check nvidia-smi (optional)
echo ""
echo "Optional components:"
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "✓ nvidia-smi: $(nvidia-smi --version | grep 'NVIDIA-SMI' | awk '{print $2}')"
    echo "  (NVIDIA GPU monitoring available)"
else
    echo "○ nvidia-smi: not found (only needed for NVIDIA GPUs)"
fi

# Check Intel GPU paths
echo ""
echo "Intel GPU detection:"
if [ -d /sys/class/drm/card0 ] || [ -d /sys/class/drm/card1 ]; then
    for card in /sys/class/drm/card*; do
        if [ -d "$card/device" ]; then
            vendor_file="$card/device/vendor"
            if [ -f "$vendor_file" ]; then
                vendor=$(cat "$vendor_file" 2>/dev/null)
                if [ "$vendor" = "0x8086" ]; then
                    echo "✓ Intel GPU detected at $card"
                    # Check for Xe or i915
                    if [ -d "$card/device/tile0" ]; then
                        echo "  Type: Intel Xe GPU"
                    elif [ -d "$card/gt" ]; then
                        echo "  Type: Intel i915 GPU"
                    fi
                fi
            fi
        fi
    done
else
    echo "○ No Intel GPU detected"
fi

# Check NPU
echo ""
echo "Intel NPU detection:"
if [ -d /sys/class/accel/accel0 ]; then
    echo "✓ Intel NPU detected at /sys/class/accel/accel0"
else
    echo "○ No Intel NPU detected"
fi

echo ""
echo "=================================================="
if [ $MISSING -eq 0 ]; then
    echo "✓ All required dependencies are installed!"
    echo ""
    echo "Database location: /tmp/monitor_tool_\${USER}.db"
    exit 0
else
    echo "✗ Missing $MISSING required dependencies!"
    echo ""
    echo "Please install the missing packages:"
    echo "  Ubuntu/Debian: sudo apt-get install bash gawk grep coreutils sqlite3"
    echo "  RHEL/CentOS:   sudo yum install bash gawk grep coreutils sqlite"
    echo "  Arch:          sudo pacman -S bash gawk grep coreutils sqlite"
    exit 1
fi
