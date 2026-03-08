"""
Info mode — shows IP address, hostname, and uptime on the display.

No buttons do anything except Y (handled by AppState to cycle modes).
"""

import logging
import socket
import subprocess
import time
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
_FONT_IP    = _best_font(30)
_FONT_SM    = _best_font(13)

_GOLD  = (212, 175, 55)
_WHITE = (255, 255, 255)
_GRAY  = (130, 130, 140)
_DIM   = (60, 60, 75)


def _get_ip() -> str:
    try:
        # Connect to an external address (doesn't send data) to find the
        # interface the OS would use — gives the LAN IP, not 127.0.0.1.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "No network"


def _get_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        h, rem = divmod(int(secs), 3600)
        m = rem // 60
        return f"{h}h {m}m"
    except Exception:
        return ""


class InfoMode(BaseMode):

    @property
    def name(self) -> str:
        return "Info"

    def handle_button(self, button: str) -> None:
        pass  # nothing to do; Y is handled by AppState

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.text((10, 8), "SYSTEM INFO", font=_FONT_LABEL, fill=_GOLD)

        # Hostname
        hostname = socket.gethostname()
        draw.text((10, 36), hostname, font=_FONT_SM, fill=_GRAY)

        # IP — large and centred
        ip = _get_ip()
        bbox = draw.textbbox((0, 0), ip, font=_FONT_IP)
        ip_w = bbox[2] - bbox[0]
        draw.text(((width - ip_w) // 2, 60), ip, font=_FONT_IP, fill=_WHITE)

        # Uptime
        uptime = _get_uptime()
        draw.text((10, 108), f"Up: {uptime}", font=_FONT_SM, fill=_GRAY)

        # Divider + button hint
        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        draw.text((3 * width // 4 + 4, 204), "Y:MENU", font=_FONT_SM, fill=_GOLD)

    def get_status(self) -> dict:
        return {
            "mode": self.name,
            "ip": _get_ip(),
            "hostname": socket.gethostname(),
            "uptime": _get_uptime(),
        }
