#!/usr/bin/env python3
"""
Hello Display - Basic text rendering on Pimoroni Display HAT Mini
Display: 2.0" 320x240 IPS LCD (ST7789V2)
"""

from displayhatmini import DisplayHATMini
from PIL import Image, ImageDraw, ImageFont

WIDTH = DisplayHATMini.WIDTH    # 320
HEIGHT = DisplayHATMini.HEIGHT  # 240

# Create a blank image
image = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(image)

# Try to load a nicer font, fall back to default
try:
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
except IOError:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

# Draw background gradient (simple horizontal bands)
for y in range(HEIGHT):
    r = int(y / HEIGHT * 50)
    draw.line([(0, y), (WIDTH, y)], fill=(r, 0, 40))

# Draw text
draw.text((WIDTH // 2, 80), "Display HAT Mini", font=font_large, fill=(255, 255, 255), anchor="mm")
draw.text((WIDTH // 2, 130), "Pi Zero W2 Ready!", font=font_small, fill=(100, 200, 255), anchor="mm")
draw.text((WIDTH // 2, 165), "320 x 240  ST7789V2", font=font_small, fill=(150, 150, 150), anchor="mm")

# Draw a coloured border
border = 4
draw.rectangle([border, border, WIDTH - border, HEIGHT - border], outline=(0, 180, 255), width=border)

# Initialise the display and show the image
display = DisplayHATMini(image)
display.set_backlight(1.0)  # Full brightness (0.0 – 1.0)
display.display()

print("Image displayed. Press Ctrl+C to exit.")

try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    # Turn off backlight on exit
    display.set_backlight(0)
    print("Done.")
