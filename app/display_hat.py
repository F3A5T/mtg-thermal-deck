"""
Wrapper around the Pimoroni Display HAT Mini.

Hardware: 320x240 IPS LCD (ST7789 via SPI) + 4 buttons (A/B/X/Y).
Falls back to a no-op mock when the library isn't available (dev machines).

Button layout on the HAT:
  A — top-left      B — bottom-left
  X — top-right     Y — bottom-right
"""

import logging
import threading
import time
from typing import Callable, Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

BUTTON_A = "A"
BUTTON_B = "B"
BUTTON_X = "X"
BUTTON_Y = "Y"


class DisplayHat:
    # Physical display resolution
    WIDTH = 320
    HEIGHT = 240

    def __init__(self, mock: bool = False, brightness: float = 0.8):
        self.mock = mock
        self.brightness = brightness
        self._display = None
        self._buffer = Image.new("RGB", (self.WIDTH, self.HEIGHT))
        self._callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        if not mock:
            self._init_hardware()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_hardware(self):
        try:
            from displayhatmini import DisplayHATMini

            self._buffer = Image.new("RGB", (DisplayHATMini.WIDTH, DisplayHATMini.HEIGHT))
            self._display = DisplayHATMini(self._buffer)
            self._display.set_backlight(self.brightness)
            self.WIDTH = DisplayHATMini.WIDTH
            self.HEIGHT = DisplayHATMini.HEIGHT
            logger.info("Display HAT Mini initialised (%dx%d)", self.WIDTH, self.HEIGHT)
        except ImportError:
            logger.warning("displayhatmini library not found — using mock display")
            self.mock = True
        except Exception as exc:
            logger.error("Display init failed: %s", exc)
            self.mock = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_button_callback(self, callback: Callable[[str], None]):
        """Register a callback invoked with the button label ('A','B','X','Y')."""
        self._callback = callback

    def start(self):
        """Start the background button-polling thread."""
        self._running = True
        self._thread = threading.Thread(target=self._button_loop, daemon=True, name="display-buttons")
        self._thread.start()

    def stop(self):
        self._running = False

    def update(self, image: Image.Image):
        """Push a PIL Image to the display."""
        self._buffer.paste(image)
        if not self.mock and self._display:
            try:
                self._display.display()
            except Exception as exc:
                logger.error("Display update error: %s", exc)

    def blank_canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        """Return a fresh (image, draw) pair sized to the display."""
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), (18, 18, 28))
        return img, ImageDraw.Draw(img)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _button_loop(self):
        if self.mock:
            return

        try:
            from displayhatmini import DisplayHATMini

            hw_buttons = {
                DisplayHATMini.BUTTON_A: BUTTON_A,
                DisplayHATMini.BUTTON_B: BUTTON_B,
                DisplayHATMini.BUTTON_X: BUTTON_X,
                DisplayHATMini.BUTTON_Y: BUTTON_Y,
            }
            prev: dict[object, bool] = {btn: False for btn in hw_buttons}

            while self._running:
                for hw_btn, label in hw_buttons.items():
                    pressed = self._display.read_button(hw_btn)
                    if pressed and not prev[hw_btn]:
                        if self._callback:
                            self._callback(label)
                    prev[hw_btn] = pressed
                time.sleep(0.05)  # 20 Hz poll

        except Exception as exc:
            logger.error("Button loop crashed: %s", exc, exc_info=True)
