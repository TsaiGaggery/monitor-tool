# System Monitor Tool

A unified Linux system monitoring dashboard for real-time CPU, GPU, NPU, and memory monitoring with frequency control.

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

**All-in-One Dashboard** - Single PyQt5 interface showing:
- 📊 CPU usage, frequency, temperature (per-core)
- 🎮 GPU monitoring (Intel/NVIDIA/AMD)
- 🧠 NPU monitoring (Intel Meteor Lake+)
- 💾 Memory & swap usage
- ⚙️ CPU frequency & governor control
- 📈 Real-time charts with historical data logging

## Quick Start

### 1. Install
```bash
./scripts/install.sh
```

The script installs all dependencies and creates a launcher.

### 2. Run
```bash
./monitor-tool
```

Or search "System Monitor Tool" in your application menu.

That's it! The dashboard will open showing all monitoring data in one window.

## System Requirements

- **OS**: Ubuntu 18.04+ or Debian-based Linux
- **Python**: 3.7+
- **Hardware**: Intel/NVIDIA/AMD GPU (optional), Intel NPU (Meteor Lake+, optional)

## Dashboard Layout

The unified dashboard displays:

```
┌─────────────────────────────────────────────────────┐
│  Overview Tab                                       │
│  ├─ CPU Usage Chart                                 │
│  ├─ Memory Usage Chart                              │
│  └─ System Info Summary                             │
│                                                      │
│  CPU Tab                                            │
│  ├─ Per-core usage                                  │
│  ├─ Frequency & Temperature                         │
│  └─ Real-time frequency chart                       │
│                                                      │
│  Memory Tab                                         │
│  ├─ RAM & Swap usage                                │
│  └─ Usage history chart                             │
│                                                      │
│  GPU Tab (if detected)                              │
│  ├─ GPU usage, temp, memory                         │
│  └─ Clock speed chart                               │
│                                                      │
│  NPU Tab (if detected)                              │
│  ├─ NPU utilization                                 │
│  └─ Frequency monitoring                            │
│                                                      │
│  Control Panel (sidebar)                            │
│  ├─ CPU Governor selector                           │
│  ├─ Frequency range control                         │
│  └─ Performance presets                             │
└─────────────────────────────────────────────────────┘
```

## Configuration

Edit `config/default.yaml` to customize:
- Update interval (default: 1000ms)
- Chart display points (default: 60)
- Data retention (default: 7 days)

## Advanced Usage

### Frequency Control (requires sudo)
The installer can configure passwordless sudo for frequency control.
During installation, select "yes" when prompted.

### Data Export
Monitoring data is stored in `~/.monitor-tool/monitor_data.db`
```bash
sqlite3 ~/.monitor-tool/monitor_data.db "SELECT * FROM monitoring_data LIMIT 10;"
```

### Manual Installation
```bash
sudo apt-get install python3 python3-pip python3-pyqt5
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Build Debian Package
```bash
./scripts/build-deb.sh
sudo dpkg -i ../monitor-tool_*.deb
```

## Troubleshooting

**"could not connect to display" error?**
This means you're not in a graphical environment. Try:
```bash
# If on local machine, ensure you're in a graphical session
# Switch to GUI: Ctrl+Alt+F7 or Ctrl+Alt+F1

# If using SSH, enable X forwarding
ssh -X user@hostname
./monitor-tool

# Or set DISPLAY manually
DISPLAY=:0 ./monitor-tool

# Alternative: Use systemd user service (see below)
```

**GPU not showing?**
```bash
# Intel GPU
lspci | grep -i vga
ls -l /sys/class/drm/card0
sudo apt install intel-gpu-tools  # Optional: provides intel_gpu_top

# NVIDIA GPU
lspci | grep -i nvidia
nvidia-smi  # Requires NVIDIA drivers

