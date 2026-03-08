"""
Token Printer mode.

Displays a scrollable list of tokens sorted alphabetically by name,
then by power/toughness. Navigate and print just like Momir Basic.

Normal mode:
  A       — next token
  B       — previous token
  X       — print selected token
  X_HOLD  — enter letter-select mode
  Y       — handled by AppState (cycle mode)

Letter-select mode:
  A       — next letter (that has tokens)
  B       — previous letter
  X       — jump to first token of selected letter, return to normal
  X_HOLD  — cancel, return to normal without jumping
  Y       — handled by AppState (cycle mode)
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


_FONT_LABEL  = _best_font(14)
_FONT_NAME   = _best_font(26)
_FONT_PT     = _best_font(36)
_FONT_LETTER = _best_font(80)
_FONT_SM     = _best_font(13)

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

        # Letter-select state
        self._letter_mode: bool = False
        self._letters: list[str] = []        # letters that have at least one token
        self._letter_index: dict[str, int] = {}  # letter -> first token index
        self._cur_letter_pos: int = 0        # position in self._letters

        self._load()

    def _load(self):
        if not self.tokens_path.exists():
            logger.warning("Token index not found at %s — run fetch_cards.py --tokens-only", self.tokens_path)
            return
        with open(self.tokens_path, encoding="utf-8") as f:
            raw = json.load(f)
        self._tokens = [Token(t) for t in raw]
        self._build_letter_index()
        logger.info("Loaded %d tokens", len(self._tokens))

    def _build_letter_index(self):
        self._letter_index = {}
        for i, t in enumerate(self._tokens):
            ch = t.name[0].upper() if t.name else "?"
            if ch not in self._letter_index:
                self._letter_index[ch] = i
        self._letters = sorted(self._letter_index.keys())

    def on_activate(self) -> None:
        """Enter letter filter automatically when switching to this mode."""
        self._show_help = False
        if self._letters:
            if self._tokens:
                cur_letter = self._tokens[self._index].name[0].upper()
                self._cur_letter_pos = self._letters.index(cur_letter) if cur_letter in self._letters else 0
            self._letter_mode = True

    def reload(self):
        self._tokens.clear()
        self._index = 0
        self._letter_mode = False
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
        if button == "Y_HOLD_FIRST":
            self._toggle_help()
            return
        if self._show_help:
            return
        if self._letter_mode:
            self._handle_letter_mode(button)
        else:
            self._handle_browse_mode(button)

    def help_lines(self) -> list:
        return [
            ("A", "Next token"),
            ("B", "Previous token"),
            ("X", "Print selected token"),
            ("Hold X", "Enter letter filter"),
            ("Y", "Next mode"),
            ("Hold Y", "This help"),
            ("  In letter filter:", ""),
            ("A / B", "Cycle letters"),
            ("X", "Jump to letter"),
            ("Hold X", "Cancel filter"),
        ]

    def _handle_browse_mode(self, button: str) -> None:
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
        elif button == "X_HOLD_FIRST":
            # Enter letter-select mode
            if self._letters:
                cur_letter = self._tokens[self._index].name[0].upper()
                if cur_letter in self._letters:
                    self._cur_letter_pos = self._letters.index(cur_letter)
                else:
                    self._cur_letter_pos = 0
                self._letter_mode = True
                self.status_message = ""

    def _handle_letter_mode(self, button: str) -> None:
        if button == "A":
            self._cur_letter_pos = (self._cur_letter_pos + 1) % len(self._letters)
        elif button == "B":
            self._cur_letter_pos = (self._cur_letter_pos - 1) % len(self._letters)
        elif button == "X":
            # Confirm — jump to first token for this letter
            letter = self._letters[self._cur_letter_pos]
            self._index = self._letter_index[letter]
            self._letter_mode = False
            self.status_message = ""
        elif button == "X_HOLD_FIRST":
            # Cancel — return without jumping (first hold only, ignore repeats)
            self._letter_mode = False
            self.status_message = ""

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        if self._show_help:
            self._render_help_overlay(draw, width, height)
        elif self._letter_mode:
            self._render_letter_select(draw, width, height)
        else:
            self._render_browse(draw, width, height)

    def _render_browse(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.text((10, 8), "TOKEN PRINTER", font=_FONT_LABEL, fill=_GOLD)

        if not self._tokens:
            msg = "No tokens — run fetch_cards.py"
            bbox = draw.textbbox((0, 0), msg, font=_FONT_SM)
            w = bbox[2] - bbox[0]
            draw.text(((width - w) // 2, height // 2), msg, font=_FONT_SM, fill=_RED)
            return

        token = self._tokens[self._index]

        draw.text((10, 32), token.name, font=_FONT_NAME, fill=_WHITE)

        if token.pt:
            bbox = draw.textbbox((0, 0), token.pt, font=_FONT_PT)
            pt_w = bbox[2] - bbox[0]
            draw.text(((width - pt_w) // 2, 68), token.pt, font=_FONT_PT, fill=_GOLD)

        tl = token.type_line
        if len(tl) > 36:
            tl = tl[:33] + "..."
        draw.text((10, 120), tl, font=_FONT_SM, fill=_GRAY)

        if self.status_message:
            color = _RED if "fail" in self.status_message.lower() else _WHITE
            draw.text((10, 140), self.status_message[:38], font=_FONT_SM, fill=color)
        elif self.last_token:
            n = self.last_token.name
            if len(n) > 28:
                n = n[:25] + "..."
            draw.text((10, 140), f"Last: {n}", font=_FONT_SM, fill=_GRAY)

        pos = f"{self._index + 1} / {len(self._tokens)}"
        bbox = draw.textbbox((0, 0), pos, font=_FONT_SM)
        draw.text((width - bbox[2] - 8, 140), pos, font=_FONT_SM, fill=_GRAY)

        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [(0, "A:NEXT"), (width // 4, "B:PREV"), (width // 2, "X:PRINT"), (3 * width // 4, "HX:FILTER")]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    def _render_letter_select(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.text((10, 8), "TOKEN PRINTER", font=_FONT_LABEL, fill=_GOLD)

        if not self._letters:
            return

        letter = self._letters[self._cur_letter_pos]

        # Big letter centred
        bbox = draw.textbbox((0, 0), letter, font=_FONT_LETTER)
        lw = bbox[2] - bbox[0]
        draw.text(((width - lw) // 2, 30), letter, font=_FONT_LETTER, fill=_WHITE)

        # First token name preview
        first_idx = self._letter_index[letter]
        preview = self._tokens[first_idx].name
        if len(preview) > 28:
            preview = preview[:25] + "..."
        bbox = draw.textbbox((0, 0), preview, font=_FONT_SM)
        pw = bbox[2] - bbox[0]
        draw.text(((width - pw) // 2, 128), preview, font=_FONT_SM, fill=_GRAY)

        # Letter position counter
        pos = f"{self._cur_letter_pos + 1} / {len(self._letters)}"
        bbox = draw.textbbox((0, 0), pos, font=_FONT_SM)
        draw.text((width - bbox[2] - 8, 148), pos, font=_FONT_SM, fill=_DIM)

        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [(0, "A:NEXT"), (width // 4, "B:PREV"), (width // 2, "X:JUMP"), (3 * width // 4, "HOLD:BACK")]
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
            "letter_mode": self._letter_mode,
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
