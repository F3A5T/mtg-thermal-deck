#!/usr/bin/env bash
# Install and enable pisugar-server on the Raspberry Pi.
# Run once: bash scripts/setup_pisugar.sh
#
# After running, battery level and charging state are available at:
#   echo "get battery" | nc -q 1 127.0.0.1 8423

set -e

echo "Installing pisugar-server..."
curl -s https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash

echo "Enabling pisugar-server service..."
sudo systemctl enable pisugar-server
sudo systemctl start pisugar-server

echo ""
echo "Verifying..."
sleep 2
BAT=$(echo "get battery" | nc -q 1 127.0.0.1 8423 2>/dev/null || echo "no response")
CHG=$(echo "get battery_charging" | nc -q 1 127.0.0.1 8423 2>/dev/null || echo "no response")
echo "  $BAT"
echo "  $CHG"
echo ""
echo "Done. The mtg-console app will now show battery level on the Info screen and web UI."
