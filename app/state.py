from typing import List
from app.modes.base import BaseMode


class AppState:
    """Holds the list of modes and tracks which one is active."""

    def __init__(self, modes: List[BaseMode]):
        if not modes:
            raise ValueError("At least one mode is required")
        self.modes = modes
        self._index = 0

    @property
    def current_mode(self) -> BaseMode:
        return self.modes[self._index]

    def next_mode(self):
        self._index = (self._index + 1) % len(self.modes)
        self.current_mode.on_activate()

    def get_status(self) -> dict:
        return {
            "current_mode": self.current_mode.name,
            "modes": [m.name for m in self.modes],
            "status": self.current_mode.get_status(),
        }
