#!/bin/bash
# Setup script for Pimoroni Display HAT Mini on Raspberry Pi Zero W2
# Display: 2.0" 320x240 IPS LCD (ST7789V2), SPI interface
# https://shop.pimoroni.com/products/display-hat-mini

set -e

echo "=== Pimoroni Display HAT Mini Setup ==="
echo ""

# --- 1. System update ---
echo "[1/5] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# --- 2. Enable SPI interface ---
echo "[2/5] Enabling SPI interface..."
sudo raspi-config nonint do_spi 0
echo "SPI enabled."

# Verify SPI is enabled
if ls /dev/spidev* &>/dev/null; then
    echo "SPI device(s) found: $(ls /dev/spidev*)"
else
    echo "WARNING: No SPI devices found. You may need to reboot first."
fi

# --- 3. Install Python dependencies ---
echo "[3/5] Installing Python dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-pil \
    python3-numpy \
    python3-rpi.gpio \
    python3-spidev \
    fonts-dejavu

# --- 4. Install the Pimoroni Display HAT Mini library ---
echo "[4/5] Installing displayhatmini Python library..."

# Use pip with --break-system-packages for newer Raspberry Pi OS (Bookworm+)
# or without it for Bullseye and older
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
OS_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")

echo "Detected Python $PYTHON_VERSION on $OS_CODENAME"

if [[ "$OS_CODENAME" == "bookworm" ]] || python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    pip3 install displayhatmini st7789 --break-system-packages
else
    pip3 install displayhatmini st7789
fi

# --- 5. Verify installation ---
echo "[5/5] Verifying installation..."
python3 -c "import displayhatmini; print('displayhatmini library OK')"
python3 -c "from PIL import Image; print('Pillow (PIL) OK')"

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "GPIO pin reference for Display HAT Mini:"
echo "  LCD SPI MOSI  : GPIO 10 (Pin 19)"
echo "  LCD SPI SCLK  : GPIO 11 (Pin 23)"
echo "  LCD SPI CS    : GPIO  7 (Pin 26)"
echo "  LCD DC        : GPIO  9 (Pin 21)"
echo "  LCD Backlight : GPIO 13 (Pin 33)"
echo "  Button A      : GPIO  5 (Pin 29)"
echo "  Button B      : GPIO  6 (Pin 31)"
echo "  Button X      : GPIO 16 (Pin 36)"
echo "  Button Y      : GPIO 24 (Pin 18)"
echo "  LED Red       : GPIO 17 (Pin 11)"
echo "  LED Green     : GPIO 27 (Pin 13)"
echo "  LED Blue      : GPIO 22 (Pin 15)"
echo ""
echo "Next steps:"
echo "  1. Reboot if SPI was just enabled: sudo reboot"
echo "  2. Run example: python3 examples/hello_display.py"
echo "  3. Run button test: python3 examples/buttons_and_led.py"
