#!/bin/bash
# Update sudoers configuration for CPU/GPU/NPU frequency control and monitoring

echo "=== Updating sudoers configuration for system monitoring and control ==="

SUDOERS_FILE="/etc/sudoers.d/monitor-tool"
CURRENT_USER=$(whoami)

echo "This will update $SUDOERS_FILE to allow CPU/GPU/NPU frequency control and monitoring"
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
# Allow monitor-tool to control GPU frequencies without password (Intel Xe/i915)
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/device/tile*/gt*/freq0/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/gt_*_freq_mhz
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/class/drm/card*/device/tile*/gt*/freq0/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/class/drm/card*/gt_*_freq_mhz
# Allow monitor-tool to read GPU debug info without password (for Intel GPU utilization)
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/kernel/debug/dri/*/i915_engine_info
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/kernel/debug/dri/*/i915_gem_objects
# Allow monitor-tool to access NPU debug info without password (Intel NPU, if needed in future)
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/kernel/debug/dri/*/i915_vpu_usage
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/kernel/debug/npu/*
# Allow monitor-tool to control NPU frequencies without password (if writeable in future)
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/accel/accel*/device/npu_*
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/devfreq/*/npu/*
# Allow monitor-tool to read CPU power consumption (RAPL/AMD) without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/class/powercap/intel-rapl/intel-rapl*/energy_uj
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/class/powercap/intel-rapl-mmio/intel-rapl-mmio*/energy_uj
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/class/hwmon/hwmon*/energy*_input
EOFCFG"

# Fix the variable substitution
sudo sed -i "s/\$CURRENT_USER/$CURRENT_USER/g" "$SUDOERS_FILE"

sudo chmod 0440 "$SUDOERS_FILE"

echo ""
echo "✓ Sudoers configuration updated"
echo ""
echo "You can now control CPU/GPU frequencies and access all monitoring data from the dashboard!"
echo "Note: NPU monitoring works without sudo (read-only sysfs files)"
echo "Please restart the monitor tool to apply changes."
