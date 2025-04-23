#!/bin/bash

set -e

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

echo "Stopping muppet-client.service..."
systemctl stop muppet-client.service || true
echo "Disabling muppet-client.service..."
systemctl disable muppet-client.service || true

echo "Removing service file..."
rm -f /etc/systemd/system/muppet-client.service
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Removing installation directory..."
rm -rf /opt/muppet

echo "Muppet client has been uninstalled."
