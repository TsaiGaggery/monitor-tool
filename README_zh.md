# 系統監控工具

Linux 系統全面的即時監控儀表板，支援 CPU、GPU、NPU、記憶體、網路和磁碟 I/O 監控以及頻率控制。

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

[English](README.md)

## 功能特性

### 🖥️ 即時監控
- **CPU 監控**
  - 整體和單核心利用率
  - 即時頻率監控
  - 溫度監控（支援多個感測器）
  - CPU 統計資訊（上下文切換、中斷等）

- **GPU 監控**
  - NVIDIA GPU 支援（透過 pynvml）
  - AMD GPU 支援（透過 rocm-smi）
  - Intel GPU 支援（i915/Xe 驅動程式）
  - GPU 利用率、溫度、記憶體
  - 時脈速度監控
  - 雙軸圖表（使用率 + 頻率）

- **NPU 監控**
  - Intel NPU 支援（Meteor Lake+）
  - RockChip、Qualcomm、MediaTek 平台支援
  - 利用率和頻率追蹤
  - 雙軸即時視覺化

- **記憶體監控**
  - RAM 使用量詳細分解
  - Swap 使用量追蹤
  - 歷史趨勢

- **網路監控** 🌐
  - 即時上傳/下載速度
  - 網路介面統計
  - 活躍連線數（TCP/UDP）
  - 封包統計（發送/接收、錯誤、丟包）
  - 雙軸速度圖表

- **磁碟 I/O 監控** 💿
  - 即時讀取/寫入速度
  - IOPS（每秒讀寫次數）
  - 分割區使用狀況
  - 多磁碟支援
  - 雙軸 I/O 圖表

### ⚙️ 頻率控制
- CPU 調速器控制（Performance、Powersave、Ondemand）
- 最小/最大頻率調整
- 快速效能預設

### 📊 資料記錄和匯出
- SQLite 資料庫儲存
- 自動資料保留管理（預設 7 天）
- 匯出格式：CSV、JSON、HTML
- 互動式 HTML 報告（13+ 圖表）
- 縮放、平移和篩選功能

### 🎨 使用者介面
- PyQt5 圖形介面
- 高效能即時圖表（pyqtgraph）
- 多分頁佈局
- 深色主題
- 彩色編碼的雙軸圖例
- 低系統開銷

## 快速開始

### 1. 安裝
```bash
git clone https://github.com/TsaiGaggery/monitor-tool.git
cd monitor-tool
./scripts/install.sh
```

安裝腳本會：
- 安裝系統相依套件
- 建立 Python 虛擬環境
- 安裝所需套件
- 建立桌面啟動器
- （可選）設定 sudoers 以便頻率控制

### 2. 執行
```bash
./monitor-tool
```

或在應用程式選單中搜尋「System Monitor Tool」。

## 安裝方式

### 方法 1：安裝腳本（推薦）
```bash
./scripts/install.sh
```

### 方法 2：建置 Debian 軟體套件
```bash
# 安裝建置相依套件
sudo apt-get install devscripts debhelper dh-python python3-all

# 建置軟體套件
dpkg-buildpackage -us -uc -b

# 安裝
sudo dpkg -i ../monitor-tool_1.1.0_all.deb
sudo apt-get install -f  # 如果需要修復相依性
```

Debian 軟體套件包含：
- 所有原始碼檔案位於 `/usr/share/monitor-tool/`
- 啟動腳本位於 `/usr/bin/monitor-tool`
- 應用程式選單的桌面項目
- 自動相依性管理

### 方法 3：手動安裝
```bash
# 安裝系統相依套件
sudo apt-get install python3 python3-pip python3-pyqt5

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝 Python 相依套件
pip install -r requirements.txt

# 執行
python src/main.py
```

## 系統需求

- **作業系統**：Ubuntu 18.04+ 或基於 Debian 的 Linux
- **Python**：3.8+
- **硬體**：
  - Intel/NVIDIA/AMD GPU（可選）
  - Intel NPU（Meteor Lake+，可選）

## 儀表板配置