# AMD GPU
rocm-smi
```

**GPU usage shows 0%?**

This is normal when GPU is idle. GPU usage monitoring varies by hardware:

- **Intel Xe GPU**: Estimated from frequency (act_freq). Usage increases when running graphics applications
- **Intel i915 GPU**: Requires `intel_gpu_top` (sudo access)
- **NVIDIA GPU**: Requires NVIDIA drivers installed
  ```bash
  sudo apt install nvidia-driver-550  # Or recommended version
  sudo reboot
  ```
- **AMD GPU**: Requires ROCm drivers

To test GPU monitoring, run a graphics workload:
```bash
# Simple GPU load test
sudo apt install mesa-utils
glxgears  # Watch GPU usage increase in dashboard
```

**NPU not detected?**
```bash
# Intel NPU (Meteor Lake+, requires kernel 6.2+)
lspci | grep -i vpu
ls -l /sys/class/accel/accel0
```

**Frequency control not working?**
- Re-run `./scripts/install.sh` and select sudoers configuration
- Or run with sudo: `sudo ./monitor-tool` (not recommended)

**Reduce system overhead?**
- Edit `config/default.yaml`, increase `update_interval` to 2000ms

## Running as Systemd User Service (Optional)

For automatic startup with graphical session:

```bash
# Create service file
mkdir -p ~/.config/systemd/user/
cat > ~/.config/systemd/user/monitor-tool.service << EOF
[Unit]
Description=System Monitor Tool
After=graphical-session.target

[Service]
Type=simple
ExecStart=/home/$USER/monitor-tool/monitor-tool
Restart=on-failure

[Install]
WantedBy=default.target
EOF

# Enable and start
systemctl --user daemon-reload
systemctl --user enable monitor-tool
systemctl --user start monitor-tool
```

## Uninstall
```bash
./scripts/uninstall.sh
```

## Platform Support

| Component | Intel | NVIDIA | AMD | ARM |
|-----------|-------|--------|-----|-----|
| CPU | ✅ | ✅ | ✅ | ✅ |
| GPU | ✅ | ✅ | ✅ | ✅ |
| NPU | ✅ (Meteor Lake+) | ❌ | ❌ | 🟡 (Platform-specific) |
| Frequency Control | ✅ | ❌ | ❌ | 🟡 |

## License & Contributing

MIT License - Issues and PRs welcome!

**Author**: TsaiGaggery  
**Version**: 1.0.0

## 主要功能

### 🖥️ 即時監控
- **CPU 監控**
  - 整體和各核心使用率
  - 即時頻率監控
  - 溫度監測（支援多種感測器）
  - CPU 統計資訊（上下文切換、中斷等）

- **GPU 監控**
  - NVIDIA GPU 支援（透過 pynvml）
  - AMD GPU 支援（透過 rocm-smi）
  - GPU 使用率、溫度、記憶體
  - 時脈速度監控

- **NPU 監控**
  - RockChip NPU 支援
  - Qualcomm、MediaTek、Amlogic 平台支援
  - 通用 NPU 介面

- **記憶體監控**
  - RAM 使用情況
  - Swap 使用情況
  - 詳細的記憶體分配資訊

### ⚙️ 頻率控制
- CPU 調速器（Governor）控制
  - Performance、Powersave、Ondemand 等模式
  - 即時切換
- CPU 頻率範圍設定
  - 最小/最大頻率調整
  - 快速預設模式

### 📊 資料記錄
- SQLite 資料庫儲存
- 歷史資料查詢
- 統計分析
- 自動清理舊資料

### 🎨 使用者介面
- PyQt5 圖形化介面
- 即時圖表顯示（pyqtgraph）
- 多分頁設計
- 低開銷顯示

## 系統需求

- **作業系統**: Ubuntu 18.04+ 或其他 Debian 系 Linux
- **Python**: 3.7+
- **依賴套件**:
  - PyQt5 >= 5.15.0
  - pyqtgraph >= 0.13.0
  - psutil >= 5.9.0
  - numpy >= 1.21.0
  - pynvml >= 11.5.0 (NVIDIA GPU 支援)

## 安裝方式

### 方法 1: 使用安裝腳本（推薦）

```bash
cd monitor-tool
./scripts/install.sh
```

安裝腳本會：
1. 檢查並安裝系統依賴
2. 建立 Python 虛擬環境
3. 安裝所需的 Python 套件
4. 建立桌面啟動項目
5. （可選）配置 sudoers 以便頻率控制

### 方法 2: 建立 Debian 套件

```bash
cd monitor-tool
./scripts/build-deb.sh

