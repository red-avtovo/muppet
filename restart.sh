#!/bin/bash

set -e

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# Restart the service. Restart command was not always working.
# Stop the service to make sure it's not running
systemctl stop muppet-client.service
# Start the service
systemctl start muppet-client.service

echo "Muppet client service restarted."
echo "Check status with: systemctl status muppet-client.service"