```
┌─────────────────────────────────────────────────────┐
│  概覽分頁                                            │
│  ├─ CPU 使用率圖表                                   │
│  ├─ 記憶體使用率圖表                                 │
│  └─ 系統資訊摘要                                     │
│                                                      │
│  CPU 分頁                                           │
│  ├─ 單核心使用率（預設顯示前 4 個）                   │
│  ├─ 頻率和溫度                                       │
│  └─ 即時圖表                                         │
│                                                      │
│  記憶體分頁                                          │
│  ├─ RAM 和 Swap 使用率                              │
│  └─ 歷史趨勢                                         │
│                                                      │
│  GPU 分頁（如果偵測到）                              │
│  ├─ 使用率和頻率（雙軸）                             │
│  ├─ 溫度和功耗                                       │
│  └─ 記憶體利用率                                     │
│                                                      │
│  NPU 分頁（如果偵測到）                              │
│  ├─ 利用率和頻率（雙軸）                             │
│  └─ 記憶體使用量                                     │
│                                                      │
│  控制面板（側邊欄）                                   │
│  ├─ CPU 調速器選擇器                                 │
│  ├─ 頻率範圍控制                                     │
│  └─ 效能預設                                         │
└─────────────────────────────────────────────────────┘
```

## 設定

編輯 `config/default.yaml` 以自訂：
- 更新間隔（預設：1000ms）
- 圖表顯示點數（預設：60）
- 資料保留期（預設：7 天）
- 低開銷模式

## 進階用法

### CLI 模式（無 GUI / Server 環境）

對於沒有圖形介面的伺服器或透過 SSH 遠端連線，可以使用 CLI 版本：

```bash
# 互動式儀表板（每秒更新，類似 htop）
./monitor-tool-cli

# 帶 CPU/GPU 頻率控制（按 'c' 控制 CPU，'g' 控制 GPU）
./monitor-tool-cli

# 單次快照簡單格式（適合腳本）
./monitor-tool-cli --once --format simple
# 輸出: CPU: 45.2% | Mem: 62.3% | GPU: 12% | Net: ↑0.5 ↓2.3 MB/s | Disk: R1.2 W0.8 MB/s

# JSON 格式（用於自動化）
./monitor-tool-cli --once --format json > status.json

# 執行並在按 'q' 退出時匯出 HTML
./monitor-tool-cli --export-format html --output report.html

# 執行並在退出時匯出 CSV
./monitor-tool-cli -e csv

# 自訂更新間隔
./monitor-tool-cli --interval 2.0
```

**CLI 功能特點：**
- ✅ 無 GUI 依賴（可透過 SSH 使用）
- ✅ 即時文字儀表板（curses 介面）
- ✅ CPU/GPU 頻率控制（按 'c'/'g'）
- ✅ 多種輸出格式（text、json、simple）
- ✅ 資料記錄至 SQLite（預設啟用）
- ✅ 匯出為 CSV、JSON、HTML
- ✅ 可配置更新間隔
- ✅ 低資源消耗

**已知限制：**
- ⚠️ 在頻率控制選單中（'c' 或 'g'）資料記錄會暫停
- 📝 待辦：實作背景執行緒以在選單操作時繼續記錄資料

### 頻率控制（需要 sudo）
安裝時選擇「yes」進行 sudoers 設定，以啟用無密碼頻率控制。

### 資料匯出
透過選單匯出監控資料：**檔案 → 匯出資料**
- **CSV**：用於試算表分析
- **JSON**：用於程式存取
- **HTML**：帶縮放/平移的互動式圖表
- **全部匯出（Ctrl+E）**：一次匯出所有格式

匯出檔案包括：
- 所有監控指標
- 真實時間戳記（不是秒數）
- 單核心 CPU 資料
- GPU 溫度、功耗、頻率
- 記憶體詳情（已用/可用）
- NPU 指標（如果可用）

資料位置：`~/.monitor-tool/monitor_data.db`

### 查詢歷史資料
```bash
sqlite3 ~/.monitor-tool/monitor_data.db "SELECT * FROM monitoring_data ORDER BY timestamp DESC LIMIT 10;"
```

## 疑難排解