# 安裝套件
sudo dpkg -i ../monitor-tool_*.deb
sudo apt-get install -f  # 修復依賴問題
```

### 方法 3: 手動安裝

```bash
# 安裝系統依賴
sudo apt-get update
sudo apt-get install python3 python3-pip python3-pyqt5

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝 Python 依賴
pip install -r requirements.txt

# 執行
python src/main.py
```

## 使用方式

### 啟動應用程式

```bash
# 使用啟動腳本
./monitor-tool

# 或從應用程式選單搜尋 "System Monitor Tool"

# 或直接執行
source venv/bin/activate
python src/main.py
```

### 頻率控制

頻率控制功能需要 root 權限。有以下選項：

1. **配置 sudoers（推薦）**：安裝時選擇設定 sudoers 配置
2. **使用 sudo 執行**：`sudo ./monitor-tool`（不推薦用於 GUI 應用程式）
3. **唯讀模式**：不使用頻率控制功能

### 監控資料

- 資料庫位置：`~/.monitor-tool/monitor_data.db`
- 預設保留 7 天歷史資料
- 可透過選單 "Tools → Cleanup Old Data" 手動清理

## 專案結構

```
monitor-tool/
├── src/
│   ├── monitors/           # 監控模組
│   │   ├── cpu_monitor.py
│   │   ├── gpu_monitor.py
│   │   ├── memory_monitor.py
│   │   └── npu_monitor.py
│   ├── controllers/        # 控制模組
│   │   └── freq_controller.py
│   ├── ui/                # UI 模組
│   │   ├── main_window.py
│   │   └── widgets/
│   ├── storage/           # 資料儲存
│   │   └── data_logger.py
│   └── main.py           # 主程式入口
├── scripts/              # 安裝/建置腳本
│   ├── install.sh
│   ├── uninstall.sh
│   └── build-deb.sh
├── debian/              # Debian 打包文件
│   ├── control
│   ├── rules
│   └── ...
├── config/              # 配置文件
│   └── default.yaml
├── requirements.txt     # Python 依賴
└── README.md
```

## 配置

配置文件位於 `config/default.yaml`，可以調整：

- 更新間隔
- 資料記錄設定
- 圖表顯示點數
- UI 主題
- 監控模組開關

## 卸載

```bash
./scripts/uninstall.sh
```

或如果是使用 Debian 套件安裝：

```bash
sudo apt-get remove monitor-tool
```

## 常見問題

### Q: 為什麼看不到 GPU 資訊？
A: 確保已安裝對應的 GPU 工具：
- NVIDIA: `nvidia-smi`
- AMD: `rocm-smi`

### Q: 頻率控制無法使用？
A: 需要 root 權限。執行 `./scripts/install.sh` 時選擇配置 sudoers，或使用 sudo 執行程式。

### Q: NPU 監控顯示不可用？
A: NPU 監控取決於硬體平台和驅動支援。目前支援 RockChip、Qualcomm、MediaTek 等平台。

### Q: 如何降低系統開銷？
A: 可以在配置文件中：
- 增加 `update_interval`（例如改為 2000ms）
- 減少 `max_points`
- 啟用 `low_overhead_mode`

## 技術特點

- **低開銷設計**：最小化系統影響
- **模組化架構**：易於擴展和維護
- **跨平台支援**：支援多種 GPU/NPU 平台
- **即時視覺化**：使用 pyqtgraph 實現高效能圖表
- **資料持久化**：SQLite 儲存歷史資料

## 授權

MIT License - 詳見 `debian/copyright`

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 作者

TsaiGaggery

## 更新日誌

### v1.0.0 (2024-11-14)
- 初始版本
- CPU/GPU/NPU/Memory 監控
- 頻率控制
- 資料記錄
- PyQt5 GUI
Performance monitoring tool
