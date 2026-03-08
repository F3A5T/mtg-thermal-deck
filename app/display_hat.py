"""
Wrapper around the Pimoroni Display HAT Mini.

Hardware: 320x240 IPS LCD (ST7789 via SPI) + 4 buttons (A/B/X/Y).
Falls back to a no-op mock when the library isn't available (dev machines).

Button layout on the HAT:
  A — top-left      B — bottom-left
  X — top-right     Y — bottom-right

Threading note: displayhatmini is NOT thread-safe. All display operations
(rendering and button reads) must happen on the same thread. Use poll_buttons()
and update() from the same loop — see app/__init__.py.
"""

import logging
import time
from typing import Callable, Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

BUTTON_A = "A"
BUTTON_B = "B"
BUTTON_X = "X"
BUTTON_Y = "Y"


class DisplayHat:
    WIDTH = 320
    HEIGHT = 240

    def __init__(self, mock: bool = False, brightness: float = 0.8):
        self.mock = mock
        self.brightness = brightness
        self._display = None
        self._callback: Optional[Callable[[str], None]] = None
        self._prev_buttons: dict = {}

        if not mock:
            self._init_hardware()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_hardware(self):
        try:
            from displayhatmini import DisplayHATMini

            self.WIDTH = DisplayHATMini.WIDTH
            self.HEIGHT = DisplayHATMini.HEIGHT

            # Single persistent buffer — draw into this every frame, never replace it.
            # The DisplayHATMini display() method reads from whatever image it was
            # initialised with; reassigning display.image doesn't work reliably.
            self._buf = Image.new("RGB", (self.WIDTH, self.HEIGHT))
            self._display = DisplayHATMini(self._buf)
            # set_backlight in non-PWM mode calls st7789.set_backlight(int(value))
            # so anything < 1.0 becomes 0 (off). Always pass 1 to keep it on.
            self._display.set_backlight(1)

            # Build button map for polling
            self._hw_buttons = {
                DisplayHATMini.BUTTON_A: BUTTON_A,
                DisplayHATMini.BUTTON_B: BUTTON_B,
                DisplayHATMini.BUTTON_X: BUTTON_X,
                DisplayHATMini.BUTTON_Y: BUTTON_Y,
            }
            self._prev_buttons = {btn: False for btn in self._hw_buttons}
            self._press_start: dict  = {btn: None for btn in self._hw_buttons}
            self._last_repeat: dict  = {btn: None for btn in self._hw_buttons}

            logger.info("Display HAT Mini initialised (%dx%d)", self.WIDTH, self.HEIGHT)
        except ImportError:
            logger.warning("displayhatmini library not found — using mock display")
            self.mock = True
        except Exception as exc:
            logger.error("Display init failed: %s", exc)
            self.mock = True

    # ------------------------------------------------------------------
    # Public API — call both from the SAME thread
    # ------------------------------------------------------------------

    def set_button_callback(self, callback: Callable[[str], None]):
        self._callback = callback

    LONG_PRESS_S   = 0.8   # seconds before first hold event fires
    REPEAT_S       = 0.25  # seconds between repeated hold events while held

    def poll_buttons(self):
        """Read buttons and fire callback for any newly pressed ones.

        Fires label (e.g. "X") on rising edge (short press).
        After LONG_PRESS_S of continuous holding, fires label + "_HOLD"
        (e.g. "X_HOLD") and then repeats every REPEAT_S for as long as
        the button stays held — useful for fast life-total scrolling.
        Must be called from the same thread as update().
        """
        if self.mock or not self._display:
            return
        now = time.monotonic()
        for hw_btn, label in self._hw_buttons.items():
            pressed = self._display.read_button(hw_btn)
            was_pressed = self._prev_buttons[hw_btn]

            if pressed and not was_pressed:
                # Rising edge — start timing
                # Y fires on release so hold can be detected first; all others fire now
                self._press_start[hw_btn] = now
                self._last_repeat[hw_btn] = None
                if label != BUTTON_Y and self._callback:
                    self._callback(label)

            elif pressed and was_pressed:
                # Held — fire _HOLD_FIRST once at threshold, then _HOLD repeatedly
                start = self._press_start.get(hw_btn)
                if start and now - start >= self.LONG_PRESS_S:
                    last = self._last_repeat[hw_btn]
                    if last is None or now - last >= self.REPEAT_S:
                        is_first = last is None
                        self._last_repeat[hw_btn] = now
                        if self._callback:
                            self._callback(label + ("_HOLD_FIRST" if is_first else "_HOLD"))

            else:
                # Released — fire Y now only if it was a short press (no hold fired)
                if label == BUTTON_Y and self._last_repeat[hw_btn] is None:
                    if self._callback:
                        self._callback(label)
                self._press_start[hw_btn] = None
                self._last_repeat[hw_btn] = None

            self._prev_buttons[hw_btn] = pressed

    def update(self, image: Image.Image):
        """Paste rendered frame into the persistent buffer and push to display."""
        if not self.mock and self._display:
            try:
                self._buf.paste(image)
                self._display.display()
            except Exception as exc:
                logger.error("Display update error: %s", exc)

    def blank_canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        """Return a fresh off-screen image to draw into this frame."""
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), (18, 18, 28))
        return img, ImageDraw.Draw(img)

    def shutdown(self):
        """Turn off backlight and clear the screen on exit."""
        if not self.mock and self._display:
            try:
                self._buf.paste((0, 0, 0), [0, 0, self.WIDTH, self.HEIGHT])
                self._display.display()
                self._display.set_backlight(0)
            except Exception:
                pass
