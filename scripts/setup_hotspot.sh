#!/usr/bin/env bash
# Configure simultaneous AP+STA on Raspberry Pi.
#
# wlan0 → stays connected to your router (SSH, internet)
# uap0  → virtual AP interface running the hotspot
#
# Run once on the Pi: bash scripts/setup_hotspot.sh [SSID] [PASSWORD]
#
# After running, connect to:
#   SSID:     mtg-console  (or your chosen SSID)
#   Password: mtgprinter   (or your chosen password)
#   Web UI:   http://10.42.0.1:5000

set -e

SSID="${1:-mtg-console}"
PASSWORD="${2:-mtgprinter}"
CON_NAME="mtg-hotspot"

# ---------------------------------------------------------------------------
# 1. Systemd service to create the uap0 virtual interface at boot
# ---------------------------------------------------------------------------
echo "Installing uap0 systemd service..."
cat > /tmp/uap0.service << 'EOF'
[Unit]
Description=Create uap0 virtual WiFi AP interface
Before=NetworkManager.service
After=sys-subsystem-net-devices-wlan0.device

[Service]
Type=oneshot
ExecStart=/sbin/iw dev wlan0 interface add uap0 type __ap
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo cp /tmp/uap0.service /etc/systemd/system/uap0.service
sudo systemctl daemon-reload
sudo systemctl enable uap0.service

# Create the interface now without rebooting
if ! ip link show uap0 &>/dev/null; then
    echo "Creating uap0 interface..."
    sudo iw dev wlan0 interface add uap0 type __ap
fi
sudo ip link set uap0 up

# ---------------------------------------------------------------------------
# 2. Create the NetworkManager hotspot connection on uap0
# ---------------------------------------------------------------------------
echo "Creating NetworkManager hotspot connection on uap0..."

# Remove any existing profile with the same name
sudo nmcli connection delete "$CON_NAME" 2>/dev/null || true

sudo nmcli connection add \
    type wifi \
    ifname uap0 \
    con-name "$CON_NAME" \
    ssid "$SSID" \
    wifi.mode ap \
    wifi.band bg \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD" \
    ipv4.method shared \
    connection.autoconnect yes

echo "Bringing up hotspot..."
sudo nmcli connection up "$CON_NAME"

# ---------------------------------------------------------------------------
# 3. Allow app to toggle hotspot without password prompt
# ---------------------------------------------------------------------------
SUDOERS_LINE="dev ALL=(ALL) NOPASSWD: /usr/bin/nmcli"
SUDOERS_FILE="/etc/sudoers.d/mtg-nmcli"

if ! sudo grep -qF "$SUDOERS_LINE" "$SUDOERS_FILE" 2>/dev/null; then
    echo "Adding sudoers rule for nmcli..."
    echo "$SUDOERS_LINE" | sudo tee "$SUDOERS_FILE" > /dev/null
    sudo chmod 440 "$SUDOERS_FILE"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "Done. Your Pi now runs both connections simultaneously:"
echo ""
echo "  wlan0 → your router (SSH / internet unchanged)"
echo "  uap0  → hotspot"
echo ""
echo "  Hotspot SSID : $SSID"
echo "  Password     : $PASSWORD"
echo "  Pi IP        : 10.42.0.1"
echo "  Web UI       : http://10.42.0.1:5000"
echo ""
echo "Note: the AP and your router must be on the same WiFi channel."
echo "If clients can't connect, check: sudo iw dev wlan0 info"
echo "and set wifi.channel in the NM connection to match."
echo ""
echo "To stop the hotspot:"
echo "  sudo nmcli connection down $CON_NAME"
echo "To restart it:"
echo "  sudo nmcli connection up $CON_NAME"
