from typing import List
from app.modes.base import BaseMode


class AppState:
    """Holds the list of modes and tracks which one is active."""

    def __init__(self, modes: List[BaseMode]):
        if not modes:
            raise ValueError("At least one mode is required")
        self.modes = modes
        # Start on the first mode that's in the display rotation
        self._index = next(
            (i for i, m in enumerate(modes) if m.display_in_rotation), 0
        )

    @property
    def current_mode(self) -> BaseMode:
        return self.modes[self._index]

    def next_mode(self):
        for _ in range(len(self.modes)):
            self._index = (self._index + 1) % len(self.modes)
            if self.current_mode.display_in_rotation:
                break
        self.current_mode.on_activate()

    def get_status(self) -> dict:
        from app.modes.info import _hotspot_active
        return {
            "current_mode": self.current_mode.name,
            "modes": [m.name for m in self.modes if m.display_in_rotation],
            "status": self.current_mode.get_status(),
            "hotspot_active": _hotspot_active(),
        }
