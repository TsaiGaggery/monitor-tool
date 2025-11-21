#!/bin/bash
# Linux Frequency Controller via SSH
# Control CPU governor and frequency, GPU frequency
# Usage: bash linux_freq_controller.sh [command] [args...]

# Commands:
#   get_cpu_governors - List available CPU governors
#   get_cpu_governor - Get current CPU governor
#   set_cpu_governor [governor] - Set CPU governor (performance/powersave)
#   get_cpu_freq_range - Get CPU frequency range (kHz)
#   set_cpu_freq_range [min] [max] - Set CPU frequency range in MHz
#   get_gpu_freq_range - Get GPU frequency range (MHz)
#   set_gpu_freq_range [min] [max] - Set GPU frequency range in MHz
#   get_all - Get all frequency information

CPU_COUNT=$(ls -d /sys/devices/system/cpu/cpu[0-9]* 2>/dev/null | wc -l)

# Get available CPU governors
get_cpu_governors() {
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors" ]; then
        cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
    else
        echo "N/A"
    fi
}

# Get current CPU governor
get_cpu_governor() {
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor" ]; then
        cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
    else
        echo "N/A"
    fi
}

# Set CPU governor for all cores (requires sudo)
set_cpu_governor() {
    governor=$1
    
    if [ -z "$governor" ]; then
        echo "ERROR: Governor not specified"
        return 1
    fi
    
    # Verify governor is available
    available=$(get_cpu_governors)
    if ! echo "$available" | grep -q "$governor"; then
        echo "ERROR: Governor '$governor' not available. Available: $available"
        return 1
    fi
    
    for i in $(seq 0 $((CPU_COUNT - 1))); do
        gov_path="/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_governor"
        if [ -f "$gov_path" ]; then
            echo "$governor" | sudo tee "$gov_path" > /dev/null 2>&1
            if [ $? -ne 0 ]; then
                echo "ERROR: Failed to set governor for CPU $i"
                return 1
            fi
        fi
    done
    
    echo "OK: Governor set to $governor for $CPU_COUNT CPUs"
    return 0
    echo "OK: Governor set to $governor for $CPU_COUNT CPUs"
    return 0
}

# Get CPU Energy Performance Preference (EPP)
get_cpu_epp() {
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference" ]; then
        cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
    else
        echo "N/A"
    fi
}

# Set CPU EPP for all cores (requires sudo)
set_cpu_epp() {
    epp=$1
    
    if [ -z "$epp" ]; then
        echo "ERROR: EPP preference not specified"
        return 1
    fi
    
    # Verify EPP is available
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences" ]; then
        available=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences)
        if ! echo "$available" | grep -q "$epp"; then
            echo "ERROR: EPP '$epp' not available. Available: $available"
            return 1
        fi
    else
        # Fallback check if available_preferences file doesn't exist but EPP does
        # Common values: default, performance, balance_performance, balance_power, power
        if [[ ! "$epp" =~ ^(default|performance|balance_performance|balance_power|power)$ ]]; then
             echo "WARNING: Cannot verify EPP availability. Proceeding anyway."
        fi
    fi
    
    for i in $(seq 0 $((CPU_COUNT - 1))); do
        epp_path="/sys/devices/system/cpu/cpu${i}/cpufreq/energy_performance_preference"
        if [ -f "$epp_path" ]; then
            echo "$epp" | sudo tee "$epp_path" > /dev/null 2>&1
            if [ $? -ne 0 ]; then
                echo "ERROR: Failed to set EPP for CPU $i"
                return 1
            fi
        fi
    done
    
    echo "OK: EPP set to $epp for $CPU_COUNT CPUs"
    return 0
}

# Get available EPP preferences
get_available_epp() {
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences" ]; then
        cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences
    else
        echo "N/A"
    fi
}

# Get CPU frequency range
get_cpu_freq_range() {
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq" ]; then
        hw_min=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq)
        hw_max=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
        scaling_min=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq)
        scaling_max=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)
        
        # Convert kHz to MHz
        hw_min_mhz=$((hw_min / 1000))
        hw_max_mhz=$((hw_max / 1000))
        scaling_min_mhz=$((scaling_min / 1000))
        scaling_max_mhz=$((scaling_max / 1000))
        
        echo "HW_MIN:$hw_min_mhz HW_MAX:$hw_max_mhz SCALING_MIN:$scaling_min_mhz SCALING_MAX:$scaling_max_mhz"
    else
        echo "N/A"
    fi
}

# Set CPU frequency range (in MHz, requires sudo)
set_cpu_freq_range() {
    min_mhz=$1
    max_mhz=$2
    
    if [ -z "$min_mhz" ] || [ -z "$max_mhz" ]; then
        echo "ERROR: Min and max frequency not specified"
        return 1
    fi
    
    # Convert MHz to kHz
    min_khz=$((min_mhz * 1000))
    max_khz=$((max_mhz * 1000))
    
    for i in $(seq 0 $((CPU_COUNT - 1))); do
        min_path="/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_min_freq"
        max_path="/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_max_freq"
        
        if [ -f "$min_path" ] && [ -f "$max_path" ]; then
            echo "$min_khz" | sudo tee "$min_path" > /dev/null 2>&1
            echo "$max_khz" | sudo tee "$max_path" > /dev/null 2>&1
            if [ $? -ne 0 ]; then
                echo "ERROR: Failed to set frequency for CPU $i"
                return 1
            fi
        fi
    done
    
    echo "OK: CPU frequency range set to $min_mhz-$max_mhz MHz for $CPU_COUNT CPUs"
    return 0
}