### 「could not connect to display」錯誤？
```bash
# 本機 - 確保圖形化工作階段
# 切換到 GUI：Ctrl+Alt+F7

# 透過 SSH - 啟用 X 轉發
ssh -X user@hostname
./monitor-tool

# 或設定 DISPLAY
DISPLAY=:0 ./monitor-tool
```

### GPU 不顯示？
```bash
# 檢查 GPU 偵測
lspci | grep -i vga

# Intel GPU
ls -l /sys/class/drm/card*
sudo apt install intel-gpu-tools  # 可選

# NVIDIA GPU
nvidia-smi
sudo apt install nvidia-driver-550  # 如果缺少

# AMD GPU
rocm-smi
```

### GPU 使用率顯示 0%？
這在 GPU 閒置時是正常的。測試：
```bash
sudo apt install mesa-utils
glxgears  # 觀察 GPU 使用率增加
```

GPU 監控因硬體而異：
- **Intel Xe GPU**：使用實際頻率（act_freq），閒置時為 0
- **Intel i915 GPU**：需要 `intel_gpu_top`（sudo）
- **NVIDIA GPU**：需要 NVIDIA 驅動程式
- **AMD GPU**：需要 ROCm 驅動程式

### NPU 未偵測到？
```bash
# 檢查 NPU 硬體（Intel Meteor Lake+，核心 6.2+）
lspci | grep -i vpu
ls -l /sys/class/accel/accel0
```

### 頻率控制不運作？
- 重新執行 `./scripts/install.sh` 並選擇 sudoers 設定
- 或使用 sudo 執行：`sudo ./monitor-tool`（不建議用於 GUI）

### 降低系統開銷？
編輯 `config/default.yaml`：
```yaml
update_interval: 2000  # 增加到 2 秒
```

## 專案結構

```
monitor-tool/
├── src/
│   ├── monitors/           # 監控模組
│   │   ├── cpu_monitor.py
│   │   ├── gpu_monitor.py
│   │   ├── npu_monitor.py
│   │   └── memory_monitor.py
│   ├── controllers/        # 控制模組
│   │   └── freq_controller.py
│   ├── ui/                # UI 模組
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   └── styles/
│   ├── storage/           # 資料儲存
│   │   ├── data_logger.py
│   │   └── data_exporter.py
│   └── main.py           # 主進入點
├── scripts/              # 安裝/建置腳本
│   ├── install.sh
│   ├── uninstall.sh
│   └── update_sudoers.sh
├── debian/              # Debian 打包
│   ├── control
│   ├── rules
│   ├── changelog
│   └── postinst
├── config/              # 設定
│   └── default.yaml
├── requirements.txt     # Python 相依套件
├── setup.py            # Python 套件設定
├── monitor-tool        # 啟動腳本
└── README.md
```

## 平台支援

| 元件 | Intel | NVIDIA | AMD | ARM |
|-----------|-------|--------|-----|-----|
| CPU | ✅ | ✅ | ✅ | ✅ |
| GPU | ✅ | ✅ | ✅ | ✅ |
| NPU | ✅ (Meteor Lake+) | ❌ | ❌ | 🟡 |
| 頻率控制 | ✅ | ❌ | ❌ | 🟡 |

## 解除安裝

```bash
# 如果透過腳本安裝
./scripts/uninstall.sh

# 如果透過 Debian 軟體套件安裝
sudo apt-get remove monitor-tool
```

## 授權

MIT License - 詳見 `debian/copyright`

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 作者

**TsaiGaggery**

## 更新日誌

### v1.1.0 (2025-11-15)
- 新增 Debian 軟體套件支援
- 新增雙軸即時圖表（使用率 + 頻率）
- 修正 GPU 頻率讀取（始終使用實際頻率）
- 為雙軸圖表新增彩色編碼圖例
- 將所有文件翻譯為英文
- 全部匯出功能（Ctrl+E）
- 包含 13+ 個互動式圖表的全面 HTML 報告

### v1.0.0 (2024-11-14)
- 初始版本
- CPU/GPU/NPU/記憶體監控
- 頻率控制
- 資料記錄和匯出
- PyQt5 GUI 與即時圖表
