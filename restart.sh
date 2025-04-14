#!/bin/bash

set -e

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# Restart the service
systemctl restart muppet-client.service

echo "Muppet client service restarted."
echo "Check status with: systemctl status muppet-client.service"
