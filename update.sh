#!/bin/bash

set -e

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# if git changes exist, request confirmation
if [ -n "$(git status --porcelain)" ]; then
    read -p "Git changes exist. Are you sure you want to continue? (Y/n): " confirm
    # if y or empty, continue
    if [ "$confirm" != "n"  ]; then
        echo "Update aborted."
        exit 1
    fi

    echo "Resetting git changes..."
    git reset --hard
fi

echo "Pulling latest changes..."
git pull

INSTALL_DIR="/opt/muppet"

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Muppet installation not found at $INSTALL_DIR. Please run install.sh first." >&2
    exit 1
fi

echo "Stopping muppet-client.service..."
systemctl stop muppet-client.service

echo "Updating client script..."
cp "$(dirname "$0")/client.py" "$INSTALL_DIR/"

echo "Updating dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade websockets

echo "Starting muppet-client.service..."
systemctl start muppet-client.service

echo "Muppet client has been updated and restarted."
echo "Check status with: systemctl status muppet-client.service"