# Get GPU frequency range (Intel Xe)
get_gpu_freq_range() {
    # Try to find Intel GPU on different card numbers (card0-card4)
    for card_num in 0 1 2 3 4; do
        # Try Intel Xe first (newer, e.g., Arc GPUs)
        xe_path="/sys/class/drm/card${card_num}/device/tile0/gt0/freq0"
        if [ -d "$xe_path" ]; then
            if [ -f "$xe_path/min_freq" ] && [ -f "$xe_path/max_freq" ]; then
                hw_min=$(cat "$xe_path/rpn_freq" 2>/dev/null || echo "0")
                hw_max=$(cat "$xe_path/rp0_freq" 2>/dev/null || echo "0")
                scaling_min=$(cat "$xe_path/min_freq")
                scaling_max=$(cat "$xe_path/max_freq")
                
                echo "TYPE:intel_xe HW_MIN:$hw_min HW_MAX:$hw_max SCALING_MIN:$scaling_min SCALING_MAX:$scaling_max"
                return 0
            fi
        fi
        
        # Try legacy i915 (older Intel GPUs)
        i915_path="/sys/class/drm/card${card_num}"
        if [ -f "$i915_path/gt_min_freq_mhz" ] && [ -f "$i915_path/gt_max_freq_mhz" ]; then
            hw_min=$(cat "$i915_path/gt_RP1_freq_mhz" 2>/dev/null || echo "0")
            hw_max=$(cat "$i915_path/gt_RP0_freq_mhz" 2>/dev/null || echo "0")
            scaling_min=$(cat "$i915_path/gt_min_freq_mhz")
            scaling_max=$(cat "$i915_path/gt_max_freq_mhz")
            
            echo "TYPE:intel_i915 HW_MIN:$hw_min HW_MAX:$hw_max SCALING_MIN:$scaling_min SCALING_MAX:$scaling_max"
            return 0
        fi
    done
    
    echo "N/A"
}

# Set GPU frequency range (in MHz, requires sudo)
set_gpu_freq_range() {
    min_mhz=$1
    max_mhz=$2
    
    if [ -z "$min_mhz" ] || [ -z "$max_mhz" ]; then
        echo "ERROR: Min and max frequency not specified"
        return 1
    fi
    
    # Try to find Intel GPU on different card numbers (card0-card4)
    for card_num in 0 1 2 3 4; do
        # Try Intel Xe first
        xe_path="/sys/class/drm/card${card_num}/device/tile0/gt0/freq0"
        if [ -d "$xe_path" ]; then
            if [ -f "$xe_path/min_freq" ] && [ -f "$xe_path/max_freq" ]; then
                echo "$min_mhz" | sudo tee "$xe_path/min_freq" > /dev/null 2>&1
                echo "$max_mhz" | sudo tee "$xe_path/max_freq" > /dev/null 2>&1
                if [ $? -eq 0 ]; then
                    echo "OK: GPU (Xe card${card_num}) frequency range set to $min_mhz-$max_mhz MHz"
                    return 0
                else
                    echo "ERROR: Failed to set GPU (Xe) frequency range"
                    return 1
                fi
            fi
        fi
        
        # Try legacy i915
        i915_path="/sys/class/drm/card${card_num}"
        if [ -f "$i915_path/gt_min_freq_mhz" ] && [ -f "$i915_path/gt_max_freq_mhz" ]; then
            echo "$min_mhz" | sudo tee "$i915_path/gt_min_freq_mhz" > /dev/null 2>&1
            echo "$max_mhz" | sudo tee "$i915_path/gt_max_freq_mhz" > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo "OK: GPU (i915 card${card_num}) frequency range set to $min_mhz-$max_mhz MHz"
                return 0
            else
                echo "ERROR: Failed to set GPU (i915) frequency range"
                return 1
            fi
        fi
    done
    
    echo "ERROR: No GPU frequency control found"
    return 1
}

# Get all information
get_all() {
    echo "CPU Count: $CPU_COUNT"
    
    echo -n "Available Governors: "
    get_cpu_governors
    
    echo -n "Current Governor: "
    get_cpu_governor
    
    echo -n "CPU Freq Range: "
    get_cpu_freq_range
    
    echo -n "GPU Freq Range: "
    get_gpu_freq_range
    
    echo -n "Current EPP: "
    get_cpu_epp
    
    echo -n "Available EPP: "
    get_available_epp
}

# Main command dispatcher
case "$1" in
    get_cpu_governors)
        get_cpu_governors
        ;;
    get_cpu_governor)
        get_cpu_governor
        ;;
    set_cpu_governor)
        set_cpu_governor "$2"
        ;;
    get_cpu_freq_range)
        get_cpu_freq_range
        ;;
    set_cpu_freq_range)
        set_cpu_freq_range "$2" "$3"
        ;;
    get_gpu_freq_range)
        get_gpu_freq_range
        ;;
    set_gpu_freq_range)
        set_gpu_freq_range "$2" "$3"
        ;;
    get_all)
        get_all
        ;;
    get_cpu_epp)
        get_cpu_epp
        ;;
    set_cpu_epp)
        set_cpu_epp "$2"
        ;;
    get_available_epp)
        get_available_epp
        ;;
    *)
        echo "ERROR: Unknown command: $1"
        echo "Available commands: get_cpu_governors, get_cpu_governor, set_cpu_governor, get_cpu_freq_range, set_cpu_freq_range, get_gpu_freq_range, set_gpu_freq_range, get_all"
        exit 1
        ;;
esac
