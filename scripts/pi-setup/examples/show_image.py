#!/usr/bin/env python3
"""
Show an image file on the Pimoroni Display HAT Mini (320x240).

Usage:
    python3 show_image.py <path_to_image>
    python3 show_image.py photo.jpg
"""

import sys
from displayhatmini import DisplayHATMini
from PIL import Image

WIDTH = DisplayHATMini.WIDTH    # 320
HEIGHT = DisplayHATMini.HEIGHT  # 240

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <image_file>")
    sys.exit(1)

image_path = sys.argv[1]

# Load and resize to fit the display, preserving aspect ratio
img = Image.open(image_path).convert("RGB")
img.thumbnail((WIDTH, HEIGHT), Image.LANCZOS)

# Centre on a black canvas
canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
x = (WIDTH - img.width) // 2
y = (HEIGHT - img.height) // 2
canvas.paste(img, (x, y))

display = DisplayHATMini(canvas)
display.set_backlight(1.0)
display.display()

print(f"Showing {image_path} ({img.width}x{img.height}). Ctrl+C to exit.")

try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    display.set_backlight(0)
    print("Done.")
