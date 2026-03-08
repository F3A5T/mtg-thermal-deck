"""
Card Browser mode.

Browse the full card database with optional CMC / colour / type filters.
Print any card directly, or jump to a random card within the current filter.

  A           — next card
  B           — previous card
  X           — print current card
  Hold A      — jump to random card in filtered pool
  Hold X      — enter filter mode
  Y           — handled by AppState (cycle mode)
  Hold Y      — help overlay

Filter mode (Hold X):
  A / B       — cycle filter categories  (CMC | COLOR | TYPE | CLEAR ALL)
  X           — enter sub-selector for chosen category  /  apply CLEAR ALL
  Hold X      — cancel, return to browse

Sub-selector (CMC / COLOR / TYPE):
  A / B       — cycle values
  X           — confirm and return to browse
  Hold X      — cancel, return to browse
"""

import random
import threading
from typing import TYPE_CHECKING, Optional

from PIL import ImageDraw, ImageFont

from .base import BaseMode

if TYPE_CHECKING:
    from app.card_manager import Card, CardManager
    from app.printer import Printer

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
_FONT_NAME  = _best_font(24)
_FONT_MED   = _best_font(16)
_FONT_SM    = _best_font(13)

_GOLD  = (212, 175, 55)
_WHITE = (255, 255, 255)
_GRAY  = (130, 130, 140)
_RED   = (220, 60, 60)
_GREEN = (80, 200, 100)
_DIM   = (60, 60, 75)
_BG    = (10, 10, 20)

# W U B R G  — colour swatches drawn next to the card name
_COLOR_SWATCH = {
    "W": (240, 230, 190),
    "U": (60, 130, 220),
    "B": (110, 80, 140),
    "R": (210, 60, 60),
    "G": (50, 170, 80),
    "C": (150, 150, 150),
}

_FILTER_CATS = ["CMC", "COLOR", "TYPE", "CLEAR ALL"]
_COLOR_OPTS  = ["ANY", "W", "U", "B", "R", "G", "C"]
_TYPE_OPTS   = ["ANY", "Creature", "Instant", "Sorcery",
                "Enchantment", "Artifact", "Planeswalker", "Land"]
# CMC options: ANY then 0-16
_CMC_OPTS    = ["ANY"] + list(range(17))

# Sub-mode constants
_BROWSE     = "browse"
_FILT_CAT   = "filt_cat"
_FILT_CMC   = "filt_cmc"
_FILT_COLOR = "filt_color"
_FILT_TYPE  = "filt_type"


