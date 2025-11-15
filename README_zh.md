# 系统监控工具

Linux 系统全面的实时监控仪表板，支持 CPU、GPU、NPU 和内存监控以及频率控制。

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

[English](README.md)

## 功能特性

### 🖥️ 实时监控
- **CPU 监控**
  - 整体和单核心利用率
  - 实时频率监控
  - 温度监控（支持多个传感器）
  - CPU 统计信息（上下文切换、中断等）

- **GPU 监控**
  - NVIDIA GPU 支持（通过 pynvml）
  - AMD GPU 支持（通过 rocm-smi）
  - Intel GPU 支持（i915/Xe 驱动）
  - GPU 利用率、温度、内存
  - 时钟速度监控
  - 双轴图表（使用率 + 频率）

- **NPU 监控**
  - Intel NPU 支持（Meteor Lake+）
  - RockChip、Qualcomm、MediaTek 平台支持
  - 利用率和频率跟踪
  - 双轴实时可视化

- **内存监控**
  - RAM 使用量详细分解
  - Swap 使用量跟踪
  - 历史趋势

### ⚙️ 频率控制
- CPU 调速器控制（Performance、Powersave、Ondemand）
- 最小/最大频率调整
- 快速性能预设

### 📊 数据记录和导出
- SQLite 数据库存储
- 自动数据保留管理（默认 7 天）
- 导出格式：CSV、JSON、HTML
- 交互式 HTML 报告（13+ 图表）
- 缩放、平移和过滤功能

### 🎨 用户界面
- PyQt5 图形界面
- 高性能实时图表（pyqtgraph）
- 多标签页布局
- 深色主题
- 彩色编码的双轴图例
- 低系统开销

## 快速开始

### 1. 安装
```bash
git clone https://github.com/TsaiGaggery/monitor-tool.git
cd monitor-tool
./scripts/install.sh
```

安装脚本会：
- 安装系统依赖
- 创建 Python 虚拟环境
- 安装所需包
- 创建桌面启动器
- （可选）配置 sudoers 以便频率控制

### 2. 运行
```bash
./monitor-tool
```

或在应用程序菜单中搜索"System Monitor Tool"。

## 安装方式

### 方法 1：安装脚本（推荐）
```bash
./scripts/install.sh
```

### 方法 2：构建 Debian 软件包
```bash
# 安装构建依赖
sudo apt-get install devscripts debhelper dh-python python3-all

# 构建软件包
dpkg-buildpackage -us -uc -b

# 安装
sudo dpkg -i ../monitor-tool_1.1.0_all.deb
sudo apt-get install -f  # 如果需要修复依赖
```

Debian 软件包包含：
- 所有源文件位于 `/usr/share/monitor-tool/`
- 启动脚本位于 `/usr/bin/monitor-tool`
- 应用程序菜单的桌面条目
- 自动依赖管理

### 方法 3：手动安装
```bash
# 安装系统依赖
sudo apt-get install python3 python3-pip python3-pyqt5

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# 运行
python src/main.py
```

## 系统需求

- **操作系统**：Ubuntu 18.04+ 或基于 Debian 的 Linux
- **Python**：3.8+
- **硬件**：
  - Intel/NVIDIA/AMD GPU（可选）
  - Intel NPU（Meteor Lake+，可选）

## 仪表板布局

```
┌─────────────────────────────────────────────────────┐
│  概览标签                                            │
│  ├─ CPU 使用率图表                                   │
│  ├─ 内存使用率图表                                   │
│  └─ 系统信息摘要                                     │
│                                                      │
│  CPU 标签                                           │
│  ├─ 单核心使用率（默认显示前 4 个）                   │
│  ├─ 频率和温度                                       │
│  └─ 实时图表                                         │
│                                                      │
│  内存标签                                            │
│  ├─ RAM 和 Swap 使用率                              │
│  └─ 历史趋势                                         │
│                                                      │
│  GPU 标签（如果检测到）                              │
│  ├─ 使用率和频率（双轴）                             │
│  ├─ 温度和功耗                                       │
│  └─ 内存利用率                                       │
│                                                      │
│  NPU 标签（如果检测到）                              │
│  ├─ 利用率和频率（双轴）                             │
│  └─ 内存使用量                                       │
│                                                      │
│  控制面板（侧边栏）                                   │
│  ├─ CPU 调速器选择器                                 │
│  ├─ 频率范围控制                                     │
│  └─ 性能预设                                         │
└─────────────────────────────────────────────────────┘
```

## 配置

编辑 `config/default.yaml` 以自定义：
- 更新间隔（默认：1000ms）
- 图表显示点数（默认：60）
- 数据保留期（默认：7 天）
- 低开销模式

## 高级用法

### 频率控制（需要 sudo）
安装时选择"yes"进行 sudoers 配置，以启用无密码频率控制。

