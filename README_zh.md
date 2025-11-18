# 系統監控工具

Linux 和 Android 雙平台系統監控工具，支援即時 CPU、GPU、記憶體、網路和磁碟 I/O 監控以及頻率控制。

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Android-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

[English](README.md)

## 功能特性

### 🖥️ **多種監控模式**
- **本地模式**：監控 Ubuntu/Linux 系統
- **遠端 Linux 模式**：透過 SSH 監控遠端 Linux 系統
- **Android 模式**：透過 ADB 遠端監控 Android 裝置

### 📊 **全面監控**
- CPU 利用率、頻率、溫度（支援單核心）
- GPU 利用率和記憶體（Intel i915/Xe、NVIDIA、AMD）
- NPU 監控（Intel Meteor Lake+）
- 記憶體和 Swap 使用量
- 網路流量和速度監控
- 磁碟 I/O 和分割區使用狀況
- 即時圖表和歷史資料記錄

### ⚙️ **頻率控制**
- CPU 調速器控制（performance/powersave）
- CPU 頻率範圍調整
- GPU 頻率控制
- **Ubuntu 和 Android 雙平台支援（需要 root）**

### 💾 **資料匯出**
- SQLite 資料庫記錄
- HTML 報告生成
- CSV 匯出支援

## 快速開始

### 本地模式（Ubuntu/Linux）

```bash
# 安裝
./scripts/install.sh

# 執行
./monitor-tool
```

或在應用程式選單搜尋「System Monitor Tool」。

### 遠端 Linux 模式（SSH）

透過 SSH 監控遠端 Linux 系統，無需在遠端主機安裝任何軟體：

```bash
# 監控遠端 Linux 系統
python3 src/main.py --ssh --ip <遠端_IP> --user <使用者名稱>

# 範例
python3 src/main.py --ssh --ip 192.168.1.100 --user intel

# 使用自訂 SSH 埠
python3 src/main.py --ssh --ip 192.168.1.100 --user admin --port 2222
```

**功能特性**：
- ✅ 遠端主機無需安裝任何軟體（無代理）
- ✅ 使用遠端時間戳記避免時鐘偏移問題
- ✅ 佇列緩衝機制防止樣本遺失
- ✅ 監控 CPU、記憶體、GPU（Intel i915/Xe）、網路、磁碟 I/O
- ✅ 正確處理整合式 GPU 記憶體（與系統記憶體共享）
- ✅ 支援頻率控制（需要遠端 sudo 權限）
- ✅ 所有資料儲存在遠端主機的 SQLite（`/tmp/monitor_tool_<user>.db`）
- ✅ 匯出時同步會話資料到本地資料庫

**需求**：
- SSH 存取遠端 Linux 主機
- 遠端主機有 Bash shell
- 選用：sudo 權限用於頻率控制

詳見[遠端 Linux SSH 監控指南](docs/REMOTE_LINUX_SSH.md)。

### Android 模式

```bash
# 1. 在 Android 裝置啟用 ADB 並透過 WiFi/USB 連接
# 2. 執行監控
python3 src/main.py --adb --ip <Android_IP>

# 範例
python3 src/main.py --adb --ip 192.168.1.68
```

**Android 模式需求**：
- Android 裝置啟用 ADB
- Root 權限（su）用於頻率控制（監控功能不需要）

## 系統需求

### 本地模式
- **作業系統**：Ubuntu 18.04+ 或基於 Debian 的 Linux
- **Python**：3.8+
- **硬體**：Intel/NVIDIA/AMD GPU（選用）、Intel NPU（Meteor Lake+，選用）

### 遠端 Linux 模式
- **主機**：Ubuntu/Linux 並安裝 Python 3.8+
- **遠端**：任何有 Bash shell 的 Linux 系統
- **連接**：SSH 存取（密碼或金鑰認證）
- **選用**：遠端 sudo 權限用於頻率控制