class CardBrowserMode(BaseMode):

    def __init__(self, card_manager: "CardManager", printer: "Printer"):
        self.card_manager = card_manager
        self.printer = printer

        # Filtered card list + cursor
        self._filtered: list["Card"] = []
        self._index: int = 0

        # Active filters (None = any)
        self._filter_cmc: Optional[int] = None
        self._filter_color: Optional[str] = None
        self._filter_type: Optional[str] = None

        # UI sub-mode
        self._submode: str = _BROWSE

        # Filter-category selector
        self._cat_pos: int = 0

        # Sub-selector positions
        self._cmc_pos: int = 0    # index into _CMC_OPTS
        self._color_pos: int = 0  # index into _COLOR_OPTS
        self._type_pos: int = 0   # index into _TYPE_OPTS

        # Status
        self.status_message: str = ""
        self.last_card: Optional["Card"] = None
        self._printing: bool = False

        self._apply_filters()

    # ------------------------------------------------------------------
    # BaseMode interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Card Browser"

    def on_activate(self) -> None:
        self._show_help = False
        self._submode = _BROWSE
        self._apply_filters()

    def help_lines(self) -> list:
        return [
            ("A", "Next card"),
            ("B", "Previous card"),
            ("X", "Print current card"),
            ("Hold A", "Jump to random card"),
            ("Hold X", "Filter menu"),
            ("Y", "Next mode"),
            ("Hold Y", "This help"),
        ]

    def handle_button(self, button: str) -> None:
        if button == "Y_HOLD_FIRST":
            self._toggle_help()
            return
        if self._show_help:
            return
        if self._submode == _BROWSE:
            self._handle_browse(button)
        elif self._submode == _FILT_CAT:
            self._handle_filt_cat(button)
        elif self._submode == _FILT_CMC:
            self._handle_sub(button, _CMC_OPTS, "_cmc_pos", "_filter_cmc", _FILT_CMC)
        elif self._submode == _FILT_COLOR:
            self._handle_sub(button, _COLOR_OPTS, "_color_pos", "_filter_color", _FILT_COLOR)
        elif self._submode == _FILT_TYPE:
            self._handle_sub(button, _TYPE_OPTS, "_type_pos", "_filter_type", _FILT_TYPE)

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        if self._show_help:
            self._render_help_overlay(draw, width, height)
        elif self._submode == _BROWSE:
            self._render_browse(draw, width, height)
        elif self._submode == _FILT_CAT:
            self._render_filt_cat(draw, width, height)
        elif self._submode in (_FILT_CMC, _FILT_COLOR, _FILT_TYPE):
            self._render_sub(draw, width, height)

    def get_status(self) -> dict:
        card = self._filtered[self._index] if self._filtered else None
        return {
            "mode": self.name,
            "index": self._index,
            "total": len(self._filtered),
            "card": card.to_dict() if card else None,
            "filter_cmc": self._filter_cmc,
            "filter_color": self._filter_color,
            "filter_type": self._filter_type,
            "printing": self._printing,
            "last_card": self.last_card.to_dict() if self.last_card else None,
            "status_message": self.status_message,
        }

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _handle_browse(self, button: str) -> None:
        if button == "A":
            if self._filtered:
                self._index = (self._index + 1) % len(self._filtered)
            self.status_message = ""
        elif button == "B":
            if self._filtered:
                self._index = (self._index - 1) % len(self._filtered)
            self.status_message = ""
        elif button == "X":
            self._trigger_print()
        elif button == "A_HOLD_FIRST":
            self._jump_random()
        elif button == "X_HOLD_FIRST":
            self._submode = _FILT_CAT
            self.status_message = ""

    def _handle_filt_cat(self, button: str) -> None:
        if button == "A":
            self._cat_pos = (self._cat_pos + 1) % len(_FILTER_CATS)
        elif button == "B":
            self._cat_pos = (self._cat_pos - 1) % len(_FILTER_CATS)
        elif button == "X":
            cat = _FILTER_CATS[self._cat_pos]
            if cat == "CLEAR ALL":
                self._filter_cmc = None
                self._filter_color = None
                self._filter_type = None
                self._apply_filters()
                self._submode = _BROWSE
            elif cat == "CMC":
                # Pre-select current filter value
                cur = self._filter_cmc
                self._cmc_pos = (cur + 1) if cur is not None else 0  # ANY=0, CMC n=n+1
                if self._cmc_pos >= len(_CMC_OPTS):
                    self._cmc_pos = 0
                self._submode = _FILT_CMC
            elif cat == "COLOR":
                cur = self._filter_color
                self._color_pos = _COLOR_OPTS.index(cur) if cur in _COLOR_OPTS else 0
                self._submode = _FILT_COLOR
            elif cat == "TYPE":
                cur = self._filter_type
                try:
                    self._type_pos = _TYPE_OPTS.index(cur) if cur else 0
                except ValueError:
                    self._type_pos = 0
                self._submode = _FILT_TYPE
        elif button == "X_HOLD_FIRST":
            self._submode = _BROWSE

    def _handle_sub(self, button: str, opts: list, pos_attr: str, filter_attr: str, submode: str) -> None:
        pos = getattr(self, pos_attr)
        if button == "A":
            setattr(self, pos_attr, (pos + 1) % len(opts))
        elif button == "B":
            setattr(self, pos_attr, (pos - 1) % len(opts))
        elif button == "X":
            val = opts[getattr(self, pos_attr)]
            # "ANY" clears the filter; 0 is a valid CMC so check for string "ANY"
            if val == "ANY":
                setattr(self, filter_attr, None)
            else:
                setattr(self, filter_attr, val)
            self._apply_filters()
            self._submode = _BROWSE
        elif button == "X_HOLD_FIRST":
            self._submode = _FILT_CAT

    # ------------------------------------------------------------------
    # Render helpers
    # ------------------------------------------------------------------

    def _render_browse(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.text((10, 8), "CARD BROWSER", font=_FONT_LABEL, fill=_GOLD)

        # Filter summary top-right
        filt_parts = []
        if self._filter_cmc is not None:
            filt_parts.append(f"CMC{self._filter_cmc}")
        if self._filter_color:
            filt_parts.append(self._filter_color)
        if self._filter_type:
            filt_parts.append(self._filter_type[:4])
        filt_str = " ".join(filt_parts) if filt_parts else "ALL"
        bbox = draw.textbbox((0, 0), filt_str, font=_FONT_SM)
        draw.text((width - bbox[2] - bbox[0] - 8, 8), filt_str, font=_FONT_SM, fill=_GRAY)

        if not self._filtered:
            msg = "No cards match filters"
            bbox = draw.textbbox((0, 0), msg, font=_FONT_SM)
            draw.text(((width - (bbox[2] - bbox[0])) // 2, height // 2),
                      msg, font=_FONT_SM, fill=_RED)
        else:
            card = self._filtered[self._index]

            # Color swatches
            sx = 10
            colors = card.colors if card.colors else (["C"] if not card.colors else [])
            for col in (card.colors or []):
                swatch_color = _COLOR_SWATCH.get(col, _GRAY)
                draw.rectangle([sx, 32, sx + 10, 42], fill=swatch_color)
                sx += 14

            # Card name
            name = card.name if len(card.name) <= 22 else card.name[:19] + "..."
            draw.text((10, 46), name, font=_FONT_NAME, fill=_WHITE)

            # Type line
            tl = card.type_line if len(card.type_line) <= 36 else card.type_line[:33] + "..."
            draw.text((10, 76), tl, font=_FONT_SM, fill=_GRAY)

            # CMC + P/T
            info = f"CMC {card.cmc}"
            if card.power is not None:
                info += f"  {card.power}/{card.toughness}"
            draw.text((10, 94), info, font=_FONT_SM, fill=_GRAY)

            # Status / last printed
            if self.status_message:
                color = _RED if "fail" in self.status_message.lower() else _WHITE
                draw.text((10, 118), self.status_message[:38], font=_FONT_SM, fill=color)
            elif self.last_card:
                n = self.last_card.name
                if len(n) > 28:
                    n = n[:25] + "..."
                draw.text((10, 118), f"Last: {n}", font=_FONT_SM, fill=_GRAY)

            # Position
            pos = f"{self._index + 1}/{len(self._filtered)}"
            bbox = draw.textbbox((0, 0), pos, font=_FONT_SM)
            draw.text((width - bbox[2] - 8, 118), pos, font=_FONT_SM, fill=_GRAY)

        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [
            (0, "A:NEXT"),
            (width // 4, "B:PREV"),
            (width // 2, "X:PRINT"),
            (3 * width // 4, "HX:FILTER"),
        ]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    def _render_filt_cat(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.text((10, 8), "CARD BROWSER", font=_FONT_LABEL, fill=_GOLD)
        draw.text((10, 30), "Filter by:", font=_FONT_MED, fill=_WHITE)

        for i, cat in enumerate(_FILTER_CATS):
            y = 58 + i * 28
            if i == self._cat_pos:
                draw.rectangle([8, y - 2, width - 8, y + 18], fill=(40, 40, 60), outline=_GOLD)
            draw.text((16, y), cat, font=_FONT_MED,
                      fill=_GOLD if i == self._cat_pos else _GRAY)

        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [(0, "A/B:CYCLE"), (width // 2, "X:SELECT"), (3 * width // 4, "HX:BACK")]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    def _render_sub(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.text((10, 8), "CARD BROWSER", font=_FONT_LABEL, fill=_GOLD)

        if self._submode == _FILT_CMC:
            title = "SELECT CMC"
            val = _CMC_OPTS[self._cmc_pos]
            val_str = "ANY" if val == "ANY" else str(val)
        elif self._submode == _FILT_COLOR:
            title = "SELECT COLOR"
            val_str = _COLOR_OPTS[self._color_pos]
        else:
            title = "SELECT TYPE"
            val_str = _TYPE_OPTS[self._type_pos]

        draw.text((10, 30), title, font=_FONT_MED, fill=_WHITE)

        bbox = draw.textbbox((0, 0), val_str, font=_FONT_NAME)
        vw = bbox[2] - bbox[0]
        draw.text(((width - vw) // 2, 80), val_str, font=_FONT_NAME, fill=_GOLD)

        # Color swatch preview
        if self._submode == _FILT_COLOR and val_str != "ANY":
            swatch_color = _COLOR_SWATCH.get(val_str, _GRAY)
            draw.rectangle([(width // 2 - 16), 120, (width // 2 + 16), 140],
                           fill=swatch_color)

        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hints = [(0, "A/B:CYCLE"), (width // 2, "X:APPLY"), (3 * width // 4, "HX:BACK")]
        for x, label in hints:
            draw.text((x + 4, 204), label, font=_FONT_SM, fill=_GOLD)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_filters(self) -> None:
        self._filtered = self.card_manager.filter_cards(
            cmc=self._filter_cmc,
            color=self._filter_color,
            type_keyword=self._filter_type,
        )
        self._index = min(self._index, max(0, len(self._filtered) - 1))

    def _jump_random(self) -> None:
        if not self._filtered:
            self.status_message = "No cards to pick from"
            return
        self._index = random.randrange(len(self._filtered))
        self.status_message = ""

    def _trigger_print(self) -> None:
        if not self._filtered or self._printing:
            return
        card = self._filtered[self._index]
        self._printing = True
        self.status_message = "Printing..."

        def _do():
            success = self.printer.print_card(card)
            self.last_card = card
            self.status_message = f"Printed: {card.name}" if success else "Print failed!"
            self._printing = False

        threading.Thread(target=_do, daemon=True, name="print-job").start()
