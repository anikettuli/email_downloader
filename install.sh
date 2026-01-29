#!/bin/bash

# Ensure we are in the project directory
cd "$(dirname "$0")"

echo "Setting up Email Downloader Environment..."

# 1. Setup Python Virtual Environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing dependencies using pip3..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 2. Check Configuration
if [ ! -f "config.yaml" ]; then
    echo "----------------------------------------------------------------"
    echo "WARNING: config.yaml not found!"
    echo "Please copy config.template.yaml to config.yaml and edit it with your credentials."
    echo "cp config.template.yaml config.yaml"
    echo "----------------------------------------------------------------"
    # We don't exit, we just warn, so the plist can still be generated if desired for later.
fi

# 3. Generate macOS LaunchAgent Plist
PWD_DIR=$(pwd)
PYTHON_EXEC="$PWD_DIR/venv/bin/python"
SCRIPT_PATH="$PWD_DIR/src/main.py"
CONFIG_PATH="$PWD_DIR/config.yaml"
PLIST_NAME="com.anike.emaildownloader.plist"

echo "Generating $PLIST_NAME..."

cat << EOF > "$PLIST_NAME"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.anike.emaildownloader</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_EXEC</string>
        <string>$SCRIPT_PATH</string>
        <string>--config</string>
        <string>$CONFIG_PATH</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$PWD_DIR</string>
    <key>StandardErrorPath</key>
    <string>$PWD_DIR/downloader_error.log</string>
    <key>StandardOutPath</key>
    <string>$PWD_DIR/downloader_output.log</string>
</dict>
</plist>
EOF

# 4. Install Instructions (Conditional)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS detected."
    LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
    
    read -p "Do you want to install and load the LaunchAgent now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$LAUNCH_AGENTS_DIR"
        cp "$PLIST_NAME" "$LAUNCH_AGENTS_DIR/"
        
        # Unload if exists to reload
        launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
        launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
        
        echo "Successfully installed and loaded. The script will run every 1 hour."
        echo "Logs will be at: $PWD_DIR/downloader_output.log"
    else
        echo "Skipping installation."
    fi
else
    echo "----------------------------------------------------------------"
    echo "Setup complete (Linux/Other)."
    echo "To run manually:"
    echo "  source venv/bin/activate && python src/main.py"
    echo ""
    echo "To install on macOS manually:"
    echo "  1. Move folder to desired location on Mac."
    echo "  2. Run ./install.sh on the Mac."
    echo "  3. Verify $PLIST_NAME contains correct paths."
    echo "----------------------------------------------------------------"
fi
