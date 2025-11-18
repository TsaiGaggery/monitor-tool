# Remote Linux SSH Monitoring - Deployment Guide

## Prerequisites on Remote Machine (Target Device)

### Required Packages

- `bash` (>= 4.0)
- `awk` (gawk 或 mawk)
- `grep`
- `coreutils` (cat, date, echo, etc.)
- **`sqlite3`** - 用於在 target device 儲存資料

### Check Dependencies
執行檢查腳本來驗證所有依賴：
```bash
# 在遠端機器上執行
bash check_remote_dependencies.sh

# 或者透過 SSH 遠端執行
ssh user@remote-host 'bash -s' < scripts/check_remote_dependencies.sh
```

### Installation

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install bash gawk grep coreutils sqlite3
```

**RHEL/CentOS/Fedora:**
```bash
sudo yum install bash gawk grep coreutils sqlite
```

**Arch Linux:**
```bash
sudo pacman -S bash gawk grep coreutils sqlite
```

## Optional Components

### NVIDIA GPU Support
如果遠端機器有 NVIDIA GPU，需要安裝 NVIDIA driver 和 nvidia-smi：
```bash
# Ubuntu/Debian
sudo apt-get install nvidia-driver-xxx nvidia-utils

# 檢查
nvidia-smi --version
```

### Intel GPU Support
**不需要額外安裝！** 腳本會自動偵測：
- Intel Xe GPU: `/sys/class/drm/card*/device/tile0/gt0/`
- Intel i915 GPU: `/sys/class/drm/card*/gt/`

### Intel NPU Support
**不需要額外安裝！** 腳本會自動偵測：
- Intel NPU: `/sys/class/accel/accel0/`

## System Requirements

### File System Access
腳本需要讀取以下 sysfs 路徑：
- `/proc/stat` - CPU 統計
- `/proc/meminfo` - Memory 資訊
- `/proc/net/dev` - Network 統計
- `/proc/diskstats` - Disk I/O 統計
- `/sys/class/drm/card*/` - GPU 資訊
- `/sys/class/accel/accel*/` - NPU 資訊
- `/sys/class/thermal/thermal_zone*/` - Temperature
- `/sys/devices/system/cpu/cpu*/cpufreq/` - CPU frequency

### Permissions
- **不需要 root 權限**
- 標準用戶即可執行（需要能讀取 /proc 和 /sys）
- 某些 GPU 資訊可能需要 render group 權限

### SQLite
**必須安裝！** 資料儲存在 target device 的 SQLite database：
- Database 位置: `/tmp/monitor_tool_${USER}.db`
- 每個 user 有獨立的 database
- **重要**: 資料只存在 target device，不會傳回 host

## Data Storage Architecture

```
┌─────────────────────────────────────────┐
│ Host (Python GUI)                       │
│ ┌─────────────────────────────────────┐ │
│ │ SSHMonitorRaw                       │ │
│ │ - Receives JSON stream via SSH      │ │
│ │ - No local database for remote data │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
              ▲
              │ SSH JSON Stream
              │
┌─────────────▼───────────────────────────┐
│ Target Device (Remote Linux)            │
│ ┌─────────────────────────────────────┐ │
│ │ linux_monitor_remote.sh             │ │
│ │ - Collects system metrics           │ │
│ │ - Stores to SQLite database         │ │
│ │ - Streams JSON to stdout            │ │
│ └─────────────────────────────────────┘ │
│                 │                        │
│                 ▼                        │
│ ┌─────────────────────────────────────┐ │
│ │ /tmp/monitor_tool_${USER}.db        │ │
│ │ - Raw monitoring data               │ │
│ │ - Complete history on target device │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**重點**: 
- ✅ Target device 有完整的資料儲存 (SQLite)
- ✅ Host 只接收即時串流資料 (不儲存 remote data)
- ✅ 避免 host 本地資料與 remote 資料混合

## Quick Start

### 1. 測試連線
```bash
# 從 host (Python GUI) 機器執行
ssh user@remote-host 'echo "Connection OK"'
```

### 2. 測試腳本
```bash
# 執行 1 次採樣
ssh user@remote-host 'bash -s 1' < scripts/linux_monitor_remote.sh | head -1 | python3 -m json.tool
```

### 3. 在 GUI 中使用
```bash
# 啟動 monitor-tool，選擇 "Remote Linux (SSH)"
# 輸入：
#   Host: 172.25.65.75
#   Port: 22
#   Username: intel
#   Password/Key: (your credentials)
```

## Network Requirements

- **SSH Port**: 22 (default) or custom
- **Bandwidth**: ~1-5 KB/s (JSON streaming)
- **Latency**: 建議 < 100ms (越低越好)

## Troubleshooting

### 檢查依賴
```bash
ssh user@remote-host 'bash -s' < scripts/check_remote_dependencies.sh
```

### 測試輸出
```bash
# 看 2 個採樣
timeout 3 ssh user@remote-host 'bash -s 1' < scripts/linux_monitor_remote.sh 2>/dev/null | head -2
```

### 驗證 JSON 格式
```bash
ssh user@remote-host 'bash -s 1' < scripts/linux_monitor_remote.sh 2>/dev/null | head -1 | python3 -c "import json,sys; json.load(sys.stdin); print('JSON OK')"
```

## Summary

✅ **需要安裝 SQLite** (資料儲存在 target device)  
✅ **不需要安裝 Python**  
✅ **標準 Linux 工具**  
✅ **不需要 root 權限**  
✅ **資料只存在 target device** (/tmp/monitor_tool_${USER}.db)

### Quick Install
```bash
# Ubuntu/Debian
sudo apt-get install bash gawk grep coreutils sqlite3

# RHEL/CentOS
sudo yum install bash gawk grep coreutils sqlite

# Arch
sudo pacman -S bash gawk grep coreutils sqlite
```

## Timezone Handling (時區處理)

**重要：** 系統使用 UTC 進行資料儲存，Export 時自動轉換為本地時間。

### 資料儲存階段
- **Remote Linux**: `date +%s` 產生 UTC timestamp
- **Android**: SQLite `CURRENT_TIMESTAMP` 為 UTC 時間  
- **資料庫**: 所有 timestamp 欄位儲存 UTC 時間

### Export 階段
- **查詢範圍**: 使用 UTC timestamp 查詢資料庫
- **時間轉換**: Python `datetime.fromtimestamp()` 自動轉換為本地時間
- **輸出格式**: CSV/JSON/HTML 都顯示本地時間

範例：
```
資料庫儲存: 1763438017 (UTC timestamp)
           ↓ 
Python:    datetime.fromtimestamp(1763438017)
           ↓
Export:    2025-11-17 19:53:37 (Local time - PST)
```

**為何使用 UTC？**
- 避免夏令時問題
- 支援跨時區監控
- 資料庫查詢一致性
- Export 時根據 host 的時區自動轉換

