# System Monitor Tool

A unified system monitoring tool for Linux and Android devices with real-time CPU, GPU, memory, network, and disk I/O monitoring plus frequency control.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Android-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

[中文說明](README_zh.md)

## Features

### 🖥️ **Dual Mode Support**
- **Local Mode**: Monitor Ubuntu/Linux system
- **Android Mode**: Remote monitor Android devices via ADB

### 📊 **Comprehensive Monitoring**
- CPU usage, frequency, temperature (per-core)
- GPU utilization & memory (Intel i915/Xe, NVIDIA, AMD)
- NPU monitoring (Intel Meteor Lake+)
- Memory & swap usage
- Network traffic & speed monitoring
- Disk I/O & partition usage
- Real-time charts with historical data

### ⚙️ **Frequency Control**
- CPU governor control (performance/powersave)
- CPU frequency range adjustment
- GPU frequency control
- **Works on both Ubuntu and Android (requires root)**

### 💾 **Data Export**
- SQLite database logging
- HTML report generation
- CSV export support

## Quick Start

### Local Mode (Ubuntu/Linux)

```bash
# Install
./scripts/install.sh

# Run
./monitor-tool
```

Or search "System Monitor Tool" in your application menu.

### Android Mode

```bash
# 1. Enable ADB on Android device and connect via WiFi/USB
# 2. Run monitor
python3 src/main.py --adb --ip <ANDROID_IP>

# Example
python3 src/main.py --adb --ip 192.168.1.68
```

**Requirements for Android**:
- ADB enabled on Android device
- Root access (su) for frequency control (optional)

## System Requirements

### Local Mode
- **OS**: Ubuntu 18.04+ or Debian-based Linux
- **Python**: 3.8+
- **Hardware**: Intel/NVIDIA/AMD GPU (optional), Intel NPU (Meteor Lake+, optional)

### Android Mode
- **Host**: Ubuntu/Linux with ADB installed
- **Android**: Android x86/ARM device with ADB enabled
- **Network**: WiFi or USB connection
- **Root**: Required for frequency control (optional for monitoring)

## Dashboard Layout

The unified dashboard displays:

```
┌─────────────────────────────────────────────────────────┐
│  Overview Tab                                           │
│  ├─ Info Cards (CPU, Memory, GPU, Network, Disk)       │
│  ├─ CPU & Memory Usage Charts                          │
│  ├─ Network Speed Chart (Upload/Download)              │
│  ├─ Disk I/O Chart (Read/Write)                        │
│  └─ GPU & NPU Charts (if available)                    │
│                                                         │
│  CPU Tab                                                │
│  ├─ Per-core usage                                      │
│  ├─ Frequency & Temperature                             │
│  └─ Real-time frequency chart                           │
│                                                         │
│  Memory Tab                                             │
│  ├─ RAM & Swap usage                                    │
│  └─ Usage history chart                                 │
│                                                         │
│  GPU Tab (if detected)                                  │
│  ├─ GPU usage, temp, memory                             │
│  └─ Clock speed chart                                   │
│                                                         │
│  NPU Tab (if detected)                                  │
│  ├─ NPU utilization                                     │
│  └─ Frequency monitoring                                │
│                                                         │
│  Network Tab                                            │
│  ├─ Upload/Download speeds                              │
│  ├─ Active connections count                            │
│  └─ Real-time speed chart                               │
│                                                         │
│  Disk Tab                                               │
│  ├─ Read/Write speeds & IOPS                            │
│  ├─ Partition usage                                     │
│  └─ Real-time I/O chart                                 │
│                                                         │
│  Control Panel (sidebar)                                │
│  ├─ CPU Governor selector                               │
│  ├─ Frequency range control                             │
│  └─ Performance presets                                 │
└─────────────────────────────────────────────────────────┘
```

## Configuration

Edit `config/default.yaml` to customize:
- Update interval (default: 1000ms)
- Chart display points (default: 60)
- Data retention (default: 7 days)

## Advanced Usage

### CLI Mode (Headless/Server Environments)

For servers without GUI or remote SSH sessions, use the CLI version:

```bash
# Interactive dashboard (updates every second, like htop)
./monitor-tool-cli

# With CPU/GPU frequency control (press 'c' for CPU, 'g' for GPU)
./monitor-tool-cli

# Single snapshot in simple format (for scripts)
./monitor-tool-cli --once --format simple
# Output: CPU: 45.2% | Mem: 62.3% | GPU: 12% | Net: ↑0.5 ↓2.3 MB/s | Disk: R1.2 W0.8 MB/s

# JSON format for automation
./monitor-tool-cli --once --format json > status.json

# Run and export HTML when you press 'q' to exit
./monitor-tool-cli --export-format html --output report.html

# Run and export CSV on exit
./monitor-tool-cli -e csv

# Custom update interval
./monitor-tool-cli --interval 2.0
```

**CLI Features:**
- ✅ No GUI dependencies (works over SSH)
- ✅ Real-time text dashboard with curses
- ✅ CPU/GPU frequency control (press 'c'/'g')
- ✅ Multiple output formats (text, json, simple)
- ✅ Data logging to SQLite (always enabled)
- ✅ Export to CSV, JSON, HTML
- ✅ Configurable update interval
- ✅ Low resource usage
- ✅ Background threading - continuous logging even during menu navigation

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


## Key Features

### 🖥️ Real-time Monitoring
- **CPU Monitoring**
  - Overall and per-core utilization
  - Real-time frequency monitoring
  - Temperature monitoring (supports multiple sensors)
  - CPU statistics (context switches, interrupts, etc.)

