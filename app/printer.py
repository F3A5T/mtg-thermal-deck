import logging
import os
import textwrap
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from app.card_manager import Card

logger = logging.getLogger(__name__)


class Printer:
    def __init__(
        self,
        port: str,
        baudrate: int,
        profile: str,
        width_px: int,
        mock: bool = False,
    ):
        self.port = port
        self.baudrate = baudrate
        self.profile = profile
        self.width_px = width_px
        self.mock = mock
        self._p = None

        if not mock:
            self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self):
        try:
            from escpos.printer import Serial as EscSerial

            self._p = EscSerial(
                devfile=self.port,
                baudrate=self.baudrate,
                profile=self.profile,
            )
            logger.info("Printer connected on %s", self.port)
        except Exception as exc:
            logger.error("Failed to connect to printer: %s", exc)
            self._p = None

    def is_connected(self) -> bool:
        return self.mock or self._p is not None

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------

    def print_card(self, card: "Card") -> bool:
        """Print artwork + text for a card. Returns True on success."""
        if self.mock:
            logger.info(
                "[MOCK PRINT] %s  CMC:%s  %s/%s",
                card.name,
                card.cmc,
                card.power,
                card.toughness,
            )
            return True

        if not self._p:
            self._connect()
        if not self._p:
            logger.error("Printer unavailable — cannot print")
            return False

        try:
            self._print_artwork(card)
            self._print_text(card)
            self._p.ln(4)
            return True
        except Exception as exc:
            logger.error("Print error: %s", exc, exc_info=True)
            return False

    def _print_artwork(self, card: "Card"):
        if not card.image_path or not os.path.exists(card.image_path):
            logger.warning("No image for %s, skipping artwork", card.name)
            return

        img = Image.open(card.image_path)
        # Scale to printer width, maintain aspect ratio
        ratio = self.width_px / img.width
        new_h = int(img.height * ratio)
        img = img.resize((self.width_px, new_h), Image.LANCZOS)
        # Thermal printers handle grayscale; convert to L so escpos dithers cleanly
        img = img.convert("L")
        self._p.image(img, impl="bitImageColumn")

    def _print_text(self, card: "Card"):
        p = self._p
        # Name — bold, centred, normal size
        p.set(bold=True, align="center", custom_size=True, width=1, height=1)
        p.text(card.name + "\n")
        p.set(bold=False, align="left", custom_size=True, width=1, height=1)

        # Mana cost
        if card.mana_cost:
            p.text(f"Cost: {card.mana_cost}\n")

        # Type line
        p.text(card.type_line + "\n")

        # Oracle / rules text
        oracle = getattr(card, "oracle_text", "") or ""
        if oracle:
            for line in oracle.split("\n"):
                for wrapped in textwrap.wrap(line, width=42) or [""]:
                    p.text(wrapped + "\n")

        # Power / Toughness
        if card.power is not None and card.toughness is not None:
            p.set(bold=True, align="center", custom_size=True, width=1, height=1)
            p.text(f"{card.power} / {card.toughness}\n")
            p.set(bold=False, align="left", custom_size=True, width=1, height=1)