### Android 模式
- **主機**：Ubuntu/Linux 並安裝 ADB
- **Android**：支援 ADB 的 Android x86/ARM 裝置
- **網路**：WiFi 或 USB 連接
- **Root**：頻率控制需要（監控不需要）
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
- ✅ 背景執行緒 - 即使在選單操作時也能持續記錄資料

### 頻率控制（需要 sudo）
安裝時選擇「yes」進行 sudoers 設定，以啟用無密碼頻率控制。

### 資料管理

**資料庫位置：** `~/.monitor-tool/monitor_data.db`

**自動清理：**
- 每次啟動時自動刪除 3 天前的資料
- 自動執行 VACUUM 回收磁碟空間
- 無需手動維護

**手動清理：** 透過選單「工具 → 清理舊資料」

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

## 測試

本專案包含全面的測試套件，共有 152 個單元測試，涵蓋所有監控模組。

### 執行測試

```bash
# 執行所有測試
pytest tests/unit/

# 執行並顯示覆蓋率報告
pytest tests/unit/ --cov=src --cov-report=term-missing

# 執行特定測試檔案
pytest tests/unit/test_cpu_monitor.py -v

# 執行特定測試類別或函數
pytest tests/unit/test_gpu_monitor.py::TestGPUMonitorDetection -v
pytest tests/unit/test_data_exporter.py::TestDataExporterHTML::test_export_html -v
```

### 測試覆蓋率

目前覆蓋率（監控 + 儲存模組，不含 UI）：
- **記憶體監控**: 100%
- **網路監控**: 96%
- **磁碟監控**: 88%
- **資料記錄器**: 87%
- **NPU 監控**: 75%
- **資料匯出器**: 67%
- **CPU 監控**: 59%
- **GPU 監控**: 44%
- **總計**: 40%

### 測試結構

```
tests/
├── unit/                    # 使用 mock 的單元測試
│   ├── test_cpu_monitor.py
│   ├── test_gpu_monitor.py
│   ├── test_npu_monitor.py
│   ├── test_memory_monitor.py
│   ├── test_network_monitor.py
│   ├── test_disk_monitor.py
│   ├── test_data_logger.py
│   └── test_data_exporter.py
├── manual_test.py           # 手動測試腳本（無 GUI）
└── README.md                # 測試文件
```

### 開發環境設定

```bash
# 安裝開發相依套件
pip install -r requirements.txt

# requirements.txt 包含：
# - pytest >= 7.0.0
# - pytest-cov >= 4.0.0
# - pytest-mock >= 3.10.0
```

### CI/CD 整合

測試可整合到 CI/CD 流程中：

```bash
# 用於 CI 環境
pytest tests/unit/ --cov=src --cov-report=xml --cov-report=term

# 產生 HTML 覆蓋率報告
pytest tests/unit/ --cov=src --cov-report=html
# 檢視報告：htmlcov/index.html
```

## 技術特性

- **低開銷設計**：對系統影響最小
- **模組化架構**：易於擴充和維護
- **跨平台支援**：支援多種 GPU/NPU 平台
- **即時視覺化**：使用 pyqtgraph 的高效能圖表
- **資料持久化**：SQLite 儲存歷史資料
- **全面匯出**：包含 13+ 圖表的互動式 HTML 報告
- **雙軸圖表**：同時視覺化使用率和頻率
- **遠端監控**：
  - **時間戳記同步**：專門使用遠端時間戳記避免時鐘偏移問題
  - **佇列緩衝**：防止輪詢間隔期間樣本遺失（100 樣本緩衝區）
  - **無代理 SSH 監控**：遠端主機無需安裝任何軟體
  - **GPU 記憶體處理**：正確處理整合式 GPU 記憶體（與系統 RAM 共享）
  - **註記**：整合式 GPU 記憶體顯示為 0，因為它們與系統 RAM 共享。`/proc/*/fdinfo/*` 中的 `drm-resident-*` 值代表虛擬記憶體位址（GTT - Graphics Translation Table），由於多個程序共享緩衝區，無法準確彙總。

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
