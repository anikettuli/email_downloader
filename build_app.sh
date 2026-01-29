#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")"

OS="$(uname)"
echo "Detected OS: $OS"

# Setup Venv
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
PIP="./venv/bin/pip"
PYTHON="./venv/bin/python"

echo "Installing dependencies..."
$PIP install -r requirements.txt llama-cpp-python

# Download model if not exists
if [ ! -f "models/gemma-3-270m-it-Q4_K_M.gguf" ]; then
    echo "Downloading Gemma 3 model..."
    mkdir -p models
    curl -L https://huggingface.co/unsloth/gemma-3-270m-it-GGUF/resolve/main/gemma-3-270m-it-Q4_K_M.gguf -o models/gemma-3-270m-it-Q4_K_M.gguf
fi

# Clean
rm -rf build dist

if [ "$OS" = "Darwin" ]; then
    echo "Building macOS .app..."
    $PYTHON setup.py py2app
    
    # Create DMG
    if command -v create-dmg >/dev/null 2>&1; then
        echo "Creating .dmg installer..."
        create-dmg \
          --volname "Email Downloader Installer" \
          --volicon "app_icon.icns" \
          --background "app_icon.icns" \
          --window-pos 200 120 \
          --window-size 800 400 \
          --icon-size 100 \
          --icon "EmailDownloader.app" 200 190 \
          --hide-extension "EmailDownloader.app" \
          --app-drop-link 600 185 \
          "dist/EmailDownloader-Installer.dmg" \
          "dist/"
    else
        echo "create-dmg not found. Skipping DMG creation."
    fi

    echo "--------------------------------------------------------"
    echo "Build Complete!"
    echo "The app is located at: dist/EmailDownloader.app"
else
    echo "Building Linux executable..."
    $PIP install pyinstaller
    $PYTHON -m PyInstaller --noconfirm --onedir --windowed --name "EmailDownloader" \
        --add-data "src:src" \
        --add-data "models:models" \
        --hidden-import "babel.numbers" \
        --collect-all "customtkinter" \
        src/gui.py
        
    echo "--------------------------------------------------------"
    echo "Build Complete!"
fi

