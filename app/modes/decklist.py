"""
Decklist mode.

Load a deck from Moxfield or Archidekt (via web UI), then browse and
print cards on-screen.  URL entry is done via the web panel; the on-screen
mode shows the currently-loaded deck.

  A           — next card in deck
  B           — previous card in deck
  X           — print current card (all copies)
  Hold X      — print entire mainboard + commanders
  Y           — handled by AppState (cycle mode)
  Hold Y      — help overlay
"""

import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PIL import ImageDraw, ImageFont

from .base import BaseMode
from app.decklist import DeckCard, PRINT_CATEGORIES

if TYPE_CHECKING:
    from app.card_manager import CardManager
    from app.printer import Printer

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
_FONT_NAME  = _best_font(22)
_FONT_MED   = _best_font(16)
_FONT_SM    = _best_font(13)

_GOLD  = (212, 175, 55)
_WHITE = (255, 255, 255)
_GRAY  = (130, 130, 140)
_RED   = (220, 60, 60)
_GREEN = (80, 200, 100)
_DIM   = (60, 60, 75)


class DecklistMode(BaseMode):

    def __init__(self, card_manager: "CardManager", printer: "Printer", tokens_path: str):
        self.card_manager = card_manager
        self.printer = printer
        self.tokens_path = Path(tokens_path)

        self.deck_name: str = ""
        self._all_cards: list[DeckCard] = []   # full deck including sideboard
        self._found: list[DeckCard] = []        # only found cards, for navigation
        self._index: int = 0

        self._tokens: list = []  # Token objects for name lookup
        self._load_tokens()

        self.status_message: str = ""
        self.last_printed: str = ""
        self._printing: bool = False
        self._print_progress: int = 0   # cards printed so far in print-all
        self._print_total: int = 0      # total to print in print-all

        # Confirm state for print-all
        self._confirm_print_all: bool = False

    # ------------------------------------------------------------------
    # Token loading (for name resolution)
    # ------------------------------------------------------------------

    def _load_tokens(self):
        if not self.tokens_path.exists():
            return
        try:
            with open(self.tokens_path, encoding="utf-8") as f:
                raw = json.load(f)
            # Import here to avoid circular imports
            from app.modes.token import Token
            self._tokens = [Token(t) for t in raw]
        except Exception as exc:
            logger.warning("Could not load tokens for decklist: %s", exc)

    def _token_by_name(self, name: str):
        name_lower = name.lower()
        for t in self._tokens:
            if t.name.lower() == name_lower:
                return t
        return None

    # ------------------------------------------------------------------
    # Deck loading (called from routes)
    # ------------------------------------------------------------------

    def load_deck(self, deck_name: str, raw_cards: list[DeckCard]) -> dict:
        """Resolve card names against local DB and update state."""
        self.deck_name = deck_name
        self._all_cards = raw_cards
        self._index = 0
        self._confirm_print_all = False

        found = not_found = 0
        for dc in raw_cards:
            card = self.card_manager.get_card_by_name(dc.name)
            if card:
                dc.card = card
                dc.found = True
                found += 1
            else:
                token = self._token_by_name(dc.name)
                if token:
                    dc.card = token
                    dc.found = True
                    found += 1
                else:
                    dc.found = False
                    not_found += 1

        self._found = [dc for dc in raw_cards if dc.found]
        self.status_message = f"Loaded: {found} found, {not_found} not found"
        logger.info("Deck '%s': %d/%d cards resolved", deck_name, found, len(raw_cards))
        return self.get_status()

    def reload_tokens(self):
        self._load_tokens()

    # ------------------------------------------------------------------
    # BaseMode interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Decklist"

    def on_activate(self) -> None:
        self._show_help = False
        self._confirm_print_all = False

    def help_lines(self) -> list:
        return [
            ("A", "Next card"),
            ("B", "Previous card"),
            ("X", "Print current card"),
            ("Hold X", "Print entire deck"),
            ("Y", "Next mode"),
            ("Hold Y", "This help"),
        ]

    def handle_button(self, button: str) -> None:
        if button == "Y_HOLD_FIRST":
            self._toggle_help()
            return
        if self._show_help:
            return
        if self._printing:
            return

        if button == "A":
            if self._found:
                self._index = (self._index + 1) % len(self._found)
            self._confirm_print_all = False
            self.status_message = ""
        elif button == "B":
            if self._found:
                self._index = (self._index - 1) % len(self._found)
            self._confirm_print_all = False
            self.status_message = ""
        elif button == "X":
            if self._confirm_print_all:
                self._trigger_print_all()
                self._confirm_print_all = False
            else:
                self._trigger_print_current()
        elif button == "X_HOLD_FIRST":
            if not self._found:
                return
            if self._confirm_print_all:
                self._confirm_print_all = False
                self.status_message = ""
            else:
                self._confirm_print_all = True
                printable = sum(
                    dc.quantity for dc in self._all_cards
                    if dc.found and dc.category in PRINT_CATEGORIES
                )
                self.status_message = f"X to confirm: print {printable} cards"

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        if self._show_help:
            self._render_help_overlay(draw, width, height)
        else:
            self._render_browse(draw, width, height)

    def get_status(self) -> dict:
        current = self._found[self._index] if self._found else None
        return {
            "mode": self.name,
            "deck_name": self.deck_name,
            "total": len(self._all_cards),
            "found": len(self._found),
            "index": self._index,
            "current": current.to_dict() if current else None,
            "cards": [dc.to_dict() for dc in self._all_cards],
            "printing": self._printing,
            "print_progress": self._print_progress,
            "print_total": self._print_total,
            "status_message": self.status_message,
            "last_printed": self.last_printed,
        }

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_browse(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        # Title + deck name
        draw.text((10, 8), "DECKLIST", font=_FONT_LABEL, fill=_GOLD)

        if not self.deck_name:
            msg = "No deck loaded"
            bbox = draw.textbbox((0, 0), msg, font=_FONT_SM)
            draw.text(((width - (bbox[2] - bbox[0])) // 2, 60),
                      msg, font=_FONT_SM, fill=_GRAY)
            sub = "Load via web UI"
            bbox = draw.textbbox((0, 0), sub, font=_FONT_SM)
            draw.text(((width - (bbox[2] - bbox[0])) // 2, 82),
                      sub, font=_FONT_SM, fill=_DIM)
        else:
            # Deck name (truncated)
            dn = self.deck_name if len(self.deck_name) <= 28 else self.deck_name[:25] + "..."
            draw.text((10, 28), dn, font=_FONT_SM, fill=_GRAY)

            if not self._found:
                draw.text((10, 60), "No cards found in local DB", font=_FONT_SM, fill=_RED)
            else:
                dc = self._found[self._index]
                # Quantity badge
                qty = f"{dc.quantity}x"
                draw.text((10, 50), qty, font=_FONT_MED, fill=_GOLD)
                qw = draw.textbbox((0, 0), qty, font=_FONT_MED)[2] + 6

                # Card name
                name = dc.name if len(dc.name) <= 20 else dc.name[:17] + "..."
                draw.text((qw + 6, 50), name, font=_FONT_NAME, fill=_WHITE)

                # Category + type
                info = f"{dc.category.capitalize()}"
                if dc.card and hasattr(dc.card, "type_line"):
                    tl = dc.card.type_line
                    if len(tl) > 30:
                        tl = tl[:27] + "..."
                    info += f"  {tl}"
                draw.text((10, 82), info, font=_FONT_SM, fill=_GRAY)

                # CMC / P/T if available
                if dc.card:
                    sub = ""
                    if hasattr(dc.card, "cmc") and dc.card.cmc is not None:
                        sub += f"CMC {dc.card.cmc}"
                    if hasattr(dc.card, "power") and dc.card.power is not None:
                        sub += f"  {dc.card.power}/{dc.card.toughness}"
                    if sub:
                        draw.text((10, 98), sub, font=_FONT_SM, fill=_GRAY)

                # Position
                pos = f"{self._index + 1}/{len(self._found)}"
                bbox = draw.textbbox((0, 0), pos, font=_FONT_SM)
                draw.text((width - bbox[2] - 8, 98), pos, font=_FONT_SM, fill=_DIM)

                # Found / total summary
                summary = f"{len(self._found)}/{len(self._all_cards)} cards found"
                draw.text((10, 116), summary, font=_FONT_SM, fill=_DIM)

        # Status / last printed
        if self.status_message:
            color = _RED if "fail" in self.status_message.lower() else (
                _GOLD if "confirm" in self.status_message.lower() else _WHITE
            )
            draw.text((10, 148), self.status_message[:38], font=_FONT_SM, fill=color)
        elif self.last_printed:
            msg = self.last_printed
            if len(msg) > 36:
                msg = msg[:33] + "..."
            draw.text((10, 148), msg, font=_FONT_SM, fill=_GRAY)

        # Print-all progress bar
        if self._printing and self._print_total > 0:
            pct = self._print_progress / self._print_total
            bar_w = width - 20
            draw.rectangle([10, 168, 10 + bar_w, 178], outline=_DIM)
            draw.rectangle([10, 168, 10 + int(bar_w * pct), 178], fill=_GOLD)

        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [
            (0, "A:NEXT"),
            (width // 4, "B:PREV"),
            (width // 2, "X:PRINT"),
            (3 * width // 4, "HX:ALL"),
        ]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    # ------------------------------------------------------------------
    # Print helpers
    # ------------------------------------------------------------------

    def _trigger_print_current(self, art: bool = True) -> None:
        if not self._found or self._printing:
            return
        dc = self._found[self._index]
        if not dc.card:
            return
        copies = dc.quantity
        self._printing = True
        self.status_message = f"Printing {copies}x {dc.name}..."

        def _do():
            for _ in range(copies):
                self.printer.print_card(dc.card, art=art)
            self.last_printed = f"Printed: {copies}x {dc.name}"
            self.status_message = ""
            self._printing = False

        threading.Thread(target=_do, daemon=True, name="print-job").start()

    def _trigger_print_all(self, art: bool = True) -> None:
        if self._printing:
            return
        printable = [
            dc for dc in self._all_cards
            if dc.found and dc.category in PRINT_CATEGORIES
        ]
        if not printable:
            self.status_message = "Nothing to print"
            return

        total_copies = sum(dc.quantity for dc in printable)
        self._print_total = total_copies
        self._print_progress = 0
        self._printing = True
        self.status_message = f"Printing deck ({total_copies} cards)..."

        def _do():
            for dc in printable:
                for _ in range(dc.quantity):
                    self.printer.print_card(dc.card, art=art)
                    self._print_progress += 1
            self.last_printed = f"Printed deck: {total_copies} cards"
            self.status_message = ""
            self._printing = False
            self._print_progress = 0
            self._print_total = 0

        threading.Thread(target=_do, daemon=True, name="print-all").start()
