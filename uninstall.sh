#!/bin/bash

set -e

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# Stop and disable the service
systemctl stop muppet-client.service || true
systemctl disable muppet-client.service || true

# Remove service file
rm -f /etc/systemd/system/muppet-client.service
systemctl daemon-reload

# Remove installation directory
rm -rf /opt/muppet

echo "Muppet client has been uninstalled."
