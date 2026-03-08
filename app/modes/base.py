"""
Abstract base class for console modes.

Each mode controls what the display shows and how buttons behave.
Adding a new mode (e.g. TokenMode, DecklistMode) means subclassing this,
then registering the instance in app/__init__.py.
"""

from abc import ABC, abstractmethod
from PIL import ImageDraw


class BaseMode(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable mode name shown on display and web UI."""

    @abstractmethod
    def render(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        """
        Draw the mode UI onto the supplied ImageDraw context.
        Called at ~20 fps from the display thread.
        """

    @abstractmethod
    def handle_button(self, button: str) -> None:
        """
        React to a physical button press.
        button is one of: 'A', 'B', 'X', 'Y'
        Note: 'Y' is reserved for mode-switching by AppState unless a mode
        explicitly wants to consume it.
        """

    def get_status(self) -> dict:
        """Return a JSON-serialisable status dict for the web API."""
        return {"mode": self.name}
