#!/usr/bin/env python3
"""
Button & RGB LED demo for Pimoroni Display HAT Mini

Buttons: A (GPIO 5), B (GPIO 6), X (GPIO 16), Y (GPIO 24)
LED:     R (GPIO 17), G (GPIO 27), B (GPIO 22)

Each button press:
  - Changes the RGB LED colour
  - Updates the on-screen label
"""

import time
from displayhatmini import DisplayHATMini
from PIL import Image, ImageDraw, ImageFont

WIDTH = DisplayHATMini.WIDTH    # 320
HEIGHT = DisplayHATMini.HEIGHT  # 240

BUTTON_COLOURS = {
    DisplayHATMini.BUTTON_A: {"label": "A", "led": (1.0, 0.0, 0.0), "bg": (180, 0, 0)},
    DisplayHATMini.BUTTON_B: {"label": "B", "led": (0.0, 1.0, 0.0), "bg": (0, 180, 0)},
    DisplayHATMini.BUTTON_X: {"label": "X", "led": (0.0, 0.0, 1.0), "bg": (0, 0, 180)},
    DisplayHATMini.BUTTON_Y: {"label": "Y", "led": (1.0, 0.5, 0.0), "bg": (180, 90, 0)},
}

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
except IOError:
    font = ImageFont.load_default()
    font_sm = ImageFont.load_default()


def render(display: DisplayHATMini, label: str, bg: tuple):
    image = Image.new("RGB", (WIDTH, HEIGHT), color=bg)
    draw = ImageDraw.Draw(image)
    draw.text((WIDTH // 2, HEIGHT // 2 - 20), f"Button {label}", font=font,
              fill=(255, 255, 255), anchor="mm")
    draw.text((WIDTH // 2, HEIGHT // 2 + 40), "press A / B / X / Y", font=font_sm,
              fill=(200, 200, 200), anchor="mm")
    display.image = image
    display.display()


# Initial blank screen
image = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 20))
draw = ImageDraw.Draw(image)
draw.text((WIDTH // 2, HEIGHT // 2), "Press a button!", font=font_sm,
          fill=(255, 255, 255), anchor="mm")

display = DisplayHATMini(image)
display.set_backlight(1.0)
display.display()

print("Waiting for button presses. Ctrl+C to quit.")

try:
    while True:
        for btn, info in BUTTON_COLOURS.items():
            if display.read_button(btn):
                r, g, b = info["led"]
                display.set_led(r, g, b)
                render(display, info["label"], info["bg"])
                print(f"Button {info['label']} pressed")
                time.sleep(0.2)   # simple debounce
        time.sleep(0.05)
except KeyboardInterrupt:
    display.set_backlight(0)
    display.set_led(0, 0, 0)
    print("Done.")
