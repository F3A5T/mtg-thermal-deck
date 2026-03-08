#!/usr/bin/env bash
# setup.sh — First-time setup for MTG Console on Raspberry Pi OS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== MTG Console Setup ==="
echo "Repo: $REPO_DIR"
echo ""

# -----------------------------------------------------------------------
# System packages
# -----------------------------------------------------------------------
echo "[1/5] Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y \
  python3-pip \
  python3-venv \
  python3-dev \
  libopenjp2-7 \
  libtiff6 \
  fonts-dejavu-core \
  git

# -----------------------------------------------------------------------
# Hardware interfaces (SPI for display, serial for printer)
# -----------------------------------------------------------------------
echo "[2/5] Enabling hardware interfaces..."
sudo raspi-config nonint do_spi 0        # enable SPI
sudo raspi-config nonint do_serial_hw 0  # enable UART hardware
sudo raspi-config nonint do_serial_cons 1 # disable serial console (keep UART free for printer)

echo "  SPI and UART enabled."

# -----------------------------------------------------------------------
# User groups (needed for GPIO/SPI access without sudo)
# -----------------------------------------------------------------------
echo "[3/5] Adding user to hardware groups..."
sudo usermod -aG gpio,spi,i2c,dialout "$USER"
echo "  Added $USER to gpio, spi, i2c, dialout."

# -----------------------------------------------------------------------
# Python venv
# -----------------------------------------------------------------------
echo "[4/5] Setting up Python virtual environment..."
cd "$REPO_DIR"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# -----------------------------------------------------------------------
# Data directory
# -----------------------------------------------------------------------
mkdir -p data/cards

# -----------------------------------------------------------------------
# Systemd service
# -----------------------------------------------------------------------
echo "[5/5] Installing systemd service..."
# Patch the service file with the actual home dir and user before installing
SERVICE_SRC="$SCRIPT_DIR/mtg-console.service"
SERVICE_DST=/etc/systemd/system/mtg-console.service

sudo sed \
  -e "s|User=dev|User=$USER|g" \
  -e "s|Group=dev|Group=$USER|g" \
  -e "s|/home/dev/mtg-console|$REPO_DIR|g" \
  "$SERVICE_SRC" | sudo tee "$SERVICE_DST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable mtg-console
echo "  Service installed and enabled."

# -----------------------------------------------------------------------
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Fetch cards:  source .venv/bin/activate && python scripts/fetch_cards.py"
echo "  2. Reboot:       sudo reboot"
echo "     (service starts automatically on boot)"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status mtg-console   # check status"
echo "  sudo journalctl -u mtg-console -f   # live logs"
echo "  sudo systemctl restart mtg-console  # restart"
echo "  sudo systemctl stop mtg-console     # stop"
