#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")"

OS="$(uname)"
echo "Detected OS: $OS"

# Install Requirements
if [ -d "venv" ]; then
    PIP="./venv/bin/pip"
    PYTHON="./venv/bin/python"
else
    PIP="pip"
    PYTHON="python3"
fi

echo "Installing dependencies..."
$PIP install -r requirements.txt

# Clean
rm -rf build dist

if [ "$OS" = "Darwin" ]; then
    echo "Building macOS .app..."
    $PYTHON setup.py py2app
    
    echo "--------------------------------------------------------"
    echo "Build Complete!"
    echo "The app is located at: dist/EmailDownloader.app"
    echo "To install: Move 'dist/EmailDownloader.app' to /Applications"
else
    echo "Building Linux executable..."
    $PIP install pyinstaller
    ./venv/bin/pyinstaller --noconfirm --onedir --windowed --name "EmailDownloader" \
        --add-data "src:src" \
        --hidden-import "babel.numbers" \
        --collect-all "customtkinter" \
        src/gui.py
        
    echo "--------------------------------------------------------"
    echo "Build Complete!"
    echo "The app is located at: dist/EmailDownloader/EmailDownloader"
fi

# Check for credentials.json
if [ ! -f credentials.json ]; then
    echo "WARNING: credentials.json not found!"
    echo "You need to download 'credentials.json' from Google Cloud Console (OAuth Client ID)"
    echo "and place it in the same directory as the executable."
fi
