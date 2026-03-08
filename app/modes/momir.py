"""
Momir Basic mode.

A — increment CMC
B — decrement CMC
X — print a random creature at the current CMC
Y — handled by AppState (cycle to next mode)
"""

import logging
import random
import threading
from typing import TYPE_CHECKING, Optional

from PIL import ImageDraw, ImageFont

from .base import BaseMode

if TYPE_CHECKING:
    from app.card_manager import Card, CardManager
    from app.printer import Printer

logger = logging.getLogger(__name__)

# Font paths — DejaVu ships with most Raspberry Pi OS images
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        return None


def _best_font(size: int):
    for p in _FONT_PATHS:
        f = _load_font(p, size)
        if f:
            return f
    return ImageFont.load_default()


# Pre-build font objects once (sizes used in render)
_FONT_TITLE = _best_font(16)
_FONT_CMC = _best_font(80)
_FONT_MED = _best_font(16)
_FONT_SM = _best_font(13)

# Palette
_GOLD = (212, 175, 55)
_WHITE = (255, 255, 255)
_GRAY = (130, 130, 140)
_RED = (220, 60, 60)
_GREEN = (80, 200, 100)
_DIM = (60, 60, 75)


class MomirMode(BaseMode):
    MAX_CMC = 16
    MIN_CMC = 0

    def __init__(self, card_manager: "CardManager", printer: "Printer"):
        self.card_manager = card_manager
        self.printer = printer
        self.cmc: int = 3
        self.last_card: Optional["Card"] = None
        self.status_message: str = ""
        self._printing: bool = False

    # ------------------------------------------------------------------
    # BaseMode interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Momir Basic"

    def handle_button(self, button: str) -> None:
        if self._printing:
            return  # block input during print

        if button == "A":
            self.cmc = min(self.MAX_CMC, self.cmc + 1)
            self.status_message = ""
        elif button == "B":
            self.cmc = max(self.MIN_CMC, self.cmc - 1)
            self.status_message = ""
        elif button == "X":
            self._trigger_print()
        # Y is handled externally by AppState

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        # --- Mode title ---
        draw.text((10, 8), "MOMIR BASIC", font=_FONT_TITLE, fill=_GOLD)

        # --- Big CMC number, centred ---
        cmc_str = str(self.cmc)
        bbox = draw.textbbox((0, 0), cmc_str, font=_FONT_CMC)
        cmc_w = bbox[2] - bbox[0]
        draw.text(((width - cmc_w) // 2, 36), cmc_str, font=_FONT_CMC, fill=_WHITE)

        # --- Card count ---
        count = self.card_manager.get_card_count_at_cmc(self.cmc)
        count_str = f"{count} card{'s' if count != 1 else ''}"
        bbox = draw.textbbox((0, 0), count_str, font=_FONT_SM)
        count_w = bbox[2] - bbox[0]
        color = _GREEN if count > 0 else _RED
        draw.text(((width - count_w) // 2, 126), count_str, font=_FONT_SM, fill=color)

        # --- Status / last card ---
        if self.status_message:
            color = _RED if ("fail" in self.status_message.lower() or "no card" in self.status_message.lower()) else _WHITE
            draw.text((8, 148), self.status_message[:38], font=_FONT_SM, fill=color)
        elif self.last_card:
            name = self.last_card.name
            if len(name) > 30:
                name = name[:27] + "..."
            draw.text((8, 148), f"Last: {name}", font=_FONT_SM, fill=_GRAY)

        # --- Divider ---
        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)

        # --- Button hints ---
        hints = [
            (0, "A:+CMC"),
            (width // 4, "B:-CMC"),
            (width // 2, "X:PRINT"),
            (3 * width // 4, "Y:MENU"),
        ]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    def get_status(self) -> dict:
        return {
            "mode": self.name,
            "cmc": self.cmc,
            "card_count": self.card_manager.get_card_count_at_cmc(self.cmc),
            "printing": self._printing,
            "last_card": self.last_card.to_dict() if self.last_card else None,
            "status_message": self.status_message,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trigger_print(self):
        cards = self.card_manager.get_cards_at_cmc(self.cmc)
        if not cards:
            self.status_message = f"No cards at CMC {self.cmc}!"
            return

        card = random.choice(cards)
        self._printing = True
        self.status_message = "Printing..."

        def _do():
            success = self.printer.print_card(card)
            self.last_card = card
            self.status_message = f"Printed: {card.name}" if success else "Print failed!"
            self._printing = False

        threading.Thread(target=_do, daemon=True, name="print-job").start()
