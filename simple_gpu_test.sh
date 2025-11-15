#!/bin/bash
# Simple GPU test with glxgears

echo "=== Simple GPU Test with glxgears ==="
echo ""

echo "Before test:"
ACT=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq)
echo "  act_freq: ${ACT} MHz (0 = GPU睡眠中)"
echo ""

echo "Starting glxgears (will run for 10 seconds)..."
echo "請保持 glxgears 視窗開啟且可見"
echo ""

# Start glxgears in background
DISPLAY=:0 glxgears > /dev/null 2>&1 &
GEARS_PID=$!

# Monitor GPU for 10 seconds
echo "監控 GPU 頻率 (每秒更新):"
for i in {1..10}; do
    sleep 1
    ACT=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq 2>/dev/null || echo "0")
    CUR=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq 2>/dev/null || echo "0")
    MIN=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/min_freq 2>/dev/null || echo "500")
    MAX=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/max_freq 2>/dev/null || echo "2500")
    
    # Calculate usage
    if [ "$ACT" -gt 0 ] && [ "$MAX" -gt "$MIN" ]; then
        USAGE=$(( (ACT - MIN) * 100 / (MAX - MIN) ))
    else
        USAGE=0
    fi
    
    echo "[${i}秒] act_freq: ${ACT} MHz, usage估計: ${USAGE}%"
done

# Kill glxgears
kill $GEARS_PID 2>/dev/null
wait $GEARS_PID 2>/dev/null

echo ""
echo "測試完成！"
echo ""
ACT=$(cat /sys/class/drm/card0/device/tile0/gt0/freq0/act_freq)
echo "After test:"
echo "  act_freq: ${ACT} MHz"
echo ""

if [ "$ACT" -eq 0 ]; then
    echo "⚠️  GPU 仍然是 0 MHz，可能原因："
    echo "  1. glxgears 使用軟體渲染（llvmpipe）"
    echo "  2. 需要圖形界面（X11/Wayland）正在運行"
    echo "  3. 需要安裝 mesa-utils 和正確的 GPU 驅動"
    echo ""
    echo "解決方法："
    echo "  1. 確認有圖形界面登入"
    echo "  2. 在圖形界面的終端機執行此腳本"
    echo "  3. 或安裝 glmark2: sudo apt install glmark2"
else
    echo "✓ GPU 有被使用！檢查 monitor-tool 應該能看到使用率 > 0%"
fi
