"""
Info mode — shows IP address, hostname, uptime, and hotspot toggle.

X       — toggle WiFi hotspot on/off
Y       — handled by AppState (cycle modes)
Hold Y  — help overlay
"""

import fcntl
import logging
import socket
import struct
import subprocess
import threading

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
_FONT_IP    = _best_font(22)
_FONT_SM    = _best_font(13)

_GOLD   = (212, 175, 55)
_WHITE  = (255, 255, 255)
_GRAY   = (130, 130, 140)
_DIM    = (60, 60, 75)
_GREEN  = (80, 200, 100)
_RED    = (220, 60, 60)
_YELLOW = (220, 200, 60)

HOTSPOT_CON  = "mtg-hotspot"
HOTSPOT_IP   = "10.42.0.1"
HOTSPOT_PORT = 5000


def _get_iface_ip(iface: str) -> str:
    """Return IPv4 address for a specific interface, or empty string."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            raw = fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack("256s", iface[:15].encode()),
            )
            return socket.inet_ntoa(raw[20:24])
    except Exception:
        return ""


def _get_wifi_ip() -> str:
    ip = _get_iface_ip("wlan0")
    return ip if ip else "No network"


def _get_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        h, rem = divmod(int(secs), 3600)
        m = rem // 60
        return f"{h}h {m}m"
    except Exception:
        return ""


def _hotspot_active() -> bool:
    """Return True if the hotspot connection is currently up."""
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return HOTSPOT_CON in out.splitlines()
    except Exception:
        return False


class InfoMode(BaseMode):

    def __init__(self):
        self._status_message: str = ""
        self._toggling: bool = False

    @property
    def name(self) -> str:
        return "Info"

    def help_lines(self) -> list:
        return [
            ("X", "Toggle WiFi hotspot on/off"),
            ("", f"  SSID: {HOTSPOT_CON}"),
            ("", f"  IP:   {HOTSPOT_IP}:{HOTSPOT_PORT}"),
            ("Y", "Next mode"),
            ("Hold Y", "This help"),
        ]

    def handle_button(self, button: str) -> None:
        if button == "Y_HOLD_FIRST":
            self._toggle_help()
        elif button == "X" and not self._toggling:
            self._toggle_hotspot()

    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        if self._show_help:
            self._render_help_overlay(draw, width, height)
            return

        active = _hotspot_active()

        draw.text((10, 6), "SYSTEM INFO", font=_FONT_LABEL, fill=_GOLD)

        # Hostname + uptime on same row
        hostname = socket.gethostname()
        uptime = _get_uptime()
        draw.text((10, 26), hostname, font=_FONT_SM, fill=_GRAY)
        if uptime:
            bbox = draw.textbbox((0, 0), uptime, font=_FONT_SM)
            draw.text((width - bbox[2] - 10, 26), uptime, font=_FONT_SM, fill=_GRAY)

        # Divider
        draw.line([(10, 44), (width - 10, 44)], fill=_DIM, width=1)

        # WiFi IP row
        wifi_ip = _get_wifi_ip()
        draw.text((10, 52), "WiFi", font=_FONT_SM, fill=_GRAY)
        draw.text((10, 66), wifi_ip, font=_FONT_IP, fill=_WHITE)

        # Hotspot IP row
        if self._toggling:
            hs_label_color = _YELLOW
            hs_ip_text     = "..."
            hs_ip_color    = _YELLOW
        elif active:
            hs_label_color = _GREEN
            hs_ip_text     = HOTSPOT_IP
            hs_ip_color    = _GREEN
        else:
            hs_label_color = _GRAY
            hs_ip_text     = "OFF"
            hs_ip_color    = _GRAY

        draw.text((10, 100), "Hotspot", font=_FONT_SM, fill=hs_label_color)
        draw.text((10, 114), hs_ip_text, font=_FONT_IP, fill=hs_ip_color)

        # Status message
        if self._status_message:
            draw.text((10, 150), self._status_message, font=_FONT_SM, fill=_WHITE)

        # Divider + button hints
        draw.line([(0, 196), (width, 196)], fill=_DIM, width=1)
        hs_hint = "X:HOT OFF" if active else "X:HOT ON"
        draw.text((4, 204), hs_hint, font=_FONT_SM, fill=_GOLD)
        draw.text((3 * width // 4 + 4, 204), "Y:MENU", font=_FONT_SM, fill=_GOLD)

    def get_status(self) -> dict:
        active = _hotspot_active()
        return {
            "mode": self.name,
            "wifi_ip": _get_wifi_ip(),
            "hotspot_ip": HOTSPOT_IP if active else None,
            "ip": _get_wifi_ip(),  # kept for backwards compat
            "hostname": socket.gethostname(),
            "uptime": _get_uptime(),
            "hotspot_active": active,
            "hotspot_ssid": HOTSPOT_CON,
        }

    # ------------------------------------------------------------------
    # Hotspot toggle
    # ------------------------------------------------------------------

    def _toggle_hotspot(self) -> None:
        active = _hotspot_active()
        self._toggling = True
        self._status_message = "Starting hotspot..." if not active else "Stopping hotspot..."

        def _do():
            try:
                if active:
                    subprocess.run(
                        ["sudo", "nmcli", "connection", "down", HOTSPOT_CON],
                        check=True, capture_output=True,
                    )
                    self._status_message = "Hotspot stopped"
                else:
                    subprocess.run(
                        ["sudo", "nmcli", "connection", "up", HOTSPOT_CON],
                        check=True, capture_output=True,
                    )
                    self._status_message = f"Hotspot up — {HOTSPOT_IP}"
            except subprocess.CalledProcessError as exc:
                logger.error("Hotspot toggle failed: %s", exc.stderr)
                self._status_message = "Toggle failed"
            finally:
                self._toggling = False

        threading.Thread(target=_do, daemon=True, name="hotspot-toggle").start()