### 数据导出
通过菜单导出监控数据：**文件 → 导出数据**
- **CSV**：用于电子表格分析
- **JSON**：用于程序访问
- **HTML**：带缩放/平移的交互式图表
- **全部导出（Ctrl+E）**：一次导出所有格式

导出文件包括：
- 所有监控指标
- 真实时间戳（不是秒数）
- 单核心 CPU 数据
- GPU 温度、功耗、频率
- 内存详情（已用/可用）
- NPU 指标（如果可用）

数据位置：`~/.monitor-tool/monitor_data.db`

### 查询历史数据
```bash
sqlite3 ~/.monitor-tool/monitor_data.db "SELECT * FROM monitoring_data ORDER BY timestamp DESC LIMIT 10;"
```

## 故障排除

### "could not connect to display" 错误？
```bash
# 本地机器 - 确保图形会话
# 切换到 GUI：Ctrl+Alt+F7

# 通过 SSH - 启用 X 转发
ssh -X user@hostname
./monitor-tool

# 或设置 DISPLAY
DISPLAY=:0 ./monitor-tool
```

### GPU 不显示？
```bash
# 检查 GPU 检测
lspci | grep -i vga

# Intel GPU
ls -l /sys/class/drm/card*
sudo apt install intel-gpu-tools  # 可选

# NVIDIA GPU
nvidia-smi
sudo apt install nvidia-driver-550  # 如果缺失

# AMD GPU
rocm-smi
```

### GPU 使用率显示 0%？
这在 GPU 空闲时是正常的。测试：
```bash
sudo apt install mesa-utils
glxgears  # 观察 GPU 使用率增加
```

GPU 监控因硬件而异：
- **Intel Xe GPU**：使用实际频率（act_freq），空闲时为 0
- **Intel i915 GPU**：需要 `intel_gpu_top`（sudo）
- **NVIDIA GPU**：需要 NVIDIA 驱动
- **AMD GPU**：需要 ROCm 驱动

### NPU 未检测到？
```bash
# 检查 NPU 硬件（Intel Meteor Lake+，内核 6.2+）
lspci | grep -i vpu
ls -l /sys/class/accel/accel0
```

### 频率控制不工作？
- 重新运行 `./scripts/install.sh` 并选择 sudoers 配置
- 或使用 sudo 运行：`sudo ./monitor-tool`（不推荐用于 GUI）

### 降低系统开销？
编辑 `config/default.yaml`：
```yaml
update_interval: 2000  # 增加到 2 秒
```

## 项目结构

```
monitor-tool/
├── src/
│   ├── monitors/           # 监控模块
│   │   ├── cpu_monitor.py
│   │   ├── gpu_monitor.py
│   │   ├── npu_monitor.py
│   │   └── memory_monitor.py
│   ├── controllers/        # 控制模块
│   │   └── freq_controller.py
│   ├── ui/                # UI 模块
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   └── styles/
│   ├── storage/           # 数据存储
│   │   ├── data_logger.py
│   │   └── data_exporter.py
│   └── main.py           # 主入口
├── scripts/              # 安装/构建脚本
│   ├── install.sh
│   ├── uninstall.sh
│   └── build-deb.sh
├── debian/              # Debian 打包
│   ├── control
│   ├── rules
│   ├── changelog
│   └── postinst
├── config/              # 配置
│   └── default.yaml
├── requirements.txt     # Python 依赖
├── setup.py            # Python 包设置
├── monitor-tool        # 启动脚本
└── README.md
```

## 平台支持

| 组件 | Intel | NVIDIA | AMD | ARM |
|-----------|-------|--------|-----|-----|
| CPU | ✅ | ✅ | ✅ | ✅ |
| GPU | ✅ | ✅ | ✅ | ✅ |
| NPU | ✅ (Meteor Lake+) | ❌ | ❌ | 🟡 |
| 频率控制 | ✅ | ❌ | ❌ | 🟡 |

## 卸载

```bash
# 如果通过脚本安装
./scripts/uninstall.sh

# 如果通过 Debian 软件包安装
sudo apt-get remove monitor-tool
```

## 许可证

MIT License - 详见 `debian/copyright`

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

**TsaiGaggery**

## 更新日志

### v1.1.0 (2025-11-15)
- 添加 Debian 软件包支持
- 添加双轴实时图表（使用率 + 频率）
- 修复 GPU 频率读取（始终使用实际频率）
- 为双轴图表添加彩色编码图例
- 将所有文档翻译为英文
- 全部导出功能（Ctrl+E）
- 包含 13+ 个交互式图表的全面 HTML 报告

### v1.0.0 (2024-11-14)
- 初始版本
- CPU/GPU/NPU/内存监控
- 频率控制
- 数据记录和导出
- PyQt5 GUI 与实时图表
