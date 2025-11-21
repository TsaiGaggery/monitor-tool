#!/system/bin/sh
# Android Frequency Controller
# Control CPU governor and frequency, GPU frequency via ADB
# Usage: sh android_freq_controller.sh [command] [args...]

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

# Set CPU governor for all cores
set_cpu_governor() {
    governor=$1
    
    if [ -z "$governor" ]; then
        echo "Error: Governor not specified"
        return 1
    fi
    
    for i in $(seq 0 $((CPU_COUNT - 1))); do
        gov_path="/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_governor"
        if [ -f "$gov_path" ]; then
            echo "$governor" > "$gov_path" 2>/dev/null
            if [ $? -ne 0 ]; then
                echo "Error: Failed to set governor for CPU $i"
                return 1
            fi
        fi
    done
    
    echo "OK: Governor set to $governor"
    return 0
    echo "OK: Governor set to $governor"
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

# Set CPU EPP for all cores
set_cpu_epp() {
    epp=$1
    
    if [ -z "$epp" ]; then
        echo "Error: EPP preference not specified"
        return 1
    fi
    
    # Verify EPP is available
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences" ]; then
        available=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences)
        if ! echo "$available" | grep -q "$epp"; then
            echo "Error: EPP '$epp' not available. Available: $available"
            return 1
        fi
    fi
    
    for i in $(seq 0 $((CPU_COUNT - 1))); do
        epp_path="/sys/devices/system/cpu/cpu${i}/cpufreq/energy_performance_preference"
        if [ -f "$epp_path" ]; then
            echo "$epp" > "$epp_path" 2>/dev/null
            if [ $? -ne 0 ]; then
                echo "Error: Failed to set EPP for CPU $i"
                return 1
            fi
        fi
    done
    
    echo "OK: EPP set to $epp"
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

# Set CPU frequency range (in MHz)
set_cpu_freq_range() {
    min_mhz=$1
    max_mhz=$2
    
    if [ -z "$min_mhz" ] || [ -z "$max_mhz" ]; then
        echo "Error: Min and max frequency not specified"
        return 1
    fi
    
    # Convert MHz to kHz
    min_khz=$((min_mhz * 1000))
    max_khz=$((max_mhz * 1000))
    
    for i in $(seq 0 $((CPU_COUNT - 1))); do
        min_path="/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_min_freq"
        max_path="/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_max_freq"
        
        if [ -f "$min_path" ] && [ -f "$max_path" ]; then
            echo "$min_khz" > "$min_path" 2>/dev/null
            echo "$max_khz" > "$max_path" 2>/dev/null
            
            if [ $? -ne 0 ]; then
                echo "Error: Failed to set frequency for CPU $i"
                return 1
            fi
        fi
    done
    
    echo "OK: CPU frequency range set to $min_mhz-$max_mhz MHz"
    return 0
}

# Get GPU frequency range
get_gpu_freq_range() {
    # Try i915 driver
    for card in 0 1 2 3 4; do
        base="/sys/class/drm/card${card}"
        if [ -f "$base/gt_min_freq_mhz" ]; then
            hw_min=$(cat "$base/gt_RPn_freq_mhz" 2>/dev/null || echo "0")
            hw_max=$(cat "$base/gt_RP0_freq_mhz" 2>/dev/null || echo "0")
            scaling_min=$(cat "$base/gt_min_freq_mhz")
            scaling_max=$(cat "$base/gt_max_freq_mhz")
            current=$(cat "$base/gt_cur_freq_mhz")
            
            echo "TYPE:i915 HW_MIN:$hw_min HW_MAX:$hw_max SCALING_MIN:$scaling_min SCALING_MAX:$scaling_max CURRENT:$current"
            return 0
        fi
    done
    
    # Try Xe driver
    for card in 0 1 2 3 4; do
        base="/sys/class/drm/card${card}/device/tile0/gt0/freq0"
        if [ -f "$base/min_freq" ]; then
            hw_min=$(cat "$base/rpn_freq")
            hw_max=$(cat "$base/rp0_freq")
            scaling_min=$(cat "$base/min_freq")
            scaling_max=$(cat "$base/max_freq")
            current=$(cat "$base/act_freq")
            
            echo "TYPE:xe HW_MIN:$hw_min HW_MAX:$hw_max SCALING_MIN:$scaling_min SCALING_MAX:$scaling_max CURRENT:$current"
            return 0
        fi
    done
    
    echo "N/A"
}

# Set GPU frequency range (in MHz)
set_gpu_freq_range() {
    min_mhz=$1
    max_mhz=$2
    
    if [ -z "$min_mhz" ] || [ -z "$max_mhz" ]; then
        echo "Error: Min and max frequency not specified"
        return 1
    fi
    
    # Try i915 driver
    for card in 0 1 2 3 4; do
        base="/sys/class/drm/card${card}"
        if [ -f "$base/gt_min_freq_mhz" ]; then
            echo "$min_mhz" > "$base/gt_min_freq_mhz" 2>/dev/null
            echo "$max_mhz" > "$base/gt_max_freq_mhz" 2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo "OK: GPU frequency range set to $min_mhz-$max_mhz MHz (i915)"
                return 0
            else
                echo "Error: Failed to set GPU frequency (i915)"
                return 1
            fi
        fi
    done
    
    # Try Xe driver
    for card in 0 1 2 3 4; do
        base="/sys/class/drm/card${card}/device/tile0/gt0/freq0"
        if [ -f "$base/min_freq" ]; then
            echo "$min_mhz" > "$base/min_freq" 2>/dev/null
            echo "$max_mhz" > "$base/max_freq" 2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo "OK: GPU frequency range set to $min_mhz-$max_mhz MHz (xe)"
                return 0
            else
                echo "Error: Failed to set GPU frequency (xe)"
                return 1
            fi
        fi
    done
    
    echo "Error: GPU frequency control not available"
    return 1
}

# Get all frequency information
get_all() {
    echo "=== CPU Frequency Information ==="
    echo "CPU Count: $CPU_COUNT"
    echo "Available Governors: $(get_cpu_governors)"
    echo "Current Governor: $(get_cpu_governor)"
    echo "Frequency Range: $(get_cpu_freq_range)"
    echo ""
    echo "=== GPU Frequency Information ==="
    echo "GPU Frequency: $(get_gpu_freq_range)"
    echo "=== GPU Frequency Information ==="
    echo "GPU Frequency: $(get_gpu_freq_range)"
    echo ""
    echo "=== EPP Information ==="
    echo "Current EPP: $(get_cpu_epp)"
    echo "Available EPP: $(get_available_epp)"
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
        echo "Android Frequency Controller"
        echo "Usage: $0 [command] [args...]"
        echo ""
        echo "Commands:"
        echo "  get_cpu_governors           - List available CPU governors"
        echo "  get_cpu_governor            - Get current CPU governor"
        echo "  set_cpu_governor [gov]      - Set CPU governor (performance/powersave)"
        echo "  get_cpu_freq_range          - Get CPU frequency range"
        echo "  set_cpu_freq_range [min] [max] - Set CPU frequency range (MHz)"
        echo "  get_gpu_freq_range          - Get GPU frequency range"
        echo "  set_gpu_freq_range [min] [max] - Set GPU frequency range (MHz)"
        echo "  get_gpu_freq_range          - Get GPU frequency range"
        echo "  set_gpu_freq_range [min] [max] - Set GPU frequency range (MHz)"
        echo "  get_cpu_epp                 - Get current CPU EPP"
        echo "  set_cpu_epp [epp]           - Set CPU EPP"
        echo "  get_available_epp           - List available EPP modes"
        echo "  get_all                     - Get all frequency information"
        exit 1
        ;;
esac
