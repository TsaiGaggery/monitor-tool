#!/bin/bash
#
# Uninstall script for System Monitor Tool
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}=== System Monitor Tool Uninstallation ===${NC}"
echo ""

# Remove virtual environment
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Removing virtual environment..."
    rm -rf "$PROJECT_ROOT/venv"
fi

# Remove desktop entry
DESKTOP_FILE="$HOME/.local/share/applications/monitor-tool.desktop"
if [ -f "$DESKTOP_FILE" ]; then
    echo "Removing desktop entry..."
    rm -f "$DESKTOP_FILE"
fi

# Remove launcher
if [ -f "$PROJECT_ROOT/monitor-tool" ]; then
    echo "Removing launcher script..."
    rm -f "$PROJECT_ROOT/monitor-tool"
fi

# Ask about removing data
echo ""
read -p "Remove monitoring data (~/.monitor-tool)? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$HOME/.monitor-tool" ]; then
        rm -rf "$HOME/.monitor-tool"
        echo "Monitoring data removed"
    fi
fi

# Ask about removing sudoers configuration
echo ""
read -p "Remove sudoers configuration? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "/etc/sudoers.d/monitor-tool" ]; then
        sudo rm -f "/etc/sudoers.d/monitor-tool"
        echo "Sudoers configuration removed"
    fi
fi

echo ""
echo -e "${GREEN}Uninstallation complete!${NC}"
echo ""
echo "The source code remains in: $PROJECT_ROOT"
echo "You can safely delete this directory if you wish."
