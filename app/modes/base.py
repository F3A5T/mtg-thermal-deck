"""
Abstract base class for console modes.

Each mode controls what the display shows and how buttons behave.
Adding a new mode means subclassing this, then registering the instance
in app/__init__.py.

Hold Y fires Y_HOLD_FIRST (passed through from AppState which only catches
plain "Y"). Call self._toggle_help() from handle_button to show the help
overlay, or use Y_HOLD_FIRST for a custom action (e.g. TokenMode uses it
to enter the letter filter instead).
"""

from abc import ABC, abstractmethod
from PIL import ImageDraw, ImageFont

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_GOLD  = (212, 175, 55)
_WHITE = (255, 255, 255)
_GRAY  = (140, 140, 150)
_DIM   = (60, 60, 75)
_BG    = (10, 10, 20)


def _best_font(size: int):
    for p in _FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


_FONT_HELP_TITLE = _best_font(15)
_FONT_HELP_BODY  = _best_font(13)


class BaseMode(ABC):

    _show_help: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable mode name shown on display and web UI."""

    @abstractmethod
    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        """Draw the mode UI onto the supplied ImageDraw context."""

    @abstractmethod
    def handle_button(self, button: str) -> None:
        """
        React to a physical button press.
        Plain 'Y' is consumed by AppState for mode cycling.
        'Y_HOLD_FIRST' reaches the mode — use it for help or a custom action.
        """

    def get_status(self) -> dict:
        """Return a JSON-serialisable status dict for the web API."""
        return {"mode": self.name}

    def help_lines(self) -> list:
        """Override per mode — return list of (label, description) tuples."""
        return []

    # ------------------------------------------------------------------
    # Shared help overlay
    # ------------------------------------------------------------------

    def _toggle_help(self):
        self._show_help = not self._show_help

    def _render_help_overlay(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        pad = 12
        draw.rectangle([pad, pad, width - pad, height - pad],
                       fill=_BG, outline=_GOLD, width=2)
        draw.text((pad + 10, pad + 8), f"{self.name.upper()} — HOW TO USE",
                  font=_FONT_HELP_TITLE, fill=_GOLD)
        y = pad + 30
        for label, desc in self.help_lines():
            draw.text((pad + 10, y), label, font=_FONT_HELP_BODY, fill=_GOLD)
            bbox = draw.textbbox((0, 0), desc, font=_FONT_HELP_BODY)
            draw.text((width - pad - (bbox[2] - bbox[0]) - 10, y),
                      desc, font=_FONT_HELP_BODY, fill=_WHITE)
            y += 17
            if y > height - pad - 28:
                break
        draw.line([(pad, height - pad - 18), (width - pad, height - pad - 18)],
                  fill=_DIM, width=1)
        draw.text((pad + 10, height - pad - 14), "HOLD Y: CLOSE",
                  font=_FONT_HELP_BODY, fill=_GRAY)