- **GPU Monitoring**
  - NVIDIA GPU support (via pynvml)
  - AMD GPU support (via rocm-smi)
  - Intel GPU support (i915/Xe drivers)
  - GPU utilization, temperature, memory
  - Clock speed monitoring
  - Dual-axis plots (usage + frequency)

- **NPU Monitoring**
  - Intel NPU support (Meteor Lake+)
  - RockChip NPU support
  - Qualcomm, MediaTek, Amlogic platform support
  - Generic NPU interface
  - Utilization and frequency tracking

- **Memory Monitoring**
  - RAM usage
  - Swap usage
  - Detailed memory allocation information

### ⚙️ Frequency Control
- CPU Governor control
  - Performance, Powersave, Ondemand modes
  - Real-time switching
- CPU frequency range settings
  - Min/Max frequency adjustment
  - Quick preset modes

### 📊 Data Recording
- SQLite database storage
- Historical data queries
- Statistical analysis
- **Auto cleanup**: Old data (>3 days) automatically deleted on startup
- Export to CSV/JSON/HTML formats
- Interactive HTML charts with zoom/pan

### 🎨 User Interface
- PyQt5 graphical interface
- Real-time chart display (pyqtgraph)
- Multi-tab design
- Low overhead display
- Dark theme
- Color-coded legends for dual-axis plots

## System Requirements

- **Operating System**: Ubuntu 18.04+ or other Debian-based Linux
- **Python**: 3.7+
- **Dependencies**:
  - PyQt5 >= 5.15
  - pyqtgraph >= 0.12
  - psutil >= 5.8
  - pynvml >= 11.5.0 (for NVIDIA GPU support)

## Installation Methods

### Method 1: Using Installation Script (Recommended)

```bash
git clone https://github.com/TsaiGaggery/monitor-tool.git
cd monitor-tool
./scripts/install.sh
```

The installation script will:
1. Check and install system dependencies
2. Create Python virtual environment
3. Install required Python packages
4. Create desktop launcher
5. (Optional) Configure sudoers for frequency control

### Method 2: Build Debian Package

```bash
./scripts/build-deb.sh
sudo dpkg -i ../monitor-tool_*.deb
# Fix dependencies if needed
sudo apt-get install -f
```

### Method 3: Manual Installation

```bash
# Install system dependencies
sudo apt-get install python3 python3-pip python3-pyqt5

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run
python src/main.py
```

## Usage

### Starting the Application

```bash
# Using the launcher script
./monitor-tool

# Or search for "System Monitor Tool" in application menu

# Or run directly
source venv/bin/activate
python src/main.py
```

### Frequency Control

Frequency control requires root privileges. Options:

1. **Configure sudoers (Recommended)**: Select sudoers configuration during installation
2. **Run with sudo**: `sudo ./monitor-tool` (not recommended for GUI applications)
3. **Read-only mode**: Use without frequency control features

### Monitoring Data

- Database location: `~/.monitor-tool/monitor_data.db`
- **Auto cleanup**: Data older than 3 days automatically deleted on every startup
- Disk space automatically reclaimed after cleanup (VACUUM)
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

## Testing

The project includes a comprehensive test suite with 152 unit tests covering all monitoring modules.

### Running Tests

```bash
# Run all tests
pytest tests/unit/

# Run with coverage report
pytest tests/unit/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_cpu_monitor.py -v

# Run specific test class or function
pytest tests/unit/test_gpu_monitor.py::TestGPUMonitorDetection -v
pytest tests/unit/test_data_exporter.py::TestDataExporterHTML::test_export_html -v
```

### Test Coverage

Current coverage (monitors + storage modules, UI excluded):
- **Memory Monitor**: 100%
- **Network Monitor**: 96%
- **Disk Monitor**: 88%
- **Data Logger**: 87%
- **NPU Monitor**: 75%
- **Data Exporter**: 67%
- **CPU Monitor**: 59%
- **GPU Monitor**: 44%
- **Overall**: 40%

### Test Structure

```
tests/
├── unit/                    # Unit tests with mocked dependencies
│   ├── test_cpu_monitor.py
│   ├── test_gpu_monitor.py
│   ├── test_npu_monitor.py
│   ├── test_memory_monitor.py
│   ├── test_network_monitor.py
│   ├── test_disk_monitor.py
│   ├── test_data_logger.py
│   └── test_data_exporter.py
├── manual_test.py           # Manual testing script (no GUI)
└── README.md                # Test documentation
```

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# The requirements include:
# - pytest >= 7.0.0
# - pytest-cov >= 4.0.0
# - pytest-mock >= 3.10.0
```

### CI/CD Integration

Tests can be integrated into CI/CD pipelines:

```bash
# For CI environments
pytest tests/unit/ --cov=src --cov-report=xml --cov-report=term

# Generate HTML coverage report
pytest tests/unit/ --cov=src --cov-report=html
# View report: htmlcov/index.html
```

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

### v1.1.0 (2025-11-15)
- Added Debian package support
- Added dual-axis real-time charts (usage + frequency)
- Fixed GPU frequency reading (always use actual frequency)
- Added color-coded legends for dual-axis charts
- Translated all documentation to English
- Export All functionality (Ctrl+E)
- Comprehensive HTML reports with 13+ interactive charts

### v1.0.0 (2025-11-14)
- Initial release
- CPU/GPU/NPU/Memory monitoring
- Frequency control
- Data logging and export
- PyQt5 GUI with real-time charts
