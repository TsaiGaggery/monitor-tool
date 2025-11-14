#!/bin/bash
#
# Build Debian package script
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== Building Debian Package ===${NC}"
echo ""

# Check for required tools
echo "Checking for required build tools..."
REQUIRED_TOOLS="dpkg-buildpackage debhelper dh-python"
MISSING_TOOLS=""

for tool in $REQUIRED_TOOLS; do
    if ! dpkg -l | grep -q "^ii  $tool"; then
        MISSING_TOOLS="$MISSING_TOOLS $tool"
    fi
done

if [ -n "$MISSING_TOOLS" ]; then
    echo -e "${YELLOW}Missing build tools:$MISSING_TOOLS${NC}"
    echo "Installing missing tools..."
    sudo apt-get update
    sudo apt-get install -y build-essential debhelper dh-python devscripts
fi

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
cd "$PROJECT_ROOT"
rm -rf debian/monitor-tool
rm -f ../monitor-tool_*.deb
rm -f ../monitor-tool_*.tar.*
rm -f ../monitor-tool_*.dsc
rm -f ../monitor-tool_*.changes
rm -f ../monitor-tool_*.buildinfo

# Make rules executable
chmod +x debian/rules

# Build package
echo ""
echo -e "${GREEN}Building package...${NC}"
dpkg-buildpackage -us -uc -b

# Check if build was successful
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Build Successful! ===${NC}"
    echo ""
    echo "Package created:"
    ls -lh ../monitor-tool_*.deb
    echo ""
    echo "To install the package, run:"
    echo -e "${YELLOW}sudo dpkg -i ../monitor-tool_*.deb${NC}"
    echo -e "${YELLOW}sudo apt-get install -f  # To fix any dependency issues${NC}"
else
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi
