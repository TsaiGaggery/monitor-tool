#!/bin/bash
#
# Installation script for System Monitor Tool
# Supports Ubuntu/Debian-based systems
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== System Monitor Tool Installation ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${YELLOW}Warning: Running as root. This is not recommended.${NC}"
    echo "Consider running as normal user (will prompt for sudo when needed)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect package manager
if command_exists apt-get; then
    PKG_MANAGER="apt-get"
    PKG_UPDATE="sudo apt-get update"
    PKG_INSTALL="sudo apt-get install -y"
elif command_exists dnf; then
    PKG_MANAGER="dnf"
    PKG_UPDATE="sudo dnf check-update"
    PKG_INSTALL="sudo dnf install -y"
elif command_exists yum; then
    PKG_MANAGER="yum"
    PKG_UPDATE="sudo yum check-update"
    PKG_INSTALL="sudo yum install -y"
else
    echo -e "${RED}Error: No supported package manager found (apt-get, dnf, or yum)${NC}"
    exit 1
fi

echo "Detected package manager: $PKG_MANAGER"
echo ""

# Update package list
echo -e "${GREEN}Step 1: Updating package list...${NC}"
$PKG_UPDATE || true
echo ""

# Install system dependencies
echo -e "${GREEN}Step 2: Installing system dependencies...${NC}"

SYSTEM_DEPS="python3 python3-pip python3-venv"

# Add Qt dependencies for Ubuntu/Debian
if [ "$PKG_MANAGER" = "apt-get" ]; then
    SYSTEM_DEPS="$SYSTEM_DEPS python3-pyqt5 python3-pyqt5.qtsvg libxcb-xinerama0"
fi

$PKG_INSTALL $SYSTEM_DEPS
echo ""

# Check Python version
echo -e "${GREEN}Step 3: Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if Python version is >= 3.7
REQUIRED_VERSION="3.7"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo -e "${RED}Error: Python 3.7 or higher is required${NC}"
    exit 1
fi
echo ""

# Create virtual environment
echo -e "${GREEN}Step 4: Creating virtual environment...${NC}"
VENV_DIR="$PROJECT_ROOT/venv"

if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at $VENV_DIR"
    read -p "Recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi
else
    python3 -m venv "$VENV_DIR"
fi
echo ""

# Activate virtual environment
echo -e "${GREEN}Step 5: Installing Python dependencies...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install requirements
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    pip install -r "$PROJECT_ROOT/requirements.txt"
else
    echo -e "${RED}Error: requirements.txt not found${NC}"
    exit 1
fi
echo ""

# Install optional GPU support
echo -e "${GREEN}Step 6: Checking GPU support...${NC}"
if command_exists nvidia-smi; then
    echo "NVIDIA GPU detected. Installing pynvml..."
    pip install pynvml
elif command_exists rocm-smi; then
    echo "AMD GPU detected. ROCm support available."
else
    echo "No GPU detected or GPU tools not installed."
    echo "If you have an NVIDIA GPU, install nvidia-smi first."
fi
echo ""

# Create desktop entry
echo -e "${GREEN}Step 7: Creating desktop entry...${NC}"
DESKTOP_FILE="$HOME/.local/share/applications/monitor-tool.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=System Monitor Tool
Comment=Real-time system monitoring with frequency control
Exec=$VENV_DIR/bin/python $PROJECT_ROOT/src/main.py
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
Keywords=monitor;cpu;gpu;memory;performance;
EOF

chmod +x "$DESKTOP_FILE"
echo "Desktop entry created at $DESKTOP_FILE"
echo ""

# Create launcher script
echo -e "${GREEN}Step 8: Creating launcher script...${NC}"
LAUNCHER="$PROJECT_ROOT/monitor-tool"

cat > "$LAUNCHER" << EOF
#!/bin/bash
# Launcher script for System Monitor Tool

SCRIPT_DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" && pwd )"
source "\$SCRIPT_DIR/venv/bin/activate"
python "\$SCRIPT_DIR/src/main.py" "\$@"
EOF

chmod +x "$LAUNCHER"
echo "Launcher script created at $LAUNCHER"
echo ""

# Setup sudo permissions for frequency control (optional)
echo -e "${GREEN}Step 9: Setup frequency control permissions (optional)...${NC}"
echo "For frequency control, the application needs to write to /sys/devices/system/cpu/"
echo "You can either:"
echo "  1. Run the application with sudo (not recommended for GUI apps)"
echo "  2. Setup sudoers configuration (recommended)"
echo "  3. Skip this step and use read-only mode"
echo ""
read -p "Setup sudoers configuration? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    SUDOERS_FILE="/etc/sudoers.d/monitor-tool"
    CURRENT_USER=$(whoami)
    
    # Create sudoers configuration
    sudo bash -c "cat > $SUDOERS_FILE << 'EOF'
# Allow monitor-tool to control CPU frequencies without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/devices/system/cpu/cpu*/cpufreq/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/devices/system/cpu/cpu*/cpufreq/*
# Allow monitor-tool to control GPU frequencies without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/device/tile*/gt*/freq0/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/gt_*_freq_mhz
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/class/drm/card*/device/tile*/gt*/freq0/*
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/sh -c echo * > /sys/class/drm/card*/gt_*_freq_mhz
EOF"
    
    sudo chmod 0440 "$SUDOERS_FILE"
    echo -e "${GREEN}Sudoers configuration created (CPU + GPU frequency control)${NC}"
else
    echo "Skipped. You'll need to run with sudo for frequency control."
fi
echo ""

# Installation complete
echo -e "${GREEN}=== Installation Complete! ===${NC}"
echo ""
echo "You can now run the monitor tool in several ways:"
echo ""
echo "  1. From terminal:"
echo -e "     ${YELLOW}$LAUNCHER${NC}"
echo ""
echo "  2. From application menu:"
echo "     Search for 'System Monitor Tool'"
echo ""
echo "  3. Directly with Python:"
echo -e "     ${YELLOW}source $VENV_DIR/bin/activate${NC}"
echo -e "     ${YELLOW}python $PROJECT_ROOT/src/main.py${NC}"
echo ""
echo "Database location: ~/.monitor-tool/monitor_data.db"
echo ""
echo -e "${YELLOW}Note: For frequency control features, you may need sudo privileges.${NC}"
echo ""

deactivate
