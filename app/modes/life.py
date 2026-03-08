"""
4-Player Life Tracker mode.

Each player starts at 40 life. The display is split into four quadrants.

A       — select next player (cycles 1→2→3→4→1)
B       — selected player -1 life
X       — selected player +1 life
Hold B  — selected player -5 life
Hold X  — selected player +5 life
Hold A  — reset all players to 40
Y       — handled by AppState (cycle mode)
"""

import logging
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


_FONT_LIFE  = _best_font(52)
_FONT_LABEL = _best_font(13)
_FONT_HINT  = _best_font(11)

_GOLD   = (212, 175, 55)
_WHITE  = (255, 255, 255)
_DIM    = (50, 50, 65)
_BG     = (18, 18, 28)
_BG_SEL = (28, 26, 10)   # faint gold tint for selected quadrant
_LOW    = (200, 60, 60)  # life colour when <= 10
_DIVIDER = (60, 60, 80)

_START_LIFE = 40
_NUM_PLAYERS = 4


class LifeMode(BaseMode):

    def __init__(self):
        self._life = [_START_LIFE] * _NUM_PLAYERS
        self._selected = 0   # 0-indexed

    @property
    def name(self) -> str:
        return "Life Tracker"

    def help_lines(self) -> list:
        return [
            ("A", "Select next player"),
            ("B", "-1 life"),
            ("X", "+1 life"),
            ("Hold B", "-5 life (repeats)"),
            ("Hold X", "+5 life (repeats)"),
            ("Hold A", "Reset all to 40"),
            ("Y", "Next mode"),
            ("Hold Y", "This help"),
        ]

    def handle_button(self, button: str) -> None:
        if button == "Y_HOLD_FIRST":
            self._toggle_help()
            return
        if self._show_help:
            return
        if button == "A":
            self._selected = (self._selected + 1) % _NUM_PLAYERS
        elif button in ("A_HOLD_FIRST", "A_HOLD"):
            self._life = [_START_LIFE] * _NUM_PLAYERS
        elif button == "B":
            self._life[self._selected] -= 1
        elif button == "B_HOLD_FIRST":
            # First hold: we already applied -1 on press, add -4 to total -5
            self._life[self._selected] -= 4
        elif button == "B_HOLD":
            self._life[self._selected] -= 5
        elif button == "X":
            self._life[self._selected] += 1
        elif button == "X_HOLD_FIRST":
            # First hold: we already applied +1 on press, add +4 to total +5
            self._life[self._selected] += 4
        elif button == "X_HOLD":
            self._life[self._selected] += 5

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        if self._show_help:
            self._render_help_overlay(draw, width, height)
            return
        mid_x = width // 2
        mid_y = height // 2

        # Quadrant layout: [TL, TR, BL, BR]
        quads = [
            (0,      0,      mid_x,  mid_y),   # P1
            (mid_x,  0,      width,  mid_y),   # P2
            (0,      mid_y,  mid_x,  height),  # P3
            (mid_x,  mid_y,  width,  height),  # P4
        ]

        for i, (x0, y0, x1, y1) in enumerate(quads):
            # Background — tinted for selected player
            bg = _BG_SEL if i == self._selected else _BG
            draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=bg)

            # Gold border for selected player
            if i == self._selected:
                draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=_GOLD, width=2)

            # Player label
            label = f"P{i + 1}"
            draw.text((x0 + 6, y0 + 4), label, font=_FONT_LABEL,
                      fill=_GOLD if i == self._selected else _DIM)

            # Life total — centred in quadrant
            life_str = str(self._life[i])
            bbox = draw.textbbox((0, 0), life_str, font=_FONT_LIFE)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            lx = x0 + (x1 - x0 - lw) // 2
            ly = y0 + (y1 - y0 - lh) // 2
            color = _LOW if self._life[i] <= 10 else _WHITE
            draw.text((lx, ly), life_str, font=_FONT_LIFE, fill=color)

        # Divider lines
        draw.line([(mid_x, 0), (mid_x, height)], fill=_DIVIDER, width=1)
        draw.line([(0, mid_y), (width, mid_y)], fill=_DIVIDER, width=1)

        # Hint strip at bottom of each half (inside the bottom quadrants)
        hints_l = "B:-1  X:+1"
        hints_r = "A:SEL  HOLD:×5"
        draw.text((4, height - 14), hints_l, font=_FONT_HINT, fill=_DIM)
        bbox = draw.textbbox((0, 0), hints_r, font=_FONT_HINT)
        draw.text((width - bbox[2] - 4, height - 14), hints_r, font=_FONT_HINT, fill=_DIM)

    def get_status(self) -> dict:
        return {
            "mode": self.name,
            "life": self._life,
            "selected": self._selected,
        }

    def reset(self):
        self._life = [_START_LIFE] * _NUM_PLAYERS
        self._selected = 0
