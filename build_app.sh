#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")"

OS="$(uname)"
echo "Detected OS: $OS"

# Check if we are on macOS for building the .app
if [ "$OS" != "Darwin" ]; then
    echo "ERROR: macOS .app bundles can only be built on a macOS machine."
    echo "You are currently on $OS."
    echo "If you want a Linux executable, you can use PyInstaller (logic below), but for the .app, please use a Mac."
fi

# Setup Venv using pip3
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Ensure pip3 is used for installation
./venv/bin/python3 -m pip install --upgrade pip
./venv/bin/python3 -m pip install -r requirements.txt

# Clean previous builds
rm -rf build dist

if [ "$OS" = "Darwin" ]; then
    echo "Building macOS .app..."
    ./venv/bin/python3 setup.py py2app
    
    if [ -d "dist/EmailDownloader.app" ]; then
        echo "Moving EmailDownloader.app to Desktop..."
        cp -R "dist/EmailDownloader.app" "$HOME/Desktop/"
        echo "--------------------------------------------------------"
        echo "Build Complete!"
        echo "The app has been copied to your Desktop."
        echo "You can now drag it from the Desktop to your Applications folder."
    else
        echo "Error: Build failed, dist/EmailDownloader.app not found."
        exit 1
    fi

    # Optional: Create DMG if create-dmg is installed
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
        cp "dist/EmailDownloader-Installer.dmg" "$HOME/Desktop/"
        echo "DMG also copied to Desktop."
    fi
else
    echo "Building Linux executable..."
    ./venv/bin/python3 -m pip install pyinstaller
    ./venv/bin/python3 -m PyInstaller --noconfirm --onedir --windowed --name "EmailDownloader" \
        --add-data "src:src" \
        --hidden-import "babel.numbers" \
        --collect-all "customtkinter" \
        src/gui.py
        
    echo "--------------------------------------------------------"
    echo "Build Complete!"
    echo "Linux executable is in dist/EmailDownloader"
fi

