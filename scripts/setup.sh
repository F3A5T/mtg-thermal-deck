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
echo "[1/4] Installing system packages..."
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
echo "[2/4] Enabling hardware interfaces..."
sudo raspi-config nonint do_spi 0        # enable SPI
sudo raspi-config nonint do_serial_hw 0  # enable UART hardware
sudo raspi-config nonint do_serial_cons 1 # disable serial console (keep UART free for printer)

echo "  SPI and UART enabled."

# -----------------------------------------------------------------------
# Python venv
# -----------------------------------------------------------------------
echo "[3/4] Setting up Python virtual environment..."
cd "$REPO_DIR"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# -----------------------------------------------------------------------
# Data directory
# -----------------------------------------------------------------------
echo "[4/4] Creating data directories..."
mkdir -p data/cards

# -----------------------------------------------------------------------
# Optional: systemd service
# -----------------------------------------------------------------------
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Reboot:         sudo reboot"
echo "  2. Fetch cards:    source .venv/bin/activate && python scripts/fetch_cards.py"
echo "  3. Run app:        python run.py"
echo ""
echo "To install as a systemd service (auto-start on boot):"
echo "  sudo cp $SCRIPT_DIR/mtg-console.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now mtg-console"
