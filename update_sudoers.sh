#!/bin/bash
# Update sudoers configuration for GPU frequency control

echo "=== Updating sudoers configuration for GPU frequency control ==="

SUDOERS_FILE="/etc/sudoers.d/monitor-tool"
CURRENT_USER=$(whoami)

echo "This will update $SUDOERS_FILE to allow GPU frequency control"
read -p "Continue? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

# Create updated sudoers configuration
sudo bash -c "cat > $SUDOERS_FILE << 'EOFCFG'
# Allow monitor-tool to control CPU frequencies without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/devices/system/cpu/cpu*/cpufreq/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/devices/system/cpu/cpu*/cpufreq/*
# Allow monitor-tool to control GPU frequencies without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/device/tile*/gt*/freq0/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/gt_*_freq_mhz
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/class/drm/card*/device/tile*/gt*/freq0/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/class/drm/card*/gt_*_freq_mhz
# Allow monitor-tool to read GPU debug info without password (for Intel GPU utilization)
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/kernel/debug/dri/*/i915_engine_info
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/kernel/debug/dri/*/i915_gem_objects
EOFCFG"

# Fix the variable substitution
sudo sed -i "s/\$CURRENT_USER/$CURRENT_USER/g" "$SUDOERS_FILE"

sudo chmod 0440 "$SUDOERS_FILE"

echo ""
echo "✓ Sudoers configuration updated"
echo ""
echo "You can now control GPU frequencies from the dashboard!"
echo "Please restart the monitor tool to apply changes."
