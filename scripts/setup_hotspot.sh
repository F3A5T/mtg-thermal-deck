#!/usr/bin/env bash
# Configure the Pi as a WiFi hotspot using NetworkManager.
# Run once on the Pi: bash scripts/setup_hotspot.sh
#
# After running, connect to:
#   SSID:     mtg-console
#   Password: mtgprinter
#   Web UI:   http://10.42.0.1:5000

set -e

SSID="${1:-mtg-console}"
PASSWORD="${2:-mtgprinter}"
CON_NAME="mtg-hotspot"

echo "Creating hotspot '$SSID' ..."
sudo nmcli device wifi hotspot \
    ifname wlan0 \
    ssid "$SSID" \
    password "$PASSWORD" \
    con-name "$CON_NAME"

echo "Enabling autoconnect on boot ..."
sudo nmcli connection modify "$CON_NAME" connection.autoconnect yes

echo ""
echo "Done. Hotspot details:"
echo "  SSID     : $SSID"
echo "  Password : $PASSWORD"
echo "  Pi IP    : 10.42.0.1"
echo "  Web UI   : http://10.42.0.1:5000"
echo ""
echo "To disable and restore normal WiFi:"
echo "  sudo nmcli connection down $CON_NAME"
echo "  sudo nmcli connection up <your-wifi-ssid>"
