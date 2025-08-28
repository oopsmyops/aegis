#!/bin/bash
"""
Local build script for AEGIS CLI binary.
This script builds a standalone binary using PyInstaller.
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PYTHON_VERSION="3.11"
BINARY_NAME="aegis"
VERSION="${1:-0.1.0}"  # Use first argument as version, default to 0.1.0

print_status "Building AEGIS CLI binary v${VERSION}"
print_status "Working directory: $(pwd)"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed or not in PATH"
    exit 1
fi

PYTHON_VER=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
print_status "Using Python version: ${PYTHON_VER}"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip and install dependencies
print_status "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Update version in setup.py
print_status "Updating version to ${VERSION}..."
sed -i.bak "s/version=\"[^\"]*\"/version=\"${VERSION}\"/" setup.py

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf build/ dist/ *.spec

# Detect platform and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case $ARCH in
    x86_64)
        ARCH="x64"
        ;;
    aarch64|arm64)
        ARCH="arm64"
        ;;
    *)
        print_warning "Unknown architecture: $ARCH, using as-is"
        ;;
esac

BINARY_FULL_NAME="${BINARY_NAME}-${OS}-${ARCH}"
print_status "Building binary: ${BINARY_FULL_NAME}"

# Build with PyInstaller using spec file
print_status "Running PyInstaller..."
pyinstaller --clean \
    --onefile \
    --name "${BINARY_FULL_NAME}" \
    --add-data "aegis-config.yaml:." \
    --hidden-import=config \
    --hidden-import=models \
    --hidden-import=interfaces \
    --hidden-import=exceptions \
    --hidden-import=boto3 \
    --hidden-import=botocore \
    --hidden-import=kubernetes \
    --hidden-import=yaml \
    --hidden-import=click \
    --console \
    main.py

# Check if build was successful
if [ ! -f "dist/${BINARY_FULL_NAME}" ]; then
    print_error "Binary build failed - file not found: dist/${BINARY_FULL_NAME}"
    exit 1
fi

# Make binary executable
chmod +x "dist/${BINARY_FULL_NAME}"

# Test the binary
print_status "Testing binary..."
if ./dist/${BINARY_FULL_NAME} --help > /dev/null 2>&1; then
    print_success "Binary test passed"
else
    print_warning "Binary test failed, but binary was created"
fi

# Generate checksums
print_status "Generating checksums..."
cd dist
sha256sum "${BINARY_FULL_NAME}" > "${BINARY_FULL_NAME}.sha256"
md5sum "${BINARY_FULL_NAME}" > "${BINARY_FULL_NAME}.md5"

# Display results
print_success "Build completed successfully!"
echo ""
echo "📦 Binary Information:"
echo "   • Name: ${BINARY_FULL_NAME}"
echo "   • Size: $(du -h "${BINARY_FULL_NAME}" | cut -f1)"
echo "   • Location: $(pwd)/${BINARY_FULL_NAME}"
echo ""
echo "🔐 Checksums:"
echo "   • SHA256: $(cat "${BINARY_FULL_NAME}.sha256")"
echo "   • MD5: $(cat "${BINARY_FULL_NAME}.md5")"
echo ""
echo "🧪 Test the binary:"
echo "   ./${BINARY_FULL_NAME} --help"
echo "   ./${BINARY_FULL_NAME} --version"
echo ""
echo "📋 Installation:"
echo "   sudo cp ${BINARY_FULL_NAME} /usr/local/bin/aegis"
echo "   sudo chmod +x /usr/local/bin/aegis"

cd ..
print_success "Build process completed!"