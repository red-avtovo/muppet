#!/bin/bash

set -e

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# Get client type from argument
CLIENT_TYPE="$1"
if [ -z "$CLIENT_TYPE" ] || { [ "$CLIENT_TYPE" != "seeker" ] && [ "$CLIENT_TYPE" != "switcher" ]; }; then
    echo "Usage: $0 <seeker|switcher>" >&2
    exit 1
fi

RUN_USER=""
while [ -z "$RUN_USER" ]; do
    read -p "Enter the user to run the service as (or press Enter for default 'pi'): " RUN_USER
    RUN_USER=${RUN_USER:-"pi"}
    # Check if user exists
    if ! id "$RUN_USER" &> /dev/null; then
        echo "User $RUN_USER does not exist" >&2
        RUN_USER=""
    fi
done


# Check if VLC is installed for seeker clients
if [ "$CLIENT_TYPE" = "seeker" ]; then
    if ! command -v vlc &> /dev/null; then
        echo "VLC is required for seeker clients but not installed."
        echo "Install VLC with: apt-get install vlc"
        read -p "Install VLC now? (y/n): " INSTALL_VLC
        if [ "$INSTALL_VLC" = "y" ]; then
            apt-get update
            apt-get install -y vlc
        else
            echo "Please install VLC manually then run this script again."
            exit 1
        fi
    fi
fi

INSTALL_DIR="/opt/muppet"

# Install dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv

# Create install directory
mkdir -p "$INSTALL_DIR"

# Create virtual environment
python3 -m venv "$INSTALL_DIR/venv"

# Copy necessary files
cp "$(dirname "$0")/client.py" "$INSTALL_DIR/"

# Prompt for WebSocket server and authentication token
read -p "Enter WebSocket server URL (or press Enter for default 'ws://localhost:8765'): " SERVER_URL
SERVER_URL=${SERVER_URL:-"ws://localhost:8765"}

read -p "Enter authentication token (or press Enter for default 'secret_token_123'): " AUTH_TOKEN
AUTH_TOKEN=${AUTH_TOKEN:-"secret_token_123"}

# Create a client-specific config file
if [ "$CLIENT_TYPE" = "seeker" ]; then
    # Prompt for video path for seeker clients
    read -p "Enter path to video file for VLC (or press Enter for default): " VIDEO_PATH
    VIDEO_PATH=${VIDEO_PATH:-"/path/to/video.mp4"}
    
    cat > "$INSTALL_DIR/config.py" <<EOF
# Configuration file for Muppet client
CLIENT_TYPE = "$CLIENT_TYPE"
# Authentication token
AUTH_TOKEN = "$AUTH_TOKEN"
# WebSocket server URL
SERVER_URL = "$SERVER_URL"
# VLC connection settings
VLC_HOST = "localhost"
VLC_PORT = 4212
# Path to video file for VLC
VIDEO_PATH = "$VIDEO_PATH"
EOF
else
    # Basic config for switcher clients
    cat > "$INSTALL_DIR/config.py" <<EOF
# Configuration file for Muppet client
CLIENT_TYPE = "$CLIENT_TYPE"
# Authentication token
AUTH_TOKEN = "$AUTH_TOKEN"
# WebSocket server URL
SERVER_URL = "$SERVER_URL"
EOF
fi

# Install required packages
"$INSTALL_DIR/venv/bin/pip" install websockets

# Create systemd service
# Service configuration is the same for both client types since all parameters are in config.py
cat > "/etc/systemd/system/muppet-client.service" <<EOF
[Unit]
Description=Muppet $CLIENT_TYPE Client
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$INSTALL_DIR
Environment=DISPLAY=:0
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/client.py --type $CLIENT_TYPE
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable muppet-client.service
systemctl start muppet-client.service

echo "Muppet $CLIENT_TYPE client has been installed and started."
echo "Check status with: systemctl status muppet-client.service"
