"""
Token Printer mode.

Displays a scrollable list of tokens sorted alphabetically by name,
then by power/toughness. Navigate and print just like Momir Basic.

A — next token
B — previous token
X — print selected token
Y — handled by AppState (cycle mode)
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from PIL import ImageDraw, ImageFont

from .base import BaseMode

logger = logging.getLogger(__name__)

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _best_font(size: int):
    for p in _FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


_FONT_LABEL = _best_font(14)
_FONT_NAME  = _best_font(26)
_FONT_PT    = _best_font(36)
_FONT_SM    = _best_font(13)

_GOLD  = (212, 175, 55)
_WHITE = (255, 255, 255)
_GRAY  = (130, 130, 140)
_RED   = (220, 60, 60)
_DIM   = (60, 60, 75)


class Token:
    # These allow Token to pass through Printer.print_card duck typing
    cmc = None
    mana_cost = None

    def __init__(self, data: dict):
        self.id         = data.get("id", "")
        self.name       = data.get("name", "Unknown")
        self.type_line  = data.get("type_line", "")
        self.power      = data.get("power")
        self.toughness  = data.get("toughness")
        self.image_path = data.get("image_path")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type_line": self.type_line,
            "power": self.power,
            "toughness": self.toughness,
            "image_path": self.image_path,
        }

    def to_list_item(self, index: int) -> dict:
        """Lightweight representation for the web token list."""
        return {
            "index": index,
            "name": self.name,
            "power": self.power,
            "toughness": self.toughness,
        }

    @property
    def pt(self) -> Optional[str]:
        if self.power is not None and self.toughness is not None:
            return f"{self.power}/{self.toughness}"
        return None


class TokenMode(BaseMode):

    def __init__(self, tokens_path: str, printer):
        self.tokens_path = Path(tokens_path)
        self.printer = printer
        self._tokens: list[Token] = []
        self._index: int = 0
        self.last_token: Optional[Token] = None
        self.status_message: str = ""
        self._printing: bool = False
        self._load()

    def _load(self):
        if not self.tokens_path.exists():
            logger.warning("Token index not found at %s — run fetch_cards.py --tokens-only", self.tokens_path)
            return
        with open(self.tokens_path, encoding="utf-8") as f:
            raw = json.load(f)
        self._tokens = [Token(t) for t in raw]
        logger.info("Loaded %d tokens", len(self._tokens))

    def reload(self):
        self._tokens.clear()
        self._index = 0
        self._load()

    def goto(self, index: int):
        """Jump to a specific index (used by web UI for letter/search jumps)."""
        if self._tokens:
            self._index = max(0, min(index, len(self._tokens) - 1))
            self.status_message = ""

    def list_items(self) -> list[dict]:
        """Return lightweight list for the web UI (index, name, P/T)."""
        return [t.to_list_item(i) for i, t in enumerate(self._tokens)]

    # ------------------------------------------------------------------
    # BaseMode interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Tokens"

    def handle_button(self, button: str) -> None:
        if self._printing or not self._tokens:
            return
        if button == "A":
            self._index = (self._index + 1) % len(self._tokens)
            self.status_message = ""
        elif button == "B":
            self._index = (self._index - 1) % len(self._tokens)
            self.status_message = ""
        elif button == "X":
            self._trigger_print()

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        # Title
        draw.text((10, 8), "TOKEN PRINTER", font=_FONT_LABEL, fill=_GOLD)

        if not self._tokens:
            msg = "No tokens — run fetch_cards.py"
            bbox = draw.textbbox((0, 0), msg, font=_FONT_SM)
            w = bbox[2] - bbox[0]
            draw.text(((width - w) // 2, height // 2), msg, font=_FONT_SM, fill=_RED)
            return

        token = self._tokens[self._index]

        # Token name — wrap if long
        name = token.name
        draw.text((10, 32), name, font=_FONT_NAME, fill=_WHITE)

        # P/T — large, centred
        if token.pt:
            bbox = draw.textbbox((0, 0), token.pt, font=_FONT_PT)
            pt_w = bbox[2] - bbox[0]
            draw.text(((width - pt_w) // 2, 68), token.pt, font=_FONT_PT, fill=_GOLD)

        # Type line
        tl = token.type_line
        if len(tl) > 36:
            tl = tl[:33] + "..."
        draw.text((10, 120), tl, font=_FONT_SM, fill=_GRAY)

        # Status / last printed
        if self.status_message:
            color = _RED if "fail" in self.status_message.lower() else _WHITE
            draw.text((10, 140), self.status_message[:38], font=_FONT_SM, fill=color)
        elif self.last_token:
            n = self.last_token.name
            if len(n) > 28:
                n = n[:25] + "..."
            draw.text((10, 140), f"Last: {n}", font=_FONT_SM, fill=_GRAY)

        # Position counter
        pos = f"{self._index + 1} / {len(self._tokens)}"
        bbox = draw.textbbox((0, 0), pos, font=_FONT_SM)
        draw.text((width - bbox[2] - 8, 140), pos, font=_FONT_SM, fill=_GRAY)

        # Divider + button hints
        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [(0, "A:NEXT"), (width // 4, "B:PREV"), (width // 2, "X:PRINT"), (3 * width // 4, "Y:MENU")]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    def get_status(self) -> dict:
        token = self._tokens[self._index] if self._tokens else None
        return {
            "mode": self.name,
            "index": self._index,
            "total": len(self._tokens),
            "token": token.to_dict() if token else None,
            "printing": self._printing,
            "last_token": self.last_token.to_dict() if self.last_token else None,
            "status_message": self.status_message,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trigger_print(self):
        if not self._tokens:
            return
        token = self._tokens[self._index]
        self._printing = True
        self.status_message = "Printing..."

        def _do():
            success = self.printer.print_card(token)
            self.last_token = token
            self.status_message = f"Printed: {token.name}" if success else "Print failed!"
            self._printing = False

        threading.Thread(target=_do, daemon=True, name="print-job").start()
