# System Monitor Tool# System Monitor Tool



A comprehensive Linux system monitoring dashboard for real-time CPU, GPU, NPU, and memory monitoring with frequency control.A unified Linux system monitoring dashboard for real-time CPU, GPU, NPU, and memory monitoring with frequency control.



![Python](https://img.shields.io/badge/python-3.8+-blue.svg)![Python](https://img.shields.io/badge/python-3.7+-blue.svg)

![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)

![License](https://img.shields.io/badge/license-MIT-green.svg)![License](https://img.shields.io/badge/license-MIT-green.svg)



[中文说明](README_zh.md)## Features



## Features**All-in-One Dashboard** - Single PyQt5 interface showing:

- 📊 CPU usage, frequency, temperature (per-core)

### 🖥️ Real-time Monitoring- 🎮 GPU monitoring (Intel/NVIDIA/AMD)

- **CPU Monitoring**- 🧠 NPU monitoring (Intel Meteor Lake+)

  - Overall and per-core utilization- 💾 Memory & swap usage

  - Real-time frequency monitoring- ⚙️ CPU frequency & governor control

  - Temperature monitoring (multiple sensors support)- 📈 Real-time charts with historical data logging

  - CPU statistics (context switches, interrupts)

## Quick Start

- **GPU Monitoring**

  - NVIDIA GPU support (via pynvml)### 1. Install

  - AMD GPU support (via rocm-smi)```bash

  - Intel GPU support (i915/Xe drivers)./scripts/install.sh

  - GPU utilization, temperature, memory```

  - Clock speed monitoring

  - Dual-axis plots (usage + frequency)The script installs all dependencies and creates a launcher.



- **NPU Monitoring**### 2. Run

  - Intel NPU support (Meteor Lake+)```bash

  - RockChip, Qualcomm, MediaTek platform support./monitor-tool

  - Utilization and frequency tracking```

  - Dual-axis real-time visualization

Or search "System Monitor Tool" in your application menu.

- **Memory Monitoring**

  - RAM usage with detailed breakdownThat's it! The dashboard will open showing all monitoring data in one window.

  - Swap usage tracking

  - Historical trends## System Requirements



### ⚙️ Frequency Control- **OS**: Ubuntu 18.04+ or Debian-based Linux

- CPU Governor control (Performance, Powersave, Ondemand)- **Python**: 3.7+

- Min/Max frequency adjustment- **Hardware**: Intel/NVIDIA/AMD GPU (optional), Intel NPU (Meteor Lake+, optional)

- Quick performance presets

## Dashboard Layout

### 📊 Data Recording & Export

- SQLite database storageThe unified dashboard displays:

- Automatic data retention management (7 days default)

- Export formats: CSV, JSON, HTML```

- Interactive HTML reports with 13+ charts┌─────────────────────────────────────────────────────┐

- Zoom, pan, and filter capabilities│  Overview Tab                                       │

│  ├─ CPU Usage Chart                                 │

### 🎨 User Interface│  ├─ Memory Usage Chart                              │

- PyQt5 graphical interface│  └─ System Info Summary                             │

- High-performance real-time charts (pyqtgraph)│                                                      │

- Multi-tab layout│  CPU Tab                                            │

- Dark theme│  ├─ Per-core usage                                  │

- Color-coded dual-axis legends│  ├─ Frequency & Temperature                         │

- Low system overhead│  └─ Real-time frequency chart                       │

│                                                      │

## Quick Start│  Memory Tab                                         │

│  ├─ RAM & Swap usage                                │

### 1. Install│  └─ Usage history chart                             │

```bash│                                                      │

git clone https://github.com/TsaiGaggery/monitor-tool.git│  GPU Tab (if detected)                              │

cd monitor-tool│  ├─ GPU usage, temp, memory                         │

./scripts/install.sh│  └─ Clock speed chart                               │

```│                                                      │

│  NPU Tab (if detected)                              │

The script will:│  ├─ NPU utilization                                 │

- Install system dependencies│  └─ Frequency monitoring                            │

- Create Python virtual environment│                                                      │

- Install required packages│  Control Panel (sidebar)                            │

- Create desktop launcher│  ├─ CPU Governor selector                           │

- (Optional) Configure sudoers for frequency control│  ├─ Frequency range control                         │

│  └─ Performance presets                             │

### 2. Run└─────────────────────────────────────────────────────┘

```bash```

./monitor-tool

```## Configuration



Or search "System Monitor Tool" in your application menu.Edit `config/default.yaml` to customize:

- Update interval (default: 1000ms)

## Installation Methods- Chart display points (default: 60)

- Data retention (default: 7 days)

### Method 1: Installation Script (Recommended)

```bash## Advanced Usage

./scripts/install.sh

```### Frequency Control (requires sudo)

The installer can configure passwordless sudo for frequency control.

### Method 2: Build Debian PackageDuring installation, select "yes" when prompted.

```bash

# Install build dependencies### Data Export

sudo apt-get install devscripts debhelper dh-python python3-allMonitoring data is stored in `~/.monitor-tool/monitor_data.db`

```bash

# Build the packagesqlite3 ~/.monitor-tool/monitor_data.db "SELECT * FROM monitoring_data LIMIT 10;"

dpkg-buildpackage -us -uc -b```



# Install### Manual Installation

sudo dpkg -i ../monitor-tool_1.1.0_all.deb```bash

sudo apt-get install -f  # Fix dependencies if neededsudo apt-get install python3 python3-pip python3-pyqt5

```python3 -m venv venv

source venv/bin/activate

The Debian package includes:pip install -r requirements.txt

- All source files in `/usr/share/monitor-tool/`python src/main.py

- Launcher script in `/usr/bin/monitor-tool````

- Desktop entry for application menu

- Automatic dependency management### Build Debian Package

```bash

### Method 3: Manual Installation./scripts/build-deb.sh

```bashsudo dpkg -i ../monitor-tool_*.deb

# Install system dependencies```

sudo apt-get install python3 python3-pip python3-pyqt5

## Troubleshooting

# Create virtual environment

python3 -m venv venv**"could not connect to display" error?**

source venv/bin/activateThis means you're not in a graphical environment. Try:

```bash

# Install Python dependencies# If on local machine, ensure you're in a graphical session

pip install -r requirements.txt# Switch to GUI: Ctrl+Alt+F7 or Ctrl+Alt+F1



# Run# If using SSH, enable X forwarding

python src/main.pyssh -X user@hostname

```./monitor-tool



## System Requirements# Or set DISPLAY manually

DISPLAY=:0 ./monitor-tool

- **OS**: Ubuntu 18.04+ or Debian-based Linux

- **Python**: 3.8+# Alternative: Use systemd user service (see below)

- **Hardware**: ```

  - Intel/NVIDIA/AMD GPU (optional)

  - Intel NPU (Meteor Lake+, optional)**GPU not showing?**

```bash

## Dashboard Layout# Intel GPU

lspci | grep -i vga

```ls -l /sys/class/drm/card0

┌─────────────────────────────────────────────────────┐sudo apt install intel-gpu-tools  # Optional: provides intel_gpu_top

│  Overview Tab                                       │

│  ├─ CPU Usage Chart                                 │# NVIDIA GPU

│  ├─ Memory Usage Chart                              │lspci | grep -i nvidia

│  └─ System Info Summary                             │nvidia-smi  # Requires NVIDIA drivers

│                                                      │

│  CPU Tab                                            │# AMD GPU

│  ├─ Per-core usage (first 4 visible by default)     │rocm-smi

│  ├─ Frequency & Temperature                         │```

│  └─ Real-time charts                                │

│                                                      │**GPU usage shows 0%?**

│  Memory Tab                                         │

│  ├─ RAM & Swap usage                                │This is normal when GPU is idle. GPU usage monitoring varies by hardware:

│  └─ Historical trends                               │

│                                                      │- **Intel Xe GPU**: Estimated from frequency (act_freq). Usage increases when running graphics applications

│  GPU Tab (if detected)                              │- **Intel i915 GPU**: Requires `intel_gpu_top` (sudo access)

│  ├─ Usage & Frequency (dual-axis)                   │- **NVIDIA GPU**: Requires NVIDIA drivers installed

│  ├─ Temperature & Power                             │  ```bash

│  └─ Memory utilization                              │  sudo apt install nvidia-driver-550  # Or recommended version

│                                                      │  sudo reboot

│  NPU Tab (if detected)                              │  ```

│  ├─ Utilization & Frequency (dual-axis)             │- **AMD GPU**: Requires ROCm drivers

│  └─ Memory usage                                    │

│                                                      │To test GPU monitoring, run a graphics workload:

│  Control Panel (sidebar)                            │```bash

│  ├─ CPU Governor selector                           │# Simple GPU load test

│  ├─ Frequency range control                         │sudo apt install mesa-utils

│  └─ Performance presets                             │glxgears  # Watch GPU usage increase in dashboard

└─────────────────────────────────────────────────────┘```

```

**NPU not detected?**

## Configuration```bash

# Intel NPU (Meteor Lake+, requires kernel 6.2+)

Edit `config/default.yaml` to customize:lspci | grep -i vpu

- Update interval (default: 1000ms)ls -l /sys/class/accel/accel0

- Chart display points (default: 60)```

- Data retention (default: 7 days)

- Low overhead mode**Frequency control not working?**

- Re-run `./scripts/install.sh` and select sudoers configuration

## Advanced Usage- Or run with sudo: `sudo ./monitor-tool` (not recommended)



### Frequency Control (requires sudo)**Reduce system overhead?**

During installation, select "yes" for sudoers configuration to enable passwordless frequency control.- Edit `config/default.yaml`, increase `update_interval` to 2000ms



### Data Export## Running as Systemd User Service (Optional)

Export monitoring data via menu: **File → Export Data**

- **CSV**: For spreadsheet analysisFor automatic startup with graphical session:

- **JSON**: For programmatic access

- **HTML**: Interactive charts with zoom/pan```bash

- **Export All (Ctrl+E)**: All formats at once# Create service file

mkdir -p ~/.config/systemd/user/

Exported files include:cat > ~/.config/systemd/user/monitor-tool.service << EOF

- All monitoring metrics[Unit]

- Real timestamps (not seconds)Description=System Monitor Tool

- Per-core CPU dataAfter=graphical-session.target

- GPU temperature, power, frequency

- Memory details (used/available)[Service]

- NPU metrics (if available)Type=simple

ExecStart=/home/$USER/monitor-tool/monitor-tool

Data location: `~/.monitor-tool/monitor_data.db`Restart=on-failure



### Query Historical Data[Install]

```bashWantedBy=default.target

sqlite3 ~/.monitor-tool/monitor_data.db "SELECT * FROM monitoring_data ORDER BY timestamp DESC LIMIT 10;"EOF

```

# Enable and start

## Troubleshootingsystemctl --user daemon-reload

systemctl --user enable monitor-tool

### "could not connect to display" error?systemctl --user start monitor-tool

```bash```

# On local machine - ensure graphical session

# Switch to GUI: Ctrl+Alt+F7## Uninstall

```bash

# Via SSH - enable X forwarding./scripts/uninstall.sh

ssh -X user@hostname```

./monitor-tool

## Platform Support

# Or set DISPLAY

DISPLAY=:0 ./monitor-tool| Component | Intel | NVIDIA | AMD | ARM |

```|-----------|-------|--------|-----|-----|

| CPU | ✅ | ✅ | ✅ | ✅ |

### GPU not showing?| GPU | ✅ | ✅ | ✅ | ✅ |

```bash| NPU | ✅ (Meteor Lake+) | ❌ | ❌ | 🟡 (Platform-specific) |

# Check GPU detection| Frequency Control | ✅ | ❌ | ❌ | 🟡 |

lspci | grep -i vga

## License & Contributing

# Intel GPU

ls -l /sys/class/drm/card*MIT License - Issues and PRs welcome!

sudo apt install intel-gpu-tools  # Optional

**Author**: TsaiGaggery  

# NVIDIA GPU**Version**: 1.0.0

nvidia-smi

sudo apt install nvidia-driver-550  # If missing

## Key Features

# AMD GPU

rocm-smi### 🖥️ Real-time Monitoring

```- **CPU Monitoring**

  - Overall and per-core utilization

### GPU usage shows 0%?  - Real-time frequency monitoring

This is normal when GPU is idle. Test with:  - Temperature monitoring (supports multiple sensors)

```bash  - CPU statistics (context switches, interrupts, etc.)

sudo apt install mesa-utils

glxgears  # Watch GPU usage increase- **GPU Monitoring**

```  - NVIDIA GPU support (via pynvml)

  - AMD GPU support (via rocm-smi)

GPU monitoring varies by hardware:  - Intel GPU support (i915/Xe drivers)

- **Intel Xe GPU**: Uses actual frequency (act_freq), 0 when idle  - GPU utilization, temperature, memory

- **Intel i915 GPU**: Requires `intel_gpu_top` (sudo)  - Clock speed monitoring

- **NVIDIA GPU**: Requires NVIDIA drivers  - Dual-axis plots (usage + frequency)

- **AMD GPU**: Requires ROCm drivers

- **NPU Monitoring**

### NPU not detected?  - Intel NPU support (Meteor Lake+)

```bash  - RockChip NPU support

# Check NPU hardware (Intel Meteor Lake+, kernel 6.2+)  - Qualcomm, MediaTek, Amlogic platform support

lspci | grep -i vpu  - Generic NPU interface

ls -l /sys/class/accel/accel0  - Utilization and frequency tracking

```

- **Memory Monitoring**

### Frequency control not working?  - RAM usage

- Re-run `./scripts/install.sh` and select sudoers configuration  - Swap usage

- Or run with sudo: `sudo ./monitor-tool` (not recommended for GUI)  - Detailed memory allocation information



### Reduce system overhead?### ⚙️ Frequency Control

Edit `config/default.yaml`:- CPU Governor control

```yaml  - Performance, Powersave, Ondemand modes

update_interval: 2000  # Increase to 2 seconds  - Real-time switching

```- CPU frequency range settings

  - Min/Max frequency adjustment

## Project Structure  - Quick preset modes



```### 📊 Data Recording

monitor-tool/- SQLite database storage

├── src/- Historical data queries

│   ├── monitors/           # Monitoring modules- Statistical analysis

│   │   ├── cpu_monitor.py- Automatic old data cleanup

│   │   ├── gpu_monitor.py- Export to CSV/JSON/HTML formats

│   │   ├── npu_monitor.py- Interactive HTML charts with zoom/pan

│   │   └── memory_monitor.py

│   ├── controllers/        # Control modules### 🎨 User Interface

│   │   └── freq_controller.py- PyQt5 graphical interface

│   ├── ui/                # UI modules- Real-time chart display (pyqtgraph)

│   │   ├── main_window.py- Multi-tab design

│   │   ├── widgets/- Low overhead display

│   │   └── styles/- Dark theme

│   ├── storage/           # Data storage- Color-coded legends for dual-axis plots

│   │   ├── data_logger.py

│   │   └── data_exporter.py## System Requirements

│   └── main.py           # Main entry

├── scripts/              # Installation/build scripts- **Operating System**: Ubuntu 18.04+ or other Debian-based Linux

│   ├── install.sh- **Python**: 3.7+

│   ├── uninstall.sh- **Dependencies**:

│   └── build-deb.sh  - PyQt5 >= 5.15

├── debian/              # Debian packaging  - pyqtgraph >= 0.12

│   ├── control  - psutil >= 5.8

│   ├── rules  - pynvml >= 11.5.0 (for NVIDIA GPU support)

│   ├── changelog

│   └── postinst## Installation Methods

├── config/              # Configuration

│   └── default.yaml### Method 1: Using Installation Script (Recommended)

├── requirements.txt     # Python dependencies

├── setup.py            # Python package setup```bash

├── monitor-tool        # Launcher scriptgit clone https://github.com/TsaiGaggery/monitor-tool.git

└── README.mdcd monitor-tool

```./scripts/install.sh

```

## Platform Support

The installation script will:

| Component | Intel | NVIDIA | AMD | ARM |1. Check and install system dependencies

|-----------|-------|--------|-----|-----|2. Create Python virtual environment

| CPU | ✅ | ✅ | ✅ | ✅ |3. Install required Python packages

| GPU | ✅ | ✅ | ✅ | ✅ |4. Create desktop launcher

| NPU | ✅ (Meteor Lake+) | ❌ | ❌ | 🟡 |5. (Optional) Configure sudoers for frequency control

| Freq Control | ✅ | ❌ | ❌ | 🟡 |

### Method 2: Build Debian Package

## Uninstall

```bash

```bash./scripts/build-deb.sh

# If installed via scriptsudo dpkg -i ../monitor-tool_*.deb

./scripts/uninstall.sh# Fix dependencies if needed

sudo apt-get install -f

# If installed via Debian package```

sudo apt-get remove monitor-tool

```### Method 3: Manual Installation



## License```bash

# Install system dependencies

MIT License - See `debian/copyright` for detailssudo apt-get install python3 python3-pip python3-pyqt5



## Contributing# Create virtual environment

python3 -m venv venv

Issues and Pull Requests are welcome!source venv/bin/activate



## Author# Install Python dependencies

pip install -r requirements.txt

**TsaiGaggery**

# Run

## Changelogpython src/main.py

```

### v1.1.0 (2025-11-15)

- Add Debian package support## Usage

- Add dual-axis real-time plots (usage + frequency)

- Fix GPU frequency reading (always use actual frequency)### Starting the Application

- Add color-coded legends for dual-axis charts

- Translate all documentation to English```bash

- Export all formats feature (Ctrl+E)# Using the launcher script

- Comprehensive HTML reports with 13+ interactive charts./monitor-tool



### v1.0.0 (2024-11-14)# Or search for "System Monitor Tool" in application menu

- Initial release

- CPU/GPU/NPU/Memory monitoring# Or run directly

- Frequency controlsource venv/bin/activate

- Data logging and exportpython src/main.py

- PyQt5 GUI with real-time charts```


### Frequency Control

Frequency control requires root privileges. Options:

1. **Configure sudoers (Recommended)**: Select sudoers configuration during installation
2. **Run with sudo**: `sudo ./monitor-tool` (not recommended for GUI applications)
3. **Read-only mode**: Use without frequency control features

### Monitoring Data

- Database location: `~/.monitor-tool/monitor_data.db`
- Default retention: 7 days of historical data
- Manual cleanup via menu: "Tools → Cleanup Old Data"
- Export via menu: "File → Export Data" (CSV, JSON, HTML)

## Project Structure

```
monitor-tool/
│   ├── monitors/           # Monitoring modules
│   │   ├── cpu_monitor.py
│   │   ├── gpu_monitor.py
│   │   ├── npu_monitor.py
│   │   └── memory_monitor.py
│   ├── controllers/        # Control modules
│   │   └── frequency_controller.py
│   ├── ui/                # UI modules
│   │   ├── main_window.py
│   │   └── widgets/
│   ├── storage/           # Data storage
│   │   └── data_logger.py
│   └── main.py           # Main entry point
├── scripts/              # Installation/build scripts
│   ├── install.sh
│   ├── uninstall.sh
│   └── build-deb.sh
├── debian/              # Debian packaging files
│   ├── control
│   ├── rules
│   └── postinst
├── config/              # Configuration files
│   └── default.yaml
├── requirements.txt     # Python dependencies
├── monitor-tool        # Launcher script
└── README.md
```

## Configuration

Configuration file is located at `config/default.yaml`, where you can adjust:

- Update interval
- Data logging settings
- Chart display points
- UI theme
- Module enable/disable switches

## Uninstallation

```bash
./scripts/uninstall.sh
```

Or if installed via Debian package:

```bash
sudo apt-get remove monitor-tool
```

## Frequently Asked Questions

### Q: Why don't I see GPU information?
A: Ensure the corresponding GPU tools are installed:
- NVIDIA: `nvidia-smi`, drivers, `pynvml`
- AMD: `rocm-smi`
- Intel: Kernel support for i915/Xe drivers

### Q: Frequency control doesn't work?
A: Root privileges are required. Run `./scripts/install.sh` and select sudoers configuration, or run the program with sudo.

### Q: NPU monitoring shows unavailable?
A: NPU monitoring depends on hardware platform and driver support. Currently supports RockChip, Qualcomm, MediaTek, and Intel (Meteor Lake+) platforms.

### Q: How to reduce system overhead?
A: You can adjust in the configuration file:
- Increase `update_interval` (e.g., change to 2000ms)
- Reduce `max_points`
- Enable `low_overhead_mode`

## Technical Features

- **Low overhead design**: Minimal system impact
- **Modular architecture**: Easy to extend and maintain
- **Cross-platform support**: Supports multiple GPU/NPU platforms
- **Real-time visualization**: High-performance charts using pyqtgraph
- **Data persistence**: SQLite storage for historical data
- **Comprehensive exports**: Interactive HTML reports with 13+ charts
- **Dual-axis plots**: Visualize usage and frequency together

## License

MIT License - See `debian/copyright` for details

## Contributing

Issues and Pull Requests are welcome!

## Author

TsaiGaggery

## Changelog

### v1.0.0
- Initial release
- CPU/GPU/NPU/Memory monitoring
- Frequency control
- Data logging
- Export to CSV/JSON/HTML
- Dual-axis real-time plots


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
